/* Actual FastAPI + Chromium; isolated empty operational data and frozen replay.
   No official collection, real account data, or external provider calls. */
const {chromium} = require('playwright-core');
const {spawn} = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const net = require('node:net');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const destination = process.env.SCREENSHOT_DIR || '/tmp/outdoorwise-unified-screenshots';
fs.mkdirSync(destination, {recursive: true});
async function port() {
  const server = net.createServer(); await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const value = server.address().port; await new Promise(resolve => server.close(resolve)); return value;
}
(async () => {
  const executablePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  const browser = await chromium.launch({executablePath, headless: true});
  try {
    for (const mode of ['live', 'historical']) {
      const dataRoot = fs.mkdtempSync(path.join(os.tmpdir(), `outdoorwise-${mode}-browser-`));
      fs.cpSync(path.join(root, 'data/catalog'), path.join(dataRoot, 'catalog'), {recursive: true});
      const selectedPort = await port(); const base = `http://127.0.0.1:${selectedPort}`;
      const child = spawn(path.join(root, '.venv/bin/python'), ['-m', 'uvicorn', 'outdoorwise.api.app:app', '--host', '127.0.0.1', '--port', String(selectedPort)], {
        cwd: root, env: {...process.env, OUTDOORWISE_DATA_ROOT: dataRoot, OUTDOORWISE_DATA_MODE: 'live', OUTDOORWISE_APP_MODE: mode}, stdio: ['ignore', 'pipe', 'pipe'],
      });
      let log = ''; child.stdout.on('data', data => log += data); child.stderr.on('data', data => log += data);
      const context = await browser.newContext(); const page = await context.newPage(); const errors = []; page.on('pageerror', error => errors.push(error.message));
      await page.route('https://unpkg.com/leaflet@1.9.4/dist/**', route => {
        const name = new URL(route.request().url()).pathname.split('/').at(-1);
        return route.fulfill({contentType: name.endsWith('.js') ? 'application/javascript' : 'text/css', body: fs.readFileSync(require.resolve(`leaflet/dist/${name}`))});
      });
      await page.route('https://*.tile.openstreetmap.org/**', route => route.fulfill({contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect width="256" height="256" fill="#edf2e9"/><text x="10" y="20">Offline map tiles</text></svg>'}));
      try {
        let ready = false;
        for (let i = 0; i < 100; i++) {
          try {const response = await fetch(base + '/api/health'); if (response.ok) {ready = true; break;}} catch {}
          if (child.exitCode !== null) break;
          await new Promise(resolve => setTimeout(resolve, 100));
        }
        assert(ready, log);
        for (const width of [1440, 390]) {
          await page.setViewportSize({width, height: 1000}); await page.goto(base);
          await page.locator('#cards .card').first().waitFor({timeout: 60000});
          assert.match(await page.locator('#mode').textContent(), new RegExp('^' + mode.toUpperCase() + ' MODE'));
          assert.equal(await page.locator('#forecast-launcher, #live-forecast-launcher').count(), 0);
          assert.equal(await page.locator('#preferences button[type=submit]').textContent(), 'Find Recommended Routes');
          assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
          if (mode === 'historical') {
            assert(await page.locator('#cards .completed-run-button').first().isDisabled());
            for (const delay of ['0', '30', '60']) {
              await page.locator('#start-delay').selectOption(delay);
              const result = page.waitForResponse(response => response.url().endsWith('/api/route-recommendations') && response.request().method() === 'POST');
              await page.locator('#preferences > button').click();
              const response = await result; assert.equal(response.status(), 200);
              const data = await response.json(); assert.equal(data.requested_departure_offset_min, Number(delay));
              assert.equal(data.assessment_reference_time, '2026-10-15T19:15:00+08:00');
              await page.waitForFunction(() => document.getElementById('status').textContent === 'Routes updated.');
              assert.equal(data.recommendation_basis, delay === '0' ? 'historical_observation_risk' : 'unknown_risk_fallback');
              assert(data.recommendations.every(row => row.full_run_assessment.risk_score === null));
              assert(data.recommendations.every(row => delay === '0' ? row.risk_score !== null : row.risk_score === null));
              assert.match(await page.locator('#cards .recommendation-basis').first().textContent(), delay === '0' ? /Historical observation-based/ : /fallback/);
              if (delay === '0') await page.screenshot({path: path.join(destination, `historical-now-${width}.png`), fullPage: true});
            }
            await page.locator('#cards .prediction-details summary').first().click();
            assert.match(await page.locator('#cards .prediction-details').first().textContent(), /Offline pooled evaluation/);
          } else {
            assert.equal(await page.locator('#cards .prediction-details').count(), 0);
            assert.match(await page.locator('#cards .risk-score').first().textContent(), /Unknown/);
            assert.match(await page.locator('#cards .environment-measurements').first().textContent(), /Unavailable/);
          }
          const gpx = await page.locator('#cards .export-route-button').first().getAttribute('href');
          const response = await fetch(base + gpx); assert.equal(response.status, 200); assert((await response.text()).includes('<gpx'));
          await page.screenshot({path: path.join(destination, `${mode}-${width}.png`), fullPage: true});
          await page.locator('#dynamic-tab-button').click(); assert(await page.locator('#ai-parse-button').isVisible());
        }
        if (mode === 'live') {
          // Reuse the standalone DOM/HTTP smoke check against this isolated app.
          // Keeping one server owner avoids accidentally testing local user data.
          const smoke = spawn(process.execPath, [path.join(root, 'tests/frontend_smoke.cjs')], {
            cwd: root, env: {...process.env, BASE_URL: base}, stdio: ['ignore', 'pipe', 'pipe'],
          });
          let smokeLog = '';
          smoke.stdout.on('data', data => smokeLog += data);
          smoke.stderr.on('data', data => smokeLog += data);
          const code = await new Promise(resolve => smoke.once('exit', resolve));
          assert.equal(code, 0, smokeLog);
          console.log(smokeLog.trim());
        }
        assert.deepEqual(errors, []);
        console.log(`Actual FastAPI + Chromium ${mode}: desktop/mobile, submission, provenance/unknown coverage, map, GPX and Tab 2 controls passed. Isolated storage: ${dataRoot}`);
      } finally {
        await context.close();
        if (child.exitCode === null) {child.kill('SIGTERM'); await new Promise(resolve => child.once('exit', resolve));}
      }
    }
  } finally {await browser.close();}
  console.log('Actual backend screenshots: ' + destination);
})().catch(error => {console.error(error); process.exitCode = 1;});

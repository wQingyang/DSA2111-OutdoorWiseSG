/* Real Chromium UI checks against explicitly synthetic API fixtures.
   No environmental collection or real accounts. Use CHROME_PATH for your browser. */
const {chromium} = require('playwright-core');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/frontend_run.json'), 'utf8'));
const destination = process.env.SCREENSHOT_DIR || '/tmp/outdoorwise-sprint2-screenshots';
fs.mkdirSync(destination, {recursive: true});
let authenticated = false; let favourites = []; const runs = []; const feedback = []; const comparisons = [];
const server = http.createServer((request, response) => {
  const url = new URL(request.url, 'http://localhost');
  const route = url.pathname;
  if (route.startsWith('/api/')) {
    const json = (data, status = 200) => {response.writeHead(status, {'Content-Type': 'application/json'}); response.end(JSON.stringify(data));};
    if (route === '/api/health') return json({data_mode: 'live', agent_mode: 'demo'});
    if (route === '/api/auth/me') return json(authenticated ? {user_id: 'browser-user', username: 'DemoRunner', created_at: '2026-10-15T12:00:00Z'} : {detail: 'Authentication required'}, authenticated ? 200 : 401);
    if (route === '/api/auth/login' || route === '/api/auth/register') {authenticated = true; return json({user_id: 'browser-user', username: 'DemoRunner'});}
    if (route.startsWith('/api/auth/username-availability')) return json({available: true});
    if (route === '/api/auth/logout') {authenticated = false; return json({}, 204);}
    if (route === '/api/recommendations' || route === '/api/me/recommendations') {
      let body = ''; request.on('data', chunk => body += chunk); request.on('end', () => {
        const preferences = JSON.parse(body); comparisons.push({endpoint: route, preferences});
        const data = JSON.parse(JSON.stringify(route === '/api/me/recommendations' ? fixture.personalized : fixture.generic));
        const run = route === '/api/me/recommendations' ? data.run : data;
        run.preferences = {...run.preferences, ...preferences};
        // Explicit synthetic empty-result scenario; real access math is API-tested.
        if (preferences.location && preferences.max_access_distance_km === .001) {
          run.recommendations = []; if (data.run) data.recommendations = [];
        }
        json(data);
      }); return;
    }
    if (route === '/api/refresh') return json({status: 'success', sources: []});
    if (route === '/api/me/running-profile') return json({completed_run_count: 4, feedback_count: 4, favourite_count: favourites.length, total_distance_km: 18.5, typical_distance_min_km: 3.5, typical_distance_max_km: 6, comfortable_distance_km: 4.5, mean_pace_min_per_km: 6, mean_perceived_difficulty: 3, recent_difficulty_trend: 'stable', profile_confidence: 'medium'});
    if (route.endsWith('/difficulty')) return json({predicted_difficulty: 2.3, difficulty_label: 'Easy'});
    if (route.endsWith('/export.gpx')) {response.writeHead(200, {'Content-Type': 'application/gpx+xml', 'Content-Disposition': 'attachment; filename="synthetic-route.gpx"'}); return response.end('<?xml version="1.0"?><gpx version="1.1"><trk><name>Synthetic test</name></trk></gpx>');}
    if (route === '/api/users/browser-user/favourites') return json(favourites);
    if (route.includes('/favourites/')) {const route_id = route.split('/').at(-1); favourites = request.method === 'DELETE' ? favourites.filter(f => f.route_id !== route_id) : [...favourites, {route_id}]; return json({route_id});}
    if (route === '/api/users/browser-user/runs' && request.method === 'GET') return json(runs);
    if (route === '/api/users/browser-user/feedback') return json(feedback);
    if (route === '/api/users/browser-user/runs' || route.endsWith('/feedback')) {
      let body = ''; request.on('data', chunk => body += chunk); request.on('end', () => {
        const item = JSON.parse(body); if (route.endsWith('/feedback')) {feedback.push(item); json(item, 201);} else {item.completed_run_id = 'browser-run'; runs.push(item); json(item, 201);}
      }); return;
    }
    return json({detail: 'Unexpected test API'}, 404);
  }
  const file = route.startsWith('/assets/') ? path.join(root, 'frontend', path.basename(route)) : path.join(root, 'frontend', route === '/' ? 'index.html' : path.basename(route));
  if (!fs.existsSync(file)) {response.writeHead(404); return response.end();}
  const types = {'.js': 'application/javascript', '.css': 'text/css', '.html': 'text/html'};
  response.writeHead(200, {'Content-Type': types[path.extname(file)] || 'text/plain'}); response.end(fs.readFileSync(file));
});
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  let browser;
  try {
    browser = await chromium.launch({headless: true, executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
    const page = await browser.newPage({viewport: {width: 1440, height: 1100}});
    await page.addInitScript(() => document.addEventListener('DOMContentLoaded', () => { const header = document.querySelector('header'); if (header) { const label = document.createElement('p'); label.textContent = 'Synthetic UI test fixture · Offline map tiles'; label.style.cssText = 'background:#fff2d8;color:#775112;padding:8px;border-radius:6px;font-size:12px'; header.append(label); } }));
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    await page.route('https://unpkg.com/leaflet@1.9.4/dist/**', async route => {
      const name = new URL(route.request().url()).pathname.split('/').at(-1);
      await route.fulfill({contentType: name.endsWith('.js') ? 'application/javascript' : 'text/css', body: fs.readFileSync(require.resolve(`leaflet/dist/${name}`))});
    });
    // Deterministic offline tile placeholders: screenshots verify actual Leaflet
    // geometry/controls, not the availability or visual accuracy of OSM tiles.
    await page.route('https://*.tile.openstreetmap.org/**', route => route.fulfill({contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect width="256" height="256" fill="#edf2e9"/><path d="M0 128H256M128 0V256" stroke="#dae3d5"/><text x="10" y="20" fill="#849580" font-size="10">Offline test map</text></svg>'}));
    await page.goto(base); await page.locator('#cards .card').first().waitFor();
    await page.locator('.leaflet-interactive').first().waitFor();
    assert.equal(await page.locator('#cards .card').count(), 11);
    assert.equal(await page.locator('.environmental-details[open]').count(), 0);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({path: path.join(destination, 'dashboard-desktop.png'), fullPage: false});
    const coast = page.locator('[data-personalization-route="east_coast"]');
    await coast.locator('summary').click(); assert.equal(await coast.locator('tr[data-metric]').count(), 10);
    await coast.locator('summary').click(); await coast.locator('.view-route-button').click();
    assert.equal(await page.locator('.leaflet-interactive').count(), 1);
    await page.goto(base + '/login.html');
    await page.screenshot({path: path.join(destination, 'login.png'), fullPage: true});
    await page.locator('[name="username"]').fill('DemoRunner'); await page.locator('[name="password"]').fill('synthetic-password');
    await page.locator('#login-form button').click(); await page.waitForURL('**/profile.html');
    await page.locator('#profile-username').filter({hasText: 'DemoRunner'}).waitFor();
    assert.equal(await page.locator('#profile-pace').textContent(), '6:00 min/km');
    await page.screenshot({path: path.join(destination, 'profile.png'), fullPage: true});
    await page.goto(base); await page.locator('#cards .card').first().waitFor();
    const expected = fixture.personalized.recommendations.map(r => r.route_id);
    const order = () => page.locator('#cards .card').evaluateAll(cards => cards.map(c => c.dataset.personalizationRoute));
    assert.deepEqual(await order(), expected);
    await page.locator('#refresh').click(); await page.waitForFunction(() => document.getElementById('status').textContent === 'Routes updated.');
    assert.deepEqual(await order(), expected);
    const first = page.locator('#cards .card').first();
    await first.locator('.favourite-button').click(); await page.waitForFunction(() => document.querySelector('#cards .favourite-button').textContent.includes('Favourited'));
    await first.locator('.completed-run-button').click(); await page.locator('#run-duration').fill('30'); await page.locator('#run-difficulty').selectOption('3');
    await page.locator('#run-form button[type="submit"]').click(); await page.locator('#run-modal').waitFor({state: 'hidden'});
    assert.equal(runs.length, 1); assert.equal(feedback.length, 1);
    const download = page.waitForEvent('download'); await first.locator('.export-route-button').click(); await download;
    await page.setViewportSize({width: 390, height: 844}); await page.goto(base); await page.locator('#cards .card').first().waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({path: path.join(destination, 'dashboard-mobile.png'), fullPage: true});
    await page.evaluate(() => scrollTo(0, document.querySelector('#cards').getBoundingClientRect().top + scrollY - 16)); await page.screenshot({path: path.join(destination, 'results-mobile.png')});
    await page.goto(base + '/register.html'); assert.equal(await page.locator('#register-form').count(), 1);
    await page.screenshot({path: path.join(destination, 'register-mobile.png'), fullPage: true});
    // Sprint 2.1: actual Leaflet clicks, marker dragging, route-event isolation,
    // payload persistence and a native browser geolocation override.
    await page.setViewportSize({width: 1440, height: 1100}); await page.goto(base);
    await page.locator('#cards .card').first().waitFor();
    await page.locator('#location-mode').selectOption('map');
    await page.locator('#map').click({position: {x: 80, y: 230}});
    await page.locator('.starting-location-marker').waitFor();
    const selection = () => page.evaluate(() => window.outdoorwiseLocation.selectedPoint());
    const clicked = await selection(); assert(clicked && typeof clicked.lon === 'number');
    const markerBox = await page.locator('.starting-location-marker').boundingBox();
    await page.mouse.move(markerBox.x+24, markerBox.y+15); await page.mouse.down();
    await page.mouse.move(markerBox.x+54, markerBox.y+35, {steps: 8}); await page.mouse.up();
    const dragged = await selection(); assert.notDeepEqual(dragged, clicked);
    assert.equal(await page.locator('.starting-location-marker').count(), 1);
    await page.locator('.leaflet-interactive').first().dispatchEvent('click');
    assert.deepEqual(await selection(), dragged); assert.equal(await page.locator('.leaflet-container').count(), 1);
    await page.locator('#access').fill('25');
    await page.locator('#preferences > button').click(); await page.waitForFunction(() => document.getElementById('status').textContent === 'Routes updated.');
    assert.deepEqual(comparisons.at(-1).preferences.location, dragged); assert.equal(comparisons.at(-1).endpoint, '/api/me/recommendations');
    await page.locator('#refresh').click(); await page.waitForFunction(() => document.getElementById('status').textContent === 'Routes updated.');
    assert.deepEqual(comparisons.at(-1).preferences.location, dragged); assert.equal(comparisons.at(-1).preferences.max_access_distance_km, 25);
    await page.screenshot({path: path.join(destination, 'location-desktop.png')});
    await page.locator('#location-mode').selectOption('preset'); await page.locator('#location-preset').selectOption('bay');
    assert.deepEqual(await selection(), {lon:103.855,lat:1.287});
    await page.context().setGeolocation({latitude:1.2961,longitude:103.7762,accuracy:25});
    await page.context().grantPermissions(['geolocation'], {origin:base});
    await page.locator('#location-mode').selectOption('current'); assert.equal(await selection(), null);
    await page.locator('#get-current-location').click();
    await page.waitForFunction(() => document.getElementById('location-status').textContent.includes('Current location selected'));
    assert.deepEqual(await selection(), {lon:103.7762,lat:1.2961});
    const cdp = await page.context().newCDPSession(page);
    const {targetInfo} = await cdp.send('Target.getTargetInfo');
    await cdp.send('Browser.setPermission', {permission:{name:'geolocation'},setting:'denied',origin:base,browserContextId:targetInfo.browserContextId});
    assert.equal(await page.evaluate(async () => (await navigator.permissions.query({name:'geolocation'})).state), 'denied');
    await page.locator('#location-mode').selectOption('anywhere'); await page.locator('#location-mode').selectOption('current');
    await page.locator('#get-current-location').click();
    await page.waitForFunction(() => document.getElementById('location-status').textContent.includes('permission was denied'));
    await page.locator('#choose-location-on-map').click(); assert.equal(await page.locator('#location-mode').inputValue(), 'map');
    await page.locator('#map').click({position: {x: 80, y: 230}});
    await page.locator('#access').fill('0.001'); await page.locator('#preferences > button').click();
    await page.locator('.empty-results').waitFor();
    assert.match(await page.locator('.empty-results').textContent(), /0.001 km straight-line access limit.*not been relaxed/);
    assert.equal(await page.locator('#cards .card').count(), 0);
    await page.locator('#clear-location').click(); assert.equal(await selection(), null);
    assert.equal(await page.locator('#access').isDisabled(), true);
    await page.locator('#preferences > button').click(); await page.locator('#cards .card').first().waitFor();
    assert.equal(comparisons.at(-1).preferences.location, null); assert.equal(comparisons.at(-1).preferences.max_access_distance_km, null);
    await page.setViewportSize({width:390,height:844});
    await page.locator('#location-mode').selectOption('map');
    await cdp.send('Emulation.setTouchEmulationEnabled', {enabled:true,maxTouchPoints:1});
    await page.locator('#map').scrollIntoViewIfNeeded();
    const mobileMap = await page.locator('#map').boundingBox();
    await cdp.send('Input.dispatchTouchEvent', {type:'touchStart',touchPoints:[{x:mobileMap.x+80,y:mobileMap.y+180}]});
    await cdp.send('Input.dispatchTouchEvent', {type:'touchEnd',touchPoints:[]});
    await page.waitForFunction(() => window.outdoorwiseLocation.selectedPoint() !== null);
    await page.evaluate(() => scrollTo(0, document.querySelector('#location-mode').getBoundingClientRect().top+scrollY-20));
    await page.screenshot({path:path.join(destination,'location-mobile.png')});
    await page.locator('#map').scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(destination,'location-map-mobile.png')});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    assert.equal(await page.locator('.leaflet-container').count(), 1);
    console.log('Starting location passed: map click/drag/replacement, route isolation, presets, native geolocation success/denial, personal compare/refresh payloads, strict empty state, clear and mobile.');
    assert.deepEqual(errors, []);
    console.log('Chromium passed: desktop/mobile, Leaflet geometry and View Route, login/profile/register, personal refresh order, favourite, completed run/feedback, GPX, no page errors. Screenshots: ' + destination);
  } finally {if (browser) await browser.close(); await new Promise(resolve => server.close(resolve));}
})().catch(error => {console.error(error); process.exitCode = 1;});

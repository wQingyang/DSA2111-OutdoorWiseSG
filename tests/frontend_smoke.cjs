/* DOM + actual local HTTP API; run only against an isolated test data root. */
const {JSDOM} = require('jsdom');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
(async () => {
  const base = process.env.BASE_URL || 'http://127.0.0.1:8769';
  const expected = await (await fetch(base + '/api/route-recommendations', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({})})).json();
  const html = await (await fetch(base)).text();
  const dom = new JSDOM(html, {runScripts: 'outside-only', url: base});
  try {
    dom.window.fetch = (url, options) => fetch(base + url, options);
    for (const script of ['results', 'location', 'route-export', 'difficulty', 'personalization', 'forecast-ranking', 'app']) dom.window.eval(fs.readFileSync(path.join(__dirname, `../frontend/${script}.js`), 'utf8'));
    const d = dom.window.document;
    for (let i = 0; i < 100 && !d.getElementById('results-summary').textContent; i++) await new Promise(resolve => setTimeout(resolve, 100));
    assert.equal(d.querySelectorAll('#cards .card').length, expected.recommendations.length);
    assert.equal(d.querySelectorAll('.environmental-details[open]').length, 0);
    for (const rec of expected.recommendations) {
      const card = d.querySelector(`[data-personalization-route="${rec.route_id}"]`);
      assert(card); assert.equal(card.querySelector('.rank-label').textContent, `Shared rank #${rec.final_rank}`);
      assert.equal(card.querySelector('.export-route-button').getAttribute('href'), `/api/routes/${rec.route_id}/export.gpx`);
      assert.equal(card.querySelectorAll('tr[data-metric]').length, expected.environment.find(e => e.route_id === rec.route_id).metrics.length);
      if (rec.recommendation_score === null) assert.equal(card.querySelector('.recommendation-score strong').textContent, 'Unavailable');
    }
    assert.equal(d.querySelectorAll('#fallback svg').length, expected.routes.length);
    assert.equal(dom.window.location.pathname, '/');
    console.log(`Actual HTTP + all dashboard scripts: ${expected.routes.length} catalog routes, ${expected.recommendations.length} final cards, collapsed metric details, unavailable scores preserved, GPX and SVG fallback verified.`);
  } finally {dom.window.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});

const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM, VirtualConsole} = require('jsdom');
const root = path.resolve(__dirname, '..');
const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/frontend_run.json'), 'utf8'));
const clone = value => JSON.parse(JSON.stringify(value));
const tick = () => new Promise(resolve => setTimeout(resolve, 10));
async function until(check) { for (let i = 0; i < 100; i++) { if (check()) return; await tick(); } throw Error('Timed out waiting for UI'); }

async function boot(authenticated = false, options = {}) {
  const dom = new JSDOM(fs.readFileSync(path.join(root, 'frontend/index.html'), 'utf8'), {runScripts: 'outside-only', url: 'http://localhost/', virtualConsole: new VirtualConsole()});
  const w = dom.window; w.HTMLElement.prototype.scrollIntoView = function () {}; const requests = []; const runs = []; const feedback = []; let favourites = []; let failPersonal = false; let failFeedback = false;
  const response = (data, status = 200) => ({ok: status < 400, status, json: async () => clone(data)});
  const leaflet = {maps: [], markers: [], lines: []};
  const evented = object => Object.assign(object, {handlers: {}, on(name, fn) {this.handlers[name] = fn; return this;}, fire(name, event) {this.handlers[name]?.(event); return this;}});
  if (options.map) {
    w.L = {
      map: () => {const m = evented({layers: new Set(), setView() {return this;}, fitBounds() {return this;}, panTo() {return this;}, removeLayer(layer) {this.layers.delete(layer);}}); leaflet.maps.push(m); return m;},
      tileLayer: () => ({addTo() {return this;}}), divIcon: options => options,
      marker: latlng => {const marker = evented({latlng, dragging: {enable() {}, disable() {}}, addTo(map) {map.layers.add(this); return this;}, setLatLng(value) {this.latlng = value; return this;}, getLatLng() {return {lat: this.latlng[0], lng: this.latlng[1]};}}); leaflet.markers.push(marker); return marker;},
      polyline: (points, options) => {const line = evented({points, options, bindTooltip() {return this;}}); leaflet.lines.push(line); return line;},
      featureGroup: lines => ({lines, addTo(map) {map.layers.add(this); return this;}, getBounds() {return {extend() {return this;}};}}),
      DomEvent: {stopPropagation() {}}
    };
  }
  if (options.geolocation) Object.defineProperty(w.navigator, 'geolocation', {value: options.geolocation, configurable: true});
  let forecastCalls = 0;
  if (options.forecastUI) w.outdoorwiseForecastUI = {fetchRecommendations: async () => { forecastCalls += 1; return fixture.generic; }};
  w.fetch = async (url, opt = {}) => {
    requests.push({url, method: opt.method || 'GET', body: opt.body ? JSON.parse(opt.body) : null});
    if (url === '/api/health') return response({data_mode: 'live', agent_mode: 'demo'});
    if (url === '/api/auth/me') return response(authenticated ? {user_id: 'test-user', username: 'Runner'} : {detail: 'Authentication required'}, authenticated ? 200 : 401);
    if (url === '/api/me/recommendations') return failPersonal ? response({}, 503) : response(options.personalized || fixture.personalized);
    if (url === '/api/recommendations') return response(options.generic || fixture.generic);
    if (url === '/api/experimental/recommendations') return response(fixture.generic);
    if (url === '/api/refresh') return response({status: 'partial', sources: [{source: 'nea_rainfall', status: 'failed', error: 'internal diagnostic'}]});
    if (url === '/api/chat') return response({message: 'Existing demo assistant', trace: [], run: fixture.generic});
    if (url.endsWith('/difficulty')) return response({predicted_difficulty: 2.3, difficulty_label: 'Easy'});
    if (url === '/api/users/test-user/runs') {
      if (opt.method === 'POST') {const run = {...JSON.parse(opt.body), completed_run_id: `run-${runs.length + 1}`}; runs.push(run); return response(run, 201);}
      return response(runs);
    }
    if (url === '/api/users/test-user/feedback') return response(feedback);
    if (url === '/api/users/test-user/favourites') return response(favourites);
    if (url.includes('/favourites/')) {
      const route_id = url.split('/').at(-1);
      if (opt.method === 'DELETE') favourites = favourites.filter(f => f.route_id !== route_id);
      else favourites.push({route_id});
      return response({route_id}, opt.method === 'DELETE' ? 204 : 200);
    }
    if (url.endsWith('/feedback')) {
      if (failFeedback) return response({}, 422);
      feedback.push({...JSON.parse(opt.body), completed_run_id: url.split('/').at(-2)}); return response(feedback.at(-1), 201);
    }
    throw Error('Unexpected endpoint ' + url);
  };
  for (const script of ['results', 'location', 'route-export', 'difficulty', 'personalization', 'forecast-ranking', 'app']) w.eval(fs.readFileSync(path.join(root, `frontend/${script}.js`), 'utf8'));
  await until(() => w.document.querySelectorAll('#cards .card').length > 0);
  await until(() => w.document.getElementById('personalization-status').textContent.includes(authenticated ? 'Loaded' : 'Sign in'));
  return {dom, w, d: w.document, leaflet, requests, runs, feedback, forecastCalls: () => forecastCalls, failPersonal: value => failPersonal = value, failFeedback: value => failFeedback = value};
}
const card = (d, id) => d.querySelector(`[data-personalization-route="${id}"]`);
const submit = (w, id) => w.document.getElementById(id).dispatchEvent(new w.Event('submit', {bubbles: true, cancelable: true}));

test('forecast UI presence does not hijack anonymous normal recommendations', async t => {
  const ui = await boot(false, {forecastUI: true}); t.after(() => ui.dom.window.close());
  assert.equal(ui.forecastCalls(), 0);
  assert.equal(ui.requests.filter(r => r.url === '/api/recommendations').length, 1);
  assert.equal(ui.requests.filter(r => r.url === '/api/experimental/recommendations').length, 0);
  assert(ui.d.querySelectorAll('#cards .card').length > 0);
});

test('forecast UI presence does not hijack authenticated personalized recommendations', async t => {
  const ui = await boot(true, {forecastUI: true}); t.after(() => ui.dom.window.close());
  assert.equal(ui.forecastCalls(), 0);
  assert.equal(ui.requests.filter(r => r.url === '/api/me/recommendations').length, 1);
  assert.equal(ui.requests.filter(r => r.url === '/api/experimental/recommendations').length, 0);
  assert.match(ui.d.getElementById('results-summary').textContent, /running profile/);
});

test('historical forecast is opt-in and preserves normal cards when unavailable', async t => {
  const ui = await boot(false, {forecastUI: true}); t.after(() => ui.dom.window.close());
  const launcher = ui.d.getElementById('forecast-launcher');
  assert.equal(launcher.hidden, false);
  assert.equal(ui.requests.filter(r => r.url === '/api/experimental/recommendations').length, 0);
  assert(ui.d.querySelectorAll('#cards .card').length > 0);
  launcher.click();
  await until(() => ui.requests.filter(r => r.url === '/api/experimental/recommendations').length === 1);
  assert(ui.d.querySelectorAll('#cards .card').length > 0);
});

test('current recommendations use the shared top-three toggle without refetching', async t => {
  const ui = await boot(true); t.after(() => ui.dom.window.close());
  const order = () => [...ui.d.querySelectorAll('#cards .card')].filter(c => !c.hidden).map(c => c.dataset.personalizationRoute);
  const allOrder = [...ui.d.querySelectorAll('#cards .card')].map(c => c.dataset.personalizationRoute);
  const before = ui.requests.length;
  const toggle = ui.d.getElementById('toggle-all-routes');
  assert.equal(order().length, 3);
  toggle.click();
  assert.equal(order().length, allOrder.length);
  assert.deepEqual(order(), allOrder);
  toggle.click();
  assert.equal(order().length, 3);
  assert.deepEqual(order(), allOrder.slice(0, 3));
  assert.equal(ui.requests.length, before);
});

test('historical collapse uses the active historical cards after a context switch', async t => {
  const ui = await boot(false); t.after(() => ui.dom.window.close());
  const launcher = ui.d.getElementById('forecast-launcher');
  launcher.click();
  await until(() => ui.requests.filter(r => r.url === '/api/experimental/recommendations').length === 1);
  await until(() => ui.d.querySelectorAll('#cards .unified-route-card').length > 0);
  const toggle = ui.d.getElementById('toggle-all-routes');
  const total = ui.d.querySelectorAll('#cards .unified-route-card').length;
  toggle.click();
  assert.equal([...ui.d.querySelectorAll('#cards .unified-route-card')].filter(card => !card.hidden).length, total);
  toggle.click();
  assert.equal([...ui.d.querySelectorAll('#cards .unified-route-card')].filter(card => !card.hidden).length, 3);
  assert.equal(toggle.textContent, `View all routes (${total})`);
});

 test('cards show new scores and zero risk correctly; technical details are closed', async t => {
  const ui = await boot(); t.after(() => ui.dom.window.close());
  const c = card(ui.d, 'marina_bay'); const rec = fixture.generic.recommendations.find(r => r.route_id === 'marina_bay');
  assert.match(c.querySelector('.recommendation-score').textContent, new RegExp(rec.recommendation_score.toFixed(1)));
  assert.match(c.querySelector('.risk-score').textContent, /0\.0 \/ 100Low risk/);
  assert(!c.querySelector('.score-pair').textContent.includes(rec.score.toString()));
  const details = c.querySelector('.environmental-details'); assert.equal(details.open, false);
  assert.equal(details.querySelectorAll('tr[data-metric]').length, 10);
  assert.match(details.textContent, /nea_wbgt/); assert.match(details.textContent, /2026-10-15T12:00:00/);
  details.open = true; assert(details.open);
  assert.match(c.querySelector('.assessment-time').textContent, /08:00 pm SGT/i);
  assert(!c.querySelector('.route-meta').textContent.includes('out_and_back'));
  assert.match(c.querySelector('.route-warnings').textContent, /geometry needs visual review/);
  assert.equal(ui.w.location.pathname, '/');
});

test('missing, stale, future and approximate states never become false low-risk claims', async t => {
  const ui = await boot(); t.after(() => ui.dom.window.close());
  for (const id of ['woodlands_waterfront', 'bishan_ang_mo_kio', 'bedok_reservoir']) {
    const c = card(ui.d, id); assert.match(c.querySelector('.risk-score').textContent, /Unknown/);
    assert(!c.querySelector('.risk-score').textContent.includes('Low risk'));
    assert.equal(c.querySelector('.recommendation-score strong').textContent, 'Unavailable');
    assert.match(c.querySelector('.fallback-message').textContent, /environmental assessment unavailable/);
  }
  assert.match(card(ui.d, 'bishan_ang_mo_kio').textContent, /currently outdated/);
  assert.match(card(ui.d, 'bedok_reservoir').textContent, /not available at the assessment time/);
  const approximate = card(ui.d, 'east_coast');
  assert.match(approximate.textContent, /Very low confidence/); assert.match(approximate.textContent, /5\.19 km/);
  assert.match(approximate.textContent, /not measurements along the full route/);
  assert.match(approximate.textContent, /Heat has the highest component risk score/);
  assert.match(approximate.textContent, /Forecast unavailable/);
});

test('blocked routes are separate discovery items, never given recommendation ranks', async t => {
  const ui = await boot(); t.after(() => ui.dom.window.close());
  assert.equal(ui.d.querySelectorAll('#cards .card').length, 11);
  const blocked = card(ui.d, 'jurong_lake_gardens');
  assert(blocked.closest('#blocked-routes')); assert.equal(blocked.querySelector('.rank-label').textContent, 'Not recommended');
  assert.equal(blocked.querySelector('.recommendation-score strong').textContent, 'Not recommended');
  assert.equal(ui.d.querySelector('.blocked-discovery').open, false);
});

test('authenticated final ordering persists through load, compare, refresh and chat', async t => {
  const ui = await boot(true); t.after(() => ui.dom.window.close());
  const order = () => [...ui.d.querySelectorAll('#cards .card')].map(c => c.dataset.personalizationRoute);
  const expected = fixture.personalized.recommendations.map(r => r.route_id);
  assert.deepEqual(order(), expected);
  fixture.personalized.recommendations.forEach((r, i) => {
    assert.equal(card(ui.d, r.route_id).querySelector('.rank-label').textContent, `Your difficulty-match rank #${r.personalized_rank}`);
    assert.match(card(ui.d, r.route_id).querySelector('.shared-rank-label').textContent, new RegExp(`Shared rank #${r.pipeline_rank}`));
  });
  submit(ui.w, 'preferences'); await until(() => ui.requests.filter(r => r.url === '/api/me/recommendations').length === 2); await tick();
  assert.deepEqual(order(), expected);
  ui.d.getElementById('refresh').click(); await until(() => ui.requests.filter(r => r.url === '/api/me/recommendations').length === 3); await tick();
  assert.deepEqual(order(), expected); assert(!ui.d.getElementById('ingestion').textContent.includes('nea_rainfall'));
  submit(ui.w, 'chat'); await until(() => ui.requests.filter(r => r.url === '/api/me/recommendations').length === 4); await tick();
  assert.deepEqual(order(), expected); assert(!ui.requests.some(r => r.url === '/api/recommendations'));
  assert(ui.requests.filter(r => r.url === '/api/me/recommendations').every(r => r.body.target_difficulty === 3));
  const c = card(ui.d, 'west_coast'); assert.match(c.querySelector('.difficulty-summary').textContent, /Predicted difficulty for you: 3\.0/);
});

test('personal endpoint failures remain visible and never silently call generic ranking', async t => {
  const ui = await boot(true); t.after(() => ui.dom.window.close()); ui.failPersonal(true);
  submit(ui.w, 'preferences'); await until(() => ui.d.getElementById('status').textContent.includes('could not update'));
  assert(!ui.requests.some(r => r.url === '/api/recommendations'));
});

test('favourite, completed-run feedback and GPX actions remain functional', async t => {
  const ui = await boot(true); t.after(() => ui.dom.window.close());
  const c = card(ui.d, 'west_coast'); c.querySelector('.favourite-button').click();
  await until(() => c.querySelector('.favourite-button').textContent.includes('Favourited'));
  c.querySelector('.favourite-button').click(); await until(() => !c.querySelector('.favourite-button').textContent.includes('Favourited'));
  assert.equal(c.querySelector('.export-route-button').getAttribute('href'), '/api/routes/west_coast/export.gpx');
  c.querySelector('.completed-run-button').click(); assert.equal(ui.d.getElementById('run-modal').hidden, false);
  assert.equal(ui.d.getElementById('run-distance').checkValidity(), true);
  assert(!ui.d.getElementById('run-route-label').textContent.includes('west_coast'));
  ui.d.getElementById('run-duration').value = '30'; ui.d.getElementById('run-difficulty').value = '3';
  submit(ui.w, 'run-form'); await until(() => ui.d.getElementById('run-modal').hidden);
  assert.equal(ui.runs.length, 1); assert.equal(ui.feedback.length, 1);
  assert.equal(ui.runs[0].personalized_predicted_difficulty, 3);
  assert.equal(ui.runs[0].predicted_difficulty, 3);
});

test('retrying feedback after a partial save does not duplicate completed runs', async t => {
  const ui = await boot(true); t.after(() => ui.dom.window.close()); ui.failFeedback(true);
  card(ui.d, 'west_coast').querySelector('.completed-run-button').click();
  ui.d.getElementById('run-duration').value = '30'; ui.d.getElementById('run-difficulty').value = '3';
  submit(ui.w, 'run-form'); await until(() => ui.d.getElementById('run-error').textContent.includes('Run saved'));
  assert.equal(ui.runs.length, 1); ui.failFeedback(false); await tick();
  submit(ui.w, 'run-form'); await until(() => ui.d.getElementById('run-modal').hidden);
  assert.equal(ui.runs.length, 1); assert.equal(ui.feedback.length, 1);
});

test('distance mismatch shows absolute and relative differences, without shortened geometry', async t => {
  const run = clone(fixture.generic); run.preferences.target_distance_km = 1.2;
  const rec = run.recommendations.find(r => r.route_id === 'west_coast'); rec.distance_difference_km = 2.841; rec.relative_distance_difference = 2.3675; rec.distance_match_warning = 'Not close';
  const ui = await boot(false, {generic: run}); t.after(() => ui.dom.window.close());
  const c = card(ui.d, 'west_coast'); assert.match(c.textContent, /2\.84 km longer than your 1\.2 km target/);
  assert.match(c.textContent, /237% difference/); assert.match(c.textContent, /Route length is unchanged/);
  c.querySelector('.view-route-button').click(); assert.equal(ui.d.querySelectorAll('#fallback svg').length, 1);
});

test('late difficulty responses cannot attach an old prediction after a new render', async t => {
  const dom = new JSDOM(fs.readFileSync(path.join(root, 'frontend/index.html'), 'utf8'), {runScripts: 'outside-only', url: 'http://localhost/'});
  t.after(() => dom.window.close()); const w = dom.window; const pending = [];
  w.fetch = () => new Promise(resolve => pending.push(resolve));
  w.eval(fs.readFileSync(path.join(root, 'frontend/difficulty.js'), 'utf8'));
  const route = fixture.generic.routes.find(r => r.route_id === 'west_coast');
  const makeCard = () => {const c = w.document.createElement('article'); c.dataset.personalizationRoute = route.route_id; c.innerHTML = '<div class="card-actions"></div>'; w.document.getElementById('cards').replaceChildren(c); return c;};
  makeCard(); w.document.dispatchEvent(new w.CustomEvent('outdoorwise:routes-rendered', {detail: {routes: [route]}}));
  const latest = makeCard(); w.document.dispatchEvent(new w.CustomEvent('outdoorwise:routes-rendered', {detail: {routes: [route]}}));
  pending[1]({ok: true, json: async () => ({predicted_difficulty: 4.2})}); await tick();
  pending[0]({ok: true, json: async () => ({predicted_difficulty: 1.1})}); await tick();
  assert.equal(latest.querySelectorAll('.difficulty-summary').length, 1);
  assert.match(latest.textContent, /4\.2/); assert(!latest.textContent.includes('1.1'));
  assert.equal(w.outdoorwiseDifficulty[route.route_id].predicted_difficulty, 4.2);
});

const change = (ui, id, value) => {ui.d.getElementById(id).value = value; ui.d.getElementById(id).dispatchEvent(new ui.w.Event('change', {bubbles: true}));};

for (const authenticated of [false, true]) test(`presets, compare, refresh and clear preserve location (${authenticated ? 'personal' : 'anonymous'})`, async t => {
  const ui = await boot(authenticated, {map: true}); t.after(() => ui.dom.window.close());
  change(ui, 'location-mode', 'preset'); change(ui, 'location-preset', 'bay');
  ui.d.getElementById('access').value = '2';
  assert.match(ui.d.getElementById('selected-coordinates').textContent, /1\.287000.*103\.855000/);
  const endpoint = authenticated ? '/api/me/recommendations' : '/api/recommendations';
  let count = ui.requests.filter(r => r.url === endpoint).length;
  submit(ui.w, 'preferences'); await until(() => ui.requests.filter(r => r.url === endpoint).length > count); await tick();
  let body = ui.requests.filter(r => r.url === endpoint).at(-1).body;
  assert.deepEqual(body.location, {lon: 103.855, lat: 1.287}); assert.equal(body.max_access_distance_km, 2);
  count++; ui.d.getElementById('refresh').click(); await until(() => ui.requests.filter(r => r.url === endpoint).length > count); await tick();
  body = ui.requests.filter(r => r.url === endpoint).at(-1).body;
  assert.deepEqual(body.location, {lon: 103.855, lat: 1.287}); assert.equal(body.max_access_distance_km, 2);
  change(ui, 'location-preset', 'north'); assert.deepEqual({...ui.w.outdoorwiseLocation.selectedPoint()}, {lon: 103.786, lat: 1.438});
  change(ui, 'location-preset', 'nus'); assert.deepEqual({...ui.w.outdoorwiseLocation.selectedPoint()}, {lon: 103.776, lat: 1.296});
  ui.d.getElementById('clear-location').click(); assert.equal(ui.w.outdoorwiseLocation.selectedPoint(), null);
  assert.equal(ui.d.getElementById('location-mode').value, 'anywhere'); assert(ui.d.getElementById('access').disabled);
  count = ui.requests.filter(r => r.url === endpoint).length;
  submit(ui.w, 'preferences'); await until(() => ui.requests.filter(r => r.url === endpoint).length > count);
  body = ui.requests.filter(r => r.url === endpoint).at(-1).body;
  assert.equal(body.location, null); assert.equal(body.max_access_distance_km, null);
  assert.equal(ui.leaflet.maps.length, 1);
});

test('map clicks replace one marker; dragging and route clicks cannot confuse the starting point', async t => {
  const ui = await boot(false, {map: true}); t.after(() => ui.dom.window.close());
  const map = ui.leaflet.maps[0]; change(ui, 'location-mode', 'map');
  map.fire('click', {latlng: {lat: 1.30, lng: 103.80}});
  assert.deepEqual({...ui.w.outdoorwiseLocation.selectedPoint()}, {lon: 103.8, lat: 1.3});
  const marker = ui.leaflet.markers[0];
  map.fire('click', {latlng: {lat: 1.31, lng: 103.81}}); assert.equal(ui.leaflet.markers.length, 1);
  assert.deepEqual([...marker.latlng], [1.31, 103.81]);
  marker.setLatLng([1.32, 103.82]); marker.fire('dragend', {target: marker});
  assert.deepEqual({...ui.w.outdoorwiseLocation.selectedPoint()}, {lon: 103.82, lat: 1.32});
  const before = {...ui.w.outdoorwiseLocation.selectedPoint()};
  const route = ui.leaflet.lines[0]; assert.equal(route.options.bubblingMouseEvents, false);
  route.fire('click', {originalEvent: {}}); assert.deepEqual({...ui.w.outdoorwiseLocation.selectedPoint()}, before);
  const target = ui.d.createElement('div'); target.className = 'leaflet-interactive';
  map.fire('click', {latlng: {lat: 0, lng: 0}, originalEvent: {target}});
  assert.deepEqual({...ui.w.outdoorwiseLocation.selectedPoint()}, before);
  assert(map.layers.has(marker)); assert.equal(ui.leaflet.maps.length, 1);
  const count = ui.requests.filter(r => r.url === '/api/recommendations').length;
  submit(ui.w, 'preferences'); await until(() => ui.requests.filter(r => r.url === '/api/recommendations').length > count);
  assert.deepEqual(ui.requests.filter(r => r.url === '/api/recommendations').at(-1).body.location, before);
});

for (const [code, text] of [[1, 'permission was denied'], [2, 'could not be determined'], [3, 'timed out']]) test(`geolocation error ${code} preserves explicit manual fallback without relaxing access`, async t => {
  const calls = [];
  const ui = await boot(false, {map: true, geolocation: {getCurrentPosition(success, failure, options) {calls.push({success, failure, options});}}});
  t.after(() => ui.dom.window.close());
  change(ui, 'location-mode', 'current'); assert.equal(calls.length, 0); // Explicit button only.
  ui.d.getElementById('access').value = '2'; ui.d.getElementById('get-current-location').click(); assert.equal(calls.length, 1);
  assert.equal(calls[0].options.timeout, 10000); assert.equal(calls[0].options.maximumAge, 0);
  calls[0].failure({code}); assert.match(ui.d.getElementById('location-status').textContent, new RegExp(text));
  const count = ui.requests.filter(r => r.url === '/api/recommendations').length;
  submit(ui.w, 'preferences'); await tick(); assert.equal(ui.requests.filter(r => r.url === '/api/recommendations').length, count);
  assert.match(ui.d.getElementById('status').textContent, /access limit has not been relaxed/);
  ui.d.getElementById('choose-location-on-map').click();
  ui.leaflet.maps[0].fire('click', {latlng: {lat: 1.29, lng: 103.85}});
  submit(ui.w, 'preferences'); await until(() => ui.requests.filter(r => r.url === '/api/recommendations').length > count);
  assert.equal(ui.requests.filter(r => r.url === '/api/recommendations').at(-1).body.max_access_distance_km, 2);
});

test('one-shot location success and late callbacks never overwrite a later preset', async t => {
  const calls = []; const ui = await boot(false, {map: true, geolocation: {getCurrentPosition(success, failure) {calls.push({success, failure});}}});
  t.after(() => ui.dom.window.close()); change(ui, 'location-mode', 'current'); ui.d.getElementById('get-current-location').click();
  calls[0].success({coords: {latitude: 1.2961, longitude: 103.7762, accuracy: 24}});
  assert.deepEqual({...ui.w.outdoorwiseLocation.selectedPoint()}, {lon: 103.7762, lat: 1.2961}); assert.match(ui.d.getElementById('location-status').textContent, /24 m/);
  ui.d.getElementById('get-current-location').click(); change(ui, 'location-mode', 'preset');
  calls[1].success({coords: {latitude: 0, longitude: 0}});
  assert.deepEqual({...ui.w.outdoorwiseLocation.selectedPoint()}, {lon: 103.776, lat: 1.296});
  assert.equal(calls.length, 2); assert.equal(ui.w.navigator.geolocation.watchPosition, undefined);
});

test('unsupported geolocation and unavailable map retain presets and Anywhere mode', async t => {
  const ui = await boot(); t.after(() => ui.dom.window.close()); change(ui, 'location-mode', 'current');
  ui.d.getElementById('get-current-location').click(); assert.match(ui.d.getElementById('location-status').textContent, /supported browser/);
  assert(ui.d.getElementById('choose-location-on-map').disabled);
  change(ui, 'location-mode', 'preset'); assert.deepEqual({...ui.w.outdoorwiseLocation.selectedPoint()}, {lon: 103.776, lat: 1.296});
  ui.d.getElementById('clear-location').click(); assert.equal(ui.w.outdoorwiseLocation.locationForRequest(), null);
});

test('empty access-filter result retains limit and renders no invented candidates', async t => {
  const run = clone(fixture.generic); run.recommendations = []; run.preferences.location = {lon: 103.776, lat: 1.296}; run.preferences.max_access_distance_km = .1;
  const ui = await boot(false, {generic: fixture.generic}); t.after(() => ui.dom.window.close());
  ui.w.eval(`render(${JSON.stringify(run)})`);
  assert.equal(ui.d.querySelectorAll('#cards .card').length, 0);
  assert.match(ui.d.querySelector('.empty-results').textContent, /0\.1 km straight-line access limit/);
  assert.match(ui.d.querySelector('.empty-results').textContent, /limit has not been relaxed/);
});

test('result summaries show the actual API straight-line distance without travel-time claims', async t => {
  const run = clone(fixture.generic); run.recommendations[0].access_distance_km = 1.234;
  const ui = await boot(false, {generic: run}); t.after(() => ui.dom.window.close());
  assert.match(ui.d.querySelector('#cards .access-distance').textContent, /1\.23 km straight-line/);
  assert.match(ui.d.querySelector('#cards .access-distance').textContent, /not walking or driving distance/);
});

test('changing the starting point while a comparison is pending rejects the old result', async t => {
  const ui = await boot(false, {map: true}); t.after(() => ui.dom.window.close());
  const fetch = ui.w.fetch; let release;
  ui.w.fetch = (url, options) => url === '/api/recommendations' ? new Promise(resolve => release = resolve) : fetch(url, options);
  submit(ui.w, 'preferences'); await until(() => release);
  change(ui, 'location-mode', 'preset');
  release({ok: true, status: 200, json: async () => clone(fixture.generic)});
  await until(() => ui.d.getElementById('status').textContent.includes('Starting point changed while routes were updating'));
  assert.deepEqual({...ui.w.outdoorwiseLocation.selectedPoint()}, {lon: 103.776, lat: 1.296});
});

test('invalid access limits are not silently cleared on comparison or refresh', async t => {
  const ui = await boot(false, {map: true}); t.after(() => ui.dom.window.close());
  change(ui, 'location-mode', 'preset'); ui.d.getElementById('access').value = '-1';
  const before = ui.requests.length; submit(ui.w, 'preferences'); await tick();
  assert.match(ui.d.getElementById('status').textContent, /valid positive straight-line access limit/);
  ui.d.getElementById('refresh').click(); await tick(); assert.equal(ui.requests.length, before);
});

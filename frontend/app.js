const $ = id => document.getElementById(id);
let map, layer, dynamicMap, dynamicLayer, routes = [];
function preferences() {
  const location = window.outdoorwiseLocation.locationForRequest();
  if (location && !$('access').checkValidity()) throw Error('Enter a valid positive straight-line access limit, or clear the limit.');
  return {target_distance_km: Number($('distance').value), duration_min: Number($('duration').value), horizon_min: Number($('duration').value) <= 30 ? 30 : 60,
    target_difficulty: Number($('target-difficulty').value), location,
    max_access_distance_km: location && $('access').value ? Number($('access').value) : null};
}
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  if (!response.ok) {
    const error = Error(response.status === 401 ? 'Your session expired. Sign in again to use your personal recommendations.' : 'We could not update your routes. Please try again.');
    error.status = response.status; throw error;
  }
  return response.json();
}
async function dynamicApi(path, body) {
  const response = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw Error(typeof data.detail === 'string' ? data.detail : 'The dynamic route request failed. Please try again.');
  return data;
}
function ensureMap() {
  if (!window.L) {window.outdoorwiseLocation.mapUnavailable(); return null;}
  if (!map) {
    map = L.map('map').setView([1.36, 103.82], 11);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {attribution: '© OpenStreetMap contributors', maxZoom: 19}).addTo(map);
    window.outdoorwiseLocation.attachMap(map);
  }
  return map;
}
function draw(selected){if(!window.L){window.outdoorwiseLocation.mapUnavailable();$('map').hidden=true;$('fallback').hidden=false;$('fallback').replaceChildren();const p=document.createElement('p');p.textContent='Map library unavailable. Route shapes shown below (separate local coordinate panels).';$('fallback').append(p);for(const r of selected){const pts=r.geometry.coordinates,xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]);const minx=Math.min(...xs),miny=Math.min(...ys),dx=Math.max(...xs)-minx||1,dy=Math.max(...ys)-miny||1;const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 600 280');const line=document.createElementNS(svg.namespaceURI,'polyline');line.setAttribute('points',pts.map(p=>`${20+560*(p[0]-minx)/dx},${260-220*(p[1]-miny)/dy}`).join(' '));line.setAttribute('fill','none');line.setAttribute('stroke','#24684c');line.setAttribute('stroke-width','3');const title=document.createElement('p');title.textContent=r.name;$('fallback').append(title,svg);svg.append(line);}return;}
ensureMap();
if (layer) map.removeLayer(layer);
layer = L.featureGroup(selected.map((route, index) => {
  const line = L.polyline(route.geometry.coordinates.map(p => [p[1], p[0]]), {color: index ? '#bb792c' : '#24684c', weight: 5, bubblingMouseEvents: false});
  const label = document.createElement('span'); label.textContent = route.name; line.bindTooltip(label);
  line.on('click', event => {
    if (event.originalEvent) L.DomEvent.stopPropagation(event.originalEvent);
    draw([route]);
  });
  return line;
})).addTo(map);
if (selected.length) {
  const bounds = layer.getBounds(); const startingPoint = window.outdoorwiseLocation.selectedPoint();
  if (startingPoint) bounds.extend([startingPoint.lat, startingPoint.lon]);
  map.fitBounds(bounds, {padding: [25, 25]});
}
}

function drawDynamic(selected) {
  if (!window.L) { $('dynamic-map').hidden = true; $('dynamic-fallback').hidden = false; $('dynamic-fallback').textContent = 'Map library unavailable.'; return; }
  if (!dynamicMap) {
    dynamicMap = L.map('dynamic-map').setView([1.36, 103.82], 11);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {attribution: '© OpenStreetMap contributors', maxZoom: 19}).addTo(dynamicMap);
    dynamicMap.on('click', event => {
      $('route-lat').value = event.latlng.lat.toFixed(6); $('route-lon').value = event.latlng.lng.toFixed(6);
      $('route-generator-status').textContent = 'Start point selected on the dynamic-route map.';
    });
  }
  if (dynamicLayer) dynamicMap.removeLayer(dynamicLayer);
  dynamicLayer = L.featureGroup(selected.map((route, index) => L.polyline(route.geometry.coordinates.map(point => [point[1], point[0]]),
    {color: ['#24684c', '#bb792c', '#496bb3'][index % 3], weight: 5}))).addTo(dynamicMap);
  if (selected.length) dynamicMap.fitBounds(dynamicLayer.getBounds(), {padding: [25, 25]});
}

function render(run) {
  if (window.outdoorwiseForecastUI && run.mode === 'experimental_historical_forecast_ranking') {
    routes = run.routes;
    window.outdoorwiseForecastUI.render(run);
    return;
  }
  $('context-indicator').textContent = 'Current conditions';
  routes = run.routes;
  draw(routes);
  $('cards').replaceChildren(); $('blocked-routes').replaceChildren();
  const rows = run.recommendations || [];
  const riskMap = new Map((run.risks || []).map(r => [r.route_id, r]));
  const envMap = new Map((run.environment || []).map(e => [e.route_id, e]));
  const predictionMap = new Map((run.predictions || []).map(p => [p.route_id, p]));
  const routeMap = new Map(routes.map(r => [r.route_id, r]));
  const blocked = (run.risks || []).filter(r => r.eligibility === 'blocked');
  $('results-summary').textContent = `${rows.length} route${rows.length === 1 ? '' : 's'} · ${window.personalizedRanking ? 'Matched to your running profile' : 'Matched to your preferences'}`;
  const messages = [];
  if (rows.length && rows.every(r => r.recommendation_score === null)) messages.push('Environmental assessment unavailable. Routes are ordered using available distance, access and difficulty preferences.');
  if (rows.length && rows.every(r => r.distance_match_warning)) messages.push('No available route closely matches your target distance. Route lengths have not been shortened.');
  if (blocked.length) messages.push(`${blocked.length} route${blocked.length === 1 ? '' : 's'} excluded by environmental policy. Review them below.`);
  if (run.data_mode === 'demo') messages.push('Demo observations are synthetic. They do not describe current weather.');
  $('warnings').textContent = messages.join(' '); $('warnings').hidden = !messages.length;
  const addCard = (route, rec, risk, index, parent) => {
    if (!route) return;
    parent.append(window.outdoorwiseResults.card(route, rec, risk, envMap.get(route.route_id), predictionMap.get(route.route_id), run.preferences,
      window.personalizedRanking?.[route.route_id], index, selected => draw([selected])));
  };
  rows.forEach((rec, index) => addCard(routeMap.get(rec.route_id), rec, riskMap.get(rec.route_id), index, $('cards')));
  if (!rows.length) {
    const limit = run.preferences.max_access_distance_km;
    const empty = run.preferences.location && typeof limit === 'number'
      ? `No recommended routes meet your preferences and ${limit} km straight-line access limit. The limit has not been relaxed. Choose another starting point or change the limit.`
      : blocked.length ? 'No routes can currently be recommended. Review policy exclusions below or adjust your preferences.' : 'No routes match these preferences. Try a different starting location or distance.';
    $('cards').append(Object.assign(document.createElement('p'), {className: 'empty-results', textContent: empty}));
  }
  if (blocked.length) {
    const details = document.createElement('details'); details.className = 'blocked-discovery';
    const summary = document.createElement('summary'); summary.textContent = `Routes not recommended (${blocked.length})`;
    const container = document.createElement('div'); container.className = 'blocked-cards'; details.append(summary, container);
    blocked.forEach((risk, index) => addCard(routeMap.get(risk.route_id), null, risk, index, container));
    $('blocked-routes').append(details);
  }
  window.outdoorwiseRouteVisibility?.apply(Boolean(window.personalizedRanking));
  document.dispatchEvent(new CustomEvent('outdoorwise:routes-rendered', {detail: {routes, recommendations: rows,
    personalizedRanking: window.personalizedRanking, authenticated: Boolean(window.outdoorwiseSession)}}));
}
async function personalizedOrGeneric() {
  const base = preferences();
  const revision = window.outdoorwiseLocation.revision();
  const confirmSelection = run => {
    if (revision !== window.outdoorwiseLocation.revision()) throw Error('Starting point changed while routes were updating. Compare Routes again to use the new point.');
    if (base.max_access_distance_km !== preferences().max_access_distance_km) throw Error('Access limit changed while routes were updating. Compare Routes again to use the new limit.');
    return run;
  };
  const session = await fetch('/api/auth/me');
  if (session.status === 401) {
    window.outdoorwiseSession = null; window.personalizedRanking = null;
    return confirmSelection(await api('/api/recommendations', base));
  }
  if (!session.ok) throw Error('We could not check your sign-in status. Please try again.');
  window.outdoorwiseSession = await session.json();
  const response = await api('/api/me/recommendations', base);
  confirmSelection(response.run);
  window.personalizedRanking = Object.fromEntries(response.recommendations.map(r => [r.route_id, r]));
  const order = new Map(response.recommendations.map((r, index) => [r.route_id, index]));
  // Preserve the final server ordering, including personalized unknown-risk fallback.
  response.run.recommendations.sort((a, b) => order.get(a.route_id) - order.get(b.route_id));
  return response.run;
}
async function busy(action) {
  const buttons = [...document.querySelectorAll('#preferences > button, #refresh, #chat button')];
  buttons.forEach(button => button.disabled = true); $('status').textContent = 'Updating routes…';
  try { await action(); $('status').textContent = 'Routes updated.'; }
  catch (error) { $('status').textContent = error.message; }
  finally { buttons.forEach(button => button.disabled = false); }
}
$('preferences').onsubmit = event => {event.preventDefault(); busy(async () => render(await personalizedOrGeneric()));};
$('refresh').onclick = () => busy(async () => {
  preferences(); // Never drop a pending/unselected location or its access constraint.
  const report = await api('/api/refresh', {});
  $('ingestion').textContent = report.status === 'partial' ? 'Some observations could not be refreshed. Retained data may be outdated.' : 'Environmental observations refreshed.';
  render(await personalizedOrGeneric());
});
$('chat').onsubmit = event => {event.preventDefault(); busy(async () => {
  const response = await api('/api/chat', {message: $('message').value, preferences: preferences()});
  $('answer').textContent = response.message; $('trace').textContent = JSON.stringify(response.trace, null, 2);
  // Assistant prose does not replace the final user-specific recommendation list.
  render(await personalizedOrGeneric());
});};
$('route-generator').onsubmit = async event => {
  event.preventDefault(); const status = $('route-generator-status'); const cards = $('generated-route-cards');
  status.textContent = 'Generating, sampling environment, and ranking candidates…'; cards.replaceChildren();
  try {
    const result = await dynamicApi('/api/generated-routes', {start: {lat: Number($('route-lat').value), lon: Number($('route-lon').value)},
      target_distance_km: Number($('route-distance').value), candidate_count: 3, target_difficulty: Number($('dynamic-target-difficulty').value),
      preferences: {prefer_green: $('route-green').checked, prefer_quiet: $('route-quiet').checked, avoid_steps: $('route-steps').checked}});
    drawDynamic(result.candidates); const assessments = new Map(result.assessments.map(item => [item.route_id, item]));
    result.candidates.forEach((route, index) => {
      const assessment = assessments.get(route.route_id); const card = document.createElement('article'); card.className = 'card'; card.dataset.personalizationRoute = route.route_id;
      const title = document.createElement('h3'); title.textContent = `${assessment?.rank || index + 1}. ${route.name}`;
      const detail = document.createElement('p'); detail.textContent = `${route.distance_km.toFixed(2)} km · ${route.distance_error_pct.toFixed(1)}% from target · score ${assessment?.score ?? 'N/A'}`;
      card.append(title, detail);
      if (assessment) {
        const personal = assessment.personalized_difficulty?.personalized_predicted_difficulty; const difficulty = document.createElement('p');
        difficulty.textContent = `${personal == null ? 'Generic difficulty' : 'Predicted difficulty for you'}: ${(personal ?? assessment.generic_difficulty.predicted_difficulty).toFixed(1)} / 5 · ${assessment.generic_difficulty.data_quality}`;
        card.append(difficulty); window.outdoorwiseDifficulty = window.outdoorwiseDifficulty || {};
        window.outdoorwiseDifficulty[route.route_id] = {predicted_difficulty: assessment.generic_difficulty.predicted_difficulty, personalized_predicted_difficulty: personal};
        const important = new Set(['rainfall', 'wbgt', 'heat_stress_level', 'pm25', 'psi']);
        assessment.environment.metrics.filter(metric => important.has(metric.metric)).forEach(metric => {
          const row = document.createElement('p'); const value = metric.category_value ?? (metric.value == null ? 'Unavailable' : `${Number(metric.value.toFixed(1))} ${metric.unit}`);
          row.textContent = `${metric.metric}: ${value} · ${metric.state}/${metric.delivery}`; row.title = metric.reason; card.append(row);
        });
      }
      const warning = document.createElement('p'); warning.textContent = route.warnings.join(' ');
      const actions = document.createElement('div'); actions.className = 'card-actions';
      const favourite = document.createElement('button'); favourite.className = 'favourite-button';
      const completed = document.createElement('button'); completed.className = 'completed-run-button'; completed.textContent = 'I completed this run'; actions.append(favourite, completed);
      const show = document.createElement('button'); show.textContent = 'Show route'; show.onclick = () => drawDynamic([route]);
      const download = document.createElement('a'); download.className = 'export-route-button'; download.href = `/api/generated-routes/${encodeURIComponent(route.route_id)}/export.gpx`; download.textContent = 'Download GPX';
      card.append(warning, actions, show, download); cards.append(card);
    });
    document.dispatchEvent(new CustomEvent('outdoorwise:routes-rendered', {detail: {routes: result.candidates}}));
    status.textContent = `Generated and ranked ${result.candidates.length} validated candidate(s). ${result.warnings.join(' ')}`;
  } catch (error) { status.textContent = error.message; }
};
function activateRouteTab(name) {
  const catalog = name === 'catalog'; $('catalog-panel').hidden = !catalog; $('dynamic-panel').hidden = catalog;
  $('catalog-tab-button').classList.toggle('active', catalog); $('dynamic-tab-button').classList.toggle('active', !catalog);
  $('catalog-tab-button').setAttribute('aria-selected', String(catalog)); $('dynamic-tab-button').setAttribute('aria-selected', String(!catalog));
  setTimeout(() => (catalog ? map : dynamicMap)?.invalidateSize(), 0);
}
$('catalog-tab-button').onclick = () => activateRouteTab('catalog');
$('dynamic-tab-button').onclick = () => { activateRouteTab('dynamic'); if (!dynamicMap) drawDynamic([]); };
document.addEventListener('outdoorwise:location-changed', () => { $('status').textContent = 'Starting point changed. Compare Routes to update your results.'; });
ensureMap();
busy(async () => {
  const health = await api('/api/health');
  $('mode').textContent = health.data_mode === 'demo' ? 'Demo observations' : 'Environmental observations';
  render(await personalizedOrGeneric());
});

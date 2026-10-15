/* Present backend assessments without calculating risk or changing route order. */
(() => {
  const number = value => typeof value === 'number' && Number.isFinite(value);
  const labels = {fresh: 'Fresh at assessment', stale: 'Outdated observations', missing: 'Observations unavailable', unavailable_as_of: 'Not available at assessment time', mixed: 'Some observations unavailable', high: 'High', moderate: 'Moderate', low: 'Low', very_low: 'Very low', regional: 'Regional estimate', unknown: 'Unknown', elevated: 'Elevated'};
  const metricNames = {rainfall: 'Rainfall', wind_speed: 'Wind speed', wind_direction: 'Wind direction', air_temperature: 'Air temperature', relative_humidity: 'Relative humidity', pm25: 'PM2.5', psi: 'PSI', pm10: 'PM10', wbgt: 'WBGT', heat_stress_level: 'Official heat stress'};
  const kinds = {loop: 'Loop', out_and_back: 'Out and back', point_to_point: 'Point to point'};
  const formatTime = value => {
    if (!value || Number.isNaN(new Date(value).getTime())) return 'Not available';
    return new Intl.DateTimeFormat('en-SG', {timeZone: 'Asia/Singapore', day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: true}).format(new Date(value)) + ' SGT';
  };
  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function technicalTime(value) {
    const node = element('time', formatTime(value));
    if (value) { node.dateTime = value; node.title = value; node.append(element('small', value, 'technical-timestamp')); }
    return node;
  }
  function environmentalDetails(env, risk, rec, prediction) {
    const details = element('details', undefined, 'environmental-details');
    details.append(element('summary', 'Environmental Details'));
    details.append(element('p', 'Station readings describe conditions near the route start; regional readings cover a wider area. They do not measure the full route.', 'detail-note'));
    if (risk?.assessed_at) details.append(element('p', `Assessment: ${formatTime(risk.assessed_at)}`), technicalTime(risk.assessed_at));
    const wrap = element('div', undefined, 'environment-scroll');
    const table = element('table', undefined, 'environment');
    table.append(element('caption', 'Environmental observations and source information'));
    const head = element('thead'); const headings = element('tr');
    for (const title of ['Metric / window', 'Measured value', 'Source / station or region', 'Station distance', 'Observed', 'Fetched', 'Freshness / delivery', 'Mapping / confidence']) {
      const th = element('th', title); th.scope = 'col'; headings.append(th);
    }
    head.append(headings); table.append(head);
    const body = element('tbody');
    for (const m of env?.metrics || []) {
      const component = Object.values(risk?.risk_components || {}).find(c => c.metric === m.metric);
      const row = element('tr'); row.dataset.metric = m.metric; row.dataset.state = m.state;
      const values = [
        `${metricNames[m.metric] || m.metric} · ${m.metric} / ${m.aggregation_window}`,
        m.category_value ?? (number(m.value) ? `${m.value.toLocaleString('en-SG', {maximumFractionDigits: 2})} ${m.unit}` : 'Unavailable'),
        `${m.source} / ${m.location_name || m.location_id || 'Unavailable'}`,
        number(m.station_distance_km) ? `${m.station_distance_km} km` : 'Not a station measurement / unavailable',
        technicalTime(m.observed_at), technicalTime(m.fetched_at),
        `${component?.freshness || m.state} / ${m.delivery}`,
        `${m.match_method} · ${component?.spatial_quality || 'Not assessed'}${component ? ' / ' + component.estimate_status : ''}`
      ];
      for (const value of values) { const td = element('td'); td.append(typeof value === 'string' ? document.createTextNode(value) : value); row.append(td); }
      // Full raw timestamp and status explanations stay available without hover.
      row.title = `${m.reason || ''} · source updated ${m.source_updated_at || 'not supplied'}`;
      if (m.source_updated_at) {
        const note = element('small', `Source updated: ${m.source_updated_at}`, 'technical-timestamp');
        row.children[5].append(note);
      }
      if (m.reason) row.children[7].append(element('small', m.reason, 'technical-timestamp'));
      body.append(row);
    }
    table.append(body); wrap.append(table); details.append(wrap);
    if (!env?.metrics?.length) details.append(element('p', 'No environmental observations were returned.'));
    const notes = element('ul', undefined, 'technical-notes');
    for (const text of [...(risk?.risk_warnings || []), ...(risk?.reasons || []), ...(rec?.ranking_reasons || [])]) notes.append(element('li', text));
    details.append(notes);
    if (rec) details.append(element('p', `Original baseline rank: ${rec.original_base_rank ?? 'Unavailable'} · Legacy baseline score: ${rec.score ?? 'Unavailable'} · Ranking method: ${rec.ranking_method || 'Unavailable'}`));
    if (prediction) details.append(element('p', `Prediction status: ${prediction.prediction_status} · Source: ${prediction.source} · Simulated: ${prediction.is_mock ? 'yes' : 'no'}`));
    return details;
  }
  function card(route, rec, risk, env, prediction, preferences, personal, index, viewRoute) {
    const card = element('article', undefined, 'card route-summary');
    card.dataset.personalizationRoute = route.route_id;
    const blocked = risk?.eligibility === 'blocked' || rec?.eligibility === 'blocked';
    card.dataset.eligibility = blocked ? 'blocked' : (rec?.eligibility || risk?.eligibility || 'unknown');
    const components = risk?.risk_components || {};
    const selected = Object.values(components);
    const outdated = selected.some(c => c.freshness === 'stale') || risk?.risk_data_quality?.observation_freshness === 'stale';
    const future = selected.some(c => c.freshness === 'unavailable_as_of');
    const complete = risk?.risk_status === 'complete' && number(risk?.risk_score) && !outdated && !future;
    const heading = element('div', undefined, 'route-heading');
    const rank = blocked ? 'Not recommended' : `Final rank #${rec?.final_rank ?? personal?.final_rank ?? index + 1}`;
    heading.append(element('span', rank, 'rank-label'), element('span', blocked ? 'Blocked by policy' : complete ? (card.dataset.eligibility === 'caution' ? 'Use caution' : 'Assessment complete') : 'Assessment unavailable', 'assessment-label'));
    card.append(heading, element('h3', route.name), element('p', `${route.distance_km.toLocaleString('en-SG', {maximumFractionDigits: 3})} km · ${kinds[route.kind] || 'Running route'}`, 'route-meta'));
    const scores = element('div', undefined, 'score-pair');
    const match = element('div', undefined, 'score-block recommendation-score');
    match.append(element('span', 'Recommendation Score', 'score-title'));
    if (complete && !blocked && number(rec?.recommendation_score)) {
      match.append(element('strong', `${rec.recommendation_score.toFixed(1)} / 100`), element('small', 'Higher = better match'));
    } else match.append(element('strong', blocked ? 'Not recommended' : 'Unavailable'));
    const environmental = element('div', undefined, 'score-block risk-score');
    environmental.append(element('span', 'Environmental Risk', 'score-title'));
    if (complete) environmental.append(element('strong', `${risk.risk_score.toFixed(1)} / 100`), element('small', `${labels[risk.risk_level] || 'Unknown'} risk · Higher = greater risk`));
    else environmental.append(element('strong', 'Unknown'), element('small', 'Incomplete environmental information'));
    scores.append(match, environmental); card.append(scores);
    if (!complete && !blocked) card.append(element('p', 'Ranked by available distance and difficulty preferences; environmental assessment unavailable.', 'fallback-message'));
    const risks = element('dl', undefined, 'component-risks');
    for (const [name, label] of [['rainfall', 'Rainfall risk'], ['heat', 'Heat risk'], ['air_quality', 'Air-quality risk']]) {
      const c = components[name]; const item = element('div');
      item.append(element('dt', label), element('dd', c?.freshness === 'fresh' && number(c.score) ? `${c.score.toFixed(1)} / 100` : 'Unavailable'));
      risks.append(item);
    }
    card.append(risks);
    const confidence = risk?.risk_data_quality?.confidence || rec?.risk_confidence || 'unknown';
    const freshness = outdated ? 'Outdated observations' : future ? 'Not available at assessment time' : labels[risk?.risk_data_quality?.observation_freshness] || 'Observations unavailable';
    card.append(element('p', `${freshness} · ${labels[confidence] || 'Unknown'} confidence`, 'data-quality'));
    if (risk?.assessed_at) card.append(element('p', `Assessed ${formatTime(risk.assessed_at)}`, 'assessment-time'));
    if (risk?.risk_data_quality?.simulated) card.append(element('p', 'Synthetic demo observations', 'important-warning'));
    const reasons = element('ul', undefined, 'route-reasons');
    if (rec && number(rec.distance_difference_km)) {
      const target = preferences.target_distance_km;
      if (rec.distance_match_warning) {
        const relation = route.distance_km >= target ? 'longer' : 'shorter';
        reasons.append(element('li', `${rec.distance_difference_km.toFixed(2)} km ${relation} than your ${target} km target${number(rec.relative_distance_difference) ? ` (${(100 * rec.relative_distance_difference).toFixed(0)}% difference)` : ''}. Route length is unchanged.`, 'distance-warning'));
      } else reasons.append(element('li', `Close to your target distance · ${rec.distance_difference_km.toFixed(2)} km difference.`));
    }
    const highest = Object.entries(components).filter(([, c]) => c.freshness === 'fresh' && number(c.score) && c.score > 0).sort((a, b) => b[1].score - a[1].score);
    if (highest.length) {
      const names = {rainfall: 'Rainfall', heat: 'Heat', air_quality: 'Air quality', wind: 'Wind'};
      reasons.append(element('li', `${names[highest[0][0]] || 'An environmental factor'} has the highest component risk score.`));
    }
    if (personal && number(personal.personalized_difficulty)) reasons.append(element('li', `Your requested difficulty: ${personal.target_difficulty} / 5.`));
    if (rec && rec.access_distance_km === null) reasons.append(element('li', preferences.location ? 'Straight-line access distance is unavailable for this route.' : 'No starting location selected; access distance is not estimated.'));
    if (rec && number(rec.access_distance_km)) reasons.append(element('li', `${rec.access_distance_km.toFixed(2)} km straight-line distance from your starting point to the route start; not walking or driving distance.`, 'access-distance'));
    card.append(reasons);
    const warnings = element('ul', undefined, 'route-warnings');
    if (blocked) warnings.append(element('li', 'This route is excluded by the environmental policy. It is shown for discovery only.'));
    if (outdated) warnings.append(element('li', 'Environmental observations are currently outdated. A low risk level cannot be established.'));
    if (future) warnings.append(element('li', 'Some observations were not available at the assessment time.'));
    const approximate = selected.filter(c => c.estimate_status === 'approximate' && number(c.station_distance_km));
    if (approximate.length) warnings.append(element('li', `A selected weather station is ${Math.max(...approximate.map(c => c.station_distance_km)).toFixed(2)} km from the route start. This is an approximate estimate, not measurements along the full route.`));
    else if (['low', 'very_low'].includes(confidence)) warnings.append(element('li', 'Weather coverage near the route start is limited; conditions can vary along the route.'));
    if (route.status === 'candidate_requires_visual_review') warnings.append(element('li', 'Route geometry needs visual review before navigation.'));
    if (!prediction || prediction.prediction_status !== 'forecast_available' || prediction.is_mock) warnings.append(element('li', `Current observations only. Forecast unavailable for the requested ${preferences.horizon_min}-minute window.`));
    card.append(warnings);
    const actions = element('div', undefined, 'card-actions');
    const view = element('button', 'View Route', 'view-route-button'); view.type = 'button'; view.onclick = () => viewRoute(route);
    const favourite = element('button', 'Favourite', 'favourite-button'); favourite.type = 'button';
    const completed = element('button', 'Completed Run', 'completed-run-button'); completed.type = 'button';
    actions.append(view, favourite, completed); card.append(actions, environmentalDetails(env, risk, rec, prediction));
    return card;
  }
  window.outdoorwiseResults = {card, formatTime};
})();

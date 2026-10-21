/* One catalog comparison flow using the historical forecast endpoint. */
(() => {
  const byId = id => document.getElementById(id);
  const form = byId('preferences');
  const cards = byId('cards');
  const delay = byId('start-delay');
  const duration = byId('duration');
  const access = byId('access');
  if (!form || !cards || !delay || !duration || !access) return;
  const launcher = byId('forecast-launcher');
  const forecastStatus = byId('forecast-status');

  access.placeholder = 'Clear for no limit';
  const accessHint = document.createElement('small');
  accessHint.id = 'forecast-access-hint';
  access.closest('label').append(accessHint);
  const timing = byId('time-selection-summary') || document.createElement('p');
  timing.id = 'time-selection-summary';
  timing.className = 'forecast-replay-label';
  timing.textContent = 'Historical demo · 15 Oct 2026, 19:15 SGT';
  delay.closest('label').after(timing);
  const toggle = document.createElement('button');
  toggle.type = 'button';
  toggle.className = 'secondary';
  toggle.id = 'toggle-all-routes';
  toggle.setAttribute('aria-controls', 'cards');
  toggle.hidden = true;
  cards.after(toggle);

  let current = null;
  let expanded = false;
  let activeContext = 'current';
  let version = 0;
  let controller;
  let active = false;
  let normalCards = null;

  function el(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  function modeLabels() {
    byId('mode').textContent = 'Catalog: historical demo';
    byId('context-indicator').textContent = 'Historical snapshot';
    byId('warnings').textContent = '';
    byId('warnings').hidden = true;
    byId('ingestion').textContent = '';
    byId('blocked-routes').replaceChildren();
    const refresh = byId('refresh');
    if (refresh) refresh.hidden = true;
  }

  function distanceHint() {
    const anywhere = byId('location-mode').value === 'anywhere';
    accessHint.textContent = anywhere
      ? 'Anywhere allows routes across Singapore. Select a starting point to apply a distance limit.'
      : access.value
        ? `Only routes within ${access.value} km straight-line distance of your starting point are eligible.`
        : 'No maximum distance: far routes may still rank highly. Enter a limit to exclude them.';
  }

  function input() {
    duration.setCustomValidity('');
    const start = Number(delay.value);
    const minutes = Number(duration.value);
    if (![0, 30, 60, 120].includes(start) || !Number.isInteger(minutes) || minutes <= 0) {
      throw Error('Enter a valid starting time and whole-number duration.');
    }
    if (start + minutes > 180) {
      duration.setCustomValidity('Start delay plus duration must not exceed 180 minutes.');
      throw Error('Start delay plus duration must not exceed 180 minutes.');
    }
    if (!form.reportValidity()) throw Error('Check the highlighted inputs.');
    return {...preferences(), start_delay_min: start};
  }

  function shortTime(value) {
    return new Date(value).toLocaleString('en-GB', {
      timeZone: 'Asia/Singapore', day: 'numeric', month: 'short',
      hour: '2-digit', minute: '2-digit', hour12: false,
    });
  }

  function invalidate() {
    if (!active) return;
    version += 1;
    controller?.abort();
    current = null;
    cards.replaceChildren(el('p', 'Preferences changed. Select Compare routes to update your results.', 'empty-results'));
    toggle.hidden = true;
    byId('results-summary').textContent = 'Results need updating';
    byId('status').textContent = 'Compare routes to apply your preferences.';
    modeLabels();
    distanceHint();
  }

  function updateVisible() {
    if (!current) return;
    const list = [...cards.querySelectorAll('.unified-route-card')];
    list.forEach((card, index) => { card.hidden = !expanded && index >= 3; });
    toggle.hidden = list.length <= 3;
    toggle.setAttribute('aria-expanded', String(expanded));
    toggle.textContent = expanded ? 'Show top 3' : `View all routes (${list.length})`;
    const count = expanded ? list.length : Math.min(3, list.length);
    byId('results-summary').textContent = `Showing ${count} of ${list.length} routes · ${current.personalized ? 'Personal difficulty match' : 'Matched to your preferences'}`;
    const routeById = new Map(current.routes.map(route => [route.route_id, route]));
    const visible = current.recommendations.slice(0, expanded ? list.length : 3);
    window.draw(visible.map(row => routeById.get(row.route_id)).filter(Boolean));
  }

  function applySharedVisibility(personalized) {
    activeContext = 'current';
    current = null;
    const list = [...cards.querySelectorAll('.card')];
    list.forEach((card, index) => { card.hidden = index >= 3; });
    toggle.hidden = list.length <= 3;
    expanded = false;
    toggle.setAttribute('aria-expanded', 'false');
    toggle.textContent = `View all routes (${list.length})`;
    const summary = byId('results-summary');
    if (summary && list.length) summary.textContent = `Showing ${Math.min(3, list.length)} of ${list.length} routes · ${personalized ? 'Personal difficulty match' : 'Matched to your preferences'}`;
  }

  function forecastDetails(row, result) {
    const details = el('details', undefined, 'unified-forecast-details');
    details.append(el('summary', 'Forecast & scoring details'));
    const labels = {wbgt: 'WBGT', pm25: 'PM2.5', rain_probability: 'Rain probability'};
    for (const [name, metric] of Object.entries(row.forecast_metrics || {})) {
      details.append(el('strong', labels[name] || name));
      for (const block of metric.blocks) {
        let value = 'Insufficient data';
        if (block.method === 'unsupported_horizon') value = 'Not supported';
        else if (typeof block.value === 'number' && Number.isFinite(block.value)) {
          value = name === 'rain_probability' ? `${(block.value*100).toFixed(2)}%` : `${block.value.toFixed(1)} ${name === 'wbgt' ? '°C' : 'µg/m³'}`;
        }
        details.append(el('p', `${shortTime(block.valid_from)} – ${shortTime(block.valid_to)}: ${value}`));
      }
      if (!metric.covers_entire_run) details.append(el('p', 'Forecast does not cover the entire run.'));
    }
    details.append(el('p', 'Rain risk uses a rainfall-amount persistence baseline, not the displayed rain probability. Wind scoring is neutral under the current configuration but still requires usable input.'));
    details.append(el('p', 'Component scores: ' + Object.entries(row.risk_components).map(([name, item]) => `${name}: ${item.score ?? 'N/A'}/100`).join(' · ')));
    details.append(el('p', `Historical observation reference rank: ${row.reference_rank}.`));
    details.append(el('p', 'Recommendation weights: ' + Object.entries(result.ranking_weights).map(([name, weight]) => `${name} ${(weight*100).toFixed(0)}%`).join(' · ')));
    result.warnings.forEach(text => details.append(el('p', text)));
    return details;
  }

  function render(result) {
    current = result;
    activeContext = 'historical';
    expanded = false;
    modeLabels();
    byId('context-indicator').textContent = `Historical snapshot · ${shortTime(result.as_of)}`;
    distanceHint();
    cards.replaceChildren();
    byId('ingestion').textContent = `Historical demo · Run: ${shortTime(result.run_start)} – ${shortTime(result.run_end)} SGT · Experimental estimates`;
    const routeById = new Map(result.routes.map(route => [route.route_id, route]));
    for (const row of result.recommendations) {
      const route = routeById.get(row.route_id);
      const card = el('article', undefined, 'card unified-route-card');
      card.dataset.personalizationRoute = row.route_id;
      card.append(el('small', `Your difficulty-match rank #${row.personalized_rank ?? row.pipeline_rank ?? row.final_rank}`, 'unified-rank'));
      card.append(el('small', `Shared rank #${row.pipeline_rank ?? row.reference_rank ?? row.final_rank}`, 'shared-rank-label'));
      card.append(el('h3', row.route_name));
      const lengthLine = el('p', undefined, 'unified-route-meta');
      lengthLine.append(
        el('strong', 'Route length: ', 'unified-info-label'),
        el('span', `${row.distance_km.toFixed(2)} km`)
      );
      card.append(lengthLine);
      const target = result.preferences.target_distance_km;
      const difference = row.distance_km - target;
      const absoluteDifference = Math.abs(difference);
      const percent = target > 0 ? absoluteDifference / target * 100 : 0;
      const match = absoluteDifference < 0.005
        ? `Matches your ${target} km target`
        : `${absoluteDifference.toFixed(2)} km ${difference > 0 ? 'longer' : 'shorter'} than your ${target} km target (${percent.toFixed(0)}% difference)`;
      card.append(el('p', match, 'unified-distance-match' + (row.distance_match_warning ? ' unified-distance-warning' : '')));
      const accessLine = el('p', undefined, 'unified-route-meta');
      accessLine.append(
        el('strong', 'Distance from your start: ', 'unified-info-label'),
        el('span', row.access_distance_km === null
          ? 'Not set'
          : `${row.access_distance_km.toFixed(2)} km · straight-line`)
      );
      card.append(accessLine);
      const scores = el('div', undefined, 'unified-score-grid');
      for (const [label, value] of [['Recommendation Score', row.recommendation_score], ['Environmental Risk', row.forecast_risk_score]]) {
        const box = el('div');
        box.append(el('small', label), el('strong', value === null ? 'Unavailable' : `${value.toFixed(2)} / 100`));
        scores.append(box);
      }
      card.append(scores);
      const components = el('div', undefined, 'unified-risk-components');
      for (const [key, label] of [['rainfall', 'Rain risk'], ['heat', 'Heat risk'], ['air_quality', 'Air-quality risk'], ['wind', 'Wind risk']]) {
        const component = row.risk_components?.[key];
        const cell = el('div');
        const score = component?.score;
        cell.append(el('small', label), el('strong', typeof score === 'number' && Number.isFinite(score) ? `${score.toFixed(1)} / 100` : 'Unavailable'));
        components.append(cell);
      }
      card.append(components);
      card.append(el('p', 'Historical forecast · Includes baseline assumptions', 'unified-muted'));
      card.append(el('p', `Generic difficulty: ${(row.generic_difficulty ?? row.difficulty).toFixed(1)} / 5`));
      if (result.personalized && typeof row.personalized_difficulty === 'number') {
        card.append(el('p', `Predicted difficulty for you: ${row.personalized_difficulty.toFixed(1)} / 5`));
        card.append(el('p', `Your target: ${row.target_difficulty} / 5 · Difficulty difference: ${row.difficulty_mismatch.toFixed(1)}.`));
      }
      if (row.distance_match_warning) card.append(el('p', 'Route length is unchanged; the route is not shortened or extended to match your target.', 'unified-muted'));
      if (row.forecast_risk_score === null) card.append(el('p', 'Incomplete environmental estimate; fallback ranking is used.'));
      const actions = el('div', undefined, 'card-actions');
      const view = el('button', 'View route');
      view.type = 'button';
      view.onclick = () => window.draw([route]);
      const favourite = el('button', 'Favourite', 'favourite-button');
      favourite.type = 'button';
      const completed = el('button', 'Completed Run', 'completed-run-button');
      completed.type = 'button';
      actions.append(view, favourite, completed);
      card.append(actions, forecastDetails(row, result));
      cards.append(card);
    }
    if (!result.recommendations.length) {
      const limit = result.preferences.max_access_distance_km;
      cards.append(el('p', result.preferences.location && limit !== null
        ? `No routes meet the ${limit} km straight-line access limit and policy constraints. Increase the limit or choose another starting point. The limit has not been relaxed.`
        : 'No routes meet your preferences and policy constraints.', 'empty-results'));
    }
    updateVisible();
    // Keep favourite/export/run-entry handlers; do not save replay difficulty as today's prediction.
    document.dispatchEvent(new CustomEvent('outdoorwise:routes-rendered', {detail: {
      routes: result.routes, recommendations: result.recommendations,
      authenticated: result.personalized, historical_replay: true,
    }}));
  }

  async function fetchRecommendations() {
    active = true;
    normalCards = normalCards || [...cards.childNodes].map(node => node.cloneNode(true));
    const body = input();
    const signature = JSON.stringify(body);
    const myVersion = ++version;
    controller?.abort();
    controller = new AbortController();
    const signal = controller.signal;
    if (forecastStatus) forecastStatus.textContent = 'Loading historical forecast comparison…';
    cards.replaceChildren(el('p', 'Calculating forecasts for all eligible routes…', 'empty-results'));
    toggle.hidden = true;
    modeLabels();
    try {
      const session = await fetch('/api/auth/me', {signal});
      if (session.status === 401) window.outdoorwiseSession = null;
      else if (session.ok) window.outdoorwiseSession = await session.json();
      else throw Error('Could not check your sign-in status.');
      window.personalizedRanking = null;
      const response = await fetch('/api/experimental/recommendations', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: signature, signal,
      });
      const data = await response.json();
      if (!response.ok) throw Error(typeof data.detail === 'string' ? data.detail : 'Check the selected inputs.');
      if (myVersion !== version || signature !== JSON.stringify(input())) throw Error('Preferences changed. Compare routes again.');
      if (forecastStatus) forecastStatus.textContent = 'Historical forecast comparison loaded.';
      return data;
    } catch (error) {
      if (myVersion === version) {
        cards.replaceChildren(...(normalCards || []).map(node => node.cloneNode(true)));
        if (forecastStatus) forecastStatus.textContent = error.name === 'AbortError' ? 'Preferences changed. Compare routes again.' : `Historical forecast unavailable: ${error.message}`;
        byId('results-summary').textContent = 'No updated results';
      }
      throw error;
    }
  }

  toggle.onclick = () => {
    if (activeContext === 'current') {
      const list = [...cards.querySelectorAll('.card')];
      const showAll = toggle.getAttribute('aria-expanded') !== 'true';
      list.forEach((card, index) => { card.hidden = !showAll && index >= 3; });
      toggle.setAttribute('aria-expanded', String(showAll));
      toggle.textContent = showAll ? 'Show top 3' : `View all routes (${list.length})`;
      const summary = byId('results-summary');
      if (summary) summary.textContent = `Showing ${showAll ? list.length : Math.min(3, list.length)} of ${list.length} routes · ${window.personalizedRanking ? 'Personal difficulty match' : 'Matched to your preferences'}`;
      return;
    }
    expanded = !expanded;
    updateVisible();
  };
  launcher?.addEventListener('click', async () => {
    active = true;
    launcher.disabled = true;
    try {
      const result = await fetchRecommendations();
      render(result);
    } catch (_) {
      // The normal recommendation cards are restored by fetchRecommendations.
    } finally {
      launcher.disabled = false;
    }
  });
  form.addEventListener('input', invalidate);
  form.addEventListener('change', invalidate);
  document.addEventListener('outdoorwise:location-changed', invalidate);
  window.outdoorwiseForecastUI = {fetchRecommendations, render};
  window.outdoorwiseRouteVisibility = {apply: applySharedVisibility};
  distanceHint();
})();

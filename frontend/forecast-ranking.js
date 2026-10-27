/* Replay response adapter and evidence only; shared cards/maps live in results/app. */
(() => {
  const el = (tag, text) => Object.assign(document.createElement(tag), {textContent: text});
  function adapt(result) {
    const origin = new Map([...(result.origin_risks || []), ...(result.departure_risks || [])].map(row => [row.route_id, row]));
    const risks = result.recommendations.map(row => row.departure_assessment?.risk || ({
      route_id: row.route_id, assessed_at: result.as_of, eligibility: row.eligibility,
      risk_score: row.forecast_risk_score, risk_level: 'unknown', risk_status: row.forecast_risk_score == null ? 'incomplete' : 'complete',
      risk_components: Object.fromEntries(Object.entries(row.risk_components).map(([name, item]) => [name, {...item, freshness: item.score == null ? 'missing' : 'fresh'}])),
      risk_data_quality: {confidence: 'very_low'}, risk_warnings: ['Experimental predictions; continuous run-window coverage is not established.'],
    }));
    for (const id of result.excluded_route_ids || []) {
      if (origin.has(id)) risks.push({...origin.get(id), risk_score: null, risk_status: 'incomplete', risk_components: {}, risk_data_quality: {confidence: 'very_low'}, risk_warnings: ['Excluded by observation policy at the historical reference time. Forecast eligibility is unverified.']});
    }
    return {...result, recommendations: result.recommendations.map(row => ({...row, final_rank: row.pipeline_rank ?? row.final_rank})), risks, environment: (result.environment || []).map(env => ({...env, historical_origin: true})), predictions: []};
  }
  function decorate(card, id, result) {
    const row = result.recommendations.find(item => item.route_id === id);
    if (row?.departure_assessment) {
      const departure = row.departure_assessment;
      card.querySelector('.risk-score .score-title').textContent = 'Departure-time risk';
      card.querySelector('.data-quality').textContent = `${departure.assessment_type === 'historical_observation' ? 'Historical observations' : 'Experimental native forecasts'} · ${departure.risk.risk_data_quality.confidence} confidence`;
      const basis = {historical_observation_risk: 'Historical observation-based risk', forecast_departure_risk: 'Valid forecast-based departure risk', unknown_risk_fallback: 'Existing unknown-risk fallback ordering'};
      const coverage = el('p', `Full-run coverage: ${row.full_run_assessment.status}. Full-run risk: ${row.full_run_assessment.risk_score ?? 'Unknown'}. Departure assessment does not cover the subsequent run.`);
      coverage.className = 'full-run-coverage';
      const ranking = el('p', `Recommendation basis: ${basis[row.recommendation_basis]}.`); ranking.className = 'recommendation-basis';
      card.insertBefore(coverage, card.querySelector('.card-actions'));
      card.insertBefore(ranking, card.querySelector('.card-actions'));
    }
    if (row) {
      card.append(el('p', `Generic difficulty at replay origin: ${row.generic_difficulty.toFixed(1)} / 5. Future effort is not predicted.`));
    }
    const forecast = result.prediction_details?.[id];
    if (!forecast) return;
    const estimates = el('ul', ''); estimates.className = 'environment-estimates';
    const names = {wbgt: 'WBGT', pm25: 'PM2.5', rain_probability: 'Rain probability'};
    for (const [name, metric] of Object.entries(forecast.metrics || {})) {
      const available = metric.blocks?.filter(block => block.value != null) || [];
      estimates.append(el('li', `${names[name] || name}: ${available.length ? available.map(block => `${block.value.toFixed(1)} ${metric.unit} at ${window.outdoorwiseResults.formatTime(block.target_timestamp)} (${block.method})`).join('; ') : 'Unavailable for this window'}. Continuous exposure coverage unverified.`));
    }
    card.insertBefore(estimates, card.querySelector('.card-actions'));
    const details = document.createElement('details'); details.className = 'prediction-details';
    details.append(el('summary', 'Prediction Details'));
    details.append(el('p', `Forecast origin: ${forecast.as_of}. Inputs come from the frozen snapshot; ground truth is evaluation only.`));
    if (row?.departure_assessment) {
      details.append(el('h4', 'Departure-time input evidence'));
      details.append(el('p', `Departure: ${row.departure_assessment.assessment_time}. Scope: departure only.`));
      for (const name of ['rainfall', 'wbgt', 'pm25', 'wind_speed']) {
        const input = row.departure_assessment.inputs[name];
        if (!input) continue;
        details.append(el('p', `${name}: ${input.value ?? 'Unavailable'} ${input.unit} · ${input.method} · ${input.location_id || 'No source'} · input observed ${input.observed_at || 'unavailable'} · forecast origin ${input.forecast_origin || 'not applicable'} · target ${input.target_timestamp || 'not applicable'}. ${input.reason}`));
      }
    }
    for (const [name, metric] of Object.entries(forecast.metrics || {})) {
      details.append(el('h4', `${name} · ${metric.unit}`));
      details.append(el('p', `${metric.coverage_status || 'Coverage unverified'} Full run covered: ${metric.covers_entire_run ? 'yes' : 'no'}. Model origin: ${metric.model_origin}`));
      for (const block of metric.blocks || []) {
        details.append(el('p', `${block.horizon_min} min · target ${block.target_timestamp} · predicted ${block.value ?? 'Unavailable'} ${metric.unit} · method: ${block.method}. ${block.target_semantics}`));
        details.append(el('p', `Ground truth: ${block.ground_truth?.value ?? 'Unavailable'} ${metric.unit} · signed error (prediction minus observation): ${block.forecast_error ?? 'Unavailable'}. ${block.evaluation_status}`));
        const provenance = el('pre', JSON.stringify({source: block.input_source, input_provenance: block.input_provenance, ground_truth: block.ground_truth, model_version: block.model_version, training_cutoff: block.training_cutoff}, null, 2));
        provenance.style.whiteSpace = 'pre-wrap'; provenance.style.overflowWrap = 'anywhere';
        const sourceDetails = document.createElement('details'); sourceDetails.append(el('summary', 'Input, target and model provenance'), provenance); details.append(sourceDetails);
      }
    }
    for (const [name, item] of Object.entries(forecast.forecast_risk?.components || {})) {
      details.append(el('p', `${name} origin input: ${item.input_value ?? 'Unavailable'} ${item.unit || ''} · ${item.methods?.join(', ') || 'Unavailable'} · coverage fraction ${item.coverage_fraction} · ${item.reason || item.assumption || ''} · input observed ${item.input_observed_at || 'unavailable'} · available ${item.input_available_at || 'unavailable'} · valid ${item.valid_from || 'unavailable'} – ${item.valid_to || 'unavailable'}`));
    }
    const evaluation = result.offline_evaluation;
    if (evaluation) {
      details.append(el('h4', 'Offline pooled evaluation — not this route’s forecast error'));
      for (const item of evaluation.pm25 || []) {
        details.append(el('p', `PM2.5 ${item.horizon_min} min · ${item.n} samples · frozen MAE/RMSE ${item.frozen.mae_ug_m3.toFixed(3)}/${item.frozen.rmse_ug_m3.toFixed(3)} µg/m³ · persistence MAE/RMSE ${item.persistence.mae_ug_m3.toFixed(3)}/${item.persistence.rmse_ug_m3.toFixed(3)} µg/m³.`));
      }
      details.append(el('p', 'The 60-minute frozen model underperformed persistence. Short, gapped holdouts do not validate continuous exposure forecasts.'));

    } else details.append(el('p', 'Saved evaluation evidence unavailable.'));
    card.append(details);
  }
  const toggle = el('button', 'View all routes'); toggle.type = 'button'; toggle.id = 'toggle-all-routes'; toggle.hidden = true;
  document.getElementById('cards')?.after(toggle);
  let all = false;
  function visibility() {
    const cards = [...document.querySelectorAll('#cards .route-summary')];
    cards.forEach((card, index) => card.hidden = !all && index >= 3);
    toggle.hidden = cards.length <= 3; toggle.textContent = all ? 'Show top 3' : `View all routes (${cards.length})`;
    toggle.setAttribute('aria-expanded', String(all));
  }
  toggle.onclick = () => { all = !all; visibility(); };
  window.outdoorwiseReplay = {adapt, decorate};
  window.outdoorwiseRouteVisibility = {apply() {all = false; visibility();}};
})();

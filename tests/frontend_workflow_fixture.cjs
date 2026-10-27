/* Synthetic response adapter for frontend tests, not prediction evidence. */
module.exports = function workflow(fixture, authenticated, mode = 'live', preferences = {}) {
  const data = structuredClone(authenticated ? fixture.personalized : fixture.generic);
  const run = authenticated ? data.run : data;
  run.preferences = {...run.preferences, ...preferences};
  const personal = authenticated ? data.recommendations : [];
  if (authenticated) {
    const order = new Map(personal.map((row, index) => [row.route_id, index]));
    run.recommendations.sort((a, b) => order.get(a.route_id) - order.get(b.route_id));
  }
  Object.assign(run, {app_mode: mode, personalized: authenticated, personalized_recommendations: personal});
  if (mode === 'historical') {
    Object.assign(run, {as_of: '2026-10-15T19:15:00+08:00', run_start: '2026-10-15T20:15:00+08:00', run_end: '2026-10-15T20:45:00+08:00',
      origin_risks: run.risks, excluded_route_ids: run.risks.filter(row => row.eligibility === 'blocked').map(row => row.route_id), prediction_details: {}});
    const delay = preferences.start_delay_min || 0;
    run.recommendation_basis = delay === 0 ? 'historical_observation_risk' : 'unknown_risk_fallback';
    run.recommendations.forEach(row => {
      Object.assign(row, {forecast_risk_score: null, risk_score: null, recommendation_score: null, eligibility: 'unknown', generic_difficulty: 3, risk_components: {heat: {score: null}}});
      const origin = run.risks.find(item => item.route_id === row.route_id);
      const risk = delay === 0 ? origin : {...origin, risk_score: null, risk_status: 'incomplete', eligibility: 'unknown', risk_components: {heat: {score: null}}};
      Object.assign(row, {risk_score: risk.risk_score, eligibility: risk.eligibility,
        recommendation_score: delay === 0 ? 80 : null,
        departure_assessment: {assessment_time: delay === 0 ? run.as_of : run.run_start,
          assessment_type: delay === 0 ? 'historical_observation' : 'forecast_based', risk, inputs: {}},
        full_run_assessment: {status: delay === 0 ? 'partial' : 'unavailable', risk_score: null},
        recommendation_basis: run.recommendation_basis});
      run.prediction_details[row.route_id] = {as_of: run.as_of, metrics: {pm25: {unit: 'ug/m3', model_origin: '2026-10-15T19:00:00+08:00', covers_entire_run: false, blocks: [{horizon_min: 120, target_timestamp: '2026-10-15T21:00:00+08:00', method: 'persistence_fallback', value: 10, ground_truth: null, forecast_error: null, evaluation_status: 'Exact target ground truth unavailable', target_semantics: 'Direct point target'}]}}};
    });
  }
  return run;
};

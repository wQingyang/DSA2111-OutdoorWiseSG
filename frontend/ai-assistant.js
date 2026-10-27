/* Parsing supplies preferences only; users explicitly select/confirm geometry origins. */
(() => {
  const byId = id => document.getElementById(id);
  const input = byId('ai-route-input');
  const button = byId('ai-parse-button');
  const status = byId('ai-route-status');
  const confirm = byId('confirm-route-start');
  if (!input || !button || !status || !confirm) return;
  let parsing = false;
  let location = null;
  const locationStatus = byId('dynamic-location-status');
  function describe() {
    locationStatus.textContent = location
      ? `Requested location: ${location}. Select its point on the map or enter coordinates, then confirm them.`
      : 'Select a point on the map or review and confirm the coordinates.';
  }
  window.outdoorwiseDynamicStart = {ready: () => !parsing && confirm.checked};
  for (const id of ['route-lat', 'route-lon']) {
    byId(id).addEventListener('input', () => { confirm.checked = false; describe(); });
  }
  document.addEventListener('outdoorwise:dynamic-start-selected', () => {
    confirm.checked = false;
    describe();
  });
  button.addEventListener('click', async () => {
    const text = input.value.trim();
    if (!text) { status.textContent = 'Please describe your route.'; return; }
    parsing = true;
    location = null;
    describe();
    confirm.checked = false;
    button.disabled = true;
    status.textContent = 'Parsing route preferences…';
    try {
      const response = await fetch('/api/llm/parse', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({text}), signal: AbortSignal.timeout(65000),
      });
      const data = await response.json();
      if (!response.ok) throw Error(typeof data.detail === 'string' ? data.detail : 'Parser request failed.');
      byId('route-distance').value = data.target_distance_km;
      byId('dynamic-target-difficulty').value = String(data.target_difficulty);
      byId('route-green').checked = data.preferences.prefer_green;
      byId('route-quiet').checked = data.preferences.prefer_quiet;
      byId('route-steps').checked = data.preferences.avoid_steps;
      location = data.location;
      describe();
      status.textContent = 'Preferences applied. Confirm your starting point, then select Generate three loops.';
    } catch (error) {
      status.textContent = `Parsing unavailable: ${error.message} You can still use the manual form.`;
    } finally {
      parsing = false;
      button.disabled = false;
    }
  });
})();

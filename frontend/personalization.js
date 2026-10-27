(() => {
  let userId = null;
  let pendingRun = null;
  let snapshot = { runs: [], feedback: [], favourites: [] };
  const $ = id => document.getElementById(id);

  async function request(path, options = {}) {
    const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options });
    const data = response.status === 204 ? null : await response.json();
    if (!response.ok) { const error = Error('Could not update your running history. Please try again.'); error.status = response.status; throw error; }
    return data;
  }
  function base() { return `/api/users/${encodeURIComponent(userId)}`; }
  function setMessage(text, kind = '') { const el = $('personalization-status'); el.textContent = text; el.className = kind; }
  function favouriteIds() { return new Set(snapshot.favourites.map(item => item.route_id)); }
  function routeName(id) {
    const route = (window.outdoorwiseRoutes || []).find(item => item.route_id === id);
    return route ? route.name : 'Saved route (not in current catalog)';
  }
  function formatDate(value) { return window.outdoorwiseResults.formatTime(value); }

  async function load() {
    setMessage('Loading your runs and favourites…');
    try {
      const me = await request('/api/auth/me'); userId = me.user_id;
      const [runs, feedback, favourites] = await Promise.all([
        request(`${base()}/runs`), request(`${base()}/feedback`), request(`${base()}/favourites`)
      ]);
      snapshot = { runs, feedback, favourites };
      renderHistory();
      updateCards();
      setMessage(`Loaded ${runs.length} run${runs.length === 1 ? '' : 's'}.`, 'success');
    } catch (error) {
      if (error.status === 401) { userId = null; snapshot = {runs: [], feedback: [], favourites: []}; renderHistory(); updateCards(); setMessage('Sign in to save favourite routes and completed runs.'); return; }
      setMessage(`Personalization unavailable: ${error.message}`, 'error');
      renderHistory();
    }
  }
  function renderHistory() {
    const list = $('my-runs'); list.replaceChildren();
    const feedbackByRun = new Map(snapshot.feedback.map(item => [item.completed_run_id, item]));
    if (!snapshot.runs.length) { list.textContent = 'No completed runs yet.'; }
    snapshot.runs.slice().reverse().slice(0, 8).forEach(run => {
      const item = document.createElement('li'); const feedback = feedbackByRun.get(run.completed_run_id);
      item.textContent = `${routeName(run.route_id)} · ${run.actual_distance_km} km · ${run.actual_duration_min} min` +
        (run.average_pace_min_per_km ? ` · pace ${Number(run.average_pace_min_per_km).toFixed(2)} min/km` : '') +
        (feedback ? ` · difficulty ${feedback.difficulty}/5` : '') + ` · ${formatDate(run.completed_at)}`;
      list.append(item);
    });
    const favourites = $('my-favourites'); favourites.replaceChildren();
    if (!snapshot.favourites.length) favourites.textContent = 'No favourite routes yet.';
    snapshot.favourites.forEach(item => { const li = document.createElement('li'); li.textContent = routeName(item.route_id); favourites.append(li); });
  }
  function updateCards() {
    const ids = favouriteIds();
    document.querySelectorAll('[data-personalization-route]').forEach(card => {
      const id = card.dataset.personalizationRoute; const button = card.querySelector('.favourite-button');
      if (button) { button.textContent = ids.has(id) ? '♥ Favourited' : '♡ Favourite'; button.dataset.favourited = ids.has(id); }
    });
  }
  async function toggleFavourite(routeId, button) {
    if (!userId) { window.location.href = '/login.html'; return; }
    button.disabled = true;
    try {
      if (favouriteIds().has(routeId)) await request(`${base()}/favourites/${encodeURIComponent(routeId)}`, { method: 'DELETE' });
      else await request(`${base()}/favourites/${encodeURIComponent(routeId)}`, { method: 'PUT' });
      snapshot.favourites = await request(`${base()}/favourites`); renderHistory(); updateCards();
      setMessage('Favourite routes updated.', 'success');
    } catch (error) { setMessage(error.message, 'error'); }
    finally { button.disabled = false; }
  }
  function openRunForm(route) {
    if (!userId) { window.location.href = '/login.html'; return; }
    pendingRun = null;
    $('run-form').querySelector('button[type=submit]').textContent = 'Save';
    $('run-distance').disabled = false; $('run-duration').disabled = false;
    $('run-modal').hidden = false; $('run-route-label').textContent = route.name;
    $('run-route-id').value = route.route_id; $('run-distance').value = route.distance_km || '';
    $('run-duration').value = ''; $('run-difficulty').value = ''; $('run-tags').value = ''; $('run-comment').value = '';
    $('run-error').textContent = '';
  }
  async function saveRun(event) {
    event.preventDefault(); const form = event.target; const routeId = $('run-route-id').value;
    const submit = form.querySelector('button[type=submit]'); if (submit.disabled) return; submit.disabled = true;
    const body = { route_id: routeId, completed_at: new Date().toISOString(), actual_distance_km: Number($('run-distance').value), actual_duration_min: Number($('run-duration').value) };
    const generic = window.outdoorwiseDifficulty?.[routeId]; if (generic) { body.predicted_difficulty = generic.predicted_difficulty; if (generic.personalized_predicted_difficulty != null) body.personalized_predicted_difficulty = generic.personalized_predicted_difficulty; }
    const difficulty = $('run-difficulty').value; const tags = $('run-tags').value.split(',').map(x => x.trim()).filter(Boolean); const comment = $('run-comment').value.trim();
    try {
      const run = pendingRun || await request(`${base()}/runs`, { method: 'POST', body: JSON.stringify(body) });
      pendingRun = run;
      if (difficulty) {
        const feedback = { difficulty: Number(difficulty), tags }; if (comment) feedback.comment = comment;
        try { await request(`${base()}/runs/${run.completed_run_id}/feedback`, { method: 'POST', body: JSON.stringify(feedback) }); }
        catch (error) { $('run-error').textContent = 'Run saved. Feedback could not be saved; check your rating and tags, then retry feedback.'; submit.textContent = 'Retry feedback'; $('run-distance').disabled = true; $('run-duration').disabled = true; await load(); return; }
      }
      pendingRun = null; $('run-modal').hidden = true; setMessage('Completed run saved.', 'success'); await load();
    } catch (error) { $('run-error').textContent = error.message; }
    finally { form.querySelector('button[type=submit]').disabled = false; }
  }
  function bindCards(event) {
    window.outdoorwiseRoutes = event.detail.routes || [];
    renderHistory();
    document.querySelectorAll('[data-personalization-route]').forEach(card => {
      const routeId = card.dataset.personalizationRoute; const route = window.outdoorwiseRoutes.find(item => item.route_id === routeId); if (!route) return;
      card.querySelector('.favourite-button')?.addEventListener('click', e => toggleFavourite(routeId, e.currentTarget));
      if (!card.querySelector('.completed-run-button')?.disabled) card.querySelector('.completed-run-button')?.addEventListener('click', () => openRunForm(route));
    }); updateCards();
  }
  document.addEventListener('outdoorwise:routes-rendered', bindCards);
  $('run-form').addEventListener('submit', saveRun); $('run-cancel').addEventListener('click', () => { $('run-modal').hidden = true; });
  $('run-modal').addEventListener('click', event => { if (event.target === $('run-modal')) $('run-modal').hidden = true; });
  window.addEventListener('load', load);
})();

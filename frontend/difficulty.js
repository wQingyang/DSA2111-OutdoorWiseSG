(() => {
  let generation = 0;
  window.outdoorwiseDifficulty = {};
  document.addEventListener('outdoorwise:routes-rendered', async event => {
    const current = ++generation;
    window.outdoorwiseDifficulty = {};
    await Promise.all((event.detail.routes || []).map(async route => {
      const card = [...document.querySelectorAll('[data-personalization-route]')].find(c => c.dataset.personalizationRoute === route.route_id);
      if (!card) return;
      try {
        const personal = event.detail.personalizedRanking?.[route.route_id];
        let prediction;
        if (personal && typeof personal.generic_difficulty === 'number') {
          prediction = {predicted_difficulty: personal.generic_difficulty, personalized_predicted_difficulty: personal.personalized_difficulty};
        } else {
          const response = await fetch(`/api/routes/${encodeURIComponent(route.route_id)}/difficulty`);
          if (!response.ok) return;
          prediction = await response.json();
        }
        if (current !== generation || !card.isConnected) return;
        window.outdoorwiseDifficulty[route.route_id] = prediction;
        const box = document.createElement('p'); box.className = 'difficulty-summary';
        box.textContent = typeof prediction.personalized_predicted_difficulty === 'number'
          ? `Predicted difficulty for you: ${prediction.personalized_predicted_difficulty.toFixed(1)} / 5`
          : `Generic difficulty: ${prediction.predicted_difficulty.toFixed(1)} / 5${prediction.difficulty_label ? ' · ' + prediction.difficulty_label : ''}`;
        card.insertBefore(box, card.querySelector('.card-actions'));
      } catch (_) { /* A missing effort estimate does not fabricate a value or hide the route. */ }
    }));
  });
})();

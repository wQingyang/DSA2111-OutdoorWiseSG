(() => {
  document.addEventListener('outdoorwise:routes-rendered', () => {
    document.querySelectorAll('[data-personalization-route]').forEach((card) => {
      if (card.querySelector('.export-route-button')) return;
      const link = document.createElement('a');
      link.className = 'export-route-button';
      link.textContent = 'Download GPX';
      link.href = `/api/routes/${encodeURIComponent(card.dataset.personalizationRoute)}/export.gpx`;
      link.download = '';
      card.querySelector('.card-actions').append(link);
      link.title = 'Download the existing route geometry for a compatible running app.';
    });
  });
})();

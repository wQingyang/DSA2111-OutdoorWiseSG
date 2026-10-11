(() => {
  document.addEventListener('outdoorwise:routes-rendered', () => {
    document.querySelectorAll('[data-personalization-route]').forEach((card) => {
      if (card.querySelector('.export-route-button')) return;
      const link = document.createElement('a');
      link.className = 'export-route-button';
      link.textContent = 'Download GPX';
      link.href = `/api/routes/${encodeURIComponent(card.dataset.personalizationRoute)}/export.gpx`;
      link.download = '';
      card.append(link);
      const help = document.createElement('small');
      help.className = 'export-route-help';
      help.textContent = 'Download this route for use in compatible running or navigation apps.';
      card.append(help);
    });
  });
})();

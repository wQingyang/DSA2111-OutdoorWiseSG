/* One starting point in page memory; the backend owns all access-distance maths. */
(() => {
  const $ = id => document.getElementById(id);
  const presets = {nus: {lon: 103.776, lat: 1.296}, bay: {lon: 103.855, lat: 1.287}, north: {lon: 103.786, lat: 1.438}};
  let point = null, map = null, marker = null, pending = false, requestToken = 0, revision = 0;
  const mode = () => $('location-mode').value;
  const valid = p => p && Number.isFinite(p.lon) && Number.isFinite(p.lat) && Math.abs(p.lon) <= 180 && Math.abs(p.lat) <= 90;
  const copy = () => point ? {...point} : null;
  function message(text) { $('location-status').textContent = text; }
  function changed() {
    revision++;
    document.dispatchEvent(new CustomEvent('outdoorwise:location-changed', {detail: {location: copy()}}));
  }
  function syncMarker(center = false) {
    if (!map) return;
    if (!point) {if (marker) {map.removeLayer(marker); marker = null;} return;}
    if (!marker) {
      marker = L.marker([point.lat, point.lon], {title: 'Starting point', draggable: true, autoPan: true,
        bubblingMouseEvents: false, icon: L.divIcon({className: 'starting-location-marker', html: '<span>Start</span>', iconSize: [48, 32], iconAnchor: [24, 32]})}).addTo(map);
      marker.on('dragend', event => {
        const latlng = event.target.getLatLng();
        setPoint({lon: latlng.lng, lat: latlng.lat}, 'Starting point moved. Compare Routes to update results.');
      });
    } else marker.setLatLng([point.lat, point.lon]);
    if (mode() === 'map') marker.dragging.enable(); else marker.dragging.disable();
    if (center) map.panTo([point.lat, point.lon]);
  }
  function sync() {
    $('preset-location-controls').hidden = mode() !== 'preset';
    $('current-location-controls').hidden = mode() !== 'current';
    $('map-selection-hint').hidden = mode() !== 'map';
    $('selected-coordinates').textContent = point ? `Latitude ${point.lat.toFixed(6)} · Longitude ${point.lon.toFixed(6)}` : 'No starting point selected.';
    $('access').disabled = mode() === 'anywhere';
    $('access-location-note').textContent = mode() === 'anywhere' ? 'No access limit applies in Anywhere mode.' : 'Straight-line distance to the route start, not walking or driving distance.';
    $('get-current-location').disabled = pending;
    $('get-current-location').textContent = pending ? 'Finding your location…' : 'Allow location access';
    $('map').classList.toggle('selecting-start', mode() === 'map');
    syncMarker();
  }
  function setPoint(value, text, center = false) {
    if (!valid(value)) {syncMarker(); message('This point could not be used. Choose another point or a preset.'); return;}
    point = {lon: value.lon, lat: value.lat};
    sync(); syncMarker(center); message(text); changed();
  }
  function chooseMode() {
    requestToken++; pending = false;
    if (mode() === 'anywhere') {
      point = null;
      message('Routes anywhere in the Singapore catalog. No starting-point or access-distance constraint.');
    } else if (mode() === 'preset') {
      point = {...presets[$('location-preset').value]};
      message('Preset selected. Compare Routes to update results.');
    } else if (mode() === 'current') {
      point = null;
      message(navigator.geolocation && window.isSecureContext !== false
        ? 'Use the button to request your location once. Your browser will ask for permission.'
        : 'Current location is unavailable in this browser or connection. Choose a map point or a preset.');
    } else message(point ? 'Starting point retained. Click an empty map area or drag Start to replace it.' : 'Click or tap an empty map area to choose your starting point.');
    sync(); syncMarker(mode() === 'preset'); changed();
  }
  function requestCurrentLocation() {
    if (mode() !== 'current' || pending) return;
    if (!navigator.geolocation || window.isSecureContext === false) {
      message('Current location needs a supported browser and HTTPS (or localhost). Choose a map point or a preset.'); return;
    }
    const token = ++requestToken; pending = true; sync();
    message('Requesting a single location fix. You can switch to map selection at any time.');
    const success = position => {
      if (token !== requestToken || mode() !== 'current') return;
      pending = false;
      const accuracy = position.coords.accuracy;
      setPoint({lon: position.coords.longitude, lat: position.coords.latitude},
        `Current location selected${Number.isFinite(accuracy) ? ` (device accuracy about ${Math.round(accuracy)} m)` : ''}. Compare Routes to update results.`, true);
      sync();
    };
    const failure = error => {
      if (token !== requestToken || mode() !== 'current') return;
      pending = false; point = null; sync(); changed();
      const reasons = {1: 'Location permission was denied.', 2: 'Your current location could not be determined.', 3: 'The location request timed out.'};
      message(`${reasons[error.code] || 'Current location could not be used.'} Retry, choose a point on the map, or use a preset.`);
    };
    try {navigator.geolocation.getCurrentPosition(success, failure, {enableHighAccuracy: false, timeout: 10000, maximumAge: 0});}
    catch (_) {failure({code: 2});}
  }
  function attachMap(existingMap) {
    if (map === existingMap) return;
    map = existingMap;
    $('location-mode').querySelector('[value="map"]').disabled = false;
    $('choose-location-on-map').disabled = false;
    map.on('click', event => {
      if (mode() !== 'map') return;
      // Route paths/controls are not empty-map selections, even if a plugin bubbles a click.
      if (event.originalEvent?.target?.closest?.('.leaflet-interactive, .leaflet-control, .starting-location-marker')) return;
      setPoint({lon: event.latlng.lng, lat: event.latlng.lat}, 'Map starting point selected. Drag Start or click another empty area to replace it.');
    });
    syncMarker();
  }
  function mapUnavailable() {
    $('location-mode').querySelector('[value="map"]').disabled = true;
    $('choose-location-on-map').disabled = true;
    if (mode() === 'map') message('The interactive map is unavailable. Choose a preset or current location instead.');
  }
  function locationForRequest() {
    if (mode() === 'anywhere') return null;
    if (pending || !point) throw Error('Choose a starting point first, or select Anywhere in Singapore. Your access limit has not been relaxed.');
    return copy();
  }
  $('location-mode').addEventListener('change', chooseMode);
  $('location-preset').addEventListener('change', () => {
    if (mode() === 'preset') setPoint(presets[$('location-preset').value], 'Preset selected. Compare Routes to update results.', true);
  });
  $('get-current-location').addEventListener('click', requestCurrentLocation);
  $('choose-location-on-map').addEventListener('click', () => {
    $('location-mode').value = 'map'; chooseMode(); $('map').scrollIntoView({behavior: 'smooth', block: 'center'});
  });
  $('clear-location').addEventListener('click', () => {$('location-mode').value = 'anywhere'; chooseMode();});
  window.outdoorwiseLocation = {attachMap, mapUnavailable, locationForRequest, selectedPoint: copy, revision: () => revision};
  sync(); message('Routes anywhere in the Singapore catalog. Choose a starting point to compare access distances.');
})();

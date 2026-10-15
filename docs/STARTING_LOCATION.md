# Flexible starting location — Sprint 2.1

The dashboard keeps its existing Plan Your Run form and single Leaflet map. Choose one of four starting-location modes:

- **Use my current location:** press Allow location access to request one browser location fix. The browser controls permission; no continuous tracking occurs. Permission denial, unavailable position, unsupported/insecure browsers and the ten-second timeout leave the location unset and offer manual selection or presets.
- **Choose a point on the map:** click/tap an empty map area. A blue Start marker shows the selected point; drag it or click another empty area to replace it. Route paths and map controls do not change the starting point. Route selection and geometry rendering remain available.
- **Choose a preset:** NUS (1.296, 103.776), Marina Bay (1.287, 103.855), Woodlands (1.438, 103.786). These are approximate reference coordinates, not verified entrances.
- **Anywhere in Singapore:** no starting-location or maximum-access constraint. Clear starting location returns to this mode and removes the marker.

Coordinates appear in the form to six decimal places; full selected coordinates are sent. Compare Routes applies changes. Observation refresh retains the chosen point and access limit and requests personalized recommendations for authenticated users. Pending recommendations for an earlier point or access limit are rejected rather than displayed as results for the new choice. This state lives only in page memory: full page reload/navigation resets it. The default is Anywhere.

## Existing API and distance semantics

Both POST /api/recommendations and POST /api/me/recommendations receive the existing preferences fields:

```json
{"location": {"lon": 103.776, "lat": 1.296}, "max_access_distance_km": 5}
```

Anywhere sends both fields as null. A selected point with an empty access field sends a location and a null maximum. Invalid/nonpositive limits are rejected in the form; selecting map/current mode without a point never silently removes a constraint. No endpoint or response contract was changed.

The existing backend calculates geographic straight-line distance from the selected point to each catalog route start using its shared distance helper. The frontend displays returned access_distance_km; it does not duplicate that calculation. The limit filters candidates before ranking, for anonymous and authenticated requests. Empty results clearly state that the limit was not relaxed. Access distances are neither walking/driving distances nor travel times. Route geometry is unchanged.

The catalog is Singapore-based; selected coordinates use existing global longitude/latitude validation, without a Singapore polygon/geofence. Users can choose an outlying point, which may leave no routes within their access limit. GPS accuracy is device-dependent and displayed when supplied. Browser geolocation requires HTTPS or a supported localhost context. If Leaflet cannot load, map selection is disabled while presets/current-location/Anywhere remain available.

## Data handling and verification

A location request occurs only after an explicit button press, using getCurrentPosition rather than watchPosition. Late callbacks after a mode change are ignored. No location is added to browser storage. Coordinates are sent to the existing recommendation API and are included in its existing persisted Run preferences/audit records; this feature does not introduce a new storage mechanism.

Implementation: frontend/location.js owns selection and the single marker; frontend/app.js attaches it to the existing map, submits preferences, protects against stale responses and handles empty results; frontend/results.js displays the backend access distance.

Verified on 2026-10-15: 109 Python tests, 21 frontend DOM tests, isolated real HTTP smoke with all 12 catalog routes, and Chrome desktop/mobile browser checks passed. API tests exercise both endpoints with actual catalog geometry, strict filtering and deterministic repeated requests. DOM tests cover GPS errors, unsupported browsers, stale callbacks, map/marker events, presets, clear, personalized refresh persistence and request races. Chrome checks use synthetic responses/offline tiles, native geolocation permission overrides and mobile touch emulation; they do not establish real-device GPS accuracy, live tile availability or field usability.

Screenshots (synthetic fixtures): [desktop selection](screenshots/sprint2-1/location-desktop.png), [mobile controls](screenshots/sprint2-1/location-mobile.png), [mobile map marker](screenshots/sprint2-1/location-map-mobile.png). See [frontend verification](FRONTEND_VERIFICATION.md) for reproducible commands.

// OpenFreeMap vector basemap with a raster fallback chain and attribution.
// Adapted from pricephillips/data-center-map tests/ui/basemap.spec.js at
// 0938c30 (its spec 009, US2; passoff B6/B7).
'use strict';
const { test, expect } = require('./fixtures');

// A self-contained style: one background layer, no sources, so the vector
// path is exercised end to end with no network.
const STYLE = JSON.stringify({
  version: 8, name: 'test', sources: {},
  layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#f2efe9' } }]
});

for (const file of ['renewable-opposition-map.html', 'map-audit.html']) {
  test(`${file}: vector basemap renders when the OpenFreeMap style is reachable`, async ({ page }) => {
    await page.route('https://tiles.openfreemap.org/**', route =>
      route.fulfill({ status: 200, contentType: 'application/json', body: STYLE }));
    await page.goto('/' + file);
    const map = page.locator('#leafletMap');
    await expect(map).toHaveAttribute('data-basemap', 'openfreemap_light');
    await expect(page.locator('#leafletMap canvas.maplibregl-canvas')).toHaveCount(1, { timeout: 20000 });
    await page.waitForTimeout(500);
    await expect(map).toHaveAttribute('data-basemap', 'openfreemap_light');
    await expect(page.locator('.leaflet-control-attribution')).toContainText('OpenFreeMap');
    await expect(page.locator('.leaflet-control-attribution')).toContainText('OpenStreetMap');
    expect(page.consoleErrors).toEqual([]);
  });

  test(`${file}: blocked style host falls back to a raster provider with attribution`, async ({ page }) => {
    // The fixture aborts every basemap host, so the chain runs to its end.
    await page.goto('/' + file);
    const map = page.locator('#leafletMap');
    await expect(map).toHaveAttribute('data-basemap', /^(esri_light|osm)$/, { timeout: 20000 });
    await expect(page.locator('.leaflet-control-attribution')).toContainText(/Esri|OpenStreetMap/);
    // The chain asked OpenFreeMap first; the old hard-coded {s}.tile.openstreetmap.org
    // subdomains are gone.
    expect(page.requested.some(u => u.startsWith('https://tiles.openfreemap.org/styles/positron'))).toBe(true);
    expect(page.requested.filter(u => /^https:\/\/[abc]\.tile\.openstreetmap\.org\//.test(u))).toEqual([]);
  });
}

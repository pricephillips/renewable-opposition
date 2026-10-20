// OpenFreeMap vector basemap with a raster fallback chain and attribution.
// Adapted from pricephillips/data-center-map tests/ui/basemap.spec.js at
// 0938c30 (its spec 009, US2; passoff B6/B7).
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { test, expect, cdnToLocal, ROOT } = require('./fixtures');

// A self-contained style: one background layer, no sources, so the vector
// path is exercised end to end with no network.
const STYLE = JSON.stringify({
  version: 8, name: 'test', sources: {},
  layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#f2efe9' } }]
});

// map-audit.html is the one page left on Leaflet and basemap.js
// (renewable-opposition-map.html was retired in phase 4).
for (const file of ['map-audit.html']) {
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

// Every CDN file basemap.js loads carries the sha384 of the copy the tests
// serve, and the page pins the MapLibre module (loaded with import(), which
// takes no integrity attribute) in its import map.
test('basemap.js and map-audit.html pin every CDN file by integrity', () => {
  const src = fs.readFileSync(path.join(ROOT, 'basemap.js'), 'utf8');
  const { SRI } = require(path.join(ROOT, 'basemap.js'));
  const sri = f => 'sha384-' + crypto.createHash('sha384').update(fs.readFileSync(f)).digest('base64');
  const urls = [...new Set(src.match(/'https:\/\/(?:unpkg\.com|cdn\.jsdelivr\.net\/npm)\/[^']+'/g).map(u => u.slice(1, -1)))];
  expect(Object.keys(SRI).sort()).toEqual(urls.sort());
  for (const u of urls) expect(SRI[u], u).toBe(sri(cdnToLocal(u)));
  const html = fs.readFileSync(path.join(ROOT, 'map-audit.html'), 'utf8');
  const map = JSON.parse(/<script type="importmap">([\s\S]*?)<\/script>/.exec(html)[1]);
  const modules = urls.filter(u => u.endsWith('.mjs'));
  expect(Object.keys(map.integrity).sort()).toEqual(modules.sort());
  for (const u of modules) expect(map.integrity[u], u).toBe(SRI[u]);
});

// A library tag from a CDN without integrity would run whatever the CDN sends.
test('every CDN script and stylesheet tag on a page carries integrity', () => {
  for (const file of fs.readdirSync(ROOT).filter(f => f.endsWith('.html'))) {
    const html = fs.readFileSync(path.join(ROOT, file), 'utf8');
    const tags = html.match(/<(?:script|link)\b[^>]*(?:src|href)="https:\/\/(?:unpkg\.com|cdn\.jsdelivr\.net)\/[^"]*"[^>]*>/g) || [];
    for (const tag of tags) expect(tag, file).toMatch(/\bintegrity="sha(?:256|384|512)-/);
  }
});

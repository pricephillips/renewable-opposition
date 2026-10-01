// The county choropleth joins on county_fips and paints every county the
// filtered data names. Adapted from pricephillips/data-center-map
// tests/ui/choropleth.spec.js at 0938c30 (its spec 009, US1; passoff B7).
'use strict';
const { test, expect, processed } = require('./fixtures');

const FILE = 'renewable-opposition-map.html';
const restrictions = processed('restrictions.json');
const projects = processed('contested_projects.json');
const cases = processed('cases.json');

// Distinct FIPS the page should paint for a state filter ('' = all). A case
// sits in the county of the project it concerns.
function expectedFips(state, scope) {
  const bySource = new Map(projects.map(p => [p.source_record_id, p]));
  const out = new Set();
  const add = (r, fips) => { if (fips && (!state || r.state === state)) out.add(fips); };
  if (!scope) {
    projects.forEach(r => add(r, r.county_fips));
    cases.forEach(c => add(c, (bySource.get(c.source_record_id) || {}).county_fips));
  }
  restrictions.forEach(r => { if (!scope || r.scope === scope) add(r, r.county_fips); });
  return out.size;
}

async function painted(page) {
  const el = page.locator('#leafletMap');
  return [Number(await el.getAttribute('data-county-fips')), Number(await el.getAttribute('data-painted-counties'))];
}

test('every county the data names paints, filtered or not', async ({ page }) => {
  await page.goto('/' + FILE);
  const map = page.locator('#leafletMap');
  await expect(map).toHaveAttribute('data-painted-counties', /^[1-9]\d*$/, { timeout: 30000 });
  const all = expectedFips('', '');
  expect(all).toBeGreaterThan(0);
  await expect.poll(() => painted(page)).toEqual([all, all]);
  for (const state of ['IA', 'MN', 'CT']) {
    await page.selectOption('#stateFilter', state);
    const n = expectedFips(state, '');
    await expect.poll(() => painted(page)).toEqual([n, n]);
  }
  await page.selectOption('#stateFilter', '');
  await page.selectOption('#scopeFilter', 'multi_sector_data_centers');
  const multi = expectedFips('', 'multi_sector_data_centers');
  await expect.poll(() => painted(page)).toEqual([multi, multi]);
  expect(page.consoleErrors).toEqual([]);
});

test('counties draw from the local TopoJSON, never the plotly GeoJSON', async ({ page }) => {
  await page.goto('/' + FILE);
  // Let the opening fit finish; a filter applied mid-animation is a different test.
  await expect(page.locator('#resultBadge')).toContainText(/[1-9]/, { timeout: 30000 });
  await page.waitForLoadState('networkidle');
  await page.selectOption('#stateFilter', 'MN');
  // Minnesota has 87 counties; the layer draws the focused state's polygons.
  await expect.poll(() => page.locator('.leaflet-county-pane path').count(), { timeout: 30000 }).toBe(87);
  expect(page.requested.some(u => u.endsWith('/data/geo/counties_2024.topojson'))).toBe(true);
  expect(page.requested.filter(u => /geojson-counties-fips/.test(u))).toEqual([]);
});

test('geometry fetch failure says so and still draws points', async ({ page }) => {
  await page.route('**/counties_2024.topojson', route => route.fulfill({ status: 404, body: '' }));
  await page.goto('/' + FILE);
  await expect(page.locator('#mapStatus')).toContainText('County boundaries could not be loaded', { timeout: 30000 });
  await expect(page.locator('#leafletMap')).toHaveAttribute('data-painted-counties', '0');
  await expect.poll(() => page.locator('.leaflet-marker-icon').count()).toBeGreaterThan(0);
});

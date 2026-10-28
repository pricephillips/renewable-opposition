// The national dashboard (national-dashboard.html, docs/national_database_design.md
// phase 3): every figure it shows must equal the published files it reads,
// an unexamined county must never be drawn as zero, and the page must load
// clean and pass axe, offline, at desktop and phone widths.
'use strict';
const fs = require('fs');
const path = require('path');
const { test, expect, processed, ROOT } = require('./fixtures');
const AxeBuilder = require('@axe-core/playwright').default;

const FILE = '/national-dashboard.html';
const M = processed('headline_metrics.json');
const db = name => JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'db', name), 'utf8'));
const rowsOf = t => t.rows.map(r => Object.fromEntries(t.columns.map((c, i) => [c, r[i]])));
const STATES = rowsOf(db('state_summary.json'));
const COUNTIES = rowsOf(db('county_summary.json'));
const fmt = n => new Intl.NumberFormat('en-US').format(n);

async function open(page, hash, view) {
  await page.goto(FILE + hash);
  await expect(page.locator('body')).toHaveAttribute('data-ready', view, { timeout: 60000 });
}

async function noCritical(page) {
  const axe = await new AxeBuilder({ page }).analyze();
  const critical = axe.violations.filter(v => v.impact === 'critical');
  expect(critical.map(v => `${v.id}: ${v.nodes.length}`), 'critical axe violations').toEqual([]);
}

test('national view: headline figures, states table and coverage-aware map', async ({ page }) => {
  test.setTimeout(120000);
  await open(page, '#/', 'national');
  const ren = M.restrictions.by_scope.renewables_only;
  await expect(page.locator('#headlineRestrictions')).toHaveText(fmt(ren.instruments));
  await expect(page.locator('#headlineSevere')).toHaveText(fmt(ren.severe_instruments));
  await expect(page.locator('#headlineProjects')).toHaveText(fmt(M.contested_projects.projects));
  await expect(page.locator('#headlineCases')).toHaveText(fmt(M.cases.cases));
  const cov = M.county_coverage;
  await expect(page.locator('#headlineCoverage'))
    .toHaveText(`${fmt(cov.with_any_record + cov.with_negative_check_and_no_record)} of ${fmt(cov.counties)}`);

  // The states table's restrictions column adds up to the national figure.
  const cells = await page.locator('#statesHeading ~ .table-wrap tbody tr td:nth-child(2)').allTextContents();
  const sum = cells.reduce((a, t) => a + Number(t.replace(/,/g, '')), 0);
  expect(sum).toBe(ren.instruments);

  // Every county outside Puerto Rico is drawn, and exactly the unexamined
  // ones wear the "not examined" fill.
  const map = page.locator('#map');
  await expect(map).toHaveAttribute('data-painted', String(cov.counties), { timeout: 30000 });
  const none = await page.locator('#map path.county').evaluateAll(ps => ps.filter(p => p.style.fill === 'var(--map-none)').length);
  expect(none).toBe(cov.with_neither);
  await expect(page.locator('#mapLegend')).toContainText('Not examined');

  // The page reads the small published files, never the 8 MB record JSON.
  expect(page.requested.some(u => /\/data\/processed\/restrictions\.json$/.test(u))).toBe(false);
  expect(page.consoleErrors, 'console errors').toEqual([]);
  await noCritical(page);
});

test('the metric choice is in the URL and repaints the legend', async ({ page }) => {
  test.setTimeout(120000);
  await open(page, '#/', 'national');
  await page.selectOption('#metric', 'coverage');
  await expect(page).toHaveURL(/#\/\?m=coverage$/);
  await expect(page.locator('body')).toHaveAttribute('data-ready', 'national', { timeout: 60000 });
  await expect(page.locator('#mapLegend')).toContainText('Checked, none found');
});

test('state view: figures equal the state summary', async ({ page }) => {
  test.setTimeout(120000);
  const s = STATES.find(x => x.state_code === 'IA');
  await open(page, '#/state/IA', 'state');
  await expect(page.locator('h1')).toHaveText(s.state_name);
  await expect(page.locator('#stateRestrictions')).toHaveText(fmt(s.restrictions));
  await expect(page.locator('#stateProjects')).toHaveText(fmt(s.contested_projects));
  await expect(page.locator('#restrictionsHeading')).toHaveText(`Restrictions (${fmt(s.restrictions)})`);
  await expect(page.locator('#projectsHeading')).toHaveText(`Contested projects (${fmt(s.contested_projects)})`);
  const rows = await page.locator('#countiesHeading ~ .table-wrap tbody tr').count();
  expect(rows).toBe(COUNTIES.filter(c => c.state_code === 'IA').length);
  expect(page.consoleErrors, 'console errors').toEqual([]);
  await noCritical(page);
});

test('county view: records listed equal the county summary', async ({ page }) => {
  test.setTimeout(120000);
  const c = COUNTIES.filter(x => x.in_coverage_universe)
    .sort((a, b) => b.restrictions - a.restrictions || a.county_fips.localeCompare(b.county_fips))[0];
  await open(page, `#/county/${c.county_fips}`, 'county');
  await expect(page.locator('#countyRestrictions')).toHaveText(fmt(c.restrictions));
  await expect(page.locator('#inCountyHeading ~ h3').first()).toHaveText(`Restrictions (${fmt(c.restrictions)})`);
  await expect(page.locator('#coverageBanner')).toContainText('Published records');
  await expect(page.locator('#neighborMap path.county.focus')).toHaveCount(1);
  expect(page.consoleErrors, 'console errors').toEqual([]);
  await noCritical(page);
});

test('an unexamined county says so instead of showing an empty profile', async ({ page }) => {
  test.setTimeout(120000);
  const c = COUNTIES.find(x => x.in_coverage_universe && x.coverage_status === 'not_examined');
  await open(page, `#/county/${c.county_fips}`, 'county');
  await expect(page.locator('#coverageBanner')).toContainText('Not examined');
  await expect(page.locator('#countyRestrictions')).toHaveText('0');
});

test('pending review shows as a count, never as candidates', async ({ page }) => {
  test.setTimeout(120000);
  const c = COUNTIES.find(x => x.pending_review > 0);
  test.skip(!c, 'no county has a pending candidate in the current data');
  await open(page, `#/county/${c.county_fips}`, 'county');
  await expect(page.locator('#pendingNote')).toContainText('awaiting review');
  expect(page.requested.some(u => /\/data\/review\//.test(u)), 'reads review files').toBe(false);
});

test('phone width: no horizontal page scroll', async ({ page }) => {
  test.setTimeout(120000);
  await page.setViewportSize({ width: 375, height: 800 });
  for (const [hash, view] of [['#/', 'national'], ['#/state/NY', 'state'], ['#/county/36003', 'county'],
                              ['#/explore/restrictions', 'explore'], ['#/coverage', 'coverage']]) {
    await open(page, hash, view);
    const over = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(over, `${hash} overflows by ${over}px`).toBeLessThanOrEqual(0);
  }
});

// Carried over from choropleth.spec.js, retired with renewable-opposition-map.html
// in phase 4: every county the data names paints, a state view draws all of
// its counties from the local TopoJSON, and a geometry failure says so while
// the figures stay on the page.
test('every county with a restriction is shaded, and only those', async ({ page }) => {
  test.setTimeout(120000);
  await open(page, '#/?m=restrictions', 'national');
  await expect(page.locator('#map')).toHaveAttribute('data-painted', /^[1-9]/, { timeout: 30000 });
  const shaded = await page.locator('#map path.county').evaluateAll(ps =>
    ps.filter(p => /var\(--map-c[1-4]\)/.test(p.style.fill)).length);
  expect(shaded).toBe(COUNTIES.filter(c => c.in_coverage_universe && c.restrictions > 0).length);
  for (const st of ['IA', 'MN', 'CT']) {
    await open(page, `#/state/${st}`, 'state');
    await expect(page.locator('#map')).toHaveAttribute('data-painted',
      String(COUNTIES.filter(c => c.state_code === st).length), { timeout: 30000 });
  }
  expect(page.requested.some(u => u.endsWith('/data/geo/counties_2024.topojson'))).toBe(true);
  expect(page.requested.filter(u => /geojson-counties-fips/.test(u))).toEqual([]);
});

test('county boundaries failing to load still leaves every table', async ({ page }) => {
  test.setTimeout(120000);
  await page.route('**/counties_2024.topojson', route => route.fulfill({ status: 404, body: '' }));
  await open(page, '#/', 'national');
  await expect(page.locator('#mapStatus')).toContainText('County boundaries could not be loaded');
  await expect(page.locator('#map')).toHaveAttribute('data-painted', '0');
  await expect(page.locator('#statesHeading ~ .table-wrap tbody tr').first()).toBeVisible();
});

test('timeline: the dated bars and the undated count add up to the headline figure', async ({ page }) => {
  test.setTimeout(120000);
  await open(page, '#/', 'national');
  await expect(page.locator('#timelineUndated')).toBeVisible({ timeout: 30000 });
  const ren = M.restrictions.by_scope.renewables_only;
  const undated = Number((await page.locator('#timelineUndated').textContent()).match(/[\d,]+/)[0].replace(/,/g, ''));
  const all = await page.locator('#timelineTable tbody tr td:last-child').allTextContents();
  const dated = all.reduce((a, t) => a + Number(t.replace(/,/g, '')), 0);
  expect(dated + undated).toBe(ren.instruments);
  // One Vega-Lite bar segment per year and basis that has instruments.
  const segs = rowsOf(db('timeline.json')).filter(r => r.scope === 'renewables_only' && r.basis !== 'undated');
  await expect(page.locator('#timeline .mark-rect path')).toHaveCount(segs.length, { timeout: 30000 });
  // Each headline figure's history draws its own small chart.
  await expect(page.locator('#history svg')).toHaveCount(4);
  expect(page.consoleErrors, 'console errors').toEqual([]);
});

test('history: the tiles show the latest build and the change line names the one before', async ({ page }) => {
  test.setTimeout(120000);
  const rows = rowsOf(db('history.json'));
  const last = rows[rows.length - 1], prev = rows[rows.length - 2];
  await open(page, '#/', 'national');
  await expect(page.locator('#historyChange')).toContainText(`Since the build of ${prev.date}`, { timeout: 30000 });
  await expect(page.locator('#historyChange')).toContainText(`as of ${last.date}`);
  await expect(page.locator('#history .tile').first().locator('.value')).toHaveText(fmt(last.restrictions));
  await expect(page.locator('#historyTable tbody tr')).toHaveCount(rows.length);
  // The tiles follow the published history, not headline_metrics.json: CI
  // rebuilds the metrics from the seeds under test, and the history gains its
  // row for that build only when the data workflow runs headline_history.py.
});

test('a record names its Census government and GEOID', async ({ page }) => {
  test.setTimeout(120000);
  const ny = db('state/NY.json');
  const r = ny.restrictions.find(x => x.state_code === 'NY' && x.geoid && x.census_name);
  await open(page, '#/restriction/' + encodeURIComponent(r.instrument_id), 'record');
  await expect(page.locator('dt:text-is("Census government") + dd')).toHaveText(`${r.census_name} · GEOID ${r.geoid}`);
});

test('a county on the map opens its numbers with a link to its profile', async ({ page }) => {
  test.setTimeout(120000);
  const c = COUNTIES.filter(x => x.in_coverage_universe)
    .sort((a, b) => b.restrictions - a.restrictions || a.county_fips.localeCompare(b.county_fips))[0];
  await open(page, `#/state/${c.state_code}?m=restrictions`, 'state');
  await expect(page.locator('#map')).toHaveAttribute('data-painted', /^[1-9]/, { timeout: 30000 });
  await page.locator(`#map path.county[data-fips="${c.county_fips}"]`).click({ force: true });
  const pop = page.locator('.leaflet-popup .map-pop');
  await expect(pop).toContainText(`${c.county_name}, ${c.state_code}`);
  await expect(pop).toContainText(`${fmt(c.restrictions)} restrictions (renewables only)`);
  await pop.locator('a.pop-link').click();
  await expect(page.locator('body')).toHaveAttribute('data-ready', 'county', { timeout: 60000 });
  await expect(page.locator('#countyRestrictions')).toHaveText(fmt(c.restrictions));
});

test('the legend picks out one class of counties', async ({ page }) => {
  test.setTimeout(120000);
  await open(page, '#/', 'national');
  await expect(page.locator('#map')).toHaveAttribute('data-painted', /^[1-9]/, { timeout: 30000 });
  const btn = page.locator('#mapLegend button', { hasText: 'Not examined' });
  await btn.click();
  await expect(btn).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('#map')).toHaveAttribute('data-hl', 'none');
  await btn.click();
  await expect(btn).toHaveAttribute('aria-pressed', 'false');
  await expect(page.locator('#map')).not.toHaveAttribute('data-hl', /./);
});

test('a metric change keeps the map where the reader left it', async ({ page }) => {
  test.setTimeout(120000);
  await open(page, '#/', 'national');
  await expect(page.locator('#map')).toHaveAttribute('data-painted', /^[1-9]/, { timeout: 30000 });
  await page.locator('#map .map-presets button', { hasText: 'Alaska' }).click();
  await page.waitForTimeout(1200);
  const before = await page.locator('#map path.county[data-fips="02020"]').boundingBox();
  await page.selectOption('#metric', 'contested_projects');
  await expect(page).toHaveURL(/#\/\?m=contested_projects$/);
  await expect(page.locator('body')).toHaveAttribute('data-ready', 'national', { timeout: 60000 });
  await expect(page.locator('#metric')).toBeFocused();
  await expect(page.locator('#map')).toHaveAttribute('data-painted', /^[1-9]/, { timeout: 30000 });
  const after = await page.locator('#map path.county[data-fips="02020"]').boundingBox();
  expect(Math.abs(after.x - before.x)).toBeLessThan(2);
  expect(Math.abs(after.width - before.width)).toBeLessThan(2);
});

// The charts' libraries load on demand from the CDN; each carries the sha384
// of the copy the tests serve, so a changed file fails to load.
test('Vega, Vega-Lite and vega-embed are pinned by integrity', () => {
  const crypto = require('crypto');
  const { cdnToLocal } = require('./fixtures');
  const js = fs.readFileSync(path.join(ROOT, 'national-dashboard.js'), 'utf8');
  const block = /var VEGA = \[([\s\S]*?)\n  \];/.exec(js)[1];
  const pins = [...block.matchAll(/\['(https:[^']+)', '(sha384-[^']+)'\]/g)].map(m => [m[1], m[2]]);
  expect(pins.map(p => p[0].split('/npm/')[1].split('@')[0])).toEqual(['vega', 'vega-lite', 'vega-embed']);
  const lock = JSON.parse(fs.readFileSync(path.join(__dirname, 'package-lock.json'), 'utf8')).packages;
  for (const [u, sri] of pins) {
    const name = u.split('/npm/')[1].split('@')[0];
    expect(u, 'version matches tests/ui/package-lock.json').toContain(`${name}@${lock['node_modules/' + name].version}/`);
    expect(sri, u).toBe('sha384-' + crypto.createHash('sha384').update(fs.readFileSync(cdnToLocal(u))).digest('base64'));
  }
});

// The national dashboard's phase 4 views (docs/national_database_design.md):
// explorer, record pages, coverage, data and the SQL console. Every count
// must equal the published files; worklists appear as sizes only; the SQL
// console runs real queries on DuckDB-WASM, offline (fixtures.js serves the
// engine from node_modules and its Parquet extension from .cache/).
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
const fmt = n => new Intl.NumberFormat('en-US').format(n);
const EXT = path.join(__dirname, '.cache', 'duckdb-extensions', 'v1.1.1', 'wasm_eh', 'parquet.duckdb_extension.wasm');

async function open(page, hash, view) {
  await page.goto(FILE + hash);
  await expect(page.locator('body')).toHaveAttribute('data-ready', view, { timeout: 60000 });
}
async function noCritical(page) {
  const axe = await new AxeBuilder({ page }).analyze();
  const critical = axe.violations.filter(v => v.impact === 'critical');
  expect(critical.map(v => `${v.id}: ${v.nodes.length}`), 'critical axe violations').toEqual([]);
}
const count = async page => Number((await page.locator('#resultCount').textContent()).split(' ')[0].replace(/,/g, ''));

test('explorer: default counts equal the headline figures for each entity', async ({ page }) => {
  test.setTimeout(120000);
  const ren = M.restrictions.by_scope.renewables_only;
  await open(page, '#/explore/restrictions', 'explore');
  await expect(page.locator('#resultCount')).toHaveText(
    `${fmt(ren.instruments)} restrictions · ${fmt(ren.by_verification.verified || 0)} verified`);
  await page.selectOption('#f-scope', 'multi_sector_data_centers');
  expect(await count(page)).toBe(M.restrictions.by_scope.multi_sector_data_centers.instruments);
  await open(page, '#/explore/projects', 'explore');
  expect(await count(page)).toBe(M.contested_projects.projects);
  await open(page, '#/explore/cases', 'explore');
  expect(await count(page)).toBe(M.cases.cases);
  expect(page.consoleErrors, 'console errors').toEqual([]);
  await noCritical(page);
});

test('explorer: filters go into the URL, search keeps focus, CSV has every row', async ({ page }) => {
  test.setTimeout(120000);
  await open(page, '#/explore/restrictions', 'explore');
  await page.selectOption('#f-st', 'NY');
  await expect(page).toHaveURL(/#\/explore\/restrictions\?st=NY$/);
  const ny = STATES.find(s => s.state_code === 'NY');
  expect(await count(page)).toBe(ny.restrictions);

  await page.locator('#exploreSearch').fill('moratorium');
  await expect(page).toHaveURL(/q=moratorium/);
  await expect(page.locator('#exploreSearch')).toBeFocused();
  const n = await count(page);
  expect(n).toBeGreaterThan(0);
  expect(n).toBeLessThan(ny.restrictions);

  const [dl] = await Promise.all([page.waitForEvent('download'), page.click('#csvBtn')]);
  const text = fs.readFileSync(await dl.path(), 'utf8');
  const lines = text.trim().split(/\r\n/);
  expect(lines[0]).toContain('instrument_id');
  expect(lines.length - 1).toBe(n);

  // The URL alone restores the same view.
  await open(page, '#/explore/restrictions?q=moratorium&st=NY', 'explore');
  expect(await count(page)).toBe(n);
});

test('record pages: an instrument shows every technology row, its placement and sources', async ({ page }) => {
  test.setTimeout(120000);
  const ny = db('state/NY.json');
  const r = ny.restrictions.filter(x => x.state_code === 'NY' && x.rows.length > 1 && x.placements.length)[0];
  await open(page, '#/restriction/' + encodeURIComponent(r.instrument_id), 'record');
  await expect(page.locator('#rowsHeading ~ .table-wrap tbody tr')).toHaveCount(r.rows.length);
  await expect(page.locator('#placeHeading ~ ul li')).toHaveCount(r.placements.length);
  await expect(page.locator('#permalink')).toHaveText(new RegExp(encodeURIComponent(r.instrument_id) + '$'));
  await noCritical(page);

  const p = ny.projects.find(x => x.state_code === 'NY');
  await open(page, '#/project/' + encodeURIComponent(p.instrument_id), 'record');
  await expect(page.locator('h1')).toHaveText(p.project_name || 'Unnamed project');

  await page.goto(FILE + '#/restriction/no-such-record');
  await expect(page.locator('body')).toHaveAttribute('data-ready', 'error', { timeout: 60000 });
  await expect(page.locator('#status')).toContainText('No restriction with id no-such-record');
});

test('state view rows link to their record pages', async ({ page }) => {
  test.setTimeout(120000);
  await open(page, '#/state/IA', 'state');
  const first = page.locator('#restrictionsHeading ~ div tbody tr td:first-child a').first();
  await first.click();
  await expect(page.locator('body')).toHaveAttribute('data-ready', 'record', { timeout: 60000 });
  await expect(page.locator('#rowsHeading')).toBeVisible();
});

test('coverage: worklists appear as sizes only, and figures equal the headline', async ({ page }) => {
  test.setTimeout(120000);
  const cov = M.county_coverage;
  await open(page, '#/coverage', 'coverage');
  await expect(page.locator('#covNone')).toHaveText(fmt(cov.with_neither));
  await expect(page.locator('#covRecords')).toHaveText(fmt(cov.with_any_record));
  const w = rowsOf(db('worklists.json'));
  await expect(page.locator('#worklistTable tbody tr')).toHaveCount(w.length);
  for (const x of w) {
    await expect(page.locator('#worklistTable tbody')).toContainText(x.description);
  }
  // Puerto Rico is outside the coverage figures.
  await expect(page.locator('#covStatesHeading ~ .table-wrap tbody')).not.toContainText('Puerto Rico');
  expect(page.requested.some(u => /\/data\/review\//.test(u)), 'reads review files').toBe(false);
  await noCritical(page);
});

test('data: every Parquet file is listed and the dictionary covers every table', async ({ page }) => {
  test.setTimeout(120000);
  await open(page, '#/data', 'data');
  const manifest = rowsOf(db('manifest.json'));
  await expect(page.locator('#downloadsTable tbody tr')).toHaveCount(manifest.length);
  const tables = (fs.readFileSync(path.join(ROOT, 'db', 'schema.sql'), 'utf8').match(/^CREATE TABLE /gm) || []).length;
  await expect(page.locator('details.dict')).toHaveCount(tables);
  await noCritical(page);
});

test('SQL console: DuckDB-WASM answers with the published numbers, offline', async ({ page }) => {
  test.setTimeout(240000);
  if (!fs.existsSync(EXT)) throw new Error('missing ' + EXT + ': run tests/ui/fetch_duckdb_extension.sh');
  const sql = "SELECT count(*) AS n FROM restriction_instrument WHERE scope = 'renewables_only'";
  await open(page, '#/sql?q=' + encodeURIComponent(sql), 'sql');
  await expect(page.locator('#sqlStatus')).toContainText(/row in|Error/, { timeout: 180000 });
  await expect(page.locator('#sqlStatus')).toContainText('1 row in');
  await expect(page.locator('#sqlTable tbody td')).toHaveText(String(M.restrictions.by_scope.renewables_only.instruments));

  // Each example on the data page runs without an error.
  await open(page, '#/data', 'data');
  const examples = await page.locator('pre.code').allTextContents();
  await page.goto(FILE + '#/sql');
  await expect(page.locator('body')).toHaveAttribute('data-ready', 'sql', { timeout: 60000 });
  for (const q of examples) {
    await page.locator('#sqlInput').fill(q);
    await page.click('#sqlRun');
    await expect(page.locator('#sqlRun')).toBeEnabled({ timeout: 120000 });
    await expect(page.locator('#sqlStatus'), q).toContainText(/rows? in/);
  }
  expect(page.consoleErrors, 'console errors').toEqual([]);
  await noCritical(page);
});

// The SQL console names its library versions in four places; they must agree
// with what npm resolved (and the tests serve), or production and tests drift.
test('DuckDB-WASM, Arrow and their imports are pinned to the resolved versions', () => {
  const lock = JSON.parse(fs.readFileSync(path.join(__dirname, 'package-lock.json'), 'utf8')).packages;
  const v = name => lock['node_modules/' + name].version;
  const html = fs.readFileSync(path.join(ROOT, 'national-dashboard.html'), 'utf8');
  const js = fs.readFileSync(path.join(ROOT, 'national-dashboard.js'), 'utf8');
  expect(js).toContain(`@duckdb/duckdb-wasm@${v('@duckdb/duckdb-wasm')}/dist/duckdb-browser.mjs`);
  expect(html).toContain(`apache-arrow@${v('apache-arrow')}/`);
  expect(html).toContain(`tslib@${v('tslib')}/`);
  expect(html).toContain(`flatbuffers@${v('flatbuffers')}/`);
  // duckdb-wasm 1.29.x ships DuckDB v1.1.1, whose extensions fetch_duckdb_extension.sh pins.
  expect(v('@duckdb/duckdb-wasm')).toMatch(/^1\.29\./);
  expect(fs.readFileSync(path.join(__dirname, 'fetch_duckdb_extension.sh'), 'utf8')).toContain('v1.1.1/wasm_eh/');
});

test('coverage: states with every county examined, and each negative check with its grade', async ({ page }) => {
  test.setTimeout(120000);
  const counties = rowsOf(db('county_summary.json'));
  const inScope = STATES.filter(s => s.counties && s.state_code !== 'PR');
  await open(page, '#/coverage', 'coverage');
  await expect(page.locator('#covStatesDone')).toHaveText(fmt(inScope.filter(s => !s.counties_not_examined).length));
  const checked = counties.filter(c => c.last_negative_check);
  await expect(page.locator('#checksTable tbody tr')).toHaveCount(checked.length);
  for (const c of checked) {
    await expect(page.locator('#checksTable tbody')).toContainText(`${c.county_name}, ${c.state_code}`);
  }
  // A checked county's page names the grade and when to check it again.
  const none = counties.find(c => c.coverage_status === 'checked_none');
  if (none) {
    await open(page, '#/county/' + none.county_fips, 'county');
    await expect(page.locator('#coverageBanner')).toContainText(`Evidence grade ${none.negative_check_grade}`);
    await expect(page.locator('#coverageBanner')).toContainText(none.negative_check_recheck_by);
  }
});

test('the map can show verified restrictions only', async ({ page }) => {
  test.setTimeout(120000);
  await open(page, '#/?m=verified_restrictions', 'national');
  await expect(page.locator('#metric')).toHaveValue('verified_restrictions');
  const counties = rowsOf(db('county_summary.json'));
  const shaded = await page.locator('#map path.county').evaluateAll(ps =>
    ps.filter(p => /var\(--map-c[1-4]\)/.test(p.style.fill)).length);
  expect(shaded).toBe(counties.filter(c => c.in_coverage_universe && c.verified_restrictions > 0).length);
});

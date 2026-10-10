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
  await expect(page.locator('.legend')).toContainText('Not examined');

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
  await expect(page.locator('.legend')).toContainText('Checked, none found');
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
  for (const [hash, view] of [['#/', 'national'], ['#/state/NY', 'state']]) {
    await open(page, hash, view);
    const over = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(over, `${hash} overflows by ${over}px`).toBeLessThanOrEqual(0);
  }
});

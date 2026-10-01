// Smoke, count and accessibility checks over every page. Adapted from
// pricephillips/data-center-map tests/ui/pages.spec.js at 0938c30 (its spec
// 009, US5; passoff B7) for this repository's four pages.
//   - no console errors (network noise from aborted third-party hosts aside)
//   - no data load failure in the page's status line
//   - zero critical axe-core violations (serious ones are reported)
//   - map pages: at least one marker
//   - no page fetches the raw extraction CSV; every page reads data/processed/
//   - unfiltered counts equal data/processed/headline_metrics.json
'use strict';
const { test, expect, processed } = require('./fixtures');
const AxeBuilder = require('@axe-core/playwright').default;

const PAGES = [
  { file: 'index.html', ready: '#resultCountBadge', markers: '#mapSvg .marker' },
  { file: 'renewable-opposition-map.html', ready: '#resultBadge', markers: '.leaflet-marker-icon' },
  { file: 'map-audit.html', ready: '#resultBadge', markers: '.leaflet-marker-icon' },
  { file: 'dashboard.html', ready: '#table-summary' }
];

const M = processed('headline_metrics.json');
const H = {
  renewables: M.restrictions.by_scope.renewables_only.instruments,
  renewablesSevere: M.restrictions.by_scope.renewables_only.severe_instruments,
  multi: M.restrictions.by_scope.multi_sector_data_centers.instruments,
  projects: M.contested_projects.projects,
  cases: M.cases.cases
};
const fmt = n => new Intl.NumberFormat('en-US').format(n);
// processed-data.js tallyText for the unfiltered data set.
const FULL_TALLY = `${fmt(H.renewables)} renewables-only restrictions · ${fmt(H.multi)} also covering data centers · ` +
  `${fmt(H.projects)} contested projects · ${fmt(H.cases)} cases`;

async function loaded(page, p) {
  await page.goto('/' + p.file);
  await expect(page.locator(p.ready)).toContainText(/[1-9]/, { timeout: 30000 });
  await page.waitForLoadState('networkidle');
}

for (const p of PAGES) {
  test(`${p.file}: loads clean and passes axe`, async ({ page }) => {
    test.setTimeout(180000);
    await loaded(page, p);
    if (p.markers) {
      await expect.poll(() => page.locator(p.markers).count(), { timeout: 30000 }).toBeGreaterThan(0);
    }
    const status = page.locator('#mapStatus');
    if (await status.count() && await status.isVisible()) {
      await expect(status).not.toContainText(/Failed to load|could not be loaded/);
    }
    expect(page.consoleErrors, 'console errors').toEqual([]);
    expect(page.requested.filter(u => /renewable_opposition_records\.csv/.test(u)), 'raw CSV fetches').toEqual([]);
    expect(page.requested.some(u => /\/data\/processed\/restrictions\.json$/.test(u)), 'reads data/processed/').toBe(true);

    const axe = await new AxeBuilder({ page }).analyze();
    const critical = axe.violations.filter(v => v.impact === 'critical');
    const serious = axe.violations.filter(v => v.impact === 'serious');
    if (serious.length) {
      test.info().annotations.push({ type: 'axe-serious',
        description: serious.map(v => `${v.id} (${v.nodes.length})`).join(', ') });
    }
    expect(critical.map(v => `${v.id}: ${v.help} (${v.nodes.length} nodes, e.g. ${v.nodes[0].target})`),
      'critical axe violations').toEqual([]);
  });
}

test('map pages count instruments, restriction scopes apart', async ({ page }) => {
  for (const file of ['renewable-opposition-map.html', 'map-audit.html']) {
    await loaded(page, { file, ready: '#resultBadge' });
    await expect(page.locator('#resultBadge')).toHaveText(FULL_TALLY);
  }
  await expect(page.locator('#metricVisible')).toHaveText(fmt(H.renewables + H.multi + H.projects + H.cases));
});

test('renewable-opposition-map.html quotes headline_metrics.json', async ({ page }) => {
  await loaded(page, { file: 'renewable-opposition-map.html', ready: '#resultBadge' });
  await expect(page.locator('#headlineRenewables')).toHaveText(fmt(H.renewables));
  await expect(page.locator('#headlineMultiSector')).toHaveText(fmt(H.multi));
  await expect(page.locator('#headlineProjects')).toHaveText(fmt(H.projects));
  await expect(page.locator('#headlineCases')).toHaveText(fmt(H.cases));
  await page.selectOption('#scopeFilter', 'multi_sector_data_centers');
  await expect(page.locator('#resultBadge')).toHaveText(`${fmt(H.multi)} also covering data centers`);
});

test('dashboard.html quotes headline_metrics.json and counts instruments', async ({ page }) => {
  await loaded(page, { file: 'dashboard.html', ready: '#table-summary' });
  const stat = id => page.locator(`[data-headline="${id}"] .stat-value`);
  await expect(stat('renewables')).toHaveText(String(H.renewables));
  await expect(stat('multi_sector')).toHaveText(String(H.multi));
  await expect(stat('projects')).toHaveText(String(H.projects));
  await expect(stat('cases')).toHaveText(String(H.cases));
  await expect(page.locator('#cnt-r')).toHaveText(String(H.renewables));
  await expect(page.locator('#cnt-rm')).toHaveText(`${H.multi} also data centers`);
  await expect(page.locator('#cnt-c')).toHaveText(String(H.projects));
  await expect(page.locator('#cnt-k')).toHaveText(String(H.cases));
});

test('index.html quotes headline_metrics.json', async ({ page }) => {
  await loaded(page, { file: 'index.html', ready: '#resultCountBadge' });
  await expect(page.locator('#metricSevere')).toHaveText(fmt(H.renewablesSevere));
  await expect(page.locator('#metricContested')).toHaveText(fmt(H.projects));
  await expect(page.locator('#metricCases')).toHaveText(fmt(H.cases));
});

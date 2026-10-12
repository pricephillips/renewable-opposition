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

// index.html, dashboard.html and renewable-opposition-map.html were retired
// in phase 4 (docs/national_database_design.md) and now redirect to
// national-dashboard.html; national.spec.js and explore.spec.js check that
// page's figures against headline_metrics.json, and the redirects are
// checked below. map-audit.html stays as the internal geography audit.
const PAGES = [
  { file: 'map-audit.html', ready: '#resultBadge', markers: '.leaflet-marker-icon' }
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

test('map-audit.html counts instruments, restriction scopes apart', async ({ page }) => {
  await loaded(page, { file: 'map-audit.html', ready: '#resultBadge' });
  await expect(page.locator('#resultBadge')).toHaveText(FULL_TALLY);
  await expect(page.locator('#metricVisible')).toHaveText(fmt(H.renewables + H.multi + H.projects + H.cases));
});

// Old links keep working: each retired page lands on the view that replaced it.
for (const [file, hash, view] of [['index.html', '#/', 'national'], ['', '#/', 'national'],
                                   ['renewable-opposition-map.html', '#/', 'national'],
                                   ['dashboard.html', '#/explore/restrictions', 'explore']]) {
  test(`${file || '/'} redirects to national-dashboard.html${hash}`, async ({ page }) => {
    await page.goto('/' + file);
    await expect(page).toHaveURL(new RegExp('/national-dashboard\\.html' + hash.replace(/[/#]/g, m => '\\' + m) + '$'));
    await expect(page.locator('body')).toHaveAttribute('data-ready', view, { timeout: 60000 });
    expect(page.consoleErrors, 'console errors').toEqual([]);
  });
}

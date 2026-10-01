// UI and accessibility tests. Adapted from pricephillips/data-center-map
// tests/ui/playwright.config.js at 0938c30 (its spec 009; passoff B7).
// Offline by construction: fixtures.js routes every request to the working
// tree or node_modules, or aborts it.
'use strict';
const { defineConfig } = require('@playwright/test');

const PORT = Number(process.env.UI_PORT || 8765);
// Claude sessions ship a Chromium at /opt/pw-browsers and must never run
// `playwright install`; point SMOKE_CHROMIUM at it there (the same variable
// scripts/smoke_frontend.py reads). CI installs the matching build and leaves
// it unset.
const LOCAL_CHROMIUM = process.env.SMOKE_CHROMIUM || undefined;
const GL_ARGS = ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'];

module.exports = defineConfig({
  testDir: '.',
  testMatch: /.*\.spec\.js$/,
  timeout: 60000,
  retries: 0,
  workers: process.env.CI ? 2 : 3,
  reporter: [['list']],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    browserName: 'chromium',
    launchOptions: LOCAL_CHROMIUM ? { executablePath: LOCAL_CHROMIUM, args: GL_ARGS } : { args: GL_ARGS }
  },
  webServer: {
    command: 'node serve.js',
    url: `http://127.0.0.1:${PORT}/index.html`,
    reuseExistingServer: !process.env.CI,
    env: { UI_PORT: String(PORT) }
  }
});

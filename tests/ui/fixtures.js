// Shared test fixture: an offline page. Adapted from pricephillips/data-center-map
// tests/ui/fixtures.js at 0938c30 (its spec 009, FR-006; passoff B7).
//
// Every request the page makes is intercepted:
//   - the local static server passes through, so pages read data/processed/
//     and data/geo/ from the working tree under test;
//   - pinned CDN library URLs (unpkg, jsdelivr npm) are served from
//     tests/ui/node_modules, whose versions package.json pins to match;
//   - anything else (basemap styles and tiles, web fonts, third-party data) is
//     aborted and recorded in page.blockedHosts.
// Every URL requested is kept in page.requested. Console errors are collected
// in page.consoleErrors, minus the network noise those aborts produce by design.
'use strict';
const fs = require('fs');
const path = require('path');
const base = require('@playwright/test');

const ROOT = path.resolve(__dirname, '..', '..');
const NM = path.join(__dirname, 'node_modules');

const TYPES = {
  '.js': 'application/javascript', '.mjs': 'application/javascript', '.css': 'text/css',
  '.json': 'application/json', '.topojson': 'application/json', '.csv': 'text/csv',
  '.md': 'text/plain', '.png': 'image/png', '.svg': 'image/svg+xml'
};

// Map a CDN URL to a file inside node_modules, or null.
function cdnToLocal(u) {
  const m = /^https:\/\/(?:unpkg\.com|cdn\.jsdelivr\.net\/npm)\/((?:@[^/]+\/)?[^@/]+)(?:@[^/]+)?\/(.+)$/.exec(u);
  return m ? path.join(NM, m[1], m[2]) : null;
}

async function fulfillFile(route, file) {
  // jsdelivr minifies on request; npm ships only the unminified build for
  // some packages.
  if (file && !fs.existsSync(file) && /\.min\.js$/.test(file)) {
    const plain = file.replace(/\.min\.js$/, '.js');
    if (fs.existsSync(plain)) file = plain;
  }
  if (!file || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
    return route.fulfill({ status: 404, body: 'not found' });
  }
  return route.fulfill({
    status: 200,
    body: fs.readFileSync(file),
    headers: {
      'content-type': TYPES[path.extname(file)] || 'application/octet-stream',
      'access-control-allow-origin': '*'
    }
  });
}

// Extra per-test routes: { urlSubstring: 'abort' | filePath | (route) => ... }.
async function offline(page, overrides) {
  page.blockedHosts = new Set();
  page.requested = [];
  page.consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() !== 'error') return;
    const text = msg.text();
    // Aborted third-party requests are the harness working as intended, not
    // page errors.
    if (/Failed to load resource|net::ERR_/.test(text)) return;
    page.consoleErrors.push(text);
  });
  page.on('pageerror', err => page.consoleErrors.push('pageerror: ' + err.message));
  await page.route('**/*', async route => {
    const u = route.request().url();
    page.requested.push(u);
    for (const [needle, action] of Object.entries(overrides || {})) {
      if (!u.includes(needle)) continue;
      if (action === 'abort') return route.abort();
      if (typeof action === 'function') return action(route);
      return fulfillFile(route, action);
    }
    if (u.startsWith('http://127.0.0.1') || u.startsWith('http://localhost') ||
        u.startsWith('data:') || u.startsWith('blob:')) {
      return route.continue();
    }
    const local = cdnToLocal(u);
    if (local) return fulfillFile(route, local);
    try { page.blockedHosts.add(new URL(u).host); } catch (e) { /* ignore */ }
    return route.abort();
  });
}

const test = base.test.extend({
  page: async ({ page }, use) => {
    await offline(page);
    await use(page);
  }
});

// The published data, read the way the tests need it: headline figures and
// the distinct county FIPS a filter should paint.
function processed(name) {
  return JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'processed', name), 'utf8'));
}

module.exports = { test, expect: base.expect, offline, cdnToLocal, processed, ROOT };

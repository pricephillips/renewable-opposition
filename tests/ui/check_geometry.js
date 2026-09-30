#!/usr/bin/env node
/* check_geometry.js
 *
 * Coverage gate for data/geo/counties_2024.topojson. Copied from
 * pricephillips/data-center-map tests/ui/check_geometry.js at 0938c30 (its
 * spec 009, US1; passoff B4) and adapted; not imported.
 *
 * The plotly county GeoJSON the map used to draw on had no polygon for 13
 * current counties, and nothing noticed, because a county with records and no
 * polygon simply never paints. This check makes that a failure instead:
 *
 *   - every county_fips in data/processed/restrictions.json and
 *     contested_projects.json has a non-null geometry;
 *   - no geometry id appears twice;
 *   - the file is at most 1,000,000 bytes;
 *   - the file's SHA-256 matches data/geo/counties_2024_manifest.json, so a
 *     local edit to the copied file is caught (data-center-map writes the
 *     manifest; this repository only checks it).
 *
 * No dependencies beyond Node. The UI tests and validate.yml run it.
 *
 * Usage
 *   node tests/ui/check_geometry.js                 check, exit 1 on failure
 *   node tests/ui/check_geometry.js --selftest
 */
'use strict';

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const ROOT = path.resolve(__dirname, '..', '..');
const TOPO = 'data/geo/counties_2024.topojson';
const MANIFEST = 'data/geo/counties_2024_manifest.json';
const RECORDS = ['data/processed/restrictions.json', 'data/processed/contested_projects.json'];
const MAX_BYTES = 1000000;

// Distinct county_fips across the published records.
function recordFips(recordLists) {
  const out = new Set();
  recordLists.forEach(rows => rows.forEach(r => {
    const v = String(r.county_fips == null ? '' : r.county_fips).trim();
    if (v) out.add(v.padStart(5, '0'));
  }));
  return out;
}

function check(topo, bytes, needed) {
  const errors = [];
  const obj = topo && topo.objects && topo.objects.counties;
  if (!obj || !Array.isArray(obj.geometries)) {
    return { errors: ['no counties object'], featureCount: 0, missing: [...needed] };
  }
  const seen = new Set();
  const drawable = new Set();
  obj.geometries.forEach(g => {
    const id = String(g.id == null ? '' : g.id).padStart(5, '0');
    if (seen.has(id)) errors.push('duplicate id ' + id);
    seen.add(id);
    if (g.type && g.type !== 'null' && Array.isArray(g.arcs) && g.arcs.length) drawable.add(id);
  });
  const missing = [...needed].filter(f => !drawable.has(f)).sort();
  if (missing.length) errors.push(missing.length + ' record FIPS without a geometry: ' + missing.join(' '));
  if (bytes > MAX_BYTES) errors.push('file is ' + bytes + ' bytes, over ' + MAX_BYTES);
  return { errors, featureCount: obj.geometries.length, missing };
}

function checkManifest(buf, manifest) {
  const sha = crypto.createHash('sha256').update(buf).digest('hex');
  const errors = [];
  if (!manifest || manifest.sha256 !== sha) errors.push(`sha256 ${sha} does not match ${MANIFEST}`);
  if (manifest && manifest.bytes !== buf.length) errors.push(`size ${buf.length} does not match ${MANIFEST}`);
  return errors;
}

function main() {
  const buf = fs.readFileSync(path.join(ROOT, TOPO));
  const topo = JSON.parse(buf.toString('utf8'));
  const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, MANIFEST), 'utf8'));
  const needed = recordFips(RECORDS.map(f => JSON.parse(fs.readFileSync(path.join(ROOT, f), 'utf8'))));
  const r = check(topo, buf.length, needed);
  const errors = r.errors.concat(checkManifest(buf, manifest));
  console.log(`${TOPO}: ${r.featureCount} features, ${buf.length} bytes, ` +
              `${needed.size - r.missing.length} of ${needed.size} record FIPS drawable`);
  if (errors.length) {
    errors.forEach(e => console.error('FAIL: ' + e));
    return 1;
  }
  return 0;
}

function selftest() {
  let fails = 0;
  const ok = (name, cond) => { if (!cond) { fails++; console.error('FAIL ' + name); } else console.log('ok   ' + name); };
  const topo = { objects: { counties: { geometries: [
    { id: '09110', type: 'Polygon', arcs: [[0]] },
    { id: '46102', type: 'Polygon', arcs: [[1]] },
    { id: '51610', type: null }
  ] } } };
  ok('record fips pads and skips blanks',
     [...recordFips([[{ county_fips: '9110' }, { county_fips: null }], [{ county_fips: '46102' }, {}]])].join() === '09110,46102');
  ok('full coverage passes', check(topo, 10, new Set(['09110', '46102'])).errors.length === 0);
  ok('null geometry counts as missing', check(topo, 10, new Set(['51610'])).missing[0] === '51610');
  ok('absent fips fails', check(topo, 10, new Set(['02063'])).errors.length === 1);
  const dup = { objects: { counties: { geometries: [
    { id: '01001', type: 'Polygon', arcs: [[0]] }, { id: '01001', type: 'Polygon', arcs: [[0]] }] } } };
  ok('duplicate id fails', check(dup, 10, new Set()).errors.some(e => e.startsWith('duplicate')));
  ok('oversize fails', check(topo, MAX_BYTES + 1, new Set()).errors.length === 1);
  ok('missing object fails', check({ objects: {} }, 10, new Set()).errors.length === 1);
  const buf = Buffer.from('{}');
  const sha = crypto.createHash('sha256').update(buf).digest('hex');
  ok('matching manifest passes', checkManifest(buf, { sha256: sha, bytes: 2 }).length === 0);
  ok('edited file fails the manifest', checkManifest(Buffer.from('{ }'), { sha256: sha, bytes: 2 }).length === 2);
  console.log(fails ? fails + ' failed' : 'all passed');
  return fails ? 1 : 0;
}

if (require.main === module) {
  process.exit(process.argv.includes('--selftest') ? selftest() : main());
}
module.exports = { check, recordFips, checkManifest, MAX_BYTES };

/* processed-data.js
 *
 * The one way a page reads the published data.
 *
 * Every page reads data/processed/, which scripts/build_seed_outputs.py
 * regenerates on every build: restrictions.json, contested_projects.json and
 * cases.json (rows that passed qc_gate.py, with the derived instrument_id,
 * scope and evidence_level stamped by classify.py) and headline_metrics.json
 * (the numbers to quote). Pages used to read the raw Sabin extraction CSV
 * under data/, so quarantined rows still showed, Moratorium Nation rows never
 * did, and no page knew an instrument's scope.
 *
 * Counting rule (scripts/headline_metrics.py): a seed row is one technology of
 * one instrument, so rows are never counted. instruments() merges the rows of
 * one instrument into one record (technologies unioned, highest severity), and
 * every count on a page is a count of those. Restrictions that also cover data
 * centers (scope multi_sector_data_centers) are always a separate figure and
 * never folded into the renewables total.
 *
 * Usage
 *   <script src="./processed-data.js"></script>
 *   const data = await ProcessedData.load();   // { restrictions, contested_projects, cases, metrics }
 *   data.restrictions                          // one record per instrument, legacy field names
 *   ProcessedData.tally(records)               // { renewables, multi_sector, projects, cases }
 */
(function (global) {
  'use strict';

  var BASE = './data/processed/';
  var ENTITIES = ['restrictions', 'contested_projects', 'cases'];
  var METRICS_URL = BASE + 'headline_metrics.json';
  var SCOPE_LABELS = {
    renewables_only: 'Renewables only',
    multi_sector_data_centers: 'Also covers data centers'
  };
  var COUNTY_TYPES = { county: true, parish: true, borough: true };

  function s(v) { return v == null ? '' : String(v).trim(); }

  function techList(v) {
    return s(v).split(/[;,|]+/).map(function (t) { return t.trim(); }).filter(Boolean);
  }

  // Merge the rows of one instrument. Mirrors headline_metrics._instruments:
  // the highest severity wins and technologies are unioned. The first row
  // carries every other field (in practice the rows agree on them).
  function instruments(rows) {
    var out = [];
    var byId = {};
    (rows || []).forEach(function (r) {
      var iid = s(r.instrument_id) || s(r.id);
      var cur = byId[iid];
      if (!cur) {
        cur = Object.assign({}, r, { instrument_id: iid, row_ids: [], _techs: [] });
        byId[iid] = cur;
        out.push(cur);
      }
      cur.row_ids.push(r.id);
      var sev = Number(r.severity_score) || 0;
      if (sev > (Number(cur.severity_score) || 0)) cur.severity_score = sev;
      techList(r.technology).forEach(function (t) { if (cur._techs.indexOf(t) < 0) cur._techs.push(t); });
    });
    out.forEach(function (r) { r.technology = r._techs.join(', '); delete r._techs; });
    return out;
  }

  // Field names the pages were written against (the raw extraction's), filled
  // from the processed schema, with the processed fields kept alongside.
  function toRecord(entity, r) {
    var rec = Object.assign({}, r);
    rec.entity = entity;
    rec.record_id = r.id;
    rec.short_description = s(r.description);
    rec.long_description = s(r.long_description);
    rec.notes = s(r.notes);
    rec.county_fips = s(r.county_fips);
    if (entity === 'restrictions') {
      var jt = s(r.jurisdiction_type);
      var isCounty = !!COUNTY_TYPES[jt.toLowerCase()];
      rec.record_type = jt.toLowerCase() === 'state' ? 'state_restriction' : 'local_restriction';
      rec.jurisdiction_level = jt ? jt.toLowerCase() : 'local';
      rec.county = isCounty ? s(r.jurisdiction) : '';
      rec.municipality = isCounty ? '' : s(r.jurisdiction);
      rec.project_or_policy_name = [s(r.jurisdiction), s(r.restriction_type).replace(/_/g, ' ')]
        .filter(Boolean).join(' ');
      rec.policy_mechanism = s(r.restriction_type) + (s(r.mechanisms) ? ', ' + s(r.mechanisms) : '');
      rec.adopted_or_event_date_text = s(r.date_enacted_iso) || s(r.date_text);
      rec.scope = s(r.scope) || 'renewables_only';
      rec.has_litigation = '';
    } else if (entity === 'contested_projects') {
      rec.record_type = 'contested_project';
      rec.jurisdiction_level = 'project';
      rec.county = s(r.county);
      rec.municipality = s(r.municipality);
      rec.project_or_policy_name = s(r.project_name);
      rec.policy_mechanism = '';
      rec.adopted_or_event_date_text = s(r.event_date_text);
      rec.project_capacity_mw = r.capacity_mw;
      rec.project_area_acres = r.area_acres;
      rec.has_litigation = s(r.has_litigation).toLowerCase();
      rec.scope = 'renewables_only';
    } else {
      rec.record_type = 'case';
      rec.jurisdiction_level = s(r.court_level);
      rec.county = s(r.county);
      rec.municipality = '';
      rec.project_or_policy_name = s(r.case_name) || s(r.project_name);
      rec.policy_mechanism = '';
      rec.opposition_type = 'litigation';
      rec.adopted_or_event_date_text = '';
      rec.status = s(r.case_status) || 'unknown';
      rec.has_litigation = 'yes';
      rec.scope = 'renewables_only';
    }
    rec.technology = techList(rec.technology).join(', ');
    return rec;
  }

  // A case sits where the project it concerns sits: cases carry the project's
  // source_record_id but no county of their own.
  function placeCases(cases, projects) {
    var bySource = {};
    projects.forEach(function (p) { if (p.source_record_id) bySource[p.source_record_id] = p; });
    cases.forEach(function (c) {
      var p = bySource[c.source_record_id];
      if (!p) return;
      if (!c.county) c.county = p.county;
      if (!c.municipality) c.municipality = p.municipality;
      if (!c.county_fips) c.county_fips = p.county_fips;
    });
  }

  function fetchJson(url) {
    return fetch(url, { cache: 'no-store' }).then(function (res) {
      if (!res.ok) throw new Error('HTTP ' + res.status + ': ' + url);
      return res.json();
    });
  }

  function load() {
    return Promise.all(ENTITIES.map(function (e) { return fetchJson(BASE + e + '.json'); })
      .concat([fetchJson(METRICS_URL)]))
      .then(function (res) {
        var out = { metrics: res[3] };
        ENTITIES.forEach(function (e, i) {
          out[e] = instruments(res[i]).map(function (r) { return toRecord(e, r); });
        });
        placeCases(out.cases, out.contested_projects);
        return out;
      });
  }

  // Instrument counts for a set of records from instruments()/load().
  function tally(records) {
    var t = { renewables: 0, multi_sector: 0, projects: 0, cases: 0 };
    (records || []).forEach(function (r) {
      if (r.entity === 'restrictions') {
        if (r.scope === 'multi_sector_data_centers') t.multi_sector++;
        else t.renewables++;
      } else if (r.entity === 'contested_projects') t.projects++;
      else if (r.entity === 'cases') t.cases++;
    });
    return t;
  }

  // The published totals, exactly as headline_metrics.json states them.
  function headline(metrics) {
    var r = metrics.restrictions.by_scope;
    return {
      renewables: r.renewables_only.instruments,
      renewables_severe: r.renewables_only.severe_instruments,
      multi_sector: r.multi_sector_data_centers.instruments,
      multi_sector_severe: r.multi_sector_data_centers.severe_instruments,
      projects: metrics.contested_projects.projects,
      confirmed_outcomes: metrics.contested_projects.confirmed_outcomes,
      cases: metrics.cases.cases
    };
  }

  function fmt(n) { return new Intl.NumberFormat('en-US').format(n || 0); }

  // "390 renewables-only restrictions, 82 also covering data centers, ..."
  // Zero parts are left out; the two restriction scopes are never summed.
  function tallyText(t) {
    var parts = [];
    if (t.renewables) parts.push(fmt(t.renewables) + ' renewables-only ' + (t.renewables === 1 ? 'restriction' : 'restrictions'));
    if (t.multi_sector) parts.push(fmt(t.multi_sector) + ' also covering data centers');
    if (t.projects) parts.push(fmt(t.projects) + ' contested ' + (t.projects === 1 ? 'project' : 'projects'));
    if (t.cases) parts.push(fmt(t.cases) + ' ' + (t.cases === 1 ? 'case' : 'cases'));
    return parts.length ? parts.join(' · ') : 'No instruments';
  }

  var api = {
    BASE: BASE,
    ENTITIES: ENTITIES,
    METRICS_URL: METRICS_URL,
    SCOPE_LABELS: SCOPE_LABELS,
    instruments: instruments,
    toRecord: toRecord,
    load: load,
    tally: tally,
    headline: headline,
    tallyText: tallyText
  };
  global.ProcessedData = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);

/* national-dashboard.js
 *
 * The national, state and county views of the national database
 * (docs/national_database_design.md, phase 3). Everything it shows is read
 * from files scripts/build_database.py publishes:
 *
 *   data/processed/headline_metrics.json   the national numbers to quote
 *   data/db/state_summary.json             one row per state (v_state_summary)
 *   data/db/county_summary.json            one row per county (v_county_summary)
 *   data/db/state/<ST>.json                a state's records, for its state and county views
 *   data/geo/counties_2024.topojson        county shapes
 *   data/snapshots/manifest.csv            the date of the latest published data
 *   data/db/record_index.json              which state file holds each record
 *   data/db/worklists.json                 review worklist sizes (never their rows)
 *   data/db/manifest.json, data/db/parquet/ the downloads, and the SQL console's tables
 *   db/schema.sql                          the data dictionary
 *
 * Rules it keeps (README, "Counting and verification"):
 *   - counts are of instruments, never rows, and come from the files above,
 *     never recounted here;
 *   - restrictions that also cover data centers are a separate figure;
 *   - every count carries its verified share;
 *   - a county nobody has examined is drawn as "not examined", never as 0;
 *   - data center events are county context and never counted;
 *   - review candidates are never shown, only how many name a county.
 *
 * Text from the data goes into the page through textContent only.
 *
 * Routes (the hash is the state, so every view can be linked):
 *   #/                      national
 *   #/state/IA              a state
 *   #/county/19113          a county
 *   #/explore/<entity>      restrictions, projects or cases, with filters as ?st=&tech=&q=…
 *   #/restriction/<id>      one record (also #/project/<id>, #/case/<id>)
 *   #/coverage              coverage, verification and worklist sizes
 *   #/data                  downloads, data dictionary, example queries
 *   #/sql?q=<sql>           SQL console (loads DuckDB-WASM, only here)
 *   ?m=<metric>             the map metric, on the map routes
 */
(function () {
  'use strict';

  var PATHS = {
    metrics: './data/processed/headline_metrics.json',
    states: './data/db/state_summary.json',
    counties: './data/db/county_summary.json',
    topo: './data/geo/counties_2024.topojson',
    snapshots: './data/snapshots/manifest.csv',
    recordIndex: './data/db/record_index.json',
    worklists: './data/db/worklists.json',
    manifest: './data/db/manifest.json',
    timeline: './data/db/timeline.json',
    history: './data/db/history.json',
    schema: './db/schema.sql',
    state: function (st) { return './data/db/state/' + st + '.json'; }
  };

  // Map metrics: a v_county_summary column, or the coverage status itself.
  var METRICS = {
    severe_restrictions: { label: 'Severe restrictions', noun: 'severe restrictions (severity 3 or 4)' },
    restrictions: { label: 'All restrictions', noun: 'restrictions (renewables only)' },
    verified_restrictions: { label: 'Verified restrictions', noun: 'restrictions verified against the instrument or its minutes' },
    active_moratoria: { label: 'Active moratoria', noun: 'active or extended moratoria' },
    contested_projects: { label: 'Contested projects', noun: 'contested projects' },
    blocked_projects: { label: 'Blocked projects', noun: 'blocked projects (confirmed or not)' },
    coverage: { label: 'Coverage', noun: 'coverage' }
  };
  var DEFAULT_METRIC = 'severe_restrictions';
  // Fixed classes, so a shade means the same count on every view.
  var BINS = [
    { min: 1, max: 1, label: '1', fill: 'var(--map-c1)' },
    { min: 2, max: 4, label: '2–4', fill: 'var(--map-c2)' },
    { min: 5, max: 9, label: '5–9', fill: 'var(--map-c3)' },
    { min: 10, max: Infinity, label: '10 or more', fill: 'var(--map-c4)' }
  ];
  var NONE_FILL = 'var(--map-none)';
  var ZERO_FILL = 'var(--map-zero)';

  var COVERAGE_WORDS = {
    has_records: 'Has published records',
    checked_none: 'Checked, none found',
    not_examined: 'Not examined: nothing known either way'
  };
  // scripts/negative_checks.py GRADE_MEANING: how strong a "checked, none
  // found" search was, never how strong the county's case is.
  var GRADE_WORDS = {
    A: 'two or more kinds of source checked, not stale',
    B: 'one kind of source checked and not stale, or two or more but stale',
    C: 'one kind of source checked, stale',
    U: 'no source classed'
  };
  function today() { return new Date().toISOString().slice(0, 10); }

  // scripts/site_profile.py VERIFICATION_WORDS, so profiles and pages agree.
  var VERIFICATION_WORDS = {
    restriction: {
      verified: 'Verified against the instrument or the minutes that adopted it',
      located: 'Instrument located but not yet read, so not verified',
      unverified: 'Not verified: no instrument or minutes read, only a news article or compiled tracker'
    },
    project: {
      verified: 'Verified: backed by a news article or court record that was read',
      unverified: 'Not verified: rests on a compiled report or tracker only'
    }
  };
  var SEVERITY_WORDS = {
    4: 'explicit moratorium or ban', 3: 'likely de facto ban',
    2: 'material burden', 1: 'procedural friction'
  };
  var OUTCOME_WORDS = {
    blocked_confirmed: 'Blocked, confirmed', blocked_unverified: 'Blocked, not confirmed',
    advanced_confirmed: 'Advanced, confirmed', advanced_unverified: 'Advanced, not confirmed',
    restricted_conditional: 'Restricted by conditions', pending: 'Pending', needs_review: 'Needs review'
  };
  var CASE_WORDS = {
    pending: 'Pending', dismissed: 'Dismissed', ruled_for_developer: 'Ruled for the developer',
    ruled_for_opposition: 'Ruled for the opposition', settled: 'Settled', withdrawn: 'Withdrawn', '': 'Status not recorded'
  };
  var ROLE_WORDS = {
    primary_source: 'Instrument or minutes', compiled_source: 'Compiled from', ordinance: 'Ordinance (NREL)',
    outcome_evidence: 'Outcome source', placement: 'County placement', court_record: 'Court record'
  };
  var ACCESS_WORDS = { opened: 'read', archived: 'archived copy read', snippet: 'located, not yet read' };
  var ROWS_SHOWN = 100;

  var fmt = new Intl.NumberFormat('en-US');
  var cache = {};
  var base = null;       // national data, loaded once
  var mapGen = 0;        // numbers each map, for its title id

  // ── Small helpers ─────────────────────────────────────────────────────────

  function el(tag, attrs) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        var v = attrs[k];
        if (v === null || v === undefined || v === false) return;
        if (k === 'text') node.textContent = v;
        else if (k === 'class') node.className = v;
        else if (k.slice(0, 2) === 'on') node.addEventListener(k.slice(2), v);
        else node.setAttribute(k, v === true ? '' : v);
      });
    }
    for (var i = 2; i < arguments.length; i++) append(node, arguments[i]);
    return node;
  }
  function append(node, child) {
    if (child === null || child === undefined || child === false) return;
    if (Array.isArray(child)) { child.forEach(function (c) { append(node, c); }); return; }
    node.appendChild(typeof child === 'object' ? child : document.createTextNode(String(child)));
  }
  function n(v) { return fmt.format(v || 0); }
  function plural(count, one, many) { return n(count) + ' ' + (count === 1 ? one : (many || one + 's')); }
  function words(code) { return String(code || '').replace(/_/g, ' '); }
  function safeUrl(u) { return /^https?:\/\//i.test(String(u || '')) ? u : null; }
  function link(href, text) { return el('a', { href: href, text: text }); }

  function getJSON(path) {
    if (!cache[path]) {
      cache[path] = fetch(path).then(function (r) {
        if (!r.ok) throw new Error(path + ' (HTTP ' + r.status + ')');
        return r.json();
      });
    }
    return cache[path];
  }
  function getText(path) {
    return fetch(path).then(function (r) { return r.ok ? r.text() : ''; }).catch(function () { return ''; });
  }
  // {"columns": [...], "rows": [[...]]} -> objects
  function objects(t) {
    return t.rows.map(function (r) {
      var o = {};
      t.columns.forEach(function (c, i) { o[c] = r[i]; });
      return o;
    });
  }

  function setStatus(text, isError) {
    var s = document.getElementById('status');
    s.textContent = text || '';
    s.className = 'status' + (isError ? ' error' : '');
  }

  // ── Routing ───────────────────────────────────────────────────────────────

  var ENTITIES = { restrictions: 'restriction', projects: 'project', cases: 'case' };

  function parseRoute() {
    var h = location.hash.replace(/^#/, '') || '/';
    var q = '';
    var qi = h.indexOf('?');
    if (qi >= 0) { q = h.slice(qi + 1); h = h.slice(0, qi); }
    var params = new URLSearchParams(q);
    var metric = METRICS[params.get('m')] ? params.get('m') : DEFAULT_METRIC;
    var m;
    if ((m = /^\/state\/([A-Z]{2})$/.exec(h))) return { view: 'state', st: m[1], metric: metric };
    if ((m = /^\/county\/(\d{5})$/.exec(h))) return { view: 'county', fips: m[1], metric: metric };
    if ((m = /^\/explore(?:\/(restrictions|projects|cases))?$/.exec(h))) {
      return { view: 'explore', entity: m[1] || 'restrictions', params: params, metric: metric };
    }
    if ((m = /^\/(restriction|project|case)\/(.+)$/.exec(h))) {
      var id;
      try { id = decodeURIComponent(m[2]); } catch (e) { id = m[2]; }
      return { view: 'record', entity: m[1], id: id, metric: metric };
    }
    if (h === '/coverage') return { view: 'coverage', metric: metric };
    if (h === '/data') return { view: 'data', metric: metric };
    if (h === '/sql') return { view: 'sql', params: params, metric: metric };
    return { view: 'national', metric: metric };
  }
  function href(view, id, metric) {
    var m = metric && metric !== DEFAULT_METRIC ? '?m=' + metric : '';
    if (view === 'state') return '#/state/' + id + m;
    if (view === 'county') return '#/county/' + id + m;
    if (view === 'restriction' || view === 'project' || view === 'case') {
      return '#/' + view + '/' + encodeURIComponent(id);
    }
    return '#/' + m;
  }
  function recordLink(entity, id, text) { return link(href(entity, id), text); }

  // ── Loading ───────────────────────────────────────────────────────────────

  function loadBase() {
    if (base) return Promise.resolve(base);
    // The county shapes are context: if they fail, the maps say so and every
    // table still renders.
    var topo = getJSON(PATHS.topo).catch(function () { return null; });
    return Promise.all([getJSON(PATHS.metrics), getJSON(PATHS.states), getJSON(PATHS.counties),
                        topo, getText(PATHS.snapshots)])
      .then(function (r) {
        var counties = objects(r[2]);
        var byFips = {};
        counties.forEach(function (c) { byFips[c.county_fips] = c; });
        var states = objects(r[1]);
        var byState = {};
        states.forEach(function (s) { byState[s.state_code] = s; });
        var features = r[3] ? topojson.feature(r[3], r[3].objects.counties).features : [];
        var asOf = r[4].split('\n').slice(1).map(function (l) { return l.split(',')[0]; })
          .filter(function (d) { return /^\d{4}-\d{2}-\d{2}$/.test(d); }).sort().pop() || '';
        base = { metrics: r[0], states: states, byState: byState, counties: counties, byFips: byFips,
                 topo: r[3], geoError: !r[3], features: features, asOf: asOf };
        return base;
      });
  }

  // ── Map ───────────────────────────────────────────────────────────────────

  function binFor(v) {
    for (var i = 0; i < BINS.length; i++) if (v >= BINS[i].min && v <= BINS[i].max) return BINS[i];
    return null;
  }
  function fillFor(c, metric) {
    if (!c || c.coverage_status === 'not_examined') return NONE_FILL;
    if (metric === 'coverage') return c.coverage_status === 'has_records' ? 'var(--map-c3)' : ZERO_FILL;
    var v = c[metric] || 0;
    return v ? binFor(v).fill : ZERO_FILL;
  }
  function legendItems(metric) {
    var items = [{ fill: NONE_FILL, text: 'Not examined: nothing known either way' }];
    if (metric === 'coverage') {
      items.push({ fill: ZERO_FILL, text: 'Checked, none found' });
      items.push({ fill: 'var(--map-c3)', text: 'Has published records' });
    } else {
      items.push({ fill: ZERO_FILL, text: '0 recorded (county examined)' });
      BINS.forEach(function (b) { items.push({ fill: b.fill, text: b.label }); });
    }
    return items;
  }
  function tooltipLines(c, metric) {
    if (!c) return ['No summary for this county'];
    var lines = [];
    if (metric !== 'coverage' && c.coverage_status !== 'not_examined') {
      lines.push(n(c[metric]) + ' ' + METRICS[metric].noun);
    }
    lines.push(COVERAGE_WORDS[c.coverage_status] || c.coverage_status);
    if (c.coverage_status === 'has_records' && metric !== 'restrictions') {
      lines.push(plural(c.restrictions, 'restriction') + ', ' + plural(c.contested_projects, 'contested project'));
    }
    return lines;
  }

  // Draws counties (features) into box. opts.focus: a FIPS to outline;
  // opts.states: draw state borders. Clicking a county opens its profile.
  function drawMap(box, features, metric, opts) {
    opts = opts || {};
    var gen = ++mapGen;
    var W = 960, H = opts.height || 600;
    var drawable = features.filter(function (f) { return f.id.slice(0, 2) !== '72'; });
    box.textContent = '';
    if (base.geoError) {
      box.setAttribute('data-painted', '0');
      box.appendChild(el('p', { id: 'mapStatus', class: 'status error',
        text: 'County boundaries could not be loaded, so no map is drawn. Every figure is in the tables on this page.' }));
      return;
    }
    if (!drawable.length) {
      box.appendChild(el('p', { class: 'muted', text: 'No map is drawn for Puerto Rico; its counties are in the table below.' }));
      return;
    }
    var projection = d3.geoAlbersUsa().fitSize([W, H], { type: 'FeatureCollection', features: drawable });
    var path = d3.geoPath(projection);
    var NS = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    svg.setAttribute('role', 'img');
    var titleId = 'map-title-' + gen;
    svg.setAttribute('aria-labelledby', titleId);
    var title = document.createElementNS(NS, 'title');
    title.id = titleId;
    title.textContent = (opts.label || 'County map') + ': ' + METRICS[metric].label +
      '. Every value on the map is also in the table below.';
    svg.appendChild(title);
    var g = document.createElementNS(NS, 'g');
    var painted = 0;
    drawable.forEach(function (f) {
      var d = path(f);
      if (!d) return;
      var p = document.createElementNS(NS, 'path');
      p.setAttribute('d', d);
      p.setAttribute('class', 'county' + (opts.focus === f.id ? ' focus' : ''));
      p.setAttribute('data-fips', f.id);
      p.style.fill = fillFor(base.byFips[f.id], metric);
      g.appendChild(p);
      painted++;
    });
    svg.appendChild(g);
    if (opts.states) {
      var ids = {};
      drawable.forEach(function (f) { ids[f.id] = true; });
      var obj = { type: 'GeometryCollection', geometries: base.topo.objects.counties.geometries
        .filter(function (gm) { return ids[gm.id]; }) };
      var borders = document.createElementNS(NS, 'path');
      borders.setAttribute('class', 'states');
      borders.setAttribute('d', path(topojson.mesh(base.topo, obj, function (a, b) {
        return a !== b && a.id.slice(0, 2) !== b.id.slice(0, 2);
      })) || '');
      svg.appendChild(borders);
    }
    box.appendChild(svg);
    box.setAttribute('data-painted', String(painted));

    var tip = el('div', { class: 'tooltip', hidden: true, 'aria-hidden': 'true' });
    box.appendChild(tip);
    function show(evt) {
      var fips = evt.target && evt.target.getAttribute && evt.target.getAttribute('data-fips');
      if (!fips) { tip.hidden = true; return; }
      var c = base.byFips[fips];
      tip.textContent = '';
      tip.appendChild(el('strong', { text: c ? c.county_name + ', ' + c.state_code : fips }));
      tooltipLines(c, metric).forEach(function (l) { tip.appendChild(el('div', { text: l })); });
      var r = box.getBoundingClientRect();
      var x = evt.clientX - r.left + 14, y = evt.clientY - r.top + 14;
      tip.hidden = false;
      if (x + tip.offsetWidth > r.width) x = Math.max(0, evt.clientX - r.left - tip.offsetWidth - 14);
      tip.style.left = x + 'px';
      tip.style.top = y + 'px';
    }
    svg.addEventListener('pointermove', show);
    svg.addEventListener('pointerleave', function () { tip.hidden = true; });
    svg.addEventListener('click', function (evt) {
      var fips = evt.target.getAttribute && evt.target.getAttribute('data-fips');
      if (fips) location.hash = href('county', fips, metric);
    });
  }

  function mapCard(title, features, route, opts) {
    var box = el('div', { class: 'map-box', id: 'map' });
    var select = el('select', { id: 'metric', onchange: function () {
      var r = parseRoute();
      location.hash = href(r.view, r.st || r.fips, select.value);
    } });
    Object.keys(METRICS).forEach(function (k) {
      select.appendChild(el('option', { value: k, text: METRICS[k].label, selected: k === route.metric }));
    });
    var legend = el('ul', { class: 'legend', id: 'mapLegend', 'aria-label': 'Map legend' });
    legendItems(route.metric).forEach(function (it) {
      var sw = el('span', { class: 'swatch', 'aria-hidden': 'true' });
      sw.style.background = it.fill;
      legend.appendChild(el('li', null, sw, it.text));
    });
    var card = el('section', { class: 'card', 'aria-labelledby': 'mapHeading' },
      el('div', { class: 'card-head' },
        el('h2', { id: 'mapHeading', text: title }),
        el('label', { class: 'field', for: 'metric' }, 'Shade counties by', select)),
      box, legend,
      el('p', { class: 'map-note', text: 'Hover a county for its numbers; click it for its profile. Each county is placed by the records that name it.' }));
    // Draw after the card is in the document, so the box has a width.
    setTimeout(function () { drawMap(box, features, route.metric, opts); }, 0);
    return card;
  }

  // ── Tables ────────────────────────────────────────────────────────────────

  // cols: [{key, label, num, render(row) -> node|string, sort(row) -> value}]
  function sortableTable(caption, cols, rows, defaultKey) {
    var state = { key: defaultKey, dir: -1 };
    var tbody = el('tbody');
    var heads = cols.map(function (c) {
      var th = el('th', { scope: 'col', class: c.num ? 'num' : null });
      th.appendChild(el('button', { type: 'button', text: c.label, onclick: function () {
        state.dir = state.key === c.key ? -state.dir : (c.num ? -1 : 1);
        state.key = c.key;
        draw();
      } }));
      return th;
    });
    function value(c, r) { return c.sort ? c.sort(r) : r[c.key]; }
    function draw() {
      var col = cols.filter(function (c) { return c.key === state.key; })[0];
      var sorted = rows.slice().sort(function (a, b) {
        var x = value(col, a), y = value(col, b);
        if (x === y) return 0;
        return (x > y ? 1 : -1) * state.dir;
      });
      heads.forEach(function (th, i) {
        th.setAttribute('aria-sort', cols[i].key === state.key ? (state.dir > 0 ? 'ascending' : 'descending') : 'none');
      });
      tbody.textContent = '';
      sorted.forEach(function (r) {
        tbody.appendChild(el('tr', null, cols.map(function (c) {
          return el('td', { class: c.num ? 'num' : null }, c.render ? c.render(r) : (c.num ? n(r[c.key]) : r[c.key]));
        })));
      });
    }
    draw();
    return el('div', { class: 'table-wrap' },
      el('table', null, el('caption', { text: caption }), el('thead', null, el('tr', null, heads)), tbody));
  }

  // A plain table that shows ROWS_SHOWN rows and a button for the rest.
  function longTable(caption, headers, rows, renderRow, emptyText) {
    if (!rows.length) return el('p', { class: 'muted', text: emptyText });
    var tbody = el('tbody');
    var wrap = el('div', null, el('div', { class: 'table-wrap' },
      el('table', null, el('caption', { text: caption }),
        el('thead', null, el('tr', null, headers.map(function (h) {
          return el('th', { scope: 'col', class: h.num ? 'num' : null, text: h.label || h });
        }))), tbody)));
    function fill(limit) {
      tbody.textContent = '';
      rows.slice(0, limit).forEach(function (r) { tbody.appendChild(renderRow(r)); });
    }
    fill(ROWS_SHOWN);
    if (rows.length > ROWS_SHOWN) {
      var btn = el('button', { type: 'button', class: 'more', text: 'Show all ' + n(rows.length) + ' rows',
        onclick: function () { fill(rows.length); btn.remove(); } });
      wrap.appendChild(btn);
    }
    return wrap;
  }

  function verificationPill(kind, v) {
    var cls = v === 'verified' ? 'pill ok' : 'pill';
    var label = v === 'verified' ? 'verified' : v === 'located' ? 'located' : 'not verified';
    return el('span', { class: cls, title: VERIFICATION_WORDS[kind][v] || VERIFICATION_WORDS[kind].unverified, text: label });
  }

  // ── Shared pieces ─────────────────────────────────────────────────────────

  function tile(id, label, value, sub) {
    return el('div', { class: 'tile' },
      el('div', { class: 'label', text: label }),
      el('div', { class: 'value', id: id, text: value }),
      sub ? el('div', { class: 'sub', text: sub }) : null);
  }
  function crumbs(items) {
    return el('nav', { class: 'crumbs', 'aria-label': 'Breadcrumb' },
      el('ol', null, items.map(function (it, i) {
        return el('li', null, i === items.length - 1 ? el('span', { 'aria-current': 'page', text: it[0] }) : link(it[1], it[0]));
      })));
  }
  function stateName(st) { return (base.byState[st] || {}).state_name || st; }

  function evidenceList(evidence) {
    var items = (evidence || []).map(function (e) {
      var url = safeUrl(e.url);
      var access = e.access && ACCESS_WORDS[e.access] ? ' (' + ACCESS_WORDS[e.access] + ')' : '';
      return el('li', null, (ROLE_WORDS[e.role] || words(e.role)) + ': ',
        url ? el('a', { href: url, rel: 'noopener', text: shortUrl(url) }) : e.url, access);
    });
    return items.length ? el('ul', null, items) : el('span', { class: 'muted', text: 'none recorded' });
  }
  function shortUrl(u) {
    try {
      var x = new URL(u);
      var p = x.pathname.length > 32 ? x.pathname.slice(0, 30) + '…' : x.pathname;
      return x.hostname.replace(/^www\./, '') + p;
    } catch (e) { return u; }
  }

  function restrictionRecord(r) {
    var types = (r.restriction_types || []).map(words).join(', ');
    var title = (r.jurisdiction_name || 'Unnamed jurisdiction') + ': ' + types;
    return el('article', { class: 'record' },
      el('h3', null, recordLink('restriction', r.instrument_id, title)),
      el('p', null, verificationPill('restriction', r.verification), ' ',
        r.scope === 'multi_sector_data_centers' ? el('span', { class: 'pill warn', text: 'also covers data centers' }) : null),
      r.description ? el('p', { text: r.description }) : null,
      el('dl', null,
        el('dt', { text: 'Technologies' }), el('dd', { text: (r.technologies || []).map(words).join(', ') }),
        el('dt', { text: 'Status' }), el('dd', { text: words(r.status || 'not recorded') }),
        el('dt', { text: 'Severity' }), el('dd', { text: r.severity_score ? r.severity_score + ' of 4: ' +
          SEVERITY_WORDS[r.severity_score] + (r.severity_basis ? ' (' + r.severity_basis + ')' : '') : 'not scored' }),
        el('dt', { text: 'Enacted' }), el('dd', { text: r.date_enacted_iso || r.date_text || 'date not recorded' }),
        el('dt', { text: 'Evidence' }), el('dd', { text: VERIFICATION_WORDS.restriction[r.verification] ||
          VERIFICATION_WORDS.restriction.unverified }),
        el('dt', { text: 'Sources' }), el('dd', null, evidenceList(r.evidence))));
  }

  function projectRecord(p, casesById) {
    var cases = (p.cases || []).map(function (id) { return casesById[id]; }).filter(Boolean);
    return el('article', { class: 'record' },
      el('h3', null, recordLink('project', p.instrument_id, p.project_name || 'Unnamed project')),
      el('p', null, verificationPill('project', p.verification), ' ',
        el('span', { class: 'pill', text: OUTCOME_WORDS[p.outcome] || words(p.outcome) })),
      p.description ? el('p', { text: p.description }) : null,
      el('dl', null,
        el('dt', { text: 'Technologies' }), el('dd', { text: (p.technologies || []).map(words).join(', ') }),
        p.capacity_mw_text ? [el('dt', { text: 'Capacity' }), el('dd', { text: p.capacity_mw_text + (/mw/i.test(p.capacity_mw_text) ? '' : ' MW') })] : null,
        p.event_date_text ? [el('dt', { text: 'Date' }), el('dd', { text: p.event_date_text })] : null,
        el('dt', { text: 'Evidence' }), el('dd', { text: VERIFICATION_WORDS.project[p.verification] ||
          VERIFICATION_WORDS.project.unverified }),
        (p.groups || []).length ? [el('dt', { text: 'Groups named' }), el('dd', { text: p.groups.join('; ') })] : null,
        cases.length ? [el('dt', { text: 'Court cases' }), el('dd', null, el('ul', null, cases.map(function (k) {
          var u = safeUrl(k.case_source_url);
          return el('li', null, u ? el('a', { href: u, rel: 'noopener', text: k.case_name || 'Case' }) : (k.case_name || 'Case'),
            ' · ' + (k.court || 'court not recorded') + ' · ' + (CASE_WORDS[k.case_status || ''] || words(k.case_status)));
        })))] : null,
        el('dt', { text: 'Sources' }), el('dd', null, evidenceList(p.evidence))));
  }

  // ── National view ─────────────────────────────────────────────────────────

  function renderNational(route) {
    var M = base.metrics;
    var ren = M.restrictions.by_scope.renewables_only;
    var multi = M.restrictions.by_scope.multi_sector_data_centers;
    var P = M.contested_projects;
    var blocked = (P.by_outcome.blocked_confirmed || 0) + (P.by_outcome.blocked_unverified || 0);
    var cov = M.county_coverage;
    var view = el('div', { class: 'stack' });

    view.appendChild(el('div', null,
      el('h1', { text: 'Opposition to renewable energy, nationwide' }),
      el('p', { class: 'lede', text: 'Local laws that restrict wind, solar and battery storage, the projects that met organized opposition, and the court cases about them, by state and county. Every figure shows how much of it has been verified.' })));

    view.appendChild(el('div', { class: 'tiles' },
      tile('headlineRestrictions', 'Restrictions on renewables', n(ren.instruments),
        n((ren.by_verification || {}).verified) + ' verified against the instrument · ' + n(multi.instruments) + ' more also cover data centers'),
      tile('headlineSevere', 'Severe restrictions', n(ren.severe_instruments),
        'severity 3 or 4: a likely or explicit ban or moratorium, in ' + n(ren.states) + ' states'),
      tile('headlineProjects', 'Contested projects', n(P.projects),
        n(blocked) + ' blocked (' + n(P.by_outcome.blocked_confirmed) + ' confirmed) · ' + n((P.by_verification || {}).verified) + ' verified'),
      tile('headlineCases', 'Court cases', n(M.cases.cases),
        n((M.cases.by_verification || {}).verified) + ' with a court record'),
      tile('headlineCoverage', 'Counties examined', n(cov.with_any_record + cov.with_negative_check_and_no_record) + ' of ' + n(cov.counties),
        n(cov.with_neither) + ' not examined: nothing known either way')));

    view.appendChild(mapCard('Counties', base.features, route, { states: true, label: 'United States counties', height: 600 }));

    var stateRows = base.states.filter(function (s) { return s.state_code !== 'PR' || s.restrictions || s.contested_projects; });
    var cols = [
      { key: 'state_name', label: 'State', render: function (s) { return link(href('state', s.state_code, route.metric), s.state_name); } },
      { key: 'restrictions', label: 'Restrictions', num: true },
      { key: 'severe_restrictions', label: 'Severe', num: true },
      { key: 'verified_restrictions', label: 'Verified', num: true },
      { key: 'multi_sector_restrictions', label: 'Also cover data centers', num: true },
      { key: 'contested_projects', label: 'Contested projects', num: true },
      { key: 'blocked_projects', label: 'Blocked', num: true },
      { key: 'cases', label: 'Cases', num: true },
      { key: 'counties_not_examined', label: 'Counties not examined', num: true,
        render: function (s) { return n(s.counties_not_examined) + ' of ' + n(s.counties); },
        sort: function (s) { return s.counties ? s.counties_not_examined / s.counties : 0; } }
    ];
    view.appendChild(el('section', { class: 'card', 'aria-labelledby': 'statesHeading' },
      el('h2', { id: 'statesHeading', text: 'States' }),
      sortableTable('Restrictions count renewables-only instruments; verified means checked against the instrument or the minutes that adopted it. Select a column heading to sort.',
        cols, stateRows, 'restrictions')));

    view.appendChild(historyCard());
    view.appendChild(timelineCard());
    view.appendChild(sourcesCard(M));
    return view;
  }

  // ── History ───────────────────────────────────────────────────────────────

  // headline_history: the headline figures as each data build published
  // them, one row per day on which they changed. Each figure has its own
  // scale, so each gets its own small chart (never two on one axis).
  var HISTORY_FIGURES = [
    { key: 'restrictions', label: 'Restrictions on renewables' },
    { key: 'verified_restrictions', label: 'Verified restrictions' },
    { key: 'contested_projects', label: 'Contested projects' },
    { key: 'counties_with_records', label: 'Counties with records' }
  ];

  function historyCard() {
    var grid = el('div', { class: 'tiles', id: 'history' });
    var change = el('p', { id: 'historyChange', class: 'small' });
    var table = el('div');
    var card = el('section', { class: 'card', 'aria-labelledby': 'historyHeading' },
      el('h2', { id: 'historyHeading', text: 'How the figures have changed' }),
      el('p', { class: 'muted small', text: 'The headline figures as each data build published them, on each day they changed. A jump can mean a source was added (NREL\'s ordinance databases arrived on 2026-10-09), not that restrictions were passed that day.' }),
      change, grid, table);
    getJSON(PATHS.history).then(function (t) { drawHistory(grid, change, table, objects(t)); })
      .catch(function () { grid.appendChild(el('p', { class: 'muted', text: 'The history could not be loaded.' })); });
    return card;
  }

  function drawHistory(grid, change, table, rows) {
    if (!rows.length) { grid.appendChild(el('p', { class: 'muted', text: 'No history is recorded yet.' })); return; }
    var last = rows[rows.length - 1], prev = rows.length > 1 ? rows[rows.length - 2] : null;
    if (prev) {
      var parts = HISTORY_FIGURES.filter(function (f) { return prev[f.key] !== null && last[f.key] !== prev[f.key]; })
        .map(function (f) {
          var d = last[f.key] - prev[f.key];
          return (d > 0 ? '+' : '−') + n(Math.abs(d)) + ' ' + f.label.toLowerCase();
        });
      change.textContent = 'Since the build of ' + prev.date + ': ' + (parts.length ? parts.join(', ') : 'none of these changed') +
        ' (as of ' + last.date + ').';
    }
    var NS = 'http://www.w3.org/2000/svg';
    var t0 = Date.parse(rows[0].date), t1 = Date.parse(last.date);
    HISTORY_FIGURES.forEach(function (f) {
      var pts = rows.filter(function (r) { return r[f.key] !== null && r[f.key] !== undefined; });
      var cell = el('div', { class: 'tile' }, el('div', { class: 'label', text: f.label }),
        el('div', { class: 'value', text: last[f.key] === null ? 'not recorded' : n(last[f.key]) }));
      if (pts.length) {
        var W = 240, H = 64, P = 6;
        var lo = Math.min.apply(null, pts.map(function (r) { return r[f.key]; }));
        var hi = Math.max.apply(null, pts.map(function (r) { return r[f.key]; }));
        if (hi === lo) { hi = lo + 1; }
        var x = function (r) { return P + (W - 2 * P) * (t1 === t0 ? 1 : (Date.parse(r.date) - t0) / (t1 - t0)); };
        var y = function (v) { return H - P - (H - 2 * P) * (v - lo) / (hi - lo); };
        var svg = document.createElementNS(NS, 'svg');
        svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
        svg.setAttribute('role', 'img');
        svg.setAttribute('aria-label', f.label + ': ' + n(pts[0][f.key]) + ' on ' + pts[0].date + ' to ' +
          n(last[f.key]) + ' on ' + last.date + '. Every value is in the table below.');
        // Steps, not slopes: a figure holds until the next build changes it.
        var d = '';
        pts.forEach(function (r, i) {
          d += (i ? 'H' + x(r).toFixed(1) + 'V' : 'M' + x(r).toFixed(1) + ',') + y(r[f.key]).toFixed(1);
        });
        var line = document.createElementNS(NS, 'path');
        line.setAttribute('d', d + 'H' + (W - P));
        line.setAttribute('fill', 'none');
        line.setAttribute('stroke', 'var(--series-1)');
        line.setAttribute('stroke-width', '2');
        svg.appendChild(line);
        pts.forEach(function (r) {
          var c = document.createElementNS(NS, 'circle');
          c.setAttribute('cx', x(r).toFixed(1));
          c.setAttribute('cy', y(r[f.key]).toFixed(1));
          c.setAttribute('r', '4');
          c.setAttribute('fill', 'var(--series-1)');
          c.setAttribute('stroke', 'var(--color-surface)');
          c.setAttribute('stroke-width', '2');
          var tt = document.createElementNS(NS, 'title');
          tt.textContent = r.date + ': ' + n(r[f.key]);
          c.appendChild(tt);
          svg.appendChild(c);
        });
        cell.appendChild(el('div', { class: 'chart-box' }, svg));
        cell.appendChild(el('div', { class: 'sub', text: (pts[0].date === rows[0].date ? 'since ' : 'recorded since ') +
          pts[0].date + ': ' + n(pts[0][f.key]) }));
      }
      grid.appendChild(cell);
    });
    table.appendChild(el('details', null, el('summary', { text: 'Show the numbers' }),
      el('div', { class: 'table-wrap' }, el('table', { id: 'historyTable' },
        el('caption', { text: 'Headline figures on each day they changed (blank: not recorded yet)' }),
        el('thead', null, el('tr', null, el('th', { scope: 'col', text: 'Date' }),
          HISTORY_FIGURES.map(function (f) { return el('th', { scope: 'col', class: 'num', text: f.label }); }))),
        el('tbody', null, rows.map(function (r) {
          return el('tr', null, el('td', { text: r.date }), HISTORY_FIGURES.map(function (f) {
            return el('td', { class: 'num', text: r[f.key] === null ? '' : n(r[f.key]) });
          }));
        }))))));
  }

  // ── Timeline ──────────────────────────────────────────────────────────────

  // v_restrictions_by_year: one basis per instrument. Bottom to top in each
  // bar, in the order the build prefers them.
  var BASES = [
    { key: 'enacted', label: 'Enactment date', color: 'var(--series-1)',
      note: 'the date the instrument was enacted (Moratorium Nation, review queue)' },
    { key: 'ordinance_year', label: 'NREL ordinance year', color: 'var(--series-3)',
      note: 'the year of the ordinance version NREL read, which can be an amendment' },
    { key: 'year_reported', label: 'Year the report gives', color: 'var(--series-2)',
      note: 'the year in the Sabin report\'s entry' }
  ];

  function timelineCard() {
    var box = el('div', { class: 'chart-box', id: 'timeline' });
    var legend = el('ul', { class: 'legend', id: 'timelineLegend', 'aria-label': 'Timeline legend' });
    var table = el('div');
    var card = el('section', { class: 'card', 'aria-labelledby': 'timelineHeading' },
      el('h2', { id: 'timelineHeading', text: 'When the restrictions date from' }),
      el('p', { class: 'muted small', text: 'Renewables-only restrictions by year, as each source dates them. The three kinds of year are not the same measurement, so each keeps its own color. The latest year is not over yet.' }),
      box, legend, table);
    getJSON(PATHS.timeline).then(function (t) {
      drawTimeline(box, legend, table, objects(t).filter(function (r) { return r.scope === 'renewables_only'; }));
    }).catch(function () {
      box.appendChild(el('p', { class: 'muted', text: 'The timeline could not be loaded.' }));
    });
    return card;
  }

  function drawTimeline(box, legend, table, rows) {
    var byYear = {};
    var totals = {};
    var undated = 0;
    rows.forEach(function (r) {
      if (r.basis === 'undated') { undated += r.instruments; return; }
      (byYear[r.year] = byYear[r.year] || {})[r.basis] = r.instruments;
      totals[r.basis] = (totals[r.basis] || 0) + r.instruments;
    });
    var years = Object.keys(byYear).map(Number).sort(function (a, b) { return a - b; });
    if (!years.length) { box.appendChild(el('p', { class: 'muted', text: 'No restriction is dated.' })); return; }
    var all = [];
    for (var y = years[0]; y <= years[years.length - 1]; y++) all.push(y);
    var sum = function (y) { var v = byYear[y] || {}; return BASES.reduce(function (t, b) { return t + (v[b.key] || 0); }, 0); };
    var max = Math.max.apply(null, all.map(sum));
    var step = Math.pow(10, Math.floor(Math.log10(max)));
    var top = Math.ceil(max / step) * step;
    if (top / step < 4) { step = step / 2; top = Math.ceil(max / step) * step; }

    var W = 960, H = 300, L = 44, R = 8, T = 10, B = 28;
    var NS = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', 'Stacked bars of restrictions by year, ' + all[0] + ' to ' + all[all.length - 1] +
      '. The numbers are in the table below.');
    var band = (W - L - R) / all.length;
    var bw = Math.max(2, band * 0.72);
    var yScale = function (v) { return T + (H - T - B) * (1 - v / top); };
    function node(tag, attrs) {
      var e = document.createElementNS(NS, tag);
      Object.keys(attrs).forEach(function (k) { e.setAttribute(k, attrs[k]); });
      return e;
    }
    var grid = node('g', { class: 'grid' });
    var axis = node('g', { class: 'axis' });
    for (var v = 0; v <= top + 1e-9; v += step) {
      var yy = yScale(v);
      if (v > 0) grid.appendChild(node('line', { x1: L, x2: W - R, y1: yy, y2: yy }));
      var lab = node('text', { x: L - 6, y: yy + 4, 'text-anchor': 'end' });
      lab.textContent = n(v);
      axis.appendChild(lab);
    }
    all.forEach(function (yr, i) {
      // The last year is labelled too, unless a five-year label sits too close.
      if (yr % 5 === 0 || (i === all.length - 1 && yr % 5 > 2)) {
        var t = node('text', { x: L + band * i + band / 2, y: H - 8, 'text-anchor': 'middle' });
        t.textContent = String(yr);
        axis.appendChild(t);
      }
    });
    svg.appendChild(grid);
    svg.appendChild(axis);
    var bars = node('g', {});
    all.forEach(function (yr, i) {
      var x = L + band * i + (band - bw) / 2;
      var base = 0;
      var stack = BASES.filter(function (b) { return (byYear[yr] || {})[b.key]; });
      stack.forEach(function (b, j) {
        var val = byYear[yr][b.key];
        var y0 = yScale(base), y1 = yScale(base + val);
        var h = Math.max(1, y0 - y1 - (j > 0 ? 2 : 0));
        var yTop = y0 - (j > 0 ? 2 : 0) - h;
        var seg;
        if (j === stack.length - 1) {
          // The bar's data end is rounded; its baseline end stays square.
          var r = Math.min(4, bw / 2, h);
          seg = node('path', { d: 'M' + x + ',' + (yTop + h) + 'V' + (yTop + r) + 'Q' + x + ',' + yTop + ' ' + (x + r) + ',' + yTop +
            'H' + (x + bw - r) + 'Q' + (x + bw) + ',' + yTop + ' ' + (x + bw) + ',' + (yTop + r) + 'V' + (yTop + h) + 'Z' });
        } else {
          seg = node('rect', { x: x, y: yTop, width: bw, height: h });
        }
        seg.setAttribute('class', 'seg');
        seg.style.fill = b.color;
        seg.setAttribute('data-year', yr);
        seg.setAttribute('data-basis', b.key);
        bars.appendChild(seg);
        base += val;
      });
    });
    svg.appendChild(bars);
    svg.appendChild(node('line', { class: 'baseline', x1: L, x2: W - R, y1: yScale(0), y2: yScale(0) }));
    box.appendChild(svg);

    var tip = el('div', { class: 'tooltip', hidden: true, 'aria-hidden': 'true' });
    box.appendChild(tip);
    svg.addEventListener('pointermove', function (evt) {
      var t = evt.target;
      var yr = t.getAttribute && t.getAttribute('data-year');
      if (!yr) { tip.hidden = true; return; }
      var b = BASES.filter(function (x) { return x.key === t.getAttribute('data-basis'); })[0];
      tip.textContent = '';
      tip.appendChild(el('strong', { text: n(byYear[yr][b.key]) + ' dated by ' + b.label.toLowerCase() }));
      tip.appendChild(el('div', { text: yr + ' · ' + n(sum(yr)) + ' in all that year' }));
      var rect = box.getBoundingClientRect();
      var x = evt.clientX - rect.left + 12;
      tip.hidden = false;
      if (x + tip.offsetWidth > rect.width) x = Math.max(0, evt.clientX - rect.left - tip.offsetWidth - 12);
      tip.style.left = x + 'px';
      tip.style.top = (evt.clientY - rect.top + 12) + 'px';
    });
    svg.addEventListener('pointerleave', function () { tip.hidden = true; });

    BASES.forEach(function (b) {
      var key = el('span', { class: 'line-key', 'aria-hidden': 'true' });
      key.style.background = b.color;
      legend.appendChild(el('li', { title: b.note }, key, b.label + ': ' + n(totals[b.key] || 0)));
    });
    legend.appendChild(el('li', { id: 'timelineUndated' }, 'Undated: ' + n(undated) + ' (no year in any source)'));

    table.appendChild(el('details', null, el('summary', { text: 'Show the numbers' }),
      el('div', { class: 'table-wrap' }, el('table', { id: 'timelineTable' },
        el('caption', { text: 'Renewables-only restrictions by year and how the year is known' }),
        el('thead', null, el('tr', null, el('th', { scope: 'col', text: 'Year' }),
          BASES.map(function (b) { return el('th', { scope: 'col', class: 'num', text: b.label }); }),
          el('th', { scope: 'col', class: 'num', text: 'All' }))),
        el('tbody', null, all.filter(function (y) { return sum(y); }).map(function (yr) {
          return el('tr', null, el('td', { text: String(yr) }),
            BASES.map(function (b) { return el('td', { class: 'num', text: n((byYear[yr] || {})[b.key] || 0) }); }),
            el('td', { class: 'num', text: n(sum(yr)) }));
        }))))));
  }

  function sourcesCard(M) {
    var rows = [];
    Object.keys(M.restrictions.by_source).forEach(function (src) {
      var s = M.restrictions.by_source[src];
      rows.push({ entity: 'Restrictions', src: src, count: s.instruments, verified: (s.by_verification || {}).verified || 0 });
    });
    Object.keys(M.contested_projects.by_source).forEach(function (src) {
      var s = M.contested_projects.by_source[src];
      rows.push({ entity: 'Contested projects', src: src, count: s.instruments, verified: (s.by_verification || {}).verified || 0 });
    });
    var max = Math.max.apply(null, rows.map(function (r) { return r.count; }));
    return el('section', { class: 'card', 'aria-labelledby': 'sourcesHeading' },
      el('h2', { id: 'sourcesHeading', text: 'Where the records come from' }),
      el('p', { class: 'muted small', text: 'Most records come from compiled sources: a report, a tracker or NREL\'s ordinance database. Each is verified only once someone reads the instrument itself.' }),
      el('div', { class: 'table-wrap' }, el('table', { id: 'sourcesTable' },
        el('caption', { text: 'Records by source, and how many of them are verified' }),
        el('thead', null, el('tr', null,
          el('th', { scope: 'col', text: 'Records' }), el('th', { scope: 'col', text: 'Source' }),
          el('th', { scope: 'col', class: 'num', text: 'Count' }), el('th', { scope: 'col', class: 'num', text: 'Verified' }))),
        el('tbody', null, rows.map(function (r) {
          var bar = el('span', { class: 'bar', 'aria-hidden': 'true' });
          bar.style.width = Math.max(2, Math.round(120 * r.count / max)) + 'px';
          return el('tr', null, el('td', { text: r.entity }), el('td', { text: r.src }),
            el('td', { class: 'num' }, bar, n(r.count)),
            el('td', { class: 'num', text: n(r.verified) + ' (' + (r.count ? Math.round(100 * r.verified / r.count) : 0) + '%)' }));
        })))));
  }

  // ── State view ────────────────────────────────────────────────────────────

  function renderState(route, detail) {
    var st = route.st;
    var s = base.byState[st];
    if (!s) throw new Error('No state ' + st + ' in the national database');
    var view = el('div', { class: 'stack' });
    view.appendChild(el('div', null,
      crumbs([['National', href('national', null, route.metric)], [s.state_name]]),
      el('h1', { text: s.state_name }),
      el('p', { class: 'lede', text: 'Restrictions, contested projects and cases recorded in ' + s.state_name + ', and which of its counties have been examined.' })));

    view.appendChild(el('div', { class: 'tiles' },
      tile('stateRestrictions', 'Restrictions on renewables', n(s.restrictions),
        n(s.verified_restrictions) + ' verified · ' + n(s.multi_sector_restrictions) + ' more also cover data centers'),
      tile('stateSevere', 'Severe restrictions', n(s.severe_restrictions), 'severity 3 or 4'),
      tile('stateProjects', 'Contested projects', n(s.contested_projects),
        n(s.blocked_projects) + ' blocked · ' + n(s.confirmed_outcomes) + ' outcomes confirmed'),
      tile('stateCases', 'Court cases', n(s.cases)),
      tile('stateCoverage', 'Counties examined', n(s.counties - s.counties_not_examined) + ' of ' + n(s.counties),
        n(s.counties_not_examined) + ' not examined')));

    view.appendChild(frameworkCard(detail, s.state_name));

    var feats = base.features.filter(function (f) { return f.id.slice(0, 2) === stateFips(st); });
    view.appendChild(mapCard('Counties of ' + s.state_name, feats, route, { label: s.state_name + ' counties', height: 560 }));

    var counties = base.counties.filter(function (c) { return c.state_code === st; });
    view.appendChild(el('section', { class: 'card', 'aria-labelledby': 'countiesHeading' },
      el('h2', { id: 'countiesHeading', text: 'Counties' }),
      sortableTable('Every county in ' + s.state_name + '. Select a column heading to sort.', [
        { key: 'county_name', label: 'County', render: function (c) { return link(href('county', c.county_fips, route.metric), c.county_name); } },
        { key: 'coverage_status', label: 'Coverage', render: function (c) { return COVERAGE_WORDS[c.coverage_status]; } },
        { key: 'restrictions', label: 'Restrictions', num: true },
        { key: 'severe_restrictions', label: 'Severe', num: true },
        { key: 'verified_restrictions', label: 'Verified', num: true },
        { key: 'contested_projects', label: 'Projects', num: true },
        { key: 'blocked_projects', label: 'Blocked', num: true },
        { key: 'siting_standard_rows', label: 'NREL standards', num: true },
        { key: 'data_center_events', label: 'Data center events', num: true }
      ], counties, 'restrictions')));

    var ren = detail.restrictions.filter(function (r) { return r.scope === 'renewables_only' && r.state_code === st; });
    var multi = detail.restrictions.filter(function (r) { return r.scope !== 'renewables_only' && r.state_code === st; });
    var countyName = function (fips) { var c = base.byFips[fips]; return c ? c.county_name : fips; };
    function restrictionRow(r) {
      var f = (r.counties || [])[0];
      return el('tr', null,
        el('td', null, recordLink('restriction', r.instrument_id, r.jurisdiction_name || 'not named')),
        el('td', null, f ? link(href('county', f, route.metric), countyName(f)) : el('span', { class: 'muted', text: 'not placed' })),
        el('td', { text: (r.restriction_types || []).map(words).join(', ') }),
        el('td', { text: (r.technologies || []).map(words).join(', ') }),
        el('td', { text: words(r.status || '') }),
        el('td', { class: 'num', text: r.severity_score || '' }),
        el('td', null, verificationPill('restriction', r.verification)),
        el('td', { text: r.source_family }));
    }
    var heads = ['Jurisdiction', 'County', 'Type', 'Technologies', 'Status', { label: 'Severity', num: true }, 'Evidence', 'Source'];
    view.appendChild(el('section', { class: 'card', 'aria-labelledby': 'restrictionsHeading' },
      el('h2', { id: 'restrictionsHeading', text: 'Restrictions (' + n(ren.length) + ')' }),
      longTable('Renewables-only restrictions, one row per instrument', heads, ren, restrictionRow,
        'No restriction on renewables is recorded for ' + s.state_name + '.'),
      multi.length ? el('h3', { style: 'margin-top:1.5rem', text: 'Also covering data centers (' + n(multi.length) + ', counted separately)' }) : null,
      multi.length ? longTable('Restrictions that also cover data centers', heads, multi, restrictionRow, '') : null));

    var projects = detail.projects.filter(function (p) { return p.state_code === st; });
    view.appendChild(el('section', { class: 'card', 'aria-labelledby': 'projectsHeading' },
      el('h2', { id: 'projectsHeading', text: 'Contested projects (' + n(projects.length) + ')' }),
      longTable('One row per project', ['Project', 'County', 'Technologies', 'Outcome', 'Evidence', 'Cases'], projects, function (p) {
        var f = (p.counties || [])[0];
        return el('tr', null,
          el('td', null, recordLink('project', p.instrument_id, p.project_name || 'not named')),
          el('td', null, f ? link(href('county', f, route.metric), countyName(f)) : el('span', { class: 'muted', text: 'not placed' })),
          el('td', { text: (p.technologies || []).map(words).join(', ') }),
          el('td', { text: OUTCOME_WORDS[p.outcome] || words(p.outcome) }),
          el('td', null, verificationPill('project', p.verification)),
          el('td', { class: 'num', text: (p.cases || []).length || '' }));
      }, 'No contested project is recorded for ' + s.state_name + '.')));

    view.appendChild(el('section', { class: 'card', 'aria-labelledby': 'casesHeading' },
      el('h2', { id: 'casesHeading', text: 'Court cases (' + n(detail.cases.length) + ')' }),
      longTable('Cases with a court record', ['Case', 'Court', 'Status'], detail.cases, function (k) {
        return el('tr', null,
          el('td', null, recordLink('case', k.instrument_id, k.case_name || 'Case')),
          el('td', { text: (k.court || '') + (k.court_level ? ' (' + words(k.court_level) + ')' : '') }),
          el('td', { text: CASE_WORDS[k.case_status || ''] || words(k.case_status) }));
      }, 'No court case is recorded for ' + s.state_name + '.')));
    return view;
  }

  function frameworkCard(detail, name) {
    var policies = detail.policies || [];
    return el('section', { class: 'card', 'aria-labelledby': 'frameworkHeading' },
      el('h2', { id: 'frameworkHeading', text: 'State siting law' }),
      policies.length ? el('div', { class: 'records' }, policies.map(function (p) {
        var u = safeUrl(p.statute_url);
        return el('article', { class: 'record' },
          el('h3', { text: words(p.policy_type) + (p.technology ? ' (' + words(p.technology) + ')' : '') }),
          p.summary ? el('p', { text: p.summary }) : null,
          el('p', { class: 'small muted' }, p.who_decides ? 'Who decides: ' + p.who_decides + '. ' : '',
            u ? el('a', { href: u, rel: 'noopener', text: p.statute_citation || 'statute' }) : (p.statute_citation || ''),
            ' · ' + (p.verification === 'verified' ? 'verified against the statute' : 'not verified')));
      })) : el('p', { class: 'muted', text: 'Not yet researched: no state siting law for ' + name + ' has been verified against the statute.' }));
  }

  function stateFips(st) {
    var c = base.counties.filter(function (x) { return x.state_code === st; })[0];
    return c ? c.county_fips.slice(0, 2) : '';
  }

  // ── County view ───────────────────────────────────────────────────────────

  function renderCounty(route, detail) {
    var c = base.byFips[route.fips];
    if (!c) throw new Error('No county ' + route.fips + ' in the national database');
    var sname = stateName(c.state_code);
    var here = function (r) { return (r.counties || []).indexOf(c.county_fips) >= 0; };
    var restrictions = detail.restrictions.filter(here);
    var ren = restrictions.filter(function (r) { return r.scope === 'renewables_only'; });
    var multi = restrictions.filter(function (r) { return r.scope !== 'renewables_only'; });
    var projects = detail.projects.filter(here);
    var standards = detail.siting_standards.filter(here);
    var dc = detail.data_center_events.filter(function (e) { return e.county_fips === c.county_fips; });
    // A drafted check counts only once someone else has reviewed it.
    var checks = detail.negative_checks.filter(function (k) { return k.county_fips === c.county_fips && !k.held; });
    var casesById = {};
    detail.cases.forEach(function (k) { casesById[k.instrument_id] = k; });
    var county = (detail.counties || []).filter(function (x) { return x.county_fips === c.county_fips; })[0] || {};

    var view = el('div', { class: 'stack' });
    view.appendChild(el('div', null,
      crumbs([['National', href('national', null, route.metric)], [sname, href('state', c.state_code, route.metric)], [c.county_name]]),
      el('h1', { text: c.county_name + ', ' + sname }),
      el('p', { class: 'lede', text: 'Everything the national database records about this county. Descriptive only: no scores and no predictions.' })));

    var bannerText;
    if (c.coverage_status === 'not_examined') {
      bannerText = 'Not examined. Nobody has searched this county\'s records yet, so an empty profile means nothing is known, not that nothing happened.';
    } else if (c.coverage_status === 'checked_none') {
      var k = checks[checks.length - 1];
      bannerText = k ? 'Checked on ' + k.checked_on + ', none found' +
        (k.governments_checked ? ', covering ' + k.governments_checked : '') + '. Searched: ' +
        (k.sources_checked || []).join('; ') + '. Evidence grade ' + k.grade + ' (' + (GRADE_WORDS[k.grade] || '') + '); ' +
        (k.recheck_by && k.recheck_by < today() ? 'due to be checked again since ' : 'check again by ') + k.recheck_by + '.'
        : 'Checked, none found.';
    } else {
      bannerText = 'Published records are placed in this county.' + (checks.length ? ' Last negative check: ' + checks[checks.length - 1].checked_on + '.' : '');
    }
    view.appendChild(el('div', { id: 'coverageBanner', class: 'status banner' + (c.coverage_status === 'has_records' ? '' : ' none'), text: bannerText }));

    view.appendChild(el('div', { class: 'tiles' },
      tile('countyRestrictions', 'Restrictions on renewables', n(c.restrictions),
        n(c.verified_restrictions) + ' verified · ' + n(c.multi_sector_restrictions) + ' more also cover data centers'),
      tile('countySevere', 'Severe restrictions', n(c.severe_restrictions), n(c.active_moratoria) + ' active moratoria'),
      tile('countyProjects', 'Contested projects', n(c.contested_projects),
        n(c.blocked_projects) + ' blocked · ' + n(c.verified_projects) + ' verified'),
      tile('countyStandards', 'NREL siting standards', n(c.siting_standard_rows), 'ordinance features, NREL\'s reading')));

    view.appendChild(frameworkCard(detail, sname));

    view.appendChild(el('section', { class: 'card', 'aria-labelledby': 'inCountyHeading' },
      el('h2', { id: 'inCountyHeading', text: 'In the county' }),
      el('h3', { text: 'Restrictions (' + n(ren.length) + ')' }),
      ren.length ? el('div', { class: 'records' }, ren.map(restrictionRecord))
        : el('p', { class: 'muted', text: c.coverage_status === 'not_examined' ? 'Nothing published; the county has not been examined.' : 'No restriction on renewables is published for this county.' }),
      multi.length ? [el('h3', { style: 'margin-top:1.25rem', text: 'Also covering data centers (' + n(multi.length) + ', counted separately)' }),
        el('div', { class: 'records' }, multi.map(restrictionRecord))] : null,
      el('h3', { style: 'margin-top:1.25rem', text: 'Contested projects (' + n(projects.length) + ')' }),
      projects.length ? el('div', { class: 'records' }, projects.map(function (p) { return projectRecord(p, casesById); }))
        : el('p', { class: 'muted', text: 'No contested project is published for this county.' }),
      c.pending_review ? el('p', { id: 'pendingNote', class: 'small muted', text: plural(c.pending_review, 'candidate') +
        ' awaiting review ' + (c.pending_review === 1 ? 'names' : 'name') + ' this county. Candidates are not published until a reviewer has read their source.' }) : null));

    view.appendChild(standardsCard(standards));
    view.appendChild(neighborsCard(c, county.neighbors || [], route));
    view.appendChild(dcCard(dc));
    return view;
  }

  function standardsCard(standards) {
    return el('section', { class: 'card', 'aria-labelledby': 'standardsHeading' },
      el('h2', { id: 'standardsHeading', text: 'Local siting standards (NREL)' }),
      el('p', { class: 'muted small', text: 'NREL compiled these ordinance features with language models. A feature not checked against the ordinance is NREL\'s reading, not a verified fact.' }),
      standards.length ? el('div', { class: 'records' }, standards.map(function (s) {
        var u = safeUrl(s.ordinance_url);
        return el('article', { class: 'record' },
          el('h3', { text: s.jurisdiction + ': ' + words(s.technology) }),
          s.geoid ? el('p', { class: 'small muted', text: 'Census: ' + (s.census_name || '') + ' (GEOID ' + s.geoid + ')' }) : null,
          el('p', { class: 'small' }, plural(s.features, 'feature') + ', ' + n(s.restricting_features) + ' restricting · ' +
            (s.verified_features ? n(s.verified_features) + ' verified against the ordinance' : 'not verified') +
            (s.ordinance_year ? ' · ordinance year ' + s.ordinance_year : '') + ' · ',
            u ? el('a', { href: u, rel: 'noopener', text: 'ordinance' }) : 'no ordinance link'),
          (s.restricting || []).length ? el('ul', { class: 'small' }, s.restricting.map(function (f) {
            return el('li', { text: f.feature + (f.value ? ': ' + f.value + (f.units ? ' ' + f.units : '') : '') });
          })) : null);
      })) : el('p', { class: 'muted', text: 'NREL\'s 2025 databases list no ordinance for this county.' }));
  }

  function neighborsCard(c, neighbors, route) {
    var rows = neighbors.map(function (f) { return base.byFips[f]; }).filter(Boolean);
    var feats = base.features.filter(function (f) { return f.id === c.county_fips || neighbors.indexOf(f.id) >= 0; });
    var box = el('div', { class: 'map-box', id: 'neighborMap' });
    setTimeout(function () { drawMap(box, feats, route.metric, { focus: c.county_fips, label: 'This county and its neighbors', height: 420 }); }, 0);
    return el('section', { class: 'card', 'aria-labelledby': 'neighborsHeading' },
      el('h2', { id: 'neighborsHeading', text: 'Adjacent counties' }),
      rows.length ? el('div', { class: 'grid-2' },
        box,
        sortableTable('Counties that share a border, across state lines', [
          { key: 'county_name', label: 'County', render: function (x) { return link(href('county', x.county_fips, route.metric), x.county_name + ', ' + x.state_code); } },
          { key: 'coverage_status', label: 'Coverage', render: function (x) { return COVERAGE_WORDS[x.coverage_status]; } },
          { key: 'restrictions', label: 'Restrictions', num: true },
          { key: 'severe_restrictions', label: 'Severe', num: true },
          { key: 'contested_projects', label: 'Projects', num: true }
        ], rows, 'restrictions'))
        : el('p', { class: 'muted', text: 'No adjacent county in the 2024 boundary file.' }));
  }

  function dcCard(events) {
    return el('section', { class: 'card', 'aria-labelledby': 'dcHeading' },
      el('h2', { id: 'dcHeading', text: 'Data center activity' }),
      el('p', { class: 'muted small', text: 'Context only, from pricephillips/data-center-map (Data Center Tracker, CC BY 4.0). Never part of the renewable counts.' }),
      events.length ? el('ul', null, events.map(function (e) {
        var u = safeUrl(e.source_url);
        return el('li', null, (e.event_date || 'undated') + ' · ' + words(e.event_type || 'event') +
          (e.status ? ' (' + words(e.status) + ')' : '') + ': ' + (e.summary || ''), ' ',
          u ? el('a', { href: u, rel: 'noopener', text: 'source' }) : null);
      })) : el('p', { class: 'muted', text: 'No data center event is recorded for this county.' }));
  }

  // ── All records (explorer, record pages) ──────────────────────────────────

  // Every state file, merged: one entry per instrument even when a record
  // is listed in two states' files (placed across a state line).
  function loadAllRecords() {
    if (cache._all) return cache._all;
    var codes = base.states.map(function (s) { return s.state_code; });
    cache._all = Promise.all(codes.map(function (st) { return getJSON(PATHS.state(st)); })).then(function (files) {
      var out = { restrictions: [], projects: [], cases: [] };
      var seen = { restrictions: {}, projects: {}, cases: {} };
      files.forEach(function (f) {
        Object.keys(out).forEach(function (k) {
          (f[k] || []).forEach(function (r) {
            if (seen[k][r.instrument_id]) return;
            seen[k][r.instrument_id] = true;
            out[k].push(r);
          });
        });
      });
      return out;
    });
    return cache._all;
  }

  function countyLabel(fips) {
    var c = base.byFips[fips];
    return c ? c.county_name + ', ' + c.state_code : fips;
  }
  function firstCounty(r) { return (r.counties || [])[0] || ''; }

  // ── Explorer ──────────────────────────────────────────────────────────────

  // Each entity: its filters (param, label, value(record) -> string or list)
  // and its columns (label, value(record) for CSV, cell(record) for the page).
  var EXPLORE = {
    restrictions: {
      title: 'Restrictions', noun: ['restriction', 'restrictions'], kind: 'restriction',
      filters: [
        { p: 'st', label: 'State', value: function (r) { return r.state_code; } },
        { p: 'scope', label: 'Scope', value: function (r) { return r.scope; }, def: 'renewables_only',
          names: { renewables_only: 'Renewables only', multi_sector_data_centers: 'Also covers data centers' } },
        { p: 'tech', label: 'Technology', value: function (r) { return r.technologies; } },
        { p: 'type', label: 'Type', value: function (r) { return r.restriction_types; } },
        { p: 'sev', label: 'Severity', value: function (r) { return r.severity_score ? String(r.severity_score) : ''; } },
        { p: 'status', label: 'Status', value: function (r) { return r.status || 'not recorded'; } },
        { p: 'ver', label: 'Verification', value: function (r) { return r.verification; } },
        { p: 'src', label: 'Source', value: function (r) { return r.source_family; } }
      ],
      search: function (r) { return [r.jurisdiction_name, r.description, r.state_code].join(' '); },
      columns: [
        { label: 'State', value: function (r) { return r.state_code; } },
        { label: 'Jurisdiction', value: function (r) { return r.jurisdiction_name || ''; },
          cell: function (r) { return recordLink('restriction', r.instrument_id, r.jurisdiction_name || 'not named'); } },
        { label: 'County', value: function (r) { return firstCounty(r) ? countyLabel(firstCounty(r)) : ''; },
          cell: function (r) { var f = firstCounty(r); return f ? link(href('county', f), countyLabel(f)) : el('span', { class: 'muted', text: 'not placed' }); } },
        { label: 'Type', value: function (r) { return (r.restriction_types || []).map(words).join('; '); } },
        { label: 'Technologies', value: function (r) { return (r.technologies || []).map(words).join('; '); } },
        { label: 'Status', value: function (r) { return words(r.status || ''); } },
        { label: 'Severity', num: true, value: function (r) { return r.severity_score || ''; } },
        { label: 'Evidence', value: function (r) { return r.verification; },
          cell: function (r) { return verificationPill('restriction', r.verification); } },
        { label: 'Source', value: function (r) { return r.source_family; } },
        { label: 'Enacted', value: function (r) { return r.date_enacted_iso || r.date_text || ''; } }
      ],
      csvExtra: function (r) { return { instrument_id: r.instrument_id, scope: r.scope, description: r.description || '' }; }
    },
    projects: {
      title: 'Contested projects', noun: ['project', 'projects'], kind: 'project',
      filters: [
        { p: 'st', label: 'State', value: function (r) { return r.state_code; } },
        { p: 'tech', label: 'Technology', value: function (r) { return r.technologies; } },
        { p: 'outcome', label: 'Outcome', value: function (r) { return r.outcome; }, names: OUTCOME_WORDS },
        { p: 'ver', label: 'Verification', value: function (r) { return r.verification; } },
        { p: 'src', label: 'Source', value: function (r) { return r.source_family; } }
      ],
      search: function (r) { return [r.project_name, r.description, r.municipality, r.state_code, (r.groups || []).join(' ')].join(' '); },
      columns: [
        { label: 'State', value: function (r) { return r.state_code; } },
        { label: 'Project', value: function (r) { return r.project_name || ''; },
          cell: function (r) { return recordLink('project', r.instrument_id, r.project_name || 'not named'); } },
        { label: 'County', value: function (r) { return firstCounty(r) ? countyLabel(firstCounty(r)) : ''; },
          cell: function (r) { var f = firstCounty(r); return f ? link(href('county', f), countyLabel(f)) : el('span', { class: 'muted', text: 'not placed' }); } },
        { label: 'Technologies', value: function (r) { return (r.technologies || []).map(words).join('; '); } },
        { label: 'Outcome', value: function (r) { return OUTCOME_WORDS[r.outcome] || words(r.outcome); } },
        { label: 'Evidence', value: function (r) { return r.verification; },
          cell: function (r) { return verificationPill('project', r.verification); } },
        { label: 'Source', value: function (r) { return r.source_family; } },
        { label: 'Cases', num: true, value: function (r) { return (r.cases || []).length || ''; } }
      ],
      csvExtra: function (r) { return { instrument_id: r.instrument_id, outcome: r.outcome, description: r.description || '' }; }
    },
    cases: {
      title: 'Court cases', noun: ['case', 'cases'], kind: 'case',
      filters: [
        { p: 'st', label: 'State', value: function (r) { return r.state_code || ''; } },
        { p: 'status', label: 'Status', value: function (r) { return r.case_status || ''; }, names: CASE_WORDS },
        { p: 'level', label: 'Court level', value: function (r) { return r.court_level || ''; } }
      ],
      search: function (r) { return [r.case_name, r.court, r.docket_number, r.state_code].join(' '); },
      columns: [
        { label: 'Case', value: function (r) { return r.case_name || ''; },
          cell: function (r) { return recordLink('case', r.instrument_id, r.case_name || 'Case'); } },
        { label: 'State', value: function (r) { return r.state_code || ''; } },
        { label: 'Court', value: function (r) { return r.court || ''; } },
        { label: 'Level', value: function (r) { return words(r.court_level || ''); } },
        { label: 'Docket', value: function (r) { return r.docket_number || ''; } },
        { label: 'Status', value: function (r) { return CASE_WORDS[r.case_status || ''] || words(r.case_status); } },
        { label: 'Projects', num: true, value: function (r) { return (r.projects || []).length || ''; } }
      ],
      csvExtra: function (r) { return { instrument_id: r.instrument_id, court_record: r.case_source_url || '' }; }
    }
  };

  function asList(v) { return Array.isArray(v) ? v : [v]; }
  function optionName(f, v) {
    if (f.p === 'st') return stateName(v);
    if (f.names && f.names[v]) return f.names[v];
    if (f.p === 'ver') return v === 'verified' ? 'Verified' : v === 'located' ? 'Located' : 'Not verified';
    if (f.p === 'sev') return v + ' of 4';
    return words(v);
  }

  function renderExplore(route, all) {
    var spec = EXPLORE[route.entity];
    var records = all[route.entity];
    var params = route.params;
    var state = {};
    spec.filters.forEach(function (f) {
      var v = params.get(f.p);
      state[f.p] = v === null ? (f.def || '') : v;
    });
    state.q = params.get('q') || '';

    function matches(r) {
      for (var i = 0; i < spec.filters.length; i++) {
        var f = spec.filters[i];
        var want = state[f.p];
        if (want && asList(f.value(r)).indexOf(want) < 0) return false;
      }
      if (state.q) {
        var hay = spec.search(r).toLowerCase();
        var terms = state.q.toLowerCase().split(/\s+/).filter(Boolean);
        for (var j = 0; j < terms.length; j++) if (hay.indexOf(terms[j]) < 0) return false;
      }
      return true;
    }

    var view = el('div', { class: 'stack' });
    view.appendChild(el('div', null,
      el('h1', { text: 'Explore the records' }),
      el('p', { class: 'lede', text: 'Every published restriction, contested project and court case, one row per instrument. Filter, follow a row to its record, or download what you see as CSV.' }),
      el('div', { class: 'tabs', role: 'navigation', 'aria-label': 'Record type' },
        Object.keys(EXPLORE).map(function (k) {
          return el('a', { href: '#/explore/' + k, 'aria-current': k === route.entity ? 'page' : null,
            text: EXPLORE[k].title });
        }))));

    var filters = el('form', { class: 'filters', role: 'search', 'aria-label': 'Filter ' + spec.title.toLowerCase(),
      onsubmit: function (e) { e.preventDefault(); } });
    var search = el('input', { type: 'search', id: 'exploreSearch', value: state.q, placeholder: 'Words in the name or description' });
    filters.appendChild(el('label', { class: 'field', for: 'exploreSearch' }, 'Search', search));
    spec.filters.forEach(function (f) {
      var values = {};
      records.forEach(function (r) { asList(f.value(r)).forEach(function (v) { if (v !== '' && v !== null && v !== undefined) values[v] = true; }); });
      var sel = el('select', { id: 'f-' + f.p, 'data-param': f.p });
      sel.appendChild(el('option', { value: '', text: f.p === 'scope' ? 'Both scopes' : 'All' }));
      Object.keys(values).sort(function (a, b) { return optionName(f, a).localeCompare(optionName(f, b)); }).forEach(function (v) {
        sel.appendChild(el('option', { value: v, text: optionName(f, v), selected: state[f.p] === v }));
      });
      filters.appendChild(el('label', { class: 'field', for: 'f-' + f.p }, f.label, sel));
    });
    var reset = el('button', { type: 'button', class: 'btn secondary', text: 'Clear filters' });
    filters.appendChild(reset);

    var line = el('p', { id: 'resultCount', role: 'status', 'aria-live': 'polite' });
    var csvBtn = el('button', { type: 'button', class: 'btn secondary', id: 'csvBtn', text: 'Download CSV' });
    var results = el('div', { id: 'results' });
    var card = el('section', { class: 'card', 'aria-labelledby': 'exploreHeading' },
      el('h2', { id: 'exploreHeading', class: 'skip', text: spec.title }),
      filters, el('div', { class: 'result-line' }, line, csvBtn), results);
    view.appendChild(card);

    var filtered = [];
    function update(pushHash) {
      filtered = records.filter(matches);
      var verified = filtered.filter(function (r) { return r.verification === 'verified'; }).length;
      line.textContent = n(filtered.length) + ' ' + (filtered.length === 1 ? spec.noun[0] : spec.noun[1]) +
        (route.entity === 'cases' ? '' : ' · ' + n(verified) + ' verified');
      results.textContent = '';
      results.appendChild(longTable(spec.title + ' matching the filters', spec.columns.map(function (c) {
        return { label: c.label, num: c.num };
      }), filtered, function (r) {
        return el('tr', null, spec.columns.map(function (c) {
          return el('td', { class: c.num ? 'num' : null }, c.cell ? c.cell(r) : c.value(r));
        }));
      }, 'Nothing matches these filters.'));
      if (pushHash) {
        var qp = new URLSearchParams();
        if (state.q) qp.set('q', state.q);
        spec.filters.forEach(function (f) {
          if (state[f.p] !== (f.def || '')) qp.set(f.p, state[f.p]);
        });
        var qs = qp.toString();
        // replaceState, not location.hash: no hashchange, so typing keeps focus.
        history.replaceState(null, '', '#/explore/' + route.entity + (qs ? '?' + qs : ''));
      }
    }
    filters.addEventListener('change', function (e) {
      var p = e.target.getAttribute && e.target.getAttribute('data-param');
      if (p) { state[p] = e.target.value; update(true); }
    });
    var timer = null;
    search.addEventListener('input', function () {
      clearTimeout(timer);
      timer = setTimeout(function () { state.q = search.value.trim(); update(true); }, 200);
    });
    reset.addEventListener('click', function () {
      spec.filters.forEach(function (f) {
        state[f.p] = f.def || '';
        filters.querySelector('#f-' + f.p).value = state[f.p];
      });
      state.q = '';
      search.value = '';
      update(true);
    });
    csvBtn.addEventListener('click', function () {
      var cols = spec.columns.map(function (c) { return c.label; });
      var extraKeys = filtered.length ? Object.keys(spec.csvExtra(filtered[0])) : [];
      var lines = [cols.concat(extraKeys, ['link']).map(csvCell).join(',')];
      var root = location.href.split('#')[0];
      filtered.forEach(function (r) {
        var extra = spec.csvExtra(r);
        lines.push(spec.columns.map(function (c) { return csvCell(c.value(r)); })
          .concat(extraKeys.map(function (k) { return csvCell(extra[k]); }),
                  [csvCell(root + href(spec.kind, r.instrument_id))]).join(','));
      });
      download(route.entity + '.csv', lines.join('\r\n') + '\r\n', 'text/csv');
    });
    update(false);
    return view;
  }

  function csvCell(v) {
    var s = v === null || v === undefined ? '' : String(v);
    // A leading =, +, - or @ would run as a formula in a spreadsheet.
    if (/^[=+\-@]/.test(s)) s = "'" + s;
    return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }
  function download(name, text, type) {
    var url = URL.createObjectURL(new Blob([text], { type: type + ';charset=utf-8' }));
    var a = el('a', { href: url, download: name });
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  // ── Record pages ──────────────────────────────────────────────────────────

  var METHOD_WORDS = {
    name: 'the county named in the record', names: 'one of several counties the record names',
    point: 'the record\'s coordinates fall inside it', place: 'a town that sits in this county alone',
    place_text: 'a town in several counties, and the record\'s text names this one',
    override: 'a reviewer\'s placement, with evidence', source_fips: 'the county code the source gives'
  };

  function renderRecord(route, rec) {
    var r = rec.record;
    var view = el('div', { class: 'stack' });
    var st = r.state_code;
    var trail = [['National', href('national')]];
    if (st && base.byState[st]) trail.push([stateName(st), href('state', st)]);
    var permalink = location.href.split('#')[0] + href(route.entity, r.instrument_id);

    if (route.entity === 'restriction') {
      trail.push([r.jurisdiction_name || 'Restriction']);
      view.appendChild(el('div', null, crumbs(trail),
        el('h1', { text: (r.jurisdiction_name || 'Unnamed jurisdiction') + ': ' + (r.restriction_types || []).map(words).join(', ') }),
        el('p', null, verificationPill('restriction', r.verification), ' ',
          r.scope === 'multi_sector_data_centers' ? el('span', { class: 'pill warn', text: 'also covers data centers' }) : null)));
      view.appendChild(el('section', { class: 'card', 'aria-labelledby': 'recHeading' },
        el('h2', { id: 'recHeading', text: 'The instrument' }),
        r.description ? el('p', { text: r.description }) : null,
        r.long_description && r.long_description !== r.description ? el('p', { class: 'muted', text: r.long_description }) : null,
        el('div', { class: 'record' }, el('dl', null,
          dlRow('Jurisdiction', (r.jurisdiction_name || 'not named') + (r.jurisdiction_type ? ' (' + r.jurisdiction_type + ')' : '')),
          dlRow('Census government', censusLine(r)),
          dlRow('State', stateName(st)),
          dlRow('Technologies', (r.technologies || []).map(words).join(', ')),
          dlRow('Status', words(r.status || 'not recorded')),
          dlRow('Severity', r.severity_score ? r.severity_score + ' of 4: ' + SEVERITY_WORDS[r.severity_score] : 'not scored'),
          dlRow('Enacted', r.date_enacted_iso || r.date_text || 'date not recorded'),
          r.current_end_date ? dlRow('Ends', r.current_end_date) : null,
          dlRow('Scope', r.scope === 'multi_sector_data_centers' ? 'also covers data centers (counted separately)' : 'renewables only'),
          dlRow('Evidence', VERIFICATION_WORDS.restriction[r.verification] || VERIFICATION_WORDS.restriction.unverified),
          dlRow('Compiled from', r.source_family + (r.sabin_edition ? ' (edition ' + r.sabin_edition + ')' : '')),
          dlRow('Record id', r.instrument_id)))));
      view.appendChild(el('section', { class: 'card', 'aria-labelledby': 'rowsHeading' },
        el('h2', { id: 'rowsHeading', text: 'By technology' }),
        el('p', { class: 'muted small', text: 'The instrument counts once; each technology it covers is one row here.' }),
        el('div', { class: 'table-wrap' }, el('table', null,
          el('caption', { text: 'Technology rows of this instrument' }),
          el('thead', null, el('tr', null, ['Technology', 'Type', 'Severity', 'Basis', 'Mechanisms'].map(function (h) {
            return el('th', { scope: 'col', text: h });
          }))),
          el('tbody', null, (r.rows || []).map(function (x) {
            return el('tr', null, el('td', { text: words(x.technology) }), el('td', { text: words(x.restriction_type) }),
              el('td', { text: x.severity_score || '' }), el('td', { text: x.severity_basis || '' }),
              el('td', { text: x.mechanisms || '' }));
          }))))));
    } else if (route.entity === 'project') {
      trail.push([r.project_name || 'Project']);
      var cases = (r.cases || []).map(function (id) { return rec.casesById[id]; }).filter(Boolean);
      view.appendChild(el('div', null, crumbs(trail),
        el('h1', { text: r.project_name || 'Unnamed project' }),
        el('p', null, verificationPill('project', r.verification), ' ',
          el('span', { class: 'pill', text: OUTCOME_WORDS[r.outcome] || words(r.outcome) }))));
      view.appendChild(el('section', { class: 'card', 'aria-labelledby': 'recHeading' },
        el('h2', { id: 'recHeading', text: 'The project' }),
        r.description ? el('p', { text: r.description }) : null,
        r.long_description && r.long_description !== r.description ? el('p', { class: 'muted', text: r.long_description }) : null,
        el('div', { class: 'record' }, el('dl', null,
          dlRow('State', stateName(st)),
          r.municipality ? dlRow('Municipality', r.municipality) : null,
          dlRow('Technologies', (r.technologies || []).map(words).join(', ')),
          r.capacity_mw_text ? dlRow('Capacity', r.capacity_mw_text + (/mw/i.test(r.capacity_mw_text) ? '' : ' MW')) : null,
          r.area_acres_text ? dlRow('Area', r.area_acres_text + ' acres') : null,
          r.event_date_text ? dlRow('Date', r.event_date_text) : null,
          dlRow('Outcome', (OUTCOME_WORDS[r.outcome] || words(r.outcome)) + (r.finality_evidence ? ' (' + r.finality_evidence + ')' : '')),
          r.opposition_type ? dlRow('Opposition', words(r.opposition_type)) : null,
          (r.groups || []).length ? dlRow('Groups named', r.groups.join('; ')) : null,
          dlRow('Evidence', VERIFICATION_WORDS.project[r.verification] || VERIFICATION_WORDS.project.unverified),
          dlRow('Compiled from', r.source_family + (r.sabin_edition ? ' (edition ' + r.sabin_edition + ')' : '')),
          dlRow('Record id', r.instrument_id)))));
      if (cases.length) {
        view.appendChild(el('section', { class: 'card', 'aria-labelledby': 'casesHeading' },
          el('h2', { id: 'casesHeading', text: 'Court cases' }),
          el('ul', null, cases.map(function (k) {
            return el('li', null, recordLink('case', k.instrument_id, k.case_name || 'Case'),
              ' · ' + (k.court || 'court not recorded') + ' · ' + (CASE_WORDS[k.case_status || ''] || words(k.case_status)));
          }))));
      }
    } else {
      trail.push([r.case_name || 'Case']);
      view.appendChild(el('div', null, crumbs(trail),
        el('h1', { text: r.case_name || 'Court case' }),
        el('p', null, el('span', { class: 'pill ok', text: 'court record' }))));
      view.appendChild(el('section', { class: 'card', 'aria-labelledby': 'recHeading' },
        el('h2', { id: 'recHeading', text: 'The case' }),
        el('div', { class: 'record' }, el('dl', null,
          dlRow('Court', (r.court || 'not recorded') + (r.court_level ? ' (' + words(r.court_level) + ')' : '')),
          r.docket_number ? dlRow('Docket', r.docket_number) : null,
          dlRow('Status', CASE_WORDS[r.case_status || ''] || words(r.case_status)),
          dlRow('Technologies', (r.technologies || []).map(words).join(', ')),
          dlRow('Record id', r.instrument_id))),
        (r.projects || []).length ? el('div', null, el('h3', { style: 'margin-top:1rem', text: 'Concerns' }),
          el('ul', null, r.projects.map(function (pid) {
            var p = rec.projectsById[pid];
            return el('li', null, recordLink('project', pid, p ? (p.project_name || 'Unnamed project') : pid));
          }))) : null));
    }

    if (r.placements) {
      view.appendChild(el('section', { class: 'card', 'aria-labelledby': 'placeHeading' },
        el('h2', { id: 'placeHeading', text: 'Where it is placed' }),
        r.placements.length ? el('ul', null, r.placements.map(function (pl) {
          return el('li', null, link(href('county', pl.county_fips), countyLabel(pl.county_fips)),
            ': ' + (METHOD_WORDS[pl.method] || words(pl.method || 'method not recorded')) + (pl.is_primary ? ' (the county the map paints)' : ''));
        })) : el('p', { class: 'muted', text: 'Not placed in any county: nothing in the record settles which county it is in.' })));
    }
    view.appendChild(el('section', { class: 'card', 'aria-labelledby': 'srcHeading' },
      el('h2', { id: 'srcHeading', text: 'Sources' }),
      route.entity === 'case' && safeUrl(r.case_source_url) ? el('p', null, 'Court record: ',
        el('a', { href: r.case_source_url, rel: 'noopener', text: shortUrl(r.case_source_url) })) : null,
      evidenceList(r.evidence),
      el('p', { class: 'small muted' }, 'Link to this record: ', el('a', { href: permalink, id: 'permalink', text: permalink }))));
    return view;
  }

  function dlRow(label, value) { return [el('dt', { text: label }), el('dd', null, value)]; }

  // The Census's own identifier for the government a record names
  // (build_database.py, geoid_match.py): 2 digits a state, 5 a county, 7 a
  // place, 10 a county subdivision.
  function censusLine(r) {
    if (!r.geoid) {
      return el('span', { class: 'muted', text: 'no single Census government fits this name, so none is assigned' });
    }
    return (r.census_name || '') + ' · GEOID ' + r.geoid;
  }

  function loadRecord(route) {
    return getJSON(PATHS.recordIndex).then(function (idx) {
      var hit = objects(idx).filter(function (x) { return x.entity === route.entity && x.instrument_id === route.id; })[0];
      if (!hit) throw new Error('No ' + route.entity + ' with id ' + route.id + ' is published');
      return getJSON(PATHS.state(hit.state_code)).then(function (detail) {
        var key = { restriction: 'restrictions', project: 'projects', case: 'cases' }[route.entity];
        var record = detail[key].filter(function (x) { return x.instrument_id === route.id; })[0];
        if (!record) throw new Error('Record ' + route.id + ' is missing from its state file');
        var casesById = {}, projectsById = {};
        detail.cases.forEach(function (k) { casesById[k.instrument_id] = k; });
        detail.projects.forEach(function (p) { projectsById[p.instrument_id] = p; });
        return { record: record, casesById: casesById, projectsById: projectsById };
      });
    });
  }

  // ── Coverage ──────────────────────────────────────────────────────────────

  function renderCoverage(route, worklists) {
    var cov = base.metrics.county_coverage;
    // The coverage figures count the 50 states and DC; Puerto Rico apart.
    var inScope = base.states.filter(function (s) { return s.counties && s.state_code !== 'PR'; });
    var done = inScope.filter(function (s) { return !s.counties_not_examined; });
    var view = el('div', { class: 'stack' });
    view.appendChild(el('div', null,
      el('h1', { text: 'Coverage and evidence' }),
      el('p', { class: 'lede', text: 'Where the records are thin, and how much of what is published has been checked against its source. A county nobody has examined is a gap in the research, not evidence that nothing happened.' })));
    view.appendChild(el('div', { class: 'tiles' },
      tile('covRecords', 'Counties with published records', n(cov.with_any_record), 'of ' + n(cov.counties)),
      tile('covChecked', 'Checked, none found', n(cov.with_negative_check_and_no_record), 'a documented search found nothing'),
      tile('covNone', 'Not examined', n(cov.with_neither), 'nothing known either way'),
      tile('covStatesDone', 'States with every county examined', n(done.length), 'of ' + n(inScope.length) + ' (the states and DC)')));
    view.appendChild(el('section', { class: 'card', 'aria-labelledby': 'covStatesHeading' },
      el('h2', { id: 'covStatesHeading', text: 'Examination progress by state' }),
      el('p', { class: 'muted small' }, 'A county is examined once it has a published record or a reviewed search that found nothing. How a county is checked: ',
        el('a', { href: 'https://github.com/pricephillips/renewable-opposition/blob/main/docs/COUNTY_CHECK.md', text: 'the county check' }), '.'),
      sortableTable('Each state\'s counties by what is known about them. Select a column heading to sort.', [
        { key: 'state_name', label: 'State', render: function (s) { return link(href('state', s.state_code), s.state_name); } },
        { key: 'counties', label: 'Counties', num: true },
        { key: 'counties_with_records', label: 'With records', num: true },
        { key: 'counties_checked_none', label: 'Checked, none', num: true },
        { key: 'counties_not_examined', label: 'Not examined', num: true },
        { key: 'examined', label: 'Share examined', num: true,
          render: function (s) { return s.counties ? Math.round(100 * (s.counties - s.counties_not_examined) / s.counties) + '%' : ''; },
          sort: function (s) { return s.counties ? (s.counties - s.counties_not_examined) / s.counties : 0; } },
        { key: 'share', label: 'Share not examined', num: true,
          render: function (s) { return s.counties ? Math.round(100 * s.counties_not_examined / s.counties) + '%' : ''; },
          sort: function (s) { return s.counties ? s.counties_not_examined / s.counties : 0; } }
      ], inScope, 'share')));
    view.appendChild(checksCard());
    view.appendChild(sourcesCard(base.metrics));
    var rows = objects(worklists);
    view.appendChild(el('section', { class: 'card', 'aria-labelledby': 'worklistHeading' },
      el('h2', { id: 'worklistHeading', text: 'Research still to do' }),
      el('p', { class: 'muted small', text: 'How long each review list is. The lists themselves stay in the repository: this page shows their size, never their contents.' }),
      el('div', { class: 'table-wrap' }, el('table', { id: 'worklistTable' },
        el('caption', { text: 'Review worklists and their sizes' }),
        el('thead', null, el('tr', null, el('th', { scope: 'col', text: 'List' }), el('th', { scope: 'col', class: 'num', text: 'Items' }))),
        el('tbody', null, rows.map(function (w) {
          return el('tr', null, el('td', { text: w.description }), el('td', { class: 'num', text: n(w.rows) }));
        }))))));
    return view;
  }

  // Every county whose latest reviewed check found nothing, with how strong
  // the check was and when it is due again.
  function checksCard() {
    var rows = base.counties.filter(function (c) { return c.last_negative_check; })
      .sort(function (a, b) { return a.county_fips < b.county_fips ? -1 : 1; });
    var due = rows.filter(function (c) { return c.negative_check_recheck_by && c.negative_check_recheck_by < today(); });
    return el('section', { class: 'card', 'aria-labelledby': 'checksHeading' },
      el('h2', { id: 'checksHeading', text: 'Searches that found nothing' }),
      el('p', { class: 'muted small', text: 'A negative check says only that the sources it names held nothing on the day it ran. It is graded by how many independent kinds of source it covered (the codes, the minutes or dockets, the news), and it is due to be run again a year later. ' +
        'Counties with one: ' + n(rows.length) + '; due to be run again: ' + n(due.length) + '.' }),
      el('div', { class: 'table-wrap' }, el('table', { id: 'checksTable' },
        el('caption', { text: 'Negative checks, by county' }),
        el('thead', null, el('tr', null, ['County', 'Checked on', 'Grade', 'Check again by', 'Status'].map(function (h, i) {
          return el('th', { scope: 'col', text: h });
        }))),
        el('tbody', null, rows.map(function (c) {
          var stale = c.negative_check_recheck_by && c.negative_check_recheck_by < today();
          return el('tr', null,
            el('td', null, link(href('county', c.county_fips), c.county_name + ', ' + c.state_code)),
            el('td', { text: c.last_negative_check }),
            el('td', { title: GRADE_WORDS[c.negative_check_grade] || '', text: c.negative_check_grade || '' }),
            el('td', { text: c.negative_check_recheck_by || '' }),
            el('td', { text: c.coverage_status === 'has_records' ? 'records since published' : (stale ? 'due again' : 'current') }));
        })))));
  }

  // ── Data ──────────────────────────────────────────────────────────────────

  var EXAMPLES = [
    { title: 'Severe restrictions by state', sql:
      "SELECT state_code, count(*) AS severe\nFROM restriction_instrument\nWHERE scope = 'renewables_only' AND is_severe\nGROUP BY state_code\nORDER BY severe DESC\nLIMIT 10;" },
    { title: 'Counties next to a blocked project that nobody has examined', sql:
      "SELECT DISTINCT n.county_fips, c.county_name, c.state_code\nFROM contested_project p\nJOIN record_county rc ON rc.entity = 'contested_project' AND rc.record_id = p.instrument_id\nJOIN county_adjacency n ON n.neighbor_fips = rc.county_fips\nJOIN v_county_summary c ON c.county_fips = n.county_fips\nWHERE p.outcome_class = 'blocked' AND c.coverage_status = 'not_examined'\nORDER BY c.state_code, c.county_name;" },
    { title: 'How restrictions were verified, by source', sql:
      "SELECT source_family, verification, count(*) AS instruments\nFROM restriction_instrument\nGROUP BY ALL\nORDER BY source_family, verification;" },
    { title: 'NREL setbacks of 1,000 feet or more', sql:
      "SELECT state_code, jurisdiction, technology, feature, min_setback_ft\nFROM siting_standard\nWHERE min_setback_ft >= 1000\nORDER BY min_setback_ft DESC\nLIMIT 50;" }
  ];

  function parseSchema(sql) {
    var tables = [];
    var re = /((?:--[^\n]*\n)*)CREATE TABLE (\w+) \(\n([\s\S]*?)\n\);/g;
    var m;
    while ((m = re.exec(sql))) {
      var note = m[1].split('\n').map(function (l) { return l.replace(/^--\s?/, ''); }).join(' ').trim();
      var cols = [];
      m[3].split('\n').forEach(function (line) {
        var c = /^\s{4}(\w+)\s+([A-Z]+(?:\[\])?)([^-]*?)(?:--\s*(.*))?$/.exec(line);
        if (c && c[1] !== 'PRIMARY') {
          cols.push({ name: c[1], type: c[2], notes: [/PRIMARY KEY/.test(c[3]) ? 'key' : '', (/REFERENCES (\w+)/.exec(c[3]) || [])[1] ? 'refers to ' + /REFERENCES (\w+)/.exec(c[3])[1] : '', c[4] || ''].filter(Boolean).join('; ') });
        }
      });
      tables.push({ name: m[2], note: note, columns: cols });
    }
    return tables;
  }

  function renderData(route, manifest, schemaSql) {
    var files = objects(manifest);
    var tables = parseSchema(schemaSql || '');
    var view = el('div', { class: 'stack' });
    view.appendChild(el('div', null,
      el('h1', { text: 'Data and downloads' }),
      el('p', { class: 'lede', text: 'The national database as files you can download, what each table holds, and queries to start from. Everything is rebuilt from the published CSVs on every data build and checked against the headline numbers before it is published.' })));
    view.appendChild(el('section', { class: 'card', 'aria-labelledby': 'dlHeading' },
      el('h2', { id: 'dlHeading', text: 'Downloads' }),
      el('p', { class: 'muted small' }, 'Parquet opens in DuckDB, pandas, R (arrow) and most data tools. The same data as CSV and JSON, one file per entity, is in ',
        el('a', { href: 'https://github.com/pricephillips/renewable-opposition/tree/main/data/processed', text: 'data/processed' }), '.'),
      el('div', { class: 'table-wrap' }, el('table', { id: 'downloadsTable' },
        el('caption', { text: 'Published Parquet files' }),
        el('thead', null, el('tr', null, ['File', 'Kind', 'Rows', 'Size'].map(function (h, i) {
          return el('th', { scope: 'col', class: i >= 2 ? 'num' : null, text: h });
        }))),
        el('tbody', null, files.map(function (f) {
          return el('tr', null, el('td', null, el('a', { href: './data/db/' + f.file, download: '', text: f.name + '.parquet' })),
            el('td', { text: f.kind }), el('td', { class: 'num', text: n(f.rows) }),
            el('td', { class: 'num', text: f.bytes >= 1048576 ? (f.bytes / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(f.bytes / 1024)) + ' KB' }));
        }))))));
    view.appendChild(el('section', { class: 'card', 'aria-labelledby': 'exHeading' },
      el('h2', { id: 'exHeading', text: 'Example queries' }),
      EXAMPLES.map(function (x) {
        return el('div', null, el('h3', { text: x.title }), el('pre', { class: 'code', text: x.sql }),
          el('p', { class: 'small' }, link('#/sql?q=' + encodeURIComponent(x.sql), 'Run it in the SQL console')));
      })));
    view.appendChild(el('section', { class: 'card', 'aria-labelledby': 'dictHeading' },
      el('h2', { id: 'dictHeading', text: 'Data dictionary' }),
      el('p', { class: 'muted small' }, 'Read from ', el('a', { href: './db/schema.sql', text: 'db/schema.sql' }),
        '. Counts are of instruments: one ordinance, project or case, however many technology rows it has.'),
      tables.length ? tables.map(function (t) {
        return el('details', { class: 'dict' }, el('summary', { text: t.name }),
          t.note ? el('p', { class: 'small muted', text: t.note }) : null,
          el('div', { class: 'table-wrap' }, el('table', null,
            el('caption', { text: 'Columns of ' + t.name }),
            el('thead', null, el('tr', null, ['Column', 'Type', 'Notes'].map(function (h) { return el('th', { scope: 'col', text: h }); }))),
            el('tbody', null, t.columns.map(function (c) {
              return el('tr', null, el('td', null, el('code', { text: c.name })), el('td', { text: c.type }), el('td', { text: c.notes }));
            })))));
      }) : el('p', { class: 'muted', text: 'The schema file could not be read.' })));
    view.appendChild(el('section', { class: 'card', 'aria-labelledby': 'licHeading' },
      el('h2', { id: 'licHeading', text: 'Sources and licenses' }),
      el('ul', null,
        el('li', { text: 'Sabin Center for Climate Change Law, Opposition to Renewable Energy Facilities in the United States (September 2026 edition).' }),
        el('li', { text: 'NREL U.S. Wind and Solar Siting Regulation and Zoning Ordinances (2025), CC BY 4.0.' }),
        el('li', { text: 'Moratorium Nation (mjbommar/moratorium-data-2026), CC BY 4.0.' }),
        el('li', { text: 'Data Center Tracker, via pricephillips/data-center-map, CC BY 4.0: county context only, never counted.' })),
      el('p', { class: 'small muted', text: 'The SQL console loads DuckDB-WASM from cdn.jsdelivr.net and its Parquet reader from extensions.duckdb.org, in your browser only when you open it.' })));
    return view;
  }

  // ── SQL console (DuckDB-WASM, loaded only here) ───────────────────────────

  var DUCKDB = 'https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@1.29.0/dist/duckdb-browser.mjs';
  var engine = null;
  var SQL_ROWS_SHOWN = 500;

  function loadEngine(onProgress) {
    if (engine) return engine;
    engine = getJSON(PATHS.manifest).then(function (manifest) {
      onProgress('Loading the query engine (DuckDB-WASM, about 7 MB, once per visit)…');
      return import(DUCKDB).then(function (duckdb) {
        return duckdb.selectBundle(duckdb.getJsDelivrBundles()).then(function (bundle) {
          var workerUrl = URL.createObjectURL(new Blob(['importScripts("' + bundle.mainWorker + '");'], { type: 'text/javascript' }));
          var db = new duckdb.AsyncDuckDB(new duckdb.VoidLogger(), new Worker(workerUrl));
          return db.instantiate(bundle.mainModule, bundle.pthreadWorker).then(function () {
            URL.revokeObjectURL(workerUrl);
            onProgress('Loading the database (' + objects(manifest).length + ' tables and views)…');
            return Promise.all(objects(manifest).map(function (f) {
              return fetch('./data/db/' + f.file).then(function (r) {
                if (!r.ok) throw new Error(f.file + ' (HTTP ' + r.status + ')');
                return r.arrayBuffer();
              }).then(function (buf) { return db.registerFileBuffer(f.name + '.parquet', new Uint8Array(buf)); });
            })).then(function () { return db.connect(); }).then(function (conn) {
              return objects(manifest).reduce(function (p, f) {
                return p.then(function () {
                  return conn.query('CREATE VIEW "' + f.name + '" AS SELECT * FROM read_parquet(\'' + f.name + '.parquet\')');
                });
              }, Promise.resolve()).then(function () { return { conn: conn, tables: objects(manifest) }; });
            });
          });
        });
      });
    });
    engine.catch(function () { engine = null; });
    return engine;
  }

  function cellValue(v) {
    if (v === null || v === undefined) return '';
    if (typeof v === 'bigint') return Number(v) <= Number.MAX_SAFE_INTEGER && Number(v) >= -Number.MAX_SAFE_INTEGER ? Number(v) : v.toString();
    if (v instanceof Date) return v.toISOString().slice(0, 10);
    if (typeof v === 'object') {
      if (typeof v.toArray === 'function') return JSON.stringify(Array.from(v.toArray()).map(cellValue));
      if (Array.isArray(v)) return JSON.stringify(v.map(cellValue));
      if (v.toString !== Object.prototype.toString) return v.toString();
      return JSON.stringify(v, function (k, x) { return typeof x === 'bigint' ? x.toString() : x; });
    }
    return v;
  }

  function renderSql(route) {
    var initial = route.params.get('q') || EXAMPLES[0].sql;
    var view = el('div', { class: 'stack' });
    view.appendChild(el('div', null,
      el('h1', { text: 'SQL console' }),
      el('p', { class: 'lede', text: 'Query the whole national database in your browser. Every table and view on the data page is here by its name. Nothing you run leaves your browser or changes the published data.' })));
    var box = el('textarea', { class: 'sql', id: 'sqlInput', spellcheck: 'false', 'aria-describedby': 'sqlHelp' });
    box.value = initial;
    var run = el('button', { type: 'button', class: 'btn', id: 'sqlRun', text: 'Run query' });
    var csv = el('button', { type: 'button', class: 'btn secondary', id: 'sqlCsv', text: 'Download results as CSV', disabled: true });
    var status = el('p', { id: 'sqlStatus', role: 'status', 'aria-live': 'polite', class: 'small muted' });
    var out = el('div', { id: 'sqlResults' });
    var last = null;
    view.appendChild(el('section', { class: 'card', 'aria-labelledby': 'sqlHeading' },
      el('h2', { id: 'sqlHeading', class: 'skip', text: 'Query' }),
      el('label', { for: 'sqlInput', class: 'field' }, 'SQL (DuckDB dialect)', box),
      el('p', { id: 'sqlHelp', class: 'small muted' }, 'Ctrl+Enter runs the query. Examples and the data dictionary are on the ', link('#/data', 'data page'), '.'),
      el('div', { class: 'result-line' }, el('div', null, run, ' ', csv), status),
      out));

    function execute() {
      var sql = box.value.trim();
      if (!sql) return;
      run.disabled = true;
      history.replaceState(null, '', '#/sql?q=' + encodeURIComponent(sql));
      var t0 = performance.now();
      loadEngine(function (msg) { status.textContent = msg; }).then(function (eng) {
        status.textContent = 'Running…';
        return eng.conn.query(sql);
      }).then(function (result) {
        var cols = result.schema.fields.map(function (f) { return f.name; });
        var rows = result.toArray().map(function (row) {
          return cols.map(function (c) { return cellValue(row[c]); });
        });
        last = { cols: cols, rows: rows };
        csv.disabled = !rows.length;
        status.textContent = plural(rows.length, 'row') + ' in ' + Math.round(performance.now() - t0) + ' ms' +
          (rows.length > SQL_ROWS_SHOWN ? '; the first ' + n(SQL_ROWS_SHOWN) + ' are shown, the CSV has all of them' : '');
        out.textContent = '';
        out.appendChild(el('div', { class: 'table-wrap' }, el('table', { id: 'sqlTable' },
          el('caption', { text: 'Query results' }),
          el('thead', null, el('tr', null, cols.map(function (c) { return el('th', { scope: 'col', text: c }); }))),
          el('tbody', null, rows.slice(0, SQL_ROWS_SHOWN).map(function (r) {
            return el('tr', null, r.map(function (v) { return el('td', { class: typeof v === 'number' ? 'num' : null, text: v }); }));
          })))));
      }).catch(function (err) {
        status.textContent = 'Error: ' + (err && err.message ? err.message : String(err));
        out.textContent = '';
      }).then(function () { run.disabled = false; });
    }
    run.addEventListener('click', execute);
    box.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); execute(); }
    });
    csv.addEventListener('click', function () {
      if (!last) return;
      download('query.csv', [last.cols.map(csvCell).join(',')].concat(last.rows.map(function (r) {
        return r.map(csvCell).join(',');
      })).join('\r\n') + '\r\n', 'text/csv');
    });
    if (route.params.get('q')) setTimeout(execute, 0);
    return view;
  }

  // ── Router ────────────────────────────────────────────────────────────────

  function render() {
    var route = parseRoute();
    var root = document.getElementById('view');
    document.body.removeAttribute('data-ready');
    document.querySelectorAll('[data-nav]').forEach(function (a) {
      var v = a.getAttribute('data-nav');
      var on = v === route.view || (v === 'national' && (route.view === 'state' || route.view === 'county')) ||
        (v === 'explore' && route.view === 'record');
      if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
    });
    loadBase().then(function () {
      document.getElementById('asOf').textContent = base.asOf ? 'Data as of ' + base.asOf + '.' : '';
      if (route.view === 'national') return renderNational(route);
      if (route.view === 'explore') return loadAllRecords().then(function (all) { return renderExplore(route, all); });
      if (route.view === 'record') return loadRecord(route).then(function (rec) { return renderRecord(route, rec); });
      if (route.view === 'coverage') return getJSON(PATHS.worklists).then(function (w) { return renderCoverage(route, w); });
      if (route.view === 'data') {
        return Promise.all([getJSON(PATHS.manifest), getText(PATHS.schema)]).then(function (r) { return renderData(route, r[0], r[1]); });
      }
      if (route.view === 'sql') return renderSql(route);
      var st = route.view === 'state' ? route.st : (base.byFips[route.fips] || {}).state_code;
      if (!st) throw new Error('No county ' + route.fips + ' in the national database');
      return getJSON(PATHS.state(st)).then(function (detail) {
        return route.view === 'state' ? renderState(route, detail) : renderCounty(route, detail);
      });
    }).then(function (node) {
      root.textContent = '';
      root.appendChild(node);
      setStatus('');
      var h1 = root.querySelector('h1');
      document.title = (h1 ? h1.textContent + ' · ' : '') + 'Renewable Opposition';
      document.body.setAttribute('data-ready', route.view);
    }).catch(function (err) {
      setStatus('Could not load the national database: ' + err.message + '. Reload the page to try again.', true);
      document.body.setAttribute('data-ready', 'error');
    });
  }

  function initTheme() {
    var btn = document.getElementById('themeToggle');
    var saved = null;
    try { saved = localStorage.getItem('ro-theme'); } catch (e) { /* storage blocked */ }
    if (saved === 'light' || saved === 'dark') document.documentElement.setAttribute('data-theme', saved);
    btn.addEventListener('click', function () {
      var cur = document.documentElement.getAttribute('data-theme') ||
        (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
      var next = cur === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      try { localStorage.setItem('ro-theme', next); } catch (e) { /* storage blocked */ }
    });
  }

  initTheme();
  window.addEventListener('hashchange', function () {
    render();
    var main = document.getElementById('main');
    if (main) main.focus({ preventScroll: false });
    window.scrollTo(0, 0);
  });
  render();
})();

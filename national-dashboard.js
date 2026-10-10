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
 *   ?m=<metric>             the map metric, on any route
 */
(function () {
  'use strict';

  var PATHS = {
    metrics: './data/processed/headline_metrics.json',
    states: './data/db/state_summary.json',
    counties: './data/db/county_summary.json',
    topo: './data/geo/counties_2024.topojson',
    snapshots: './data/snapshots/manifest.csv',
    state: function (st) { return './data/db/state/' + st + '.json'; }
  };

  // Map metrics: a v_county_summary column, or the coverage status itself.
  var METRICS = {
    severe_restrictions: { label: 'Severe restrictions', noun: 'severe restrictions (severity 3 or 4)' },
    restrictions: { label: 'All restrictions', noun: 'restrictions (renewables only)' },
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
    return { view: 'national', metric: metric };
  }
  function href(view, id, metric) {
    var m = metric && metric !== DEFAULT_METRIC ? '?m=' + metric : '';
    if (view === 'state') return '#/state/' + id + m;
    if (view === 'county') return '#/county/' + id + m;
    return '#/' + m;
  }

  // ── Loading ───────────────────────────────────────────────────────────────

  function loadBase() {
    if (base) return Promise.resolve(base);
    return Promise.all([getJSON(PATHS.metrics), getJSON(PATHS.states), getJSON(PATHS.counties),
                        getJSON(PATHS.topo), getText(PATHS.snapshots)])
      .then(function (r) {
        var counties = objects(r[2]);
        var byFips = {};
        counties.forEach(function (c) { byFips[c.county_fips] = c; });
        var states = objects(r[1]);
        var byState = {};
        states.forEach(function (s) { byState[s.state_code] = s; });
        var features = topojson.feature(r[3], r[3].objects.counties).features;
        var asOf = r[4].split('\n').slice(1).map(function (l) { return l.split(',')[0]; })
          .filter(function (d) { return /^\d{4}-\d{2}-\d{2}$/.test(d); }).sort().pop() || '';
        base = { metrics: r[0], states: states, byState: byState, counties: counties, byFips: byFips,
                 topo: r[3], features: features, asOf: asOf };
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
    var legend = el('ul', { class: 'legend', 'aria-label': 'Map legend' });
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
      el('h3', { text: title }),
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
      el('h3', { text: p.project_name || 'Unnamed project' }),
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

    view.appendChild(sourcesCard(M));
    return view;
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
        el('td', { text: r.jurisdiction_name || 'not named' }),
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
          el('td', { text: p.project_name || 'not named' }),
          el('td', null, f ? link(href('county', f, route.metric), countyName(f)) : el('span', { class: 'muted', text: 'not placed' })),
          el('td', { text: (p.technologies || []).map(words).join(', ') }),
          el('td', { text: OUTCOME_WORDS[p.outcome] || words(p.outcome) }),
          el('td', null, verificationPill('project', p.verification)),
          el('td', { class: 'num', text: (p.cases || []).length || '' }));
      }, 'No contested project is recorded for ' + s.state_name + '.')));

    view.appendChild(el('section', { class: 'card', 'aria-labelledby': 'casesHeading' },
      el('h2', { id: 'casesHeading', text: 'Court cases (' + n(detail.cases.length) + ')' }),
      longTable('Cases with a court record', ['Case', 'Court', 'Status'], detail.cases, function (k) {
        var u = safeUrl(k.case_source_url);
        return el('tr', null,
          el('td', null, u ? el('a', { href: u, rel: 'noopener', text: k.case_name || 'Case' }) : (k.case_name || 'Case')),
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
    var checks = detail.negative_checks.filter(function (k) { return k.county_fips === c.county_fips; });
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
      bannerText = 'Checked ' + (k ? (k.sources_checked || []).join('; ') + ' on ' + k.checked_on : '') + ': none found.';
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

  // ── Router ────────────────────────────────────────────────────────────────

  function render() {
    var route = parseRoute();
    var root = document.getElementById('view');
    document.body.removeAttribute('data-ready');
    loadBase().then(function () {
      document.getElementById('asOf').textContent = base.asOf ? 'Data as of ' + base.asOf + '.' : '';
      if (route.view === 'national') return renderNational(route);
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

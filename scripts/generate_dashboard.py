#!/usr/bin/env python3
"""
generate_dashboard.py - valuefund.substack.com
Fast, clean HTML dashboard.  Data-driven: embeds compact JSON, JS renders table.
Run:  python generate_dashboard.py [--no-browser]
"""

import sqlite3, json, os, sys
from datetime import datetime

import sys as _sys_
if _sys_.platform.startswith("linux"):
    BASE_DIR = "/sessions/trusting-fervent-heisenberg/mnt/StockAnalysis"
else:
    BASE_DIR = r"D:\StockAnalysis"
DB_PATH   = os.path.join(BASE_DIR, "database", "stocks.db")
HTML_PATH = os.path.join(BASE_DIR, "database", "index.html")
BRAND     = "valuefund.substack.com"

# ── DB ────────────────────────────────────────────────────────────────────────
def fetch_all_stocks():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM analyzed_stocks ORDER BY promise_score DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def dedup_stocks(rows):
    """Keep the highest-promise_score entry per ticker."""
    seen = {}
    for row in rows:
        tk = row.get('ticker') or ''
        if not tk:
            continue
        prev = seen.get(tk)
        if prev is None or (row.get('promise_score') or 0) > (prev.get('promise_score') or 0):
            seen[tk] = row
    return list(seen.values())

# ── Helpers ───────────────────────────────────────────────────────────────────
def _s(v, d=''):
    return v if v is not None else d

def _action(row):
    a = row.get('action')
    if a:
        return a
    g = _s(row.get('grade'), '')
    return {'A': 'BUY', 'B': 'WATCH'}.get(g, 'PASS')

def _report_url(rpath):
    if not rpath:
        return ''
    fname = os.path.basename(rpath)
    return os.path.splitext(fname)[0] + '.html'

# ── Main generator ────────────────────────────────────────────────────────────
def generate_html_index():
    raw_rows    = fetch_all_stocks()
    orig_count  = len(raw_rows)
    rows        = dedup_stocks(raw_rows)
    dedup_count = orig_count - len(rows)

    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    grade_counts = {}
    for r in rows:
        g = _s(r.get('grade'), '?')
        grade_counts[g] = grade_counts.get(g, 0) + 1

    # Build compact stock list (short key names to keep JSON small)
    stocks = []
    for r in rows:
        stocks.append({
            't':  _s(r.get('ticker'), ''),
            'n':  _s(r.get('company_name'), '--'),
            'ex': _s(r.get('exchange'), '?'),
            'sec':_s(r.get('sector'), 'Unknown'),
            'ind':_s(r.get('industry'), ''),
            'mc': r.get('market_cap'),
            'pr': r.get('current_price'),
            'mos':r.get('margin_of_safety'),
            'pe': r.get('pe_ratio'),
            'pb': r.get('pb_ratio'),
            'pf': r.get('piotroski_score'),
            'az': r.get('altman_z'),
            'bc': r.get('buffett_checklist'),
            'sc': r.get('promise_score') or 0,
            'g':  _s(r.get('grade'), '?'),
            'act':_action(r),
            'dt': _s(r.get('analysis_date'), ''),
            'cat':_s(r.get('catalysts'), ''),
            'hv': _s(r.get('hidden_value_notes'), ''),
            'cs': r.get('catalyst_score') or 0,
            'rp': _report_url(r.get('report_path') or ''),
            # Modal extras
            'roe':r.get('roe'),
            'de': r.get('debt_equity'),
            'rg': r.get('revenue_growth'),
            'gm': r.get('gross_margin'),
            'fcf':r.get('fcf_yield'),
            'eve':r.get('ev_ebitda'),
            'evr':r.get('ev_revenue'),
            'ps': r.get('ps_ratio'),
            'beta':r.get('beta'),
            'dy': r.get('dividend_yield'),
            'cr': r.get('current_ratio'),
            'bv': r.get('bvps'),
            'eps':r.get('eps'),
            'om': r.get('operating_margin'),
            'ins':r.get('insider_pct'),
            'si': r.get('short_interest_pct'),
            'w52':r.get('week52_position'),
            'ths':_s(r.get('short_thesis'), ''),
            'thd':_s(r.get('detailed_thesis'), ''),
            'grn':r.get('graham_number'),
            'dcf':r.get('dcf_value'),
            'nn': r.get('net_net_value'),
            'mey':r.get('magic_formula_ey'),
            'vol':r.get('avg_volume'),
        })

    stocks_json = json.dumps(stocks, ensure_ascii=False, default=str, separators=(',', ':'))
    gc_json     = json.dumps(grade_counts)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{BRAND} — Small-Cap Screener</title>
<style>
:root{{
  --bg:#080f1c;--bg2:#0f1c2e;--bg3:#152236;--bd:#1c3050;
  --tx:#d0e4f4;--mu:#4a6a8a;--bl:#5aabf0;--gr:#43a047;
  --ye:#ffd740;--or:#fb8c00;--re:#e53935;--te:#26c6da;--pu:#ce93d8;
}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--bg);color:var(--tx);font-family:"Segoe UI",system-ui,sans-serif;font-size:12px;overflow-x:hidden}}
.hdr{{background:linear-gradient(135deg,var(--bg2) 0%,#0a1520 100%);border-bottom:2px solid var(--bd);padding:14px 24px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}}
.hdr h1{{font-size:19px;font-weight:700;color:var(--bl)}}
.brand{{font-size:10px;color:var(--te);font-weight:600}}
.upd{{color:var(--mu);font-size:10px;text-align:right}}
.stats{{background:var(--bg2);border-bottom:1px solid var(--bd);padding:8px 24px;display:flex;gap:20px;flex-wrap:wrap;align-items:center}}
.st{{display:flex;flex-direction:column}}
.stl{{font-size:9px;color:var(--mu);text-transform:uppercase;letter-spacing:.8px}}
.stv{{font-size:16px;font-weight:700;color:var(--bl)}}
.fbar{{background:var(--bg3);border-bottom:1px solid var(--bd);padding:8px 24px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}}
.fbar label{{font-size:9px;color:var(--mu);text-transform:uppercase;letter-spacing:.5px;margin-right:2px}}
.srch{{background:#0a1828;border:1px solid var(--bd);color:var(--tx);padding:5px 10px;border-radius:4px;font-size:11px;width:170px;outline:none}}
.srch:focus{{border-color:var(--bl)}}
.gb{{padding:4px 11px;border-radius:4px;font-size:11px;font-weight:700;cursor:pointer;border:1px solid var(--bd);background:#0a1828;color:var(--mu);transition:all .12s}}
.gb:hover{{color:var(--tx)}}
.gb.gball.active{{background:rgba(90,171,240,.2);color:var(--bl);border-color:var(--bl)}}
.gb.gba.active{{background:rgba(67,160,71,.2);color:var(--gr);border-color:var(--gr)}}
.gb.gbb.active{{background:rgba(255,215,64,.2);color:var(--ye);border-color:var(--ye)}}
.gb.gbc.active{{background:rgba(251,140,0,.2);color:var(--or);border-color:var(--or)}}
.gb.gbd.active{{background:rgba(229,57,53,.2);color:var(--re);border-color:var(--re)}}
.gb.gbf.active{{background:rgba(120,0,0,.2);color:#e57373;border-color:#b71c1c}}
.act-btn{{padding:4px 9px;border-radius:4px;font-size:10px;font-weight:700;cursor:pointer;border:1px solid var(--bd);background:#0a1828;color:var(--mu)}}
.act-btn.active{{background:rgba(90,171,240,.15);color:var(--bl);border-color:var(--bl)}}
select.fsel{{background:#0a1828;border:1px solid var(--bd);color:var(--tx);padding:5px 7px;border-radius:4px;font-size:11px;outline:none}}
.frow-count{{margin-left:auto;color:var(--mu);font-size:10px}}
.btn{{padding:4px 10px;border-radius:4px;font-size:10px;cursor:pointer;border:1px solid var(--bd);background:#0a1828;color:var(--mu)}}
.btn:hover{{color:var(--tx);border-color:var(--mu)}}
.wrap{{padding:0 0 40px;overflow-x:auto}}
table{{width:100%;border-collapse:collapse;min-width:1400px}}
thead{{position:sticky;top:0;z-index:5}}
th{{background:var(--bg2);color:var(--mu);font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;padding:9px 6px;text-align:left;border-bottom:2px solid var(--bd);white-space:nowrap;cursor:pointer;user-select:none}}
th:hover{{color:var(--bl)}}
th.sort-asc::after{{content:" ↑";color:var(--bl)}}
th.sort-desc::after{{content:" ↓";color:var(--bl)}}
tr{{border-bottom:1px solid #0b1828;transition:background .1s}}
tr:hover{{background:rgba(90,171,240,.06)!important}}
td{{padding:6px 6px;vertical-align:middle}}
.ga{{background:rgba(67,160,71,.07);border-left:3px solid #2e7d32}}
.gb-row{{background:rgba(255,215,64,.05);border-left:3px solid #f9a825}}
.gc-row{{background:rgba(251,140,0,.05);border-left:3px solid #e65100}}
.gd-row{{background:rgba(229,57,53,.05);border-left:3px solid #b71c1c}}
.gf-row{{background:rgba(100,0,0,.05);border-left:3px solid #6a0000}}
.rank{{color:var(--mu);font-weight:700;font-size:10px;white-space:nowrap}}
.tk{{font-weight:800;color:var(--bl);font-family:Consolas,monospace;font-size:13px;cursor:pointer;text-decoration:underline dotted;white-space:nowrap}}
.tk:hover{{color:#90d4ff}}
.cn{{max-width:130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#8aaccc}}
.sec-cell{{max-width:90px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--mu);font-size:10px}}
.mc-cell{{white-space:nowrap;font-weight:600;color:#a0c4e4}}
.badge{{background:#122030;color:#6a9cbe;padding:2px 5px;border-radius:3px;font-size:9px;font-weight:700}}
.pos{{color:var(--gr);font-weight:600}}.neg{{color:var(--re);font-weight:600}}
.ye{{color:var(--ye);font-weight:600}}.na{{color:#2a4060}}
.dt{{color:var(--mu);font-size:9px;white-space:nowrap}}
.bar{{position:relative;background:#112030;border-radius:3px;height:16px;width:72px;overflow:hidden}}
.fill{{position:absolute;left:0;top:0;height:100%;background:linear-gradient(90deg,#183060,var(--bl));border-radius:3px}}
.fill-mid{{background:linear-gradient(90deg,#183040,var(--ye))}}
.fill-low{{background:linear-gradient(90deg,#1a1020,var(--re))}}
.bval{{position:absolute;width:100%;text-align:center;top:50%;transform:translateY(-50%);font-size:9px;font-weight:700;color:#fff;text-shadow:0 1px 2px rgba(0,0,0,.8);z-index:1}}
.gl{{display:inline-flex;align-items:center;justify-content:center;width:21px;height:21px;border-radius:50%;font-weight:700;font-size:11px}}
.gl.ga{{background:rgba(67,160,71,.2);color:var(--gr);border:1px solid #2e7d32}}
.gl.gb{{background:rgba(255,215,64,.2);color:var(--ye);border:1px solid #f9a825}}
.gl.gc{{background:rgba(251,140,0,.2);color:var(--or);border:1px solid #e65100}}
.gl.gd{{background:rgba(229,57,53,.2);color:var(--re);border:1px solid #b71c1c}}
.gl.gf{{background:rgba(100,0,0,.2);color:#e57373;border:1px solid #6a0000}}
.act{{display:inline-block;padding:2px 7px;border-radius:3px;font-size:9px;font-weight:700}}
.act-buy{{background:rgba(67,160,71,.18);color:var(--gr)}}
.act-watch{{background:rgba(255,215,64,.15);color:var(--ye)}}
.act-pass{{background:rgba(80,80,80,.15);color:var(--mu)}}
.rlink{{color:var(--te);text-decoration:none;font-size:14px;opacity:.8}}
.rlink:hover{{opacity:1}}
.cat-badge{{display:inline-block;padding:1px 4px;border-radius:3px;font-size:8px;font-weight:700;margin:1px;cursor:help;white-space:nowrap}}
.cat-badge.cat{{background:rgba(38,198,218,.12);color:var(--te);border:1px solid rgba(38,198,218,.25)}}
.cat-badge.hv{{background:rgba(206,147,216,.12);color:var(--pu);border:1px solid rgba(206,147,216,.25)}}
.pgbar{{display:flex;gap:6px;justify-content:center;align-items:center;padding:10px 24px;flex-wrap:wrap}}
.pgbtn{{padding:4px 10px;border-radius:4px;font-size:11px;cursor:pointer;border:1px solid var(--bd);background:#0a1828;color:var(--mu)}}
.pgbtn:hover{{color:var(--tx)}}
.pgbtn.active{{background:rgba(90,171,240,.2);color:var(--bl);border-color:var(--bl)}}
.pginfo{{color:var(--mu);font-size:10px}}
#overlay{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.72);z-index:100;backdrop-filter:blur(3px)}}
#modal{{display:none;position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);width:min(800px,95vw);max-height:90vh;overflow-y:auto;background:var(--bg2);border:1px solid var(--bd);border-radius:10px;z-index:101}}
.mhdr{{background:linear-gradient(135deg,#0d1f3a,#0a1525);padding:16px 20px;border-bottom:1px solid var(--bd);display:flex;justify-content:space-between;align-items:flex-start;position:sticky;top:0;border-radius:10px 10px 0 0}}
.mhdr-left h2{{font-size:22px;font-weight:800;color:var(--bl);font-family:Consolas,monospace}}
.mhdr-left .mname{{font-size:13px;color:var(--tx);margin-top:2px}}
.mhdr-right{{display:flex;gap:8px;align-items:center}}
.mclose{{background:none;border:none;color:var(--mu);font-size:20px;cursor:pointer;padding:4px}}
.mclose:hover{{color:var(--tx)}}
.mbody{{padding:16px 20px}}
.mrow{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px}}
.mrow3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:10px}}
.mcard{{background:var(--bg3);border:1px solid var(--bd);border-radius:6px;padding:10px 12px}}
.mcard-lbl{{font-size:9px;color:var(--mu);text-transform:uppercase;letter-spacing:.6px;margin-bottom:4px}}
.mcard-val{{font-size:15px;font-weight:700;color:var(--tx)}}
.mcard-sub{{font-size:10px;color:var(--mu);margin-top:2px}}
.thesis-box{{background:rgba(67,160,71,.05);border:1px solid rgba(67,160,71,.2);border-radius:7px;padding:12px;margin-bottom:10px}}
.thesis-box h3{{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:#43a047;margin-bottom:8px}}
.thesis-short{{font-size:12px;color:var(--tx);font-style:italic;line-height:1.7;margin-bottom:8px;padding-bottom:8px;border-bottom:1px solid rgba(67,160,71,.2)}}
.thesis-detail{{font-size:11px;color:#a0c4e4;line-height:1.8;white-space:pre-line}}
.mnav{{display:flex;gap:8px;justify-content:center;padding:10px 0 4px}}
.mnavbtn{{padding:5px 14px;border-radius:4px;font-size:11px;cursor:pointer;border:1px solid var(--bd);background:#0a1828;color:var(--mu)}}
.mnavbtn:hover{{color:var(--bl)}}
.footer{{text-align:center;padding:14px;color:var(--mu);font-size:10px;border-top:1px solid var(--bd)}}
@media(max-width:700px){{.mrow,.mrow3{{grid-template-columns:1fr}}.fbar{{gap:6px}}.srch{{width:120px}}.hdr h1{{font-size:15px}}}}
</style>
</head>
<body>

<div class="hdr">
  <div>
    <div class="brand">{BRAND}</div>
    <h1>Small-Cap Screener &lt;$2B</h1>
    <div style="color:var(--mu);font-size:10px;margin-top:2px">Deep-value &middot; Quantitative &middot; Academic methodology</div>
  </div>
  <div class="upd">Updated: {now}<br><span style="color:var(--te);font-weight:600" id="total-count"></span></div>
</div>

<div class="stats" id="stats-bar"></div>

<div class="fbar">
  <label>Grade</label>
  <button class="gb gball" id="gb-ALL" onclick="setGrade('ALL')">All</button>
  <button class="gb gba active" id="gb-A" onclick="setGrade('A')">A</button>
  <button class="gb gbb" id="gb-B" onclick="setGrade('B')">B</button>
  <button class="gb gbc" id="gb-C" onclick="setGrade('C')">C</button>
  <button class="gb gbd" id="gb-D" onclick="setGrade('D')">D</button>
  <button class="gb gbf" id="gb-F" onclick="setGrade('F')">F</button>
  &nbsp;
  <label>Action</label>
  <button class="act-btn" id="ab-ALL" onclick="setAction('ALL')">All</button>
  <button class="act-btn" id="ab-BUY" onclick="setAction('BUY')">BUY</button>
  <button class="act-btn" id="ab-WATCH" onclick="setAction('WATCH')">WATCH</button>
  <button class="act-btn" id="ab-PASS" onclick="setAction('PASS')">PASS</button>
  &nbsp;
  <label>Sector</label>
  <select class="fsel" id="flt-sector" onchange="applyFilters()"><option value="">All sectors</option></select>
  <label>Exchange</label>
  <select class="fsel" id="flt-exch" onchange="applyFilters()"><option value="">All</option></select>
  &nbsp;
  <input class="srch" id="srch" placeholder="Search ticker / company..." oninput="applyFilters()">
  <button class="btn" onclick="clearFilters()">Reset</button>
  <button class="btn" onclick="exportCSV()">Export CSV</button>
  <span class="frow-count" id="row-count"></span>
</div>

<div class="wrap">
<table>
<thead>
<tr>
  <th onclick="sortBy('rank',0)">#</th>
  <th onclick="sortBy('t',1)">Ticker</th>
  <th onclick="sortBy('n',2)">Company</th>
  <th onclick="sortBy('ex',3)">Exch</th>
  <th onclick="sortBy('sec',4)">Sector</th>
  <th onclick="sortBy('mc',5)">Mkt Cap</th>
  <th onclick="sortBy('pr',6)">Price</th>
  <th onclick="sortBy('mos',7)">MoS%</th>
  <th onclick="sortBy('pe',8)">P/E</th>
  <th onclick="sortBy('pb',9)">P/B</th>
  <th onclick="sortBy('pf',10)">Piotroski</th>
  <th onclick="sortBy('az',11)">Altman Z</th>
  <th onclick="sortBy('bc',12)">Checklist</th>
  <th>Catalysts</th>
  <th onclick="sortBy('sc',14)">Score</th>
  <th onclick="sortBy('g',15)">Grade</th>
  <th>Report</th>
  <th onclick="sortBy('act',17)">Action</th>
  <th onclick="sortBy('dt',18)">Date</th>
</tr>
</thead>
<tbody id="tbody"></tbody>
</table>
</div>

<div class="pgbar" id="pgbar"></div>
<div class="footer">{BRAND} &mdash; Not financial advice. Quantitative screen only. Always conduct your own due diligence.</div>

<div id="overlay" onclick="closeModal()"></div>
<div id="modal">
  <div class="mhdr">
    <div class="mhdr-left">
      <h2 id="m-ticker"></h2>
      <div class="mname" id="m-name"></div>
      <div style="margin-top:4px" id="m-badges"></div>
    </div>
    <div class="mhdr-right">
      <button class="mclose" onclick="closeModal()">&#x2715;</button>
    </div>
  </div>
  <div class="mbody" id="m-body"></div>
  <div class="mnav">
    <button class="mnavbtn" onclick="navModal(-1)">&larr; Prev</button>
    <span style="color:var(--mu);font-size:10px" id="m-nav-pos"></span>
    <button class="mnavbtn" onclick="navModal(1)">Next &rarr;</button>
  </div>
</div>

<script>
const STOCKS = {stocks_json};
const GRADE_COUNTS = {gc_json};

let _grade  = 'A';
let _action = 'ALL';
let _sortCol = 'sc';
let _sortDir = -1;
let _page    = 0;
const PAGE_SIZE = 200;
let _filtered = [];
let _modalIdx = 0;
let _visibleTickers = [];

function fmtMcap(v) {{
  if (v==null) return '<span class="na">&ndash;</span>';
  if (v>=1e9) return '<span class="mc-cell">$'+(v/1e9).toFixed(2)+'B</span>';
  if (v>=1e6) return '<span class="mc-cell">$'+(v/1e6).toFixed(1)+'M</span>';
  return '<span class="mc-cell">$'+v.toLocaleString()+'</span>';
}}
function fmtMcapPlain(v) {{
  if (v==null) return '&ndash;';
  if (v>=1e9) return '$'+(v/1e9).toFixed(2)+'B';
  if (v>=1e6) return '$'+(v/1e6).toFixed(1)+'M';
  return '$'+(+v).toLocaleString();
}}
function fmtPrice(v) {{
  if (v==null) return '<span class="na">&ndash;</span>';
  return '$'+(+v).toFixed(2);
}}
function fmtMos(v) {{
  if (v==null) return '<span class="na">&ndash;</span>';
  const pct=((+v)*100).toFixed(1);
  const cls=v>0.3?'pos':v>0?'ye':'neg';
  return '<span class="'+cls+'">'+pct+'%</span>';
}}
function fmtPio(v) {{
  if (v==null) return '<span class="na">&ndash;</span>';
  const n=+v;
  return '<span class="'+(n>=7?'pos':n>=5?'ye':'neg')+'">'+n+'/9</span>';
}}
function fmtAz(v) {{
  if (v==null) return '<span class="na">&ndash;</span>';
  const n=+v;
  return '<span class="'+(n>=3?'pos':n>=1.81?'ye':'neg')+'">'+n.toFixed(2)+'</span>';
}}
function gradeClass(g) {{
  return {{A:'ga',B:'gb-row',C:'gc-row',D:'gd-row',F:'gf-row'}}[g]||'';
}}
function gradeCircle(g) {{
  const m={{A:'ga',B:'gb',C:'gc',D:'gd',F:'gf'}};
  return '<span class="gl '+(m[g]||'')+'">'+g+'</span>';
}}
function actSpan(a) {{
  const cls=a==='BUY'?'act-buy':a==='WATCH'?'act-watch':'act-pass';
  return '<span class="act '+cls+'">'+a+'</span>';
}}
function catBadges(cat,hv) {{
  let out='';
  if(cat) cat.split(/[|,;]+/).forEach(c=>{{c=c.trim();if(c) out+='<span class="cat-badge cat" title="'+c+'">'+c.substring(0,14)+'</span>';}});
  if(hv)  hv.split(/[|,;]+/).forEach(h=>{{h=h.trim();if(h) out+='<span class="cat-badge hv" title="'+h+'">'+h.substring(0,14)+'</span>';}});
  return out||'<span class="na">&ndash;</span>';
}}
function scoreBar(sc) {{
  sc=sc||0;
  const cls=sc>=65?'fill':sc>=40?'fill fill-mid':'fill fill-low';
  return '<div class="bar"><div class="'+cls+'" style="width:'+sc+'%"></div><span class="bval">'+Math.round(sc)+'</span></div>';
}}

function renderRow(s, rank) {{
  const tkHtml = s.rp
    ? '<a href="../reports/'+s.rp+'" class="tk" target="_blank">'+s.t+'</a>'
    : '<span class="tk" onclick="showModal(\''+s.t+'\')">'+s.t+'</span>';
  return [
    '<td class="rank">#'+rank+'</td>',
    '<td>'+tkHtml+'</td>',
    '<td class="cn" title="'+(s.n||'').replace(/"/g,"'")+'">'+((s.n||'&ndash;').substring(0,26))+'</td>',
    '<td><span class="badge">'+(s.ex||'?')+'</span></td>',
    '<td class="sec-cell" title="'+(s.sec||'')+'">'+((s.sec||'&ndash;').substring(0,16))+'</td>',
    '<td>'+fmtMcap(s.mc)+'</td>',
    '<td>'+fmtPrice(s.pr)+'</td>',
    '<td>'+fmtMos(s.mos)+'</td>',
    '<td>'+(s.pe!=null?(+s.pe).toFixed(1)+'x':'<span class="na">&ndash;</span>')+'</td>',
    '<td>'+(s.pb!=null?(+s.pb).toFixed(2)+'x':'<span class="na">&ndash;</span>')+'</td>',
    '<td>'+fmtPio(s.pf)+'</td>',
    '<td>'+fmtAz(s.az)+'</td>',
    '<td>'+(s.bc!=null?Math.round(s.bc)+'/14':'<span class="na">&ndash;</span>')+'</td>',
    '<td style="min-width:120px">'+catBadges(s.cat,s.hv)+'</td>',
    '<td>'+scoreBar(s.sc)+'</td>',
    '<td>'+gradeCircle(s.g)+'</td>',
    '<td>'+(s.rp?'<a href="../reports/'+s.rp+'" class="rlink" target="_blank">&#128196;</a>':'<span class="na">&ndash;</span>')+'</td>',
    '<td>'+actSpan(s.act||'PASS')+'</td>',
    '<td class="dt">'+(s.dt||'&ndash;')+'</td>',
  ].join('');
}}

function renderTable() {{
  const start = _page * PAGE_SIZE;
  const slice = _filtered.slice(start, start + PAGE_SIZE);
  const tbody = document.getElementById('tbody');
  const frag  = document.createDocumentFragment();
  slice.forEach((s, i) => {{
    const tr = document.createElement('tr');
    tr.className = gradeClass(s.g);
    tr.innerHTML = renderRow(s, start + i + 1);
    frag.appendChild(tr);
  }});
  tbody.innerHTML = '';
  tbody.appendChild(frag);
  _visibleTickers = _filtered.map(s=>s.t);
  renderPagination();
  const rc = document.getElementById('row-count');
  if (rc) rc.textContent = (_filtered.length===STOCKS.length?'All '+STOCKS.length:_filtered.length+' / '+STOCKS.length)+' stocks';
}}

function renderPagination() {{
  const pages = Math.ceil(_filtered.length / PAGE_SIZE);
  const pgbar = document.getElementById('pgbar');
  if (pages<=1) {{ pgbar.innerHTML=''; return; }}
  const maxBtn=10;
  let lo=Math.max(0,_page-Math.floor(maxBtn/2));
  let hi=Math.min(pages-1,lo+maxBtn-1);
  lo=Math.max(0,hi-maxBtn+1);
  let html='<span class="pginfo">Page</span>';
  if(lo>0) html+='<button class="pgbtn" onclick="goPage(0)">1</button><span class="pginfo">...</span>';
  for(let i=lo;i<=hi;i++) html+='<button class="pgbtn'+(i===_page?' active':'')+'" onclick="goPage('+i+')">'+(i+1)+'</button>';
  if(hi<pages-1) html+='<span class="pginfo">...</span><button class="pgbtn" onclick="goPage('+(pages-1)+')">'+(pages)+'</button>';
  html+='<span class="pginfo">&nbsp;('+_filtered.length+' results)</span>';
  pgbar.innerHTML=html;
}}

function goPage(p) {{ _page=p; renderTable(); window.scrollTo(0,0); }}

function applyFilters() {{
  const q      = (document.getElementById('srch').value||'').toLowerCase().trim();
  const sector = document.getElementById('flt-sector').value;
  const exch   = document.getElementById('flt-exch').value;
  _filtered = STOCKS.filter(s => {{
    if (_grade!=='ALL' && s.g!==_grade)   return false;
    if (_action!=='ALL' && s.act!==_action) return false;
    if (sector && s.sec!==sector) return false;
    if (exch   && s.ex!==exch)   return false;
    if (q && !s.t.toLowerCase().includes(q) && !(s.n||'').toLowerCase().includes(q)) return false;
    return true;
  }});
  if (_sortCol && _sortCol!=='rank') {{
    _filtered.sort((a,b) => {{
      let va=a[_sortCol], vb=b[_sortCol];
      if(va==null&&vb==null) return 0;
      if(va==null) return 1; if(vb==null) return -1;
      if(typeof va==='string') return va.localeCompare(vb)*_sortDir;
      return (va-vb)*_sortDir;
    }});
  }}
  _page=0; renderTable();
}}

function setGrade(g) {{
  _grade=g;
  ['ALL','A','B','C','D','F'].forEach(x=>{{const el=document.getElementById('gb-'+x);if(el) el.classList.toggle('active',x===g);}});
  applyFilters();
}}
function setAction(a) {{
  _action=a;
  ['ALL','BUY','WATCH','PASS'].forEach(x=>{{const el=document.getElementById('ab-'+x);if(el) el.classList.toggle('active',x===a);}});
  applyFilters();
}}
function sortBy(col,idx) {{
  if(_sortCol===col) _sortDir*=-1; else {{ _sortCol=col; _sortDir=-1; }}
  document.querySelectorAll('th').forEach(th=>th.classList.remove('sort-asc','sort-desc'));
  const th=document.querySelectorAll('th')[idx]; if(th) th.classList.add(_sortDir===1?'sort-asc':'sort-desc');
  applyFilters();
}}
function clearFilters() {{
  document.getElementById('srch').value='';
  document.getElementById('flt-sector').value='';
  document.getElementById('flt-exch').value='';
  _action='ALL';
  ['ALL','BUY','WATCH','PASS'].forEach(x=>{{const el=document.getElementById('ab-'+x);if(el) el.classList.remove('active');}});
  setGrade('A');
}}

function populateDropdowns() {{
  const sects=[...new Set(STOCKS.map(s=>s.sec).filter(Boolean))].sort();
  const exchs=[...new Set(STOCKS.map(s=>s.ex).filter(Boolean))].sort();
  const sel=document.getElementById('flt-sector');
  sects.forEach(s=>{{const o=document.createElement('option');o.value=s;o.textContent=s;sel.appendChild(o);}});
  const sel2=document.getElementById('flt-exch');
  exchs.forEach(e=>{{const o=document.createElement('option');o.value=e;o.textContent=e;sel2.appendChild(o);}});
}}

function renderStats() {{
  const gc=GRADE_COUNTS; const total=STOCKS.length;
  const items=[['Total Stocks',total,'var(--bl)'],['Grade A (BUY)',gc.A||0,'var(--gr)'],
    ['Grade B (WATCH)',gc.B||0,'var(--ye)'],['Grade C',gc.C||0,'var(--or)'],
    ['Grade D',gc.D||0,'var(--re)'],['Grade F',gc.F||0,'#e57373']];
  document.getElementById('stats-bar').innerHTML=items.map(([l,v,c])=>
    '<div class="st"><div class="stl">'+l+'</div><div class="stv" style="color:'+c+'">'+v+'</div></div>').join('');
  document.getElementById('total-count').textContent=total+' stocks analyzed';
}}

function showModal(ticker) {{
  const s=STOCKS.find(x=>x.t===ticker); if(!s) return;
  _modalIdx=_visibleTickers.indexOf(ticker); if(_modalIdx<0) _modalIdx=0;
  _renderModal(s);
}}
function _renderModal(s) {{
  document.getElementById('m-ticker').textContent=s.t;
  document.getElementById('m-name').textContent=s.n||'&ndash;';
  document.getElementById('m-badges').innerHTML=gradeCircle(s.g)+' '+actSpan(s.act||'PASS')+
    ' <span class="badge" style="margin-left:4px">'+(s.ex||'?')+'</span>'+
    (s.sec?' <span style="color:var(--mu);font-size:10px;margin-left:6px">'+s.sec+'</span>':'');
  const f=(v,d=2)=>v!=null?(+v).toFixed(d):'&ndash;';
  const fp=v=>v!=null?((+v)*100).toFixed(1)+'%':'&ndash;';
  const fd=v=>v!=null?'$'+(+v).toFixed(2):'&ndash;';
  let body='';
  if(s.ths||s.thd) {{
    body+='<div class="thesis-box"><h3>Investment Thesis</h3>';
    if(s.ths) body+='<div class="thesis-short">'+s.ths+'</div>';
    if(s.thd) body+='<div class="thesis-detail">'+s.thd+'</div>';
    body+='</div>';
  }}
  body+=mc3(
    mcard('Promise Score',Math.round(s.sc||0)+'/100',s.sc>=65?'var(--gr)':s.sc>=40?'var(--ye)':'var(--re)'),
    mcard('Price',fd(s.pr)),
    mcard('Mkt Cap',fmtMcapPlain(s.mc))
  );
  body+=mc3(
    mcard('Margin of Safety',s.mos!=null?((+s.mos)*100).toFixed(1)+'%':'&ndash;',s.mos>0.3?'var(--gr)':s.mos>0?'var(--ye)':'var(--re)'),
    mcard('Graham Number',fd(s.grn),undefined,'Intrinsic value est.'),
    mcard('DCF Value',fd(s.dcf),undefined,'Discounted cash flow')
  );
  body+='<div class="mrow">'+
    '<div class="mcard"><div class="mcard-lbl">Valuation</div><div style="font-size:11px;line-height:1.8;color:#a0c4e4">'+
    'P/E: <b>'+f(s.pe,1)+'x</b> &nbsp;|&nbsp; P/B: <b>'+f(s.pb)+'x</b> &nbsp;|&nbsp; P/S: <b>'+f(s.ps)+'x</b><br>'+
    'EV/EBITDA: <b>'+f(s.eve)+'x</b> &nbsp;|&nbsp; EV/Rev: <b>'+f(s.evr)+'x</b><br>'+
    'FCF Yield: <b>'+fp(s.fcf)+'</b> &nbsp;|&nbsp; Div Yield: <b>'+fp(s.dy)+'</b></div></div>'+
    '<div class="mcard"><div class="mcard-lbl">Quality</div><div style="font-size:11px;line-height:1.8;color:#a0c4e4">'+
    'ROE: <b>'+fp(s.roe)+'</b> &nbsp;|&nbsp; Gross Margin: <b>'+fp(s.gm)+'</b><br>'+
    'Op Margin: <b>'+fp(s.om)+'</b> &nbsp;|&nbsp; Rev Growth: <b>'+fp(s.rg)+'</b><br>'+
    'D/E: <b>'+f(s.de)+'</b> &nbsp;|&nbsp; Curr Ratio: <b>'+f(s.cr)+'</b></div></div></div>';
  body+=mc3(
    mcard('Piotroski F',s.pf!=null?Math.round(s.pf)+'/9':'&ndash;',s.pf>=7?'var(--gr)':s.pf>=5?'var(--ye)':'var(--re)'),
    mcard('Altman Z',s.az!=null?(+s.az).toFixed(2):'&ndash;',s.az>=3?'var(--gr)':s.az>=1.81?'var(--ye)':'var(--re)'),
    mcard('Buffett Check',s.bc!=null?Math.round(s.bc)+'/14':'&ndash;')
  );
  body+='<div class="mrow">'+
    '<div class="mcard"><div class="mcard-lbl">Market Context</div><div style="font-size:11px;line-height:1.8;color:#a0c4e4">'+
    'Beta: <b>'+f(s.beta)+'</b> &nbsp;|&nbsp; 52-Wk Pos: <b>'+fp(s.w52)+'</b><br>'+
    'Insider Own: <b>'+fp(s.ins)+'</b> &nbsp;|&nbsp; Short Int: <b>'+fp(s.si)+'</b><br>'+
    'Avg Volume: <b>'+(s.vol?(+s.vol).toLocaleString():'&ndash;')+'</b> &nbsp;|&nbsp; EPS: <b>'+f(s.eps)+'</b></div></div>'+
    '<div class="mcard"><div class="mcard-lbl">Catalysts &amp; Hidden Value</div><div style="font-size:11px;line-height:1.7;color:#a0c4e4">'+
    'Score: <b style="color:var(--te)">'+(s.cs||0)+'/25</b><br>'+(s.cat||s.hv||'<span style="color:var(--mu)">None detected</span>')+
    '</div></div></div>';
  document.getElementById('m-body').innerHTML=body;
  document.getElementById('m-nav-pos').textContent=(_modalIdx+1)+' / '+_visibleTickers.length;
  document.getElementById('modal').style.display='block';
  document.getElementById('overlay').style.display='block';
  document.body.style.overflow='hidden';
}}
function mcard(lbl,val,color,sub) {{
  return '<div class="mcard"><div class="mcard-lbl">'+lbl+'</div><div class="mcard-val"'+(color?' style="color:'+color+'"':'')+'>'+val+'</div>'+(sub?'<div class="mcard-sub">'+sub+'</div>':'')+'</div>';
}}
function mc3(a,b,c) {{ return '<div class="mrow3">'+a+b+c+'</div>'; }}
function navModal(dir) {{
  _modalIdx=Math.max(0,Math.min(_visibleTickers.length-1,_modalIdx+dir));
  const t=_visibleTickers[_modalIdx]; if(t) showModal(t);
}}
function closeModal() {{
  document.getElementById('modal').style.display='none';
  document.getElementById('overlay').style.display='none';
  document.body.style.overflow='';
}}
document.addEventListener('keydown',e=>{{
  if(e.key==='Escape') closeModal();
  if(document.getElementById('modal').style.display==='block') {{
    if(e.key==='ArrowLeft') navModal(-1);
    if(e.key==='ArrowRight') navModal(1);
  }}
}});

function exportCSV() {{
  const hdrs=['Ticker','Company','Exchange','Sector','MktCap','Price','MoS%','P/E','P/B','Piotroski','AltmanZ','Checklist','Score','Grade','Action','Date'];
  const lines=[hdrs.join(',')];
  _filtered.forEach(s=>{{lines.push([s.t,'"'+(s.n||'').replace(/"/g,"'")+'"',s.ex,'"'+(s.sec||'')+'"',
    s.mc!=null?s.mc:'',s.pr!=null?s.pr:'',s.mos!=null?((+s.mos)*100).toFixed(1):'',
    s.pe!=null?(+s.pe).toFixed(1):'',s.pb!=null?(+s.pb).toFixed(2):'',s.pf!=null?s.pf:'',
    s.az!=null?(+s.az).toFixed(2):'',s.bc!=null?s.bc:'',s.sc||0,s.g,s.act||'',s.dt||''].join(','));}});
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([lines.join('\\n')],{{type:'text/csv'}}));
  a.download='valuefund_screener.csv'; a.click();
}}

renderStats();
populateDropdowns();
setGrade('A');
</script>
</body>
</html>'''

    os.makedirs(os.path.dirname(HTML_PATH), exist_ok=True)
    with open(HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f'Dashboard written: {HTML_PATH}')
    print(f'Total stocks: {len(stocks)} | Duplicates removed: {dedup_count}')
    print(f'Grade breakdown: {grade_counts}')
    return HTML_PATH

if __name__ == '__main__':
    path = generate_html_index()
    print(f'Done -> {path}')

#!/usr/bin/env python3
"""
screener_quality.py -- publishing layer for the public screener (replaces dashboard_paginator.py).

Reads database/stocks.db (never writes to it) and writes:
  database/data/stocks_index.json   compact index for the list view
  database/data/stocks_pNNN.json    detail shards (100 tickers each)
  database/index_paged.html         copy of scripts/screener_v3.html

Quality rules applied before anything is graded:
  1. Funds, BDCs, shells, SPACs and non-common securities are excluded from the ranking.
  2. Rows with impossible values (data errors) are excluded and listed as "check data".
  3. Analyses older than MAX_AGE_DAYS are excluded as "stale".
  4. The rest are scored by percentile on value / quality / safety and graded on a curve:
     A = top 10%, B = next 20%, C = next 30%, D = next 25%, F = rest.
"""
import sqlite3, json, os, math, re, sys, shutil, argparse, bisect
from datetime import date, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import screener_enrich as enrich
except Exception as _e:
    enrich = None
    print("[WARN] extras disabled:", _e)
import screener_playbooks as playbooks

def soft(fn, default, *a, **k):
    """Run an optional step; never let it stop the publish."""
    if enrich is None: return default
    try:
        return getattr(enrich, fn)(*a, **k)
    except Exception as e:
        print("[WARN] %s skipped: %s" % (fn, e))
        return default

BASE   = r"D:\StockAnalysis"
DB     = os.path.join(BASE, "database", "stocks.db")
OUT    = os.path.join(BASE, "database", "data")
RANK   = os.path.join(BASE, "database", "value_ranking_latest.json")
TPL    = os.path.join(BASE, "scripts", "screener_v3.html")
HTML   = os.path.join(BASE, "database", "index_paged.html")
MAX_AGE_DAYS = 30
PAGE = 100

def num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None

FUND_ANY = re.compile(r"\b(fund|etf|closed[- ]end|municipal|muni|bdc)\b", re.I)
FUND_AM  = re.compile(r"\b(trust|income|opportunit\w*|dividend|bond|total return|premium|yield|portfolio|"
                      r"capital corp\w*|investment corp\w*|lending|shares)\b", re.I)
MANAGER  = re.compile(r"\b(asset management|partners|group|holdings|advisors|managers|financial|management)\b", re.I)
SHELL    = re.compile(r"\b(acquisition (corp\w*|company|co)|spac|blank check)\b", re.I)
NONCOMMON= re.compile(r"\b(warrants?|rights?|units?|preferred|depositary|notes due|debentures?)\b\s*$", re.I)

def classify(r):
    name = r.get("company_name") or ""
    ind  = r.get("industry") or ""
    if "Shell" in ind or SHELL.search(name): return "shell"
    if FUND_ANY.search(name): return "fund"
    if "Asset Management" in ind and (FUND_AM.search(name) or not MANAGER.search(name)): return "fund"
    if NONCOMMON.search(name): return "other"
    return "company"

def data_flags(r):
    f = []
    px, mos, pe, pb = num(r.get("current_price")), num(r.get("margin_of_safety")), num(r.get("pe_ratio")), num(r.get("pb_ratio"))
    alt, mc = num(r.get("altman_z")), (r.get("_mc_usd") if r.get("_mc_usd") is not None else num(r.get("market_cap")))
    dcf, gra, fcf = num(r.get("dcf_value")), num(r.get("graham_number")), num(r.get("fcf_yield"))
    if mos is not None and mos >= 90: f.append("Margin of safety of 90% or more")
    if pe is not None and 0 < pe < 2: f.append("P/E below 2")
    if pb is not None and 0 < pb < 0.1: f.append("Price to book below 0.1")
    if alt is not None and (alt > 30 or alt < -10): f.append("Altman Z outside the plausible range")
    if px and dcf and dcf / px > 20: f.append("DCF value more than 20 times the price")
    if px and gra and gra / px > 10: f.append("Graham number more than 10 times the price")
    if fcf is not None and abs(fcf) > 1: f.append("Free cash flow yield above 100%")
    if mc is not None and mc < 5e6: f.append("Market cap under $5M")
    if not px or px <= 0: f.append("No price")
    return f

def clip(v, lo, hi):
    return None if v is None else max(lo, min(hi, v))

def factors(r):
    """Higher is always better. None = not available."""
    pe, pb = num(r.get("pe_ratio")), num(r.get("pb_ratio"))
    ev, de = num(r.get("ev_ebitda")), num(r.get("debt_equity"))
    return {
      "value": {
        "ey":   None if pe is None else (1.0 / pe if pe > 0 else -1.0),
        "mos":  clip(num(r.get("margin_of_safety")), -100, 90),
        "pb":   None if pb is None else (-pb if pb > 0 else -1e9),
        "fcfy": clip(num(r.get("fcf_yield")), -1, 1),
        "evebitda": None if ev is None else (-ev if ev > 0 else -1e9),
      },
      "quality": {
        "piotroski": num(r.get("piotroski_score")),
        "roe":  clip(num(r.get("roe")), -1, 1),
        "gm":   clip(num(r.get("gross_margin")), -1, 1),
        "om":   clip(num(r.get("operating_margin")), -1, 1),
        "revg": clip(num(r.get("revenue_growth")), -0.5, 1),
      },
      "safety": {
        "altman": clip(num(r.get("altman_z")), -10, 30),
        "de":   None if de is None else (-de if de >= 0 else -1e9),
        "curr": clip(num(r.get("current_ratio")), 0, 10),
      },
    }

WEIGHTS = {"value": 0.45, "quality": 0.30, "safety": 0.25}

def pct_rank(sorted_vals, v):
    n = len(sorted_vals)
    if n < 2: return 50.0
    lo = bisect.bisect_left(sorted_vals, v); hi = bisect.bisect_right(sorted_vals, v)
    return round(100.0 * ((lo + hi) / 2.0) / n, 1)

def pj(s):
    try:
        d = json.loads(s) if s else []
    except Exception:
        return []
    return d if isinstance(d, list) else []

def main():
    today = date.today()
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = [dict(x) for x in conn.execute("SELECT * FROM analyzed_stocks")]
    conn.close()
    if not rows:
        print("[WARN] No stocks in database."); return 0

    prof = soft("profiles", {})
    fx = soft("fx_rates", {"as_of": None, "rates": {}})
    hist = soft("history", {}, [r["ticker"] for r in rows])
    for r in rows:
        pr = prof.get(r["ticker"], {})
        r["_cur"] = pr.get("cur") or ("USD" if "." not in r["ticker"] else None)
        r["_adr"] = bool(pr.get("adr"))
        base = enrich.SUBUNIT.get(r["_cur"], (r["_cur"], 1))[0] if enrich else r["_cur"]
        r["_mc_usd"] = enrich.to_usd(num(r.get("market_cap")), base, fx["rates"]) if enrich else None
        r["_px_usd"] = enrich.to_usd(num(r.get("current_price")), r["_cur"], fx["rates"]) if enrich else None
        r["_kind"] = "fund" if (pr.get("etf") or pr.get("fund")) else classify(r)
        r["_flags"] = data_flags(r)
        try:
            r["_age"] = (today - date.fromisoformat((r.get("analysis_date") or "")[:10])).days
        except ValueError:
            r["_age"] = None
        r["_pb"], r["_grp"], r["_f"], r["_metrics"], r["_review"], r["_notes"] = playbooks.build(r, hist.get(r["ticker"]), fx["rates"], enrich)
        if r["_kind"] != "company": r["_status"] = r["_kind"]
        elif r["_age"] is None or r["_age"] > MAX_AGE_DAYS: r["_status"] = "stale"
        elif r["_flags"]: r["_status"] = "check"
        else: r["_status"] = "ok"

    # one row per company: several listings of the same business (OTC, home market, London) count once
    def listing_pref(r):
        tk = r["ticker"]
        return (0 if "." not in tk and "-" not in tk else 1, -(num(r.get("avg_volume")) or 0), tk)
    seen = {}
    for r in sorted(rows, key=listing_pref):
        key = re.sub(r"[^a-z0-9]", "", (r.get("company_name") or r["ticker"]).lower())
        if not key: continue
        if key in seen:
            if r["_status"] in ("ok", "check", "stale"): r["_status"] = "dup"; r["_dup_of"] = seen[key]
        elif r["_status"] in ("ok", "check", "stale"):
            seen[key] = r["ticker"]
    for r in rows:
        if r["_status"] == "ok" and num(r.get("piotroski_score")) is None and num(r.get("altman_z")) is None:
            r["_status"] = "nodata"
    pool = [r for r in rows if r["_status"] == "ok"]
    # percentiles: banks, insurers, REITs, biotech and software are compared inside their own group
    dist = {}
    for r in pool:
        for p in WEIGHTS:
            for k, (_, v, _) in r["_f"][p].items():
                if v is None: continue
                dist.setdefault((r["_grp"], k), []).append(v)
                if r["_grp"] != "*": dist.setdefault(("*", k), []).append(v)
    for v in dist.values(): v.sort()
    def dist_for(r, k):
        d = dist.get((r["_grp"], k), [])
        return d if len(d) >= 30 else dist.get(("*", k), d)
    w52 = sorted(v for v in (num(r.get("week52_position")) for r in pool) if v is not None)
    cat = sorted(v for v in (num(r.get("catalyst_score")) for r in pool) if v is not None)

    for r in rows:
        r["_pc"] = {}; r["_pillar"] = {}; r["_factors"] = {}
        for p in WEIGHTS:
            vals = []; r["_factors"][p] = []
            for k, (label, v, shown) in r["_f"][p].items():
                pc = None
                if v is not None:
                    d = dist_for(r, k)
                    if d: pc = pct_rank(d, v); r["_pc"][k] = pc; vals.append(pc)
                r["_factors"][p].append([label, shown, pc])
            r["_pillar"][p] = round(sum(vals) / len(vals), 1) if len(vals) >= 2 else None
        v = num(r.get("week52_position")); r["_pillar"]["momentum"] = pct_rank(w52, v) if v is not None and w52 else None
        v = num(r.get("catalyst_score"));  r["_pillar"]["catalysts"] = pct_rank(cat, v) if v is not None and cat else None
        have = {p: r["_pillar"][p] for p in WEIGHTS if r["_pillar"][p] is not None}
        if "value" in have and len(have) >= 2:
            r["_comp"] = round(sum(have[p] * WEIGHTS[p] for p in have) / sum(WEIGHTS[p] for p in have), 1)
        else:
            r["_comp"] = None
            if r["_status"] == "ok": r["_status"] = "nodata"

    ranked = sorted((r for r in rows if r["_status"] == "ok"), key=lambda r: -r["_comp"])
    n = len(ranked)
    for i, r in enumerate(ranked):
        q = i / n
        r["_grade"] = "A" if q < .10 else "B" if q < .30 else "C" if q < .60 else "D" if q < .85 else "F"
        r["_rank"] = i + 1
    rest = sorted((r for r in rows if r["_status"] != "ok"), key=lambda r: -(r["_comp"] or -1))
    for r in rest: r["_grade"] = "-"; r["_rank"] = None
    ordered = ranked + rest
    ins = soft("insiders", {}, [r["ticker"] for r in ranked if r["_grade"] == "A"])

    extra = {}
    try:
        with open(RANK, encoding="utf-8") as fh:
            vr = json.load(fh)
        for x in vr.get("rows", []):
            extra[x["s"]] = {"rank": x.get("r"), "of": len(vr["rows"]), "sc": x.get("sc"), "notes": x.get("fl"),
                             "as_of": vr.get("as_of"),
                             "m": {k: x.get("m", {}).get(k) for k in ("roic","nby","dil","up","anb","anh","ans","fwdg","icov")}}
    except Exception as e:
        print("[WARN] value ranking not merged:", e)

    os.makedirs(OUT, exist_ok=True)
    cols = ["t","n","g","c","v","q","s","sec","x","px","mc","mos","pe","pb","pio","alt","d","st","p","r","cur","pl","ib","rv"]
    idx = []
    for i, r in enumerate(ordered):
        pg = i // PAGE + 1
        r["_page"] = pg
        idx.append([r["ticker"], (r.get("company_name") or "")[:48], r["_grade"], r["_comp"],
                    r["_pillar"]["value"], r["_pillar"]["quality"], r["_pillar"]["safety"],
                    r.get("sector") or "Unknown", r.get("exchange") or "", num(r.get("current_price")),
                    (round(r["_mc_usd"]) if r["_mc_usd"] is not None else num(r.get("market_cap"))), None if num(r.get("margin_of_safety")) is None else round(num(r.get("margin_of_safety")), 1),
                    None if num(r.get("pe_ratio")) is None else round(num(r.get("pe_ratio")), 2),
                    None if num(r.get("pb_ratio")) is None else round(num(r.get("pb_ratio")), 2),
                    num(r.get("piotroski_score")), None if num(r.get("altman_z")) is None else round(num(r.get("altman_z")), 1),
                    (r.get("analysis_date") or "")[:10], r["_status"], pg, r["_rank"], r["_cur"],
                    playbooks.NAMES[r["_pb"]], (ins.get(r["ticker"]) or {}).get("buy_usd") or None, len(r["_review"]) or None])
    counts = {}
    for r in rows: counts[r["_status"]] = counts.get(r["_status"], 0) + 1
    grades = {}
    for r in ranked: grades[r["_grade"]] = grades.get(r["_grade"], 0) + 1
    pbc = {}
    for r in ranked: pbc[playbooks.NAMES[r["_pb"]]] = pbc.get(playbooks.NAMES[r["_pb"]], 0) + 1
    meta = {"generated": datetime.now().isoformat()[:16], "total": len(rows), "ranked": n, "counts": counts,
            "grades": grades, "playbooks": pbc, "fx_as_of": fx.get("as_of"), "max_age_days": MAX_AGE_DAYS, "weights": WEIGHTS, "cols": cols, "rows": idx}
    with open(os.path.join(OUT, "stocks_index.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, separators=(",", ":"))

    keep = ["graham_number","dcf_value","net_net_value","margin_of_safety","pe_ratio","pb_ratio","ps_ratio","fcf_yield",
            "ev_ebitda","ev_revenue","dividend_yield","roe","gross_margin","operating_margin","revenue_growth","debt_equity",
            "current_ratio","beta","insider_pct","short_interest_pct","week52_position","piotroski_score","altman_z",
            "buffett_checklist","magic_formula_ey","bvps","avg_volume"]
    pages = math.ceil(len(ordered) / PAGE)
    for pg in range(1, pages + 1):
        out = {}
        for r in ordered[(pg - 1) * PAGE: pg * PAGE]:
            d = {"ticker": r["ticker"], "name": r.get("company_name") or "", "exchange": r.get("exchange") or "",
                 "sector": r.get("sector") or "Unknown", "industry": r.get("industry") or "Unknown",
                 "price": num(r.get("current_price")), "market_cap": num(r.get("market_cap")),
                 "date": (r.get("analysis_date") or "")[:10], "age": r["_age"], "status": r["_status"],
                 "grade": r["_grade"], "rank": r["_rank"], "ranked": n, "composite": r["_comp"],
                 "dup_of": r.get("_dup_of"), "pillars": r["_pillar"], "pct": r["_pc"], "playbook": playbooks.NAMES[r["_pb"]],
                 "own_group": r["_grp"] != "*", "factors": r["_factors"], "metrics": r["_metrics"], "review": r["_review"], "notes": r["_notes"], "flags": r["_flags"],
                 "catalysts": pj(r.get("catalysts")), "hidden_value": pj(r.get("hidden_value_notes")),
                 "short_thesis": (r.get("short_thesis") or "") if r.get("short_thesis") != "None" else "",
                 "detailed_thesis": (r.get("detailed_thesis") or "") if r.get("detailed_thesis") != "None" else ""}
            for k in keep: d[k] = num(r.get(k))
            d["cur"], d["adr"] = r["_cur"], r["_adr"]
            d["mc_usd"] = round(r["_mc_usd"]) if r["_mc_usd"] is not None else None
            d["px_usd"] = round(r["_px_usd"], 4) if r["_px_usd"] is not None else None
            if r["ticker"] in hist: d["hist"] = hist[r["ticker"]]
            if r["ticker"] in ins: d["ins"] = ins[r["ticker"]]
            if r["ticker"] in extra: d["vr"] = extra[r["ticker"]]
            out[r["ticker"]] = d
        with open(os.path.join(OUT, "stocks_p%03d.json" % pg), "w", encoding="utf-8") as fh:
            json.dump({"page": pg, "total_pages": pages, "stocks": out}, fh, separators=(",", ":"))
    for fn in os.listdir(OUT):
        m = re.match(r"stocks_p(\d+)\.json$", fn)
        if m and int(m.group(1)) > pages: os.remove(os.path.join(OUT, fn))

    if os.path.exists(TPL): shutil.copyfile(TPL, HTML)
    else: print("[WARN] template missing:", TPL); return 3
    print("  [OK] playbooks", pbc, "| to review", sum(1 for r in ranked if r["_review"]), "| debt fixed", sum(1 for r in rows if any("balance sheet" in x for x in r["_notes"])))
    print("  [OK] total %d | ranked %d | grades %s | excluded %s | pages %d" % (len(rows), n, grades, counts, pages))
    return 0

if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).add_argument("--page", type=int, default=100)
    sys.exit(main())

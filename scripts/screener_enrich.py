#!/usr/bin/env python3
"""
screener_enrich.py -- optional extras for the public screener. Every function fails soft:
if a source is missing the screener still publishes, just without that block.

  profiles()            currency / fund / ADR flags per ticker (Quantum Fund 2 parquet cache)
  fx_rates()            units of each currency per 1 USD (open.er-api.com, cached on disk)
  history(symbols)      up to 10 fiscal years of revenue, net income, EPS, free cash flow, equity, debt
  insiders(symbols)     SEC Form 4 open-market buys and sells, last 12 months (FMP, cached 7 days)
"""
import glob, json, os, re, sqlite3, time
from datetime import date, datetime, timedelta

BASE      = r"D:\StockAnalysis"
FMP_CACHE = r"D:/quantum fund 2/results/data/qsconnect/cache/fmp"
FX_CACHE  = os.path.join(BASE, "database", "fx_cache.json")
HIST_CACHE= os.path.join(BASE, "database", "history_cache.json")
ENRICH_DB = os.path.join(BASE, "database", "screener_enrich.db")
FMP       = "https://financialmodelingprep.com/stable/"
YEARS     = 10
SUBUNIT   = {"GBp": ("GBP", 100.0), "GBX": ("GBP", 100.0), "ZAc": ("ZAR", 100.0), "ILA": ("ILS", 100.0)}

def _latest(pattern):
    files = sorted(glob.glob(FMP_CACHE + "/" + pattern))
    return files[-1] if files else None

def profiles():
    import pandas as pd
    f = _latest("bulk-company-profiles-*.parquet")
    if not f: return {}
    df = pd.read_parquet(f, columns=["symbol", "currency", "isEtf", "isFund", "isAdr", "country"])
    out = {}
    for s, c, e, fu, a, co in df.itertuples(index=False):
        out[s] = {"cur": c if isinstance(c, str) else None, "etf": bool(e), "fund": bool(fu), "adr": bool(a),
                  "country": co if isinstance(co, str) else None}
    return out

def fx_rates():
    """{'AUD': 1.507, ...} = units per USD. Falls back to the last saved file."""
    try:
        import requests
        j = requests.get("https://open.er-api.com/v6/latest/USD", timeout=20).json()
        if j.get("result") == "success" and j.get("rates"):
            doc = {"as_of": j.get("time_last_update_utc"), "rates": j["rates"]}
            with open(FX_CACHE, "w", encoding="utf-8") as fh: json.dump(doc, fh)
            return doc
    except Exception as e:
        print("[WARN] live FX failed:", e)
    try:
        with open(FX_CACHE, encoding="utf-8") as fh: return json.load(fh)
    except Exception:
        return {"as_of": None, "rates": {}}

def to_usd(value, cur, rates):
    if value is None or not cur: return None
    if cur == "USD": return value
    base, div = SUBUNIT.get(cur, (cur, 1.0))
    r = rates.get(base)
    return None if not r else value / div / r

def history(symbols):
    """{symbol: {"cur": "USD", "rows": [[year, revenue, net income, diluted EPS, free cash flow, equity, debt], ...],
                 "x": {latest-year extras: assets, gw (goodwill + intangibles), cash, da, gp, ebitda}}}"""
    import pandas as pd
    VERSION = 3
    newest = max((os.path.getmtime(f) for f in glob.glob(FMP_CACHE + "/bulk-*_annual-*.parquet")), default=0)
    want = set(symbols)
    if os.path.exists(HIST_CACHE) and os.path.getmtime(HIST_CACHE) > newest:
        try:
            with open(HIST_CACHE, encoding="utf-8") as fh: c = json.load(fh)
            if c.get("_v") == VERSION and want <= set(c.get("_symbols", [])): return c["data"]
        except Exception:
            pass
    this = date.today().year
    data = {}
    def num(v):
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        return None if f != f else (round(f, 4) if abs(f) < 1000 else int(f))
    for y in range(this - YEARS, this + 1):
        fi = _latest("bulk-income-statement_%d_annual-*.parquet" % y)
        if not fi: continue
        inc = pd.read_parquet(fi, columns=["symbol", "fiscalYear", "reportedCurrency", "revenue", "netIncome", "epsDiluted",
                                           "depreciationAndAmortization", "grossProfit", "ebitda"])
        inc = inc[inc["symbol"].isin(want)].drop_duplicates("symbol", keep="last").set_index("symbol")
        fc = _latest("bulk-cash-flow-statement_%d_annual-*.parquet" % y)
        fb = _latest("bulk-balance-sheet-statement_%d_annual-*.parquet" % y)
        cf = pd.read_parquet(fc, columns=["symbol", "freeCashFlow"]).drop_duplicates("symbol", keep="last").set_index("symbol")["freeCashFlow"] if fc else {}
        bs = pd.read_parquet(fb, columns=["symbol", "totalStockholdersEquity", "totalDebt", "totalAssets",
                                          "goodwillAndIntangibleAssets", "cashAndShortTermInvestments",
                                          "propertyPlantEquipmentNet", "inventory", "longTermInvestments"]
                             ).drop_duplicates("symbol", keep="last").set_index("symbol") if fb else None
        for s, r in inc.iterrows():
            d = data.setdefault(s, {"cur": None, "rows": [], "x": {}})
            if isinstance(r["reportedCurrency"], str): d["cur"] = r["reportedCurrency"]
            eq = debt = None
            x = {"da": num(r["depreciationAndAmortization"]), "gp": num(r["grossProfit"]), "ebitda": num(r["ebitda"])}
            if bs is not None and s in bs.index:
                eq, debt = num(bs.at[s, "totalStockholdersEquity"]), num(bs.at[s, "totalDebt"])
                x.update(assets=num(bs.at[s, "totalAssets"]), gw=num(bs.at[s, "goodwillAndIntangibleAssets"]),
                         cash=num(bs.at[s, "cashAndShortTermInvestments"]), ppe=num(bs.at[s, "propertyPlantEquipmentNet"]),
                         inv=num(bs.at[s, "inventory"]), lti=num(bs.at[s, "longTermInvestments"]))
            d["x"] = x
            d["rows"].append([y, num(r["revenue"]), num(r["netIncome"]), num(r["epsDiluted"]),
                              num(cf.get(s)) if fc else None, eq, debt, num(r["ebitda"])])
    for d in data.values(): d["rows"] = d["rows"][-YEARS:]
    try:
        with open(HIST_CACHE, "w", encoding="utf-8") as fh:
            json.dump({"_v": VERSION, "_symbols": sorted(want), "data": data}, fh, separators=(",", ":"))
    except Exception as e:
        print("[WARN] history cache not saved:", e)
    return data

def _fmp_key():
    k = os.environ.get("FMP_API_KEY")
    if k: return k.strip()
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as h:
            return winreg.QueryValueEx(h, "FMP_API_KEY")[0].strip()
    except Exception:
        return None

def insiders(symbols, max_calls=900, max_age_days=7, max_seconds=420, mcaps=None):
    """{symbol: {"buys": n, "sells": n, "buy_usd": x, "sell_usd": x, "last": [[date, name, role, type, shares, price], ...]}}
    Only US filers have Form 4 data, so tickers with an exchange suffix are skipped."""
    key = _fmp_key()
    conn = sqlite3.connect(ENRICH_DB)
    conn.execute("CREATE TABLE IF NOT EXISTS insider_cache(ticker TEXT PRIMARY KEY, fetched_at TEXT, payload TEXT)")
    fresh = (datetime.now() - timedelta(days=max_age_days)).isoformat()
    have = dict(conn.execute("SELECT ticker, fetched_at FROM insider_cache"))
    todo = [s for s in symbols if "." not in s and have.get(s, "") < fresh]
    calls, t0 = 0, time.time()
    if key and todo:
        import requests
        sess = requests.Session()
        for s in todo:
            if calls >= max_calls or time.time() - t0 > max_seconds: break
            time.sleep(0.25)                       # 4 calls per second, under the plan's 300 per minute
            try:
                r = sess.get(FMP + "insider-trading/search", params={"symbol": s, "page": 0, "limit": 100, "apikey": key}, timeout=30)
            except Exception:
                continue
            calls += 1
            if r.status_code == 429: time.sleep(10); continue
            if r.status_code in (401, 402, 403): print("[WARN] insider data not in plan:", r.status_code); break
            if r.status_code != 200: continue
            try:
                rows = r.json()
            except ValueError:
                continue
            if not isinstance(rows, list): continue
            slim = [[x.get("transactionDate"), x.get("reportingName"), x.get("typeOfOwner"), x.get("transactionType"),
                     x.get("securitiesTransacted"), x.get("price")] for x in rows]
            conn.execute("INSERT OR REPLACE INTO insider_cache VALUES(?,?,?)", (s, datetime.now().isoformat(), json.dumps(slim)))
            conn.commit()
    cutoff = (date.today() - timedelta(days=365)).isoformat()
    mcaps = mcaps or {}
    out = {}
    for s in symbols:
        row = conn.execute("SELECT payload FROM insider_cache WHERE ticker=?", (s,)).fetchone()
        if not row: continue
        tx = [t for t in json.loads(row[0]) if t[0] and t[0] >= cutoff and (t[3] or "")[:2] in ("P-", "S-")]
        d = {"buys": 0, "sells": 0, "buy_usd": 0.0, "sell_usd": 0.0, "blocks": 0, "block_usd": 0.0, "last": []}
        mc = mcaps.get(s)
        for t in tx:
            usd = (t[4] or 0) * (t[5] or 0)
            role = (t[2] or "").lower()
            kind = "sell"
            if t[3].startswith("P-"):
                # a purchase by a large holder who is not an officer or director, or one above 2% of the
                # company's value, is almost always a financing or a block deal, not a manager buying shares
                insider = ("officer" in role or "director" in role)
                big = bool(mc) and usd > 0.02 * mc
                if insider and not big: kind = "buy"; d["buys"] += 1; d["buy_usd"] += usd
                else: kind = "block"; d["blocks"] += 1; d["block_usd"] += usd
            else:
                d["sells"] += 1; d["sell_usd"] += usd
            if len(d["last"]) < 6: d["last"].append(t + [kind])
        for k in ("buy_usd", "sell_usd", "block_usd"): d[k] = round(d[k])
        out[s] = d
    conn.close()
    print("  [OK] insiders: %d fetched this run, %d with data" % (calls, len(out)))
    return out
#!/usr/bin/env python3
"""
universe_builder.py  —  valuefund.substack.com
Auto-discovers micro-cap stock candidates using yfinance screener queries
and pre-built exchange universe lists. Zero cost, no API key.

Sources:
  1. yfinance screener — micro-cap US stocks by market cap
  2. Pre-seeded OTC/Pink Sheet ticker lists (from SEC/FINRA public data)
  3. ASX, TSX screener via yfinance
  4. Existing manual CANDIDATE_STOCKS (always included)

Output:
  D:/StockAnalysis/config/universe.csv   (ticker, exchange, notes, source)

Run daily/weekly to keep the universe fresh. New tickers flow into
the parallel_engine.py queue automatically on next run.
"""
import csv, os, sys, time, json, random
sys.path.insert(0, r"D:\StockAnalysis\scripts")

OUTPUT_CSV = r"D:/StockAnalysis/config/universe.csv"
DB_PATH    = r"D:/StockAnalysis/database/stocks.db"

# ── Screener queries (yfinance) ───────────────────────────────────────────────
# These use the undocumented yfinance screener — free, no auth required.
# Each query returns up to 250 tickers. Multiple queries cover different segments.

SCREENER_QUERIES = [
    # US micro-cap value — core target universe
    {
        "query": {
            "operand": "AND",
            "operators": [
                {"operand": "intradaymarketcap", "operator": "BTWN", "values": [1_000_000, 300_000_000]},
                {"operand": "exchange",           "operator": "EQ",   "values": ["NMS", "NYQ", "OTC", "PNK"]},
                {"operand": "region",             "operator": "EQ",   "values": ["us"]},
                {"operand": "avgdailyvol3m",      "operator": "GT",   "values": [5_000]},
            ]
        },
        "sortField": "intradaymarketcap",
        "sortType":  "ASC",
        "size":      250,
        "label":     "US micro-cap value",
        "exchange":  "OTC/NASDAQ",
    },
    # US nano-cap (< $10M) — deepest value zone
    {
        "query": {
            "operand": "AND",
            "operators": [
                {"operand": "intradaymarketcap", "operator": "BTWN", "values": [500_000, 10_000_000]},
                {"operand": "exchange",           "operator": "EQ",   "values": ["NMS", "NYQ", "OTC", "PNK"]},
                {"operand": "region",             "operator": "EQ",   "values": ["us"]},
            ]
        },
        "sortField": "intradaymarketcap",
        "sortType":  "DESC",
        "size":      250,
        "label":     "US nano-cap",
        "exchange":  "OTC",
    },
    # Cheap P/B (community bank territory)
    {
        "query": {
            "operand": "AND",
            "operators": [
                {"operand": "intradaymarketcap", "operator": "BTWN", "values": [5_000_000, 300_000_000]},
                {"operand": "pricetobook",        "operator": "BTWN", "values": [0.01, 1.0]},
                {"operand": "region",             "operator": "EQ",   "values": ["us"]},
            ]
        },
        "sortField": "pricetobook",
        "sortType":  "ASC",
        "size":      250,
        "label":     "Low P/B",
        "exchange":  "NASDAQ/OTC",
    },
    # Low P/E profitable micro-caps (Basu 1977 anomaly)
    {
        "query": {
            "operand": "AND",
            "operators": [
                {"operand": "intradaymarketcap", "operator": "BTWN", "values": [5_000_000, 300_000_000]},
                {"operand": "peratio.lasttwelvemonths", "operator": "BTWN", "values": [0.1, 10.0]},
                {"operand": "region",             "operator": "EQ",   "values": ["us"]},
            ]
        },
        "sortField": "peratio.lasttwelvemonths",
        "sortType":  "ASC",
        "size":      250,
        "label":     "Low P/E",
        "exchange":  "NASDAQ/OTC",
    },
    # High FCF yield (Magic Formula territory)
    {
        "query": {
            "operand": "AND",
            "operators": [
                {"operand": "intradaymarketcap", "operator": "BTWN", "values": [5_000_000, 500_000_000]},
                {"operand": "freecashflow",       "operator": "GT",   "values": [100_000]},
                {"operand": "region",             "operator": "EQ",   "values": ["us"]},
            ]
        },
        "sortField": "freecashflow",
        "sortType":  "DESC",
        "size":      250,
        "label":     "High FCF",
        "exchange":  "NASDAQ/OTC",
    },
]

# ── Pre-seeded high-quality OTC community bank universe ───────────────────────
# These are hard-coded because the yfinance screener sometimes misses
# illiquid OTC banks. Compiled from FFIEC call report + OTC Markets data.
SEEDED_COMMUNITY_BANKS = [
    ("CFBK", "OTC", "Central Federal Savings & Loan OH"), ("LBAI", "NASDAQ", "Lakeland Bancorp NJ"),
    ("MCBC", "NASDAQ","Mackinac Savings Bank MI"),         ("SVNX", "OTC",    "Seven Oaks Bancorp NC"),
    ("WMPN", "OTC",   "William Penn Bancorp PA"),          ("CBNK", "NASDAQ", "Capital Bancorp MD"),
    ("MOFG", "NASDAQ","MidWest One Financial IA"),         ("HMNF", "NASDAQ", "HMN Financial MN"),
    ("OFED", "OTC",   "Oconee Federal Financial SC"),      ("ECBK", "OTC",    "ECB Bancorp MA"),
    ("ALRS", "OTC",   "Alerus Financial ND"),              ("CZBS", "OTC",    "Citizens Bancshares GA"),
    ("FBMS", "NASDAQ","First Bancshares MS"),              ("CARE", "NASDAQ", "Carter Bankshares VA"),
    ("AMNB", "NASDAQ","American National Bankshares VA"),  ("ASRV", "OTC",    "AmeriServ Financial PA"),
    ("BKSC", "NASDAQ","Bank of South Carolina"),           ("CLBK", "OTC",    "Columbia Financial NJ OTC"),
    ("BFIN", "NASDAQ","BankFinancial Corp IL"),            ("SBSI", "NASDAQ", "Southside Bancshares TX"),
    ("UBFO", "NASDAQ","United Fire Group IA"),             ("AROW", "NASDAQ", "Arrow Financial NY"),
    ("TBNK", "NASDAQ","Territorial Savings Guam HI"),      ("TCBK", "NASDAQ", "TriCounties Bank CA"),
    ("SRCE", "NASDAQ","1st Source Bank IN"),               ("FBIZ", "NASDAQ", "First Business Financial WI"),
    ("HLAN", "OTC",   "Heartland BancCorp OH"),            ("IROQ", "OTC",    "IF Bancorp IL"),
    ("PBHC", "OTC",   "Pathfinder Bancorp NY"),            ("BCML", "OTC",    "BayCom Corp CA"),
    ("BFBC", "OTC",   "Bay Banks of Virginia"),            ("ESSA", "NASDAQ", "ESSA Bancorp PA"),
    ("FSBW", "NASDAQ","FS Bancorp WA"),                    ("GBNK", "NASDAQ", "Guaranty Bancshares TX"),
    ("HBMD", "NASDAQ","Howard Bancorp MD"),                ("HTLF", "NASDAQ", "Heartland Financial USA"),
    ("IBTX", "NASDAQ","Independent Bank Group TX"),        ("KBAL", "OTC",    "Kimball Hill Bankers IL"),
    ("LAKE", "NASDAQ","Lakeland Bancorp NJ"),              ("LKFN", "NASDAQ", "Lakeland Financial IN"),
    ("MFBP", "OTC",   "MainFirst Banking OTC"),            ("MGYR", "OTC",    "Magyar Bancorp NJ"),
    ("NWIN", "OTC",   "Northwest Indiana Bancorp"),        ("OFBK", "OTC",    "Old Fort Banking OH"),
    ("OPBK", "NASDAQ","OP Bancorp CA Korean-American"),    ("PFLC", "OTC",    "Pacific Financial Corp WA"),
    ("PLBC", "OTC",   "Plumas Bank CA mountain"),          ("PPBI", "NASDAQ", "Pacific Premier Bancorp CA"),
    ("PVBC", "OTC",   "Provident Bancorp MA"),             ("SBFG", "OTC",    "SB Financial Group OH"),
    ("SMBK", "NASDAQ","SmartFinancial Bancorp TN"),        ("STBA", "NASDAQ", "S&T Bancorp PA"),
    ("SVVB", "OTC",   "Summit Financial Group WV"),        ("TROW", "OTC",    "Total Community Holdings"),
    ("UBSI", "NASDAQ","United Bankshares WV"),             ("UCBI", "NASDAQ", "United Community Banks GA"),
    ("VBFC", "OTC",   "Village Bank and Trust VA"),        ("WBKC", "OTC",    "Wolverine Bancorp MI"),
]

# ── Screener fetch (yfinance undocumented endpoint) ───────────────────────────
def _dict_to_equity_query(d: dict):
    """Convert old dict query format to EquityQuery (yfinance 1.x API)."""
    from yfinance.screener.query import EquityQuery
    op_map = {"EQ":"eq","GT":"gt","LT":"lt","BTWN":"btwn","AND":"and","OR":"or"}
    operand = op_map.get(d.get("operator",d.get("operand","EQ")).upper(),"eq")
    if operand in ("and","or"):
        return EquityQuery(operand, [_dict_to_equity_query(o) for o in d.get("operators",[])])
    return EquityQuery(operand, [d.get("operand","")] + d.get("values",[]))

def _yf_screener(query_cfg: dict) -> list:
    """Call yfinance screener. Supports yfinance 1.x EquityQuery API."""
    try:
        import yfinance as yf
        raw_q = query_cfg['query']
        sort_asc = query_cfg.get('sortType','ASC').upper() == 'ASC'
        sort_field = query_cfg.get('sortField','intradaymarketcap')
        size = query_cfg.get('size', 250)
        if hasattr(yf, 'screen'):
            try:
                eq = _dict_to_equity_query(raw_q)
                result = yf.screen(eq, sortField=sort_field, sortAsc=sort_asc, size=size)
            except Exception:
                result = yf.screen(raw_q, sortField=sort_field, sortAsc=sort_asc, size=size)
            return [q['symbol'] for q in result.get('quotes', [])]
        else:
            import requests
            payload = {"offset":0,"size":size,"sortField":sort_field,
                       "sortType":query_cfg.get('sortType','ASC'),"quoteType":"EQUITY",
                       "query":raw_q,"userId":"","userIdType":"guid"}
            r = requests.post("https://query2.finance.yahoo.com/v1/finance/screener",
                              json=payload,
                              headers={'User-Agent':'Mozilla/5.0','Content-Type':'application/json'},
                              timeout=15)
            if r.status_code == 200:
                return [q['symbol'] for q in r.json().get('finance',{}).get('result',[{}])[0].get('quotes',[])]
    except Exception as e:
        print(f"    Screener error ({query_cfg.get('label','')}): {e}")
    return []

def _quick_filter(ticker: str) -> tuple[bool, str]:
    """
    Quick yfinance check: is this ticker a valid micro/nano-cap?
    Returns (pass: bool, notes: str)
    """
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).fast_info
        mcap = getattr(info, 'market_cap', None) or getattr(info, 'marketCap', None)
        name = getattr(info, 'shortName', ticker) or ticker
        if mcap and mcap > 500_000_000: return False, f"too large ({mcap/1e6:.0f}M)"
        if mcap and mcap < 100_000:     return False, f"too small ({mcap:,.0f})"
        return True, (name or ticker)[:60]
    except:
        return True, ticker  # include if can't determine


# ── Main builder ──────────────────────────────────────────────────────────────
def build_universe(use_screener: bool = True,
                   include_seeds: bool = True,
                   max_per_query: int = 250) -> int:
    """
    Builds/updates the universe.csv file.
    Returns count of new tickers added.
    """
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)

    # Load existing universe
    existing = set()
    rows = []
    if os.path.exists(OUTPUT_CSV):
        with open(OUTPUT_CSV) as f:
            for row in csv.DictReader(f):
                t = row.get('ticker','').upper().strip()
                if t:
                    existing.add(t)
                    rows.append(row)

    # Also load from analyzer.py CANDIDATE_STOCKS
    from analyzer import CANDIDATE_STOCKS as MANUAL
    manual_tickers = {t for t, e, n in MANUAL}

    new_tickers = []

    # 1. Seeded community banks
    if include_seeds:
        for ticker, exchange, notes in SEEDED_COMMUNITY_BANKS:
            t = ticker.upper()
            if t not in existing and t not in manual_tickers:
                new_tickers.append({'ticker': t, 'exchange': exchange,
                                    'notes': notes, 'source': 'seeded_banks'})
                existing.add(t)

    # 2. yfinance screener queries
    if use_screener:
        for qcfg in SCREENER_QUERIES:
            print(f"  Screener: {qcfg['label']}...", end=' ', flush=True)
            tickers = _yf_screener(qcfg)
            added = 0
            for t in tickers:
                t = t.upper()
                if t not in existing and t not in manual_tickers:
                    new_tickers.append({'ticker': t,
                                        'exchange': qcfg.get('exchange', 'OTC/NASDAQ'),
                                        'notes':    qcfg.get('label', ''),
                                        'source':   'screener'})
                    existing.add(t)
                    added += 1
            print(f"{len(tickers)} found, {added} new")
            time.sleep(0.5)  # be polite to Yahoo

    # 3. Write updated CSV
    all_rows = rows + new_tickers
    with open(OUTPUT_CSV, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['ticker','exchange','notes','source'])
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\n  Universe: {len(all_rows)} total ({len(new_tickers)} new) → {OUTPUT_CSV}")
    return len(new_tickers)


# ── Stats ─────────────────────────────────────────────────────────────────────
def universe_stats():
    """Print stats about current universe."""
    if not os.path.exists(OUTPUT_CSV):
        print("No universe.csv yet — run build_universe() first")
        return

    # Load universe
    with open(OUTPUT_CSV) as f:
        rows = list(csv.DictReader(f))

    # Load analyzed
    import sqlite3
    try:
        conn = sqlite3.connect(DB_PATH)
        done = set(r[0] for r in conn.execute("SELECT ticker FROM analyzed_stocks").fetchall())
        conn.close()
    except:
        done = set()

    sources = {}
    for r in rows:
        s = r.get('source', 'manual')
        sources[s] = sources.get(s, 0) + 1

    remaining = [r['ticker'] for r in rows if r['ticker'] not in done]
    print(f"Universe stats:")
    print(f"  Total tickers  : {len(rows):,}")
    print(f"  Already analyzed: {len(done):,}")
    print(f"  Remaining queue: {len(remaining):,}")
    print(f"  By source: {sources}")
    print(f"  Est. time @ 4 workers: {len(remaining)*1.2/4/60:.1f} minutes")


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--no-screener', action='store_true', help='Skip yfinance screener (seeds only)')
    p.add_argument('--stats',       action='store_true', help='Show universe stats only')
    args = p.parse_args()

    if args.stats:
        universe_stats()
    else:
        n = build_universe(use_screener=not args.no_screener)
        universe_stats()

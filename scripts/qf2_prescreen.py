# -*- coding: utf-8 -*-
"""
qf2_prescreen.py  --  Pre-filter ticker universe from QF2 DuckDB (FMP fundamentals)

Outputs a list of small-cap candidates (<$2B market cap) that pass basic quality
filters, ready to feed into analyzer.py.

Usage:
    python qf2_prescreen.py                  # prints tickers to stdout
    python qf2_prescreen.py --out tickers.txt
    python qf2_prescreen.py --max-cap 2e9 --min-revenue 1e6 --limit 500

Why this exists:
    yfinance.Ticker.info is slow (~1s per call).  Pre-screening 20k tickers
    in DuckDB (local SQL) takes < 5 seconds and eliminates shells/zombies/giants
    before any API calls are made.
"""

import os, sys, argparse, json
from datetime import date, timedelta

QF2_DB_PATH = r"D:/quantum fund 2/results/data/qsconnect/database/qsconnect.duckdb"

# ---------------------------------------------------------------------------
# Filters (all optional / configurable via CLI)
# ---------------------------------------------------------------------------
DEFAULT_MAX_CAP        = 2_000_000_000   # $2B
DEFAULT_MIN_REVENUE    = 500_000         # $500K trailing revenue
DEFAULT_MAX_DEBT_EQ    = 10.0            # debt/equity < 10x
DEFAULT_MIN_CURRENT    = 0.3             # current ratio > 0.3
DEFAULT_MAX_NET_LOSS   = -1.00           # net margin > -100% (wipes out annual revenue)
DEFAULT_CUTOFF_YEARS   = 3               # only use data from last N years
DEFAULT_LIMIT          = 0               # 0 = no limit


def _connect():
    try:
        import duckdb
    except ImportError:
        print("[ERROR] duckdb not installed: pip install duckdb", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(QF2_DB_PATH):
        print(f"[ERROR] QF2 DB not found: {QF2_DB_PATH}", file=sys.stderr)
        sys.exit(1)
    print(f"[qf2_prescreen] Opening {QF2_DB_PATH} ...", file=sys.stderr)
    conn = duckdb.connect(QF2_DB_PATH, read_only=True)
    print("[qf2_prescreen] Connected.", file=sys.stderr)
    return conn


def list_tables(conn):
    rows = conn.execute("SHOW TABLES").fetchall()
    return [r[0] for r in rows]


def run_prescreen(
    max_cap=DEFAULT_MAX_CAP,
    min_revenue=DEFAULT_MIN_REVENUE,
    max_debt_eq=DEFAULT_MAX_DEBT_EQ,
    min_current=DEFAULT_MIN_CURRENT,
    max_net_loss=DEFAULT_MAX_NET_LOSS,
    cutoff_years=DEFAULT_CUTOFF_YEARS,
    limit=DEFAULT_LIMIT,
    verbose=False,
):
    conn = _connect()
    tables = list_tables(conn)
    if verbose:
        print(f"[qf2_prescreen] Tables: {tables}", file=sys.stderr)

    cutoff_date = (date.today() - timedelta(days=365 * cutoff_years)).isoformat()

    # -----------------------------------------------------------------------
    # Build SQL: join key_metrics + income_statement for each ticker,
    # take the most recent row per ticker, then apply filters.
    # -----------------------------------------------------------------------
    # Check which tables exist
    has_km  = "bulk_key_metrics_annual_fmp"  in tables
    has_inc = "bulk_income_statement_annual_fmp" in tables
    has_bs  = "bulk_balance_sheet_statement_annual_fmp" in tables

    if not has_km:
        print(f"[ERROR] bulk_key_metrics_annual_fmp not in DB. Tables: {tables}", file=sys.stderr)
        sys.exit(1)

    # Step 1: get latest key metrics per ticker
    sql_km = f"""
    WITH ranked_km AS (
        SELECT
            symbol,
            date,
            marketCap,
            peRatio,
            pbRatio,
            evToEbitda,
            currentRatio,
            debtToEquity,
            revenuePerShare,
            netIncomePerShare,
            roe,
            roa,
            roic,
            dividendYield,
            ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
        FROM bulk_key_metrics_annual_fmp
        WHERE date >= '{cutoff_date}'
    )
    SELECT * FROM ranked_km WHERE rn = 1
    """

    # Step 2 (optional): get latest revenue from income statement
    sql_inc = ""
    if has_inc:
        sql_inc = f"""
        WITH ranked_inc AS (
            SELECT
                symbol,
                date,
                revenue,
                netIncome,
                grossProfit,
                operatingIncome,
                ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
            FROM bulk_income_statement_annual_fmp
            WHERE date >= '{cutoff_date}'
        )
        SELECT * FROM ranked_inc WHERE rn = 1
        """

    try:
        km_df  = conn.execute(sql_km).df()
        print(f"[qf2_prescreen] key_metrics rows: {len(km_df)}", file=sys.stderr)

        if has_inc and sql_inc:
            inc_df = conn.execute(sql_inc).df()
            print(f"[qf2_prescreen] income_stmt rows: {len(inc_df)}", file=sys.stderr)
            merged = km_df.merge(inc_df[['symbol','revenue','netIncome','grossProfit']], 
                                  on='symbol', how='left')
        else:
            merged = km_df.copy()
            merged['revenue']    = None
            merged['netIncome']  = None
            merged['grossProfit'] = None

    except Exception as e:
        print(f"[ERROR] Query failed: {e}", file=sys.stderr)
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Apply filters in Python (easier than fighting DuckDB NULL semantics)
    # -----------------------------------------------------------------------
    df = merged.copy()
    total_before = len(df)

    # Market cap filter: must be positive and < max_cap
    has_mcap = df['marketCap'].notna() & (df['marketCap'] > 0)
    df = df[has_mcap & (df['marketCap'] < max_cap)]
    print(f"[qf2_prescreen] After mcap < ${max_cap/1e9:.1f}B: {len(df)} (was {total_before})", file=sys.stderr)

    # Minimum revenue filter
    if min_revenue > 0 and 'revenue' in df.columns:
        before = len(df)
        rev_ok = df['revenue'].isna() | (df['revenue'] >= min_revenue)
        df = df[rev_ok]
        print(f"[qf2_prescreen] After min revenue ${min_revenue/1e6:.1f}M: {len(df)} (was {before})", file=sys.stderr)

    # Debt/equity filter  
    if 'debtToEquity' in df.columns:
        before = len(df)
        de_ok = df['debtToEquity'].isna() | (df['debtToEquity'] <= max_debt_eq)
        df = df[de_ok]
        print(f"[qf2_prescreen] After D/E <= {max_debt_eq}: {len(df)} (was {before})", file=sys.stderr)

    # Current ratio filter
    if 'currentRatio' in df.columns:
        before = len(df)
        cr_ok = df['currentRatio'].isna() | (df['currentRatio'] >= min_current)
        df = df[cr_ok]
        print(f"[qf2_prescreen] After CR >= {min_current}: {len(df)} (was {before})", file=sys.stderr)

    # Net margin floor (reject total zombies)
    if 'revenue' in df.columns and 'netIncome' in df.columns:
        before = len(df)
        def net_margin_ok(row):
            r, ni = row['revenue'], row['netIncome']
            if r is None or r == 0 or ni is None:
                return True  # can't compute, keep it
            try:
                nm = float(ni) / float(r)
                return nm >= max_net_loss
            except:
                return True
        margin_mask = df.apply(net_margin_ok, axis=1)
        df = df[margin_mask]
        print(f"[qf2_prescreen] After net margin >= {max_net_loss:.0%}: {len(df)} (was {before})", file=sys.stderr)

    # -----------------------------------------------------------------------
    # Sort by market cap ascending (smallest first = most micro-cap)
    # -----------------------------------------------------------------------
    df = df.sort_values('marketCap', ascending=True)

    if limit > 0:
        df = df.head(limit)
        print(f"[qf2_prescreen] Limited to top {limit} by smallest mcap", file=sys.stderr)

    tickers = df['symbol'].str.strip().str.upper().tolist()
    print(f"[qf2_prescreen] Final universe: {len(tickers)} tickers", file=sys.stderr)
    return tickers


def main():
    parser = argparse.ArgumentParser(description='QF2 small-cap pre-screener')
    parser.add_argument('--out',          default=None,           help='Output file (default: stdout)')
    parser.add_argument('--max-cap',      type=float, default=DEFAULT_MAX_CAP,     help='Max market cap (default 2e9)')
    parser.add_argument('--min-revenue',  type=float, default=DEFAULT_MIN_REVENUE, help='Min revenue (default 500000)')
    parser.add_argument('--max-debt-eq',  type=float, default=DEFAULT_MAX_DEBT_EQ, help='Max debt/equity (default 10)')
    parser.add_argument('--min-current',  type=float, default=DEFAULT_MIN_CURRENT, help='Min current ratio (default 0.3)')
    parser.add_argument('--max-net-loss', type=float, default=DEFAULT_MAX_NET_LOSS,help='Min net margin (default -1.0)')
    parser.add_argument('--cutoff-years', type=int,   default=DEFAULT_CUTOFF_YEARS,help='Max data age in years (default 3)')
    parser.add_argument('--limit',        type=int,   default=DEFAULT_LIMIT,       help='Max tickers to output (0=all)')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--json',    '-j', action='store_true', help='Output JSON array instead of newline-separated')
    args = parser.parse_args()

    tickers = run_prescreen(
        max_cap      = args.max_cap,
        min_revenue  = args.min_revenue,
        max_debt_eq  = args.max_debt_eq,
        min_current  = args.min_current,
        max_net_loss = args.max_net_loss,
        cutoff_years = args.cutoff_years,
        limit        = args.limit,
        verbose      = args.verbose,
    )

    if args.json:
        output = json.dumps(tickers)
    else:
        output = '\n'.join(tickers)

    if args.out:
        with open(args.out, 'w') as f:
            f.write(output + '\n')
        print(f"[qf2_prescreen] Written to {args.out}", file=sys.stderr)
    else:
        print(output)


if __name__ == '__main__':
    main()

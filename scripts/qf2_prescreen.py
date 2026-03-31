# -*- coding: utf-8 -*-
"""
qf2_prescreen.py  --  Pre-filter ticker universe from QF2 FMP Parquet cache

Reads raw FMP Parquet files (not DuckDB) to avoid DuckDB connection issues.
Outputs a list of small-cap candidates (<$2B market cap) that pass basic
quality filters, ready to feed into analyzer.py.

Usage:
    python qf2_prescreen.py                  # prints tickers to stdout
    python qf2_prescreen.py --out tickers.txt
    python qf2_prescreen.py --max-cap 2e9 --min-mcap 1e6 --limit 500

Data source: QF2 FMP Parquet cache (updated ~Feb 2026):
  D:/quantum fund 2/results/data/qsconnect/cache/fmp/bulk-key-metrics_YEAR_annual-*.parquet
"""

import os, sys, argparse, json, glob
from datetime import date

FMP_CACHE = r"D:/quantum fund 2/results/data/qsconnect/cache/fmp"

DEFAULT_MAX_CAP     = 2_000_000_000   # $2B small-cap ceiling
DEFAULT_MIN_CAP     = 1_000_000       # $1M floor  (strip pink-sheet shells)
DEFAULT_MIN_REVENUE = 500_000         # $500K trailing revenue
DEFAULT_MAX_DEBT_EQ = 10.0
DEFAULT_MIN_CURRENT = 0.3
DEFAULT_MAX_NET_LOSS = -1.0           # net margin >= -100%
DEFAULT_YEARS       = [2023, 2024, 2025, 2026]
DEFAULT_LIMIT       = 0


def _load_parquet(pattern, verbose=False):
    """Load all Parquet files matching a glob pattern into a DataFrame."""
    try:
        import pandas as pd
    except ImportError:
        print("[ERROR] pandas not installed: pip install pandas pyarrow", file=sys.stderr)
        sys.exit(1)
    files = sorted(glob.glob(pattern))
    if not files:
        return None
    if verbose:
        print(f"[qf2_prescreen] Loading {len(files)} files: {pattern}", file=sys.stderr)
    dfs = [pd.read_parquet(f) for f in files]
    return pd.concat(dfs, ignore_index=True)


def run_prescreen(
    max_cap=DEFAULT_MAX_CAP,
    min_cap=DEFAULT_MIN_CAP,
    min_revenue=DEFAULT_MIN_REVENUE,
    max_debt_eq=DEFAULT_MAX_DEBT_EQ,
    min_current=DEFAULT_MIN_CURRENT,
    max_net_loss=DEFAULT_MAX_NET_LOSS,
    years=None,
    limit=DEFAULT_LIMIT,
    verbose=False,
):
    import pandas as pd

    if years is None:
        years = DEFAULT_YEARS

    # ------------------------------------------------------------------
    # Load key metrics Parquet files
    # ------------------------------------------------------------------
    km_pattern = FMP_CACHE + "/bulk-key-metrics_*_annual-*.parquet"
    km = _load_parquet(km_pattern, verbose=verbose)
    if km is None:
        print(f"[ERROR] No key-metrics Parquet files found in {FMP_CACHE}", file=sys.stderr)
        sys.exit(1)

    km["date"] = pd.to_datetime(km["date"], errors="coerce")

    # Filter to requested years
    km = km[km["date"].dt.year.isin(years)]
    print(f"[qf2_prescreen] key_metrics rows (years {years}): {len(km):,}", file=sys.stderr)

    # Most recent row per ticker
    km_latest = (km.sort_values("date", ascending=False)
                   .drop_duplicates(subset="symbol", keep="first"))
    print(f"[qf2_prescreen] Unique tickers: {len(km_latest):,}", file=sys.stderr)

    # ------------------------------------------------------------------
    # Load income statement for revenue / net income
    # ------------------------------------------------------------------
    inc_pattern = FMP_CACHE + "/bulk-income-statement_*_annual-*.parquet"
    inc = _load_parquet(inc_pattern, verbose=verbose)
    if inc is not None:
        inc["date"] = pd.to_datetime(inc["date"], errors="coerce")
        inc = inc[inc["date"].dt.year.isin(years)]
        inc_latest = (inc.sort_values("date", ascending=False)
                         .drop_duplicates(subset="symbol", keep="first"))
        cols = [c for c in ["symbol", "revenue", "netIncome"] if c in inc_latest.columns]
        km_latest = km_latest.merge(inc_latest[cols], on="symbol", how="left")
        print(f"[qf2_prescreen] income_stmt merged for {inc_latest['symbol'].nunique():,} tickers", file=sys.stderr)

    df = km_latest.copy()
    total_start = len(df)

    # ------------------------------------------------------------------
    # Apply filters
    # ------------------------------------------------------------------
    df = df[df["marketCap"].notna() & (df["marketCap"] > 0)]
    print(f"[qf2_prescreen] After marketCap > 0:      {len(df):,} (from {total_start:,})", file=sys.stderr)

    df = df[df["marketCap"] < max_cap]
    print(f"[qf2_prescreen] After mcap < ${max_cap/1e9:.1f}B:     {len(df):,}", file=sys.stderr)

    df = df[df["marketCap"] >= min_cap]
    print(f"[qf2_prescreen] After mcap >= ${min_cap/1e6:.0f}M:    {len(df):,}", file=sys.stderr)

    if min_revenue > 0 and "revenue" in df.columns:
        df = df[df["revenue"].isna() | (df["revenue"] >= min_revenue)]
        print(f"[qf2_prescreen] After revenue >= ${min_revenue/1e6:.1f}M: {len(df):,}", file=sys.stderr)

    if "debtToEquity" in df.columns:
        df = df[df["debtToEquity"].isna() | (df["debtToEquity"] <= max_debt_eq)]
        print(f"[qf2_prescreen] After D/E <= {max_debt_eq}:        {len(df):,}", file=sys.stderr)

    if "currentRatio" in df.columns:
        df = df[df["currentRatio"].isna() | (df["currentRatio"] >= min_current)]
        print(f"[qf2_prescreen] After CR >= {min_current}:           {len(df):,}", file=sys.stderr)

    if "revenue" in df.columns and "netIncome" in df.columns:
        def _margin_ok(row):
            r, ni = row["revenue"], row["netIncome"]
            if pd.isna(r) or r == 0 or pd.isna(ni): return True
            try: return (float(ni) / float(r)) >= max_net_loss
            except: return True
        df = df[df.apply(_margin_ok, axis=1)]
        print(f"[qf2_prescreen] After margin >= {max_net_loss:.0%}: {len(df):,}", file=sys.stderr)

    # Sort smallest first
    df = df.sort_values("marketCap", ascending=True)

    if limit > 0:
        df = df.head(limit)
        print(f"[qf2_prescreen] Limited to {limit}", file=sys.stderr)

    # Breakdown
    buckets = [
        ("Nano  (<$50M)",       0,     50e6),
        ("Micro ($50M-$300M)",  50e6,  300e6),
        ("Small ($300M-$2B)",   300e6, 2e9),
    ]
    for label, lo, hi in buckets:
        n = len(df[(df["marketCap"] >= lo) & (df["marketCap"] < hi)])
        print(f"[qf2_prescreen]   {label}: {n:,}", file=sys.stderr)

    tickers = df["symbol"].str.strip().str.upper().tolist()
    print(f"[qf2_prescreen] FINAL UNIVERSE: {len(tickers):,} tickers", file=sys.stderr)
    return tickers


def main():
    parser = argparse.ArgumentParser(description="QF2 small-cap pre-screener (Parquet source)")
    parser.add_argument("--out",          default=None)
    parser.add_argument("--max-cap",      type=float, default=DEFAULT_MAX_CAP)
    parser.add_argument("--min-cap",      type=float, default=DEFAULT_MIN_CAP)
    parser.add_argument("--min-revenue",  type=float, default=DEFAULT_MIN_REVENUE)
    parser.add_argument("--max-debt-eq",  type=float, default=DEFAULT_MAX_DEBT_EQ)
    parser.add_argument("--min-current",  type=float, default=DEFAULT_MIN_CURRENT)
    parser.add_argument("--max-net-loss", type=float, default=DEFAULT_MAX_NET_LOSS)
    parser.add_argument("--limit",        type=int,   default=DEFAULT_LIMIT)
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--json",    "-j", action="store_true")
    args = parser.parse_args()

    tickers = run_prescreen(
        max_cap      = args.max_cap,
        min_cap      = args.min_cap,
        min_revenue  = args.min_revenue,
        max_debt_eq  = args.max_debt_eq,
        min_current  = args.min_current,
        max_net_loss = args.max_net_loss,
        limit        = args.limit,
        verbose      = args.verbose,
    )

    output = json.dumps(tickers) if args.json else "\n".join(tickers)

    if args.out:
        with open(args.out, "w") as f:
            f.write(output + "\n")
        print(f"[qf2_prescreen] Written to {args.out}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()

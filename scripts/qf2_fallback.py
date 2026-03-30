"""
qf2_fallback.py - Pull fundamentals from the Quantum Fund 2 DuckDB (13GB FMP data)
as a fallback when yfinance returns insufficient data.

DB: D:/quantum fund 2/results/data/qsconnect/database/qsconnect.duckdb
Tables: bulk_key_metrics_annual_fmp, bulk_ratios_annual_fmp,
        bulk_balance_sheet_statement_annual_fmp,
        bulk_income_statement_annual_fmp, bulk_cash_flow_statement_annual_fmp
"""
import os, time, math, threading
from typing import Optional, Dict, Any

QF2_DB_PATH = r"D:/quantum fund 2/results/data/qsconnect/database/qsconnect.duckdb"
_conn = None
_conn_lock = threading.Lock()
_conn_failed = False


def _get_connection():
    global _conn, _conn_failed
    if _conn_failed: return None
    if _conn is not None: return _conn
    with _conn_lock:
        if _conn is not None: return _conn
        try:
            import duckdb
            if not os.path.exists(QF2_DB_PATH):
                _conn_failed = True; return None
            t0 = time.time()
            _conn = duckdb.connect(QF2_DB_PATH, read_only=True)
            print(f"[qf2] DuckDB opened in {time.time()-t0:.1f}s", flush=True)
        except Exception as e:
            print(f"[qf2] Cannot open DB: {e}", flush=True)
            _conn_failed = True; return None
    return _conn


def _s(v):
    try:
        if v is None: return None
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except: return None


def get_qf2_fundamentals(ticker: str, max_age_years: int = 3) -> Optional[Dict[str, Any]]:
    """Fetch fundamental data for ticker from QF2 DuckDB. Returns dict or None."""
    conn = _get_connection()
    if conn is None: return None
    try:
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=365*max_age_years)).strftime('%Y-%m-%d')

        km = conn.execute("""
            SELECT peRatio, pbRatio, enterpriseValueOverEBITDA,
                   freeCashFlowYield, dividendYield, currentRatio, debtToEquity,
                   netIncomePerShare, bookValuePerShare, roic, date
            FROM bulk_key_metrics_annual_fmp
            WHERE symbol=? AND date>=? ORDER BY date DESC LIMIT 1
        """, [ticker, cutoff]).fetchone()
        if km is None: return None

        rt = conn.execute("""
            SELECT returnOnEquity, returnOnAssets, grossProfitMargin,
                   operatingProfitMargin, netProfitMargin
            FROM bulk_ratios_annual_fmp
            WHERE symbol=? AND date>=? ORDER BY date DESC LIMIT 1
        """, [ticker, cutoff]).fetchone()

        inc = conn.execute("""
            SELECT revenue, netIncome, weightedAverageShsOut
            FROM bulk_income_statement_annual_fmp
            WHERE symbol=? AND date>=? ORDER BY date DESC LIMIT 1
        """, [ticker, cutoff]).fetchone()

        bs = conn.execute("""
            SELECT totalAssets, totalCurrentAssets, totalLiabilities
            FROM bulk_balance_sheet_statement_annual_fmp
            WHERE symbol=? AND date>=? ORDER BY date DESC LIMIT 1
        """, [ticker, cutoff]).fetchone()

        cf = conn.execute("""
            SELECT operatingCashFlow, capitalExpenditure
            FROM bulk_cash_flow_statement_annual_fmp
            WHERE symbol=? AND date>=? ORDER BY date DESC LIMIT 1
        """, [ticker, cutoff]).fetchone()

        d = {'_source': 'qf2_fmp', '_date': km[10]}
        if km:
            de = _s(km[6])
            d.update(pe_ratio=_s(km[0]), pb_ratio=_s(km[1]), ev_ebitda=_s(km[2]),
                     fcf_yield=_s(km[3]), dividend_yield=_s(km[4]),
                     current_ratio=_s(km[5]),
                     debt_equity=(de/100.0 if de is not None else None),
                     eps=_s(km[7]), bvps=_s(km[8]), roic=_s(km[9]))
        if rt:
            d.update(roe=_s(rt[0]), roa=_s(rt[1]), gross_margin=_s(rt[2]),
                     operating_margin=_s(rt[3]), net_margin=_s(rt[4]))
        if inc:
            d.update(revenue=_s(inc[0]), net_income=_s(inc[1]), shares=_s(inc[2]))
        if bs:
            d.update(total_assets=_s(bs[0]), current_assets=_s(bs[1]),
                     total_liabilities=_s(bs[2]))
        if cf:
            ocf = _s(cf[0]); cap = _s(cf[1])
            d.update(operating_cash_flow=ocf, capex=cap,
                     fcf=(ocf + (cap or 0)) if ocf is not None else None)
        return d if len(d) > 2 else None
    except Exception as e:
        print(f"[qf2] Error for {ticker}: {e}", flush=True)
        return None


def check_tickers_in_qf2(tickers: list) -> list:
    """Return which tickers exist in QF2 DB."""
    conn = _get_connection()
    if conn is None: return []
    try:
        ph = ','.join(['?']*len(tickers))
        rows = conn.execute(
            f"SELECT DISTINCT symbol FROM bulk_key_metrics_annual_fmp WHERE symbol IN ({ph})",
            tickers).fetchall()
        return [r[0] for r in rows]
    except: return []
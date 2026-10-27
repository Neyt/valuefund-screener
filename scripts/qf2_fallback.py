# -*- coding: utf-8 -*-
"""
qf2_fallback.py  --  QF2 FMP fundamentals lookup via Parquet cache

Replaces the DuckDB approach which crashes with STATUS_ACCESS_VIOLATION
on this system.  Instead reads the Parquet files directly using pandas
(same files the prescreen uses) and caches the merged DataFrame in memory.

The first call is slow (~3-5s to load Parquet files), all subsequent
calls are fast O(1) dict lookups.

Public API:
    get_qf2_fundamentals(ticker, max_age_years=3) -> dict | None
    check_tickers_in_qf2(tickers: list) -> list
"""

import os, threading, glob
from datetime import date, timedelta

FMP_CACHE  = r"D:/quantum fund 2/results/data/qsconnect/cache/fmp"
_YEARS     = [2022, 2023, 2024, 2025, 2026]   # which annual parquet years to load

_lock      = threading.Lock()
_loaded    = False
_load_failed = False
_km_dict   = {}   # symbol -> latest key_metrics row (dict)
_inc_dict  = {}   # symbol -> latest income row (dict)


def _load_once():
    """Load Parquet files into in-memory dicts (called once, lazy)."""
    global _loaded, _load_failed, _km_dict, _inc_dict
    if _loaded or _load_failed:
        return

    with _lock:
        if _loaded or _load_failed:
            return
        try:
            import pandas as pd
        except ImportError:
            _load_failed = True
            return

        # --- Key metrics ---
        km_files = []
        for y in _YEARS:
            pat = FMP_CACHE + f"/bulk-key-metrics_{y}_annual-*.parquet"
            km_files.extend(sorted(glob.glob(pat)))

        if not km_files:
            _load_failed = True
            return

        try:
            km = pd.concat([pd.read_parquet(f) for f in km_files], ignore_index=True)
            km["date"] = pd.to_datetime(km["date"], errors="coerce")
            km_latest  = (km.sort_values("date", ascending=False)
                            .drop_duplicates(subset="symbol", keep="first"))
            _km_dict = {
                row["symbol"].strip().upper(): row.to_dict()
                for _, row in km_latest.iterrows()
            }
        except Exception:
            _load_failed = True
            return

        # --- Income statement (for revenue / net income) ---
        inc_files = []
        for y in _YEARS:
            pat = FMP_CACHE + f"/bulk-income-statement_{y}_annual-*.parquet"
            inc_files.extend(sorted(glob.glob(pat)))

        if inc_files:
            try:
                inc = pd.concat([pd.read_parquet(f) for f in inc_files], ignore_index=True)
                inc["date"] = pd.to_datetime(inc["date"], errors="coerce")
                inc_latest  = (inc.sort_values("date", ascending=False)
                                  .drop_duplicates(subset="symbol", keep="first"))
                _inc_dict = {
                    row["symbol"].strip().upper(): row.to_dict()
                    for _, row in inc_latest.iterrows()
                }
            except Exception:
                pass   # income is optional; key metrics still usable

        _loaded = True


def _safe(v):
    try:
        f = float(v)
        return None if (f != f) else f   # NaN check
    except Exception:
        return None


def get_qf2_fundamentals(ticker: str, max_age_years: int = 3):
    """
    Return a dict of fundamental data for ticker from QF2 Parquet cache.
    Returns None if ticker not found or data is older than max_age_years.
    """
    _load_once()
    if _load_failed:
        return None

    sym = ticker.strip().upper()
    km  = _km_dict.get(sym)
    if km is None:
        return None

    # Staleness check
    cutoff = date.today() - timedelta(days=365 * max_age_years)
    rec_date = km.get("date")
    try:
        if hasattr(rec_date, "date"):
            rec_date = rec_date.date()
        if rec_date is not None and rec_date < cutoff:
            return None
    except Exception:
        pass

    inc = _inc_dict.get(sym, {})

    # -- revenue & net income from income statement -----------------------
    revenue    = _safe(inc.get("revenue"))
    net_income = _safe(inc.get("netIncome"))
    gross_profit = _safe(inc.get("grossProfit"))

    # -- key metrics fields ------------------------------------------------
    def _k(key): return _safe(km.get(key))

    shares = _k("investedCapital")   # fallback
    # better: use marketCap / price implied, or directly
    # bookValuePerShare * sharesOutstanding isn't directly available
    # but revenuePerShare lets us back-calc if revenue is known
    if revenue and _k("revenuePerShare") and _k("revenuePerShare") > 0:
        shares = revenue / _k("revenuePerShare")

    result = {
        # Valuation
        "pe_ratio":          _k("peRatio"),
        "pb_ratio":          _k("pbRatio"),
        "ev_ebitda":         _k("enterpriseValueOverEBITDA"),
        # Profitability
        "roe":               _k("roe"),
        "roa":               _k("returnOnTangibleAssets"),
        "roic":              _k("roic"),
        "gross_margin":      (gross_profit / revenue) if (gross_profit and revenue and revenue > 0) else None,
        "operating_margin":  None,   # not in key_metrics
        "net_margin":        (_safe(km.get("netIncomePerShare")) / _safe(km.get("revenuePerShare"))
                              if (_k("netIncomePerShare") and _k("revenuePerShare") and _k("revenuePerShare") > 0)
                              else None),
        # Per-share
        "eps":               _k("netIncomePerShare"),
        "bvps":              _k("bookValuePerShare"),
        "fcf":               None,  # not per-company in key_metrics
        # Balance sheet ratios
        "current_ratio":     _k("currentRatio"),
        "debt_equity":       _k("debtToEquity"),
        # Income / cash flow totals
        "revenue":           revenue,
        "net_income":        net_income,
        "shares":            shares,
        # Dividend
        "dividend_yield":    _k("dividendYield"),
        # Cash flow
        "operating_cash_flow": None,
        "capex":             None,
        # Graham
        "graham_net_net":    _k("grahamNetNet"),
        "working_capital":   _k("workingCapital"),
    }
    return result


def check_tickers_in_qf2(tickers: list) -> list:
    """Return subset of tickers that exist in the QF2 Parquet cache."""
    _load_once()
    if _load_failed:
        return []
    return [t for t in tickers if t.strip().upper() in _km_dict]

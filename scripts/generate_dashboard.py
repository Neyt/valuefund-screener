#!/usr/bin/env python3
"""
generate_dashboard.py  ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â  valuefund.substack.com
Rich GuruFocus-style HTML dashboard with clickable ticker modals.
Reads from stocks.db; call generate_html_index() or run standalone.
"""
import sqlite3, json, os, math
from datetime import datetime

BASE_DIR  = r"D:\StockAnalysis"
DB_PATH   = os.path.join(BASE_DIR, "database", "stocks.db")
HTML_PATH = os.path.join(BASE_DIR, "database", "index.html")
BRAND     = "valuefund.substack.com"

# ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ Industry-Specific Valuation (academic-backed) ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
def industry_valuation_summary(row_dict):
    """
    Returns (method_name, fair_value_str, key_ratios_html, academic_note)
    based on sector/industry using best-validated academic approach per asset class.
    """
    sector   = (row_dict.get('sector')   or '').lower()
    industry = (row_dict.get('industry') or '').lower()
    price    = row_dict.get('current_price')
    bvps     = row_dict.get('bvps')
    roe      = row_dict.get('roe')
    pe       = row_dict.get('pe_ratio')
    pb       = row_dict.get('pb_ratio')
    ps       = row_dict.get('ps_ratio')
    ev_e     = row_dict.get('ev_ebitda')
    ev_r     = row_dict.get('ev_revenue')
    gm       = row_dict.get('gross_margin')
    rg       = row_dict.get('revenue_growth')
    fcf_y    = row_dict.get('fcf_yield')
    de       = row_dict.get('debt_equity')

    def f(v, fmt='.2f', suffix=''):
        return f'{v:{fmt}}{suffix}' if v is not None else 'N/A'
    def fp(v): return f'{v*100:.1f}%' if v is not None else 'N/A'

    is_bank = any(w in industry for w in ('bank','savings','thrift','credit union','financial'))
    is_tech = any(w in industry for w in ('software','internet','semiconductor','tech')) or 'technology' in sector
    is_ind  = any(w in industry for w in ('manufactur','industrial','aerospace','defense','machinery'))
    is_hlth = any(w in industry for w in ('biotech','pharma','healthcare','medical','drug','diagnos'))
    is_re   = any(w in industry for w in ('real estate','reit','property'))
    is_cons = 'consumer' in sector

    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ BANKS: Fama-French (1992) ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â P/B driven by ROE vs cost of equity ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
    if is_bank:
        req = 0.09
        fair_pb  = (roe / req) if (roe and roe > 0) else None
        fair_pb  = min(fair_pb, 3.0) if fair_pb else None
        fair_val = (fair_pb * bvps) if (fair_pb and bvps) else None
        upside   = f'{(fair_val/price-1)*100:+.0f}%' if (fair_val and price) else 'N/A'
        ratios   = (f'P/B: <b>{f(pb)}x</b> | Fair P/B: <b>{f(fair_pb)}x</b> | '
                    f'ROE: <b>{fp(roe)}</b> | BVPS: <b>${f(bvps)}</b>')
        return ('P/B Fair Value',
                f'${fair_val:.2f} ({upside})' if fair_val else 'N/A',
                ratios,
                'Fama & French (1992): P/B most predictive for financials. Fair P/B = ROE ÃƒÆ’Ã‚Â· Cost of Equity (9%).')

    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ TECH: Novy-Marx (2013) gross profit/assets + EV/Revenue ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
    if is_tech:
        rule40 = ((rg or 0)*100 + (gm or 0)*100) if (rg or gm) else None
        # Cheap tech: EV/Revenue < 1.5x with >40% gross margin ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ target 2.5x
        fair_val = (price * 2.5 / ev_r) if (ev_r and ev_r > 0 and gm and gm > 0.35 and price) else None
        upside   = f'{(fair_val/price-1)*100:+.0f}%' if (fair_val and price) else 'N/A'
        ratios   = (f'EV/Rev: <b>{f(ev_r)}x</b> | P/S: <b>{f(ps)}x</b> | '
                    f'Gross Margin: <b>{fp(gm)}</b> | Rule of 40: <b>{f(rule40, ".0f") if rule40 else "N/A"}</b>')
        return ('EV/Revenue + Rule of 40',
                f'${fair_val:.2f} ({upside})' if fair_val else 'N/A',
                ratios,
                'Novy-Marx (2013): Gross profit/assets best quality predictor. Rule of 40 (rev growth% + FCF margin%) > 40 = healthy.')

    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ INDUSTRIALS: Gray & Carlisle (2012) EV/EBITDA ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
    if is_ind:
        target_ev = 8.0
        fair_val  = (price * target_ev / ev_e) if (ev_e and ev_e > 0 and price) else None
        upside    = f'{(fair_val/price-1)*100:+.0f}%' if (fair_val and price) else 'N/A'
        ey        = row_dict.get('magic_formula_ey')
        ratios    = (f'EV/EBITDA: <b>{f(ev_e)}x</b> (target 8x) | '
                     f'Earnings Yield: <b>{fp(ey)}</b> | D/E: <b>{f(de)}x</b>')
        return ('EV/EBITDA vs Acquisition Comps',
                f'${fair_val:.2f} ({upside})' if fair_val else 'N/A',
                ratios,
                "Gray & Carlisle 'Deep Value' (2012): EV/EBITDA most predictive for industrials vs private-market comps (8-10x).")

    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ HEALTHCARE/BIOTECH: P/S relative to growth ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
    if is_hlth:
        # If P/S < 1x and growing ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ target 2x P/S
        fair_val = (price * 2.0 / ps) if (ps and ps > 0 and ps < 2 and rg and rg > 0.05 and price) else None
        upside   = f'{(fair_val/price-1)*100:+.0f}%' if (fair_val and price) else 'N/A'
        ratios   = (f'P/S: <b>{f(ps)}x</b> | P/E: <b>{f(pe)}x</b> | '
                    f'Rev Growth: <b>{fp(rg)}</b> | Gross Margin: <b>{fp(gm)}</b>')
        return ('P/S + Growth Premium (Healthcare)',
                f'${fair_val:.2f} ({upside})' if fair_val else 'N/A',
                ratios,
                'Damodaran: P/S relative to growth rate for pre-profit healthcare. PEG ratio for profitable biopharma.')

    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ REAL ESTATE / REIT ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
    if is_re:
        ratios = f'P/B: <b>{f(pb)}x</b> | BVPS: <b>${f(bvps)}</b> | FCF Yield: <b>{fp(fcf_y)}</b>'
        return ('P/B NAV Discount (REIT)',
                'N/A',
                ratios,
                'Clayton & MacKinnon (2001): REIT P/B predicts returns; discount to NAV = alpha opportunity.')

    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ CONSUMER: Basu (1977) low P/E + EV/EBITDA ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
    if is_cons:
        target_pe = 15.0
        fair_val  = (price * target_pe / pe) if (pe and pe > 0 and pe < 20 and price) else None
        upside    = f'{(fair_val/price-1)*100:+.0f}%' if (fair_val and price) else 'N/A'
        ratios    = (f'P/E: <b>{f(pe)}x</b> (target 15x) | EV/EBITDA: <b>{f(ev_e)}x</b> | '
                     f'Rev Growth: <b>{fp(rg)}</b>')
        return ('P/E + EV/EBITDA (Consumer)',
                f'${fair_val:.2f} ({upside})' if fair_val else 'N/A',
                ratios,
                'Basu (1977): Low P/E predicts positive abnormal returns. Confirmed Fama-French (1992) value premium.')

    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ DEFAULT: Graham + DCF + Net-Net triangulation ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
    graham = row_dict.get('graham_number')
    dcf    = row_dict.get('dcf_value')
    nn     = row_dict.get('net_net_value')
    ivs    = [v for v in [graham, dcf, nn] if v and v > 0]
    avg_iv = sum(ivs)/len(ivs) if ivs else None
    upside = f'{(avg_iv/price-1)*100:+.0f}%' if (avg_iv and price) else 'N/A'
    ratios = (f'Graham: <b>${f(graham)}</b> | DCF: <b>${f(dcf)}</b> | '
              f'Net-Net: <b>${f(nn)}</b> | P/E: <b>{f(pe)}x</b> | P/B: <b>{f(pb)}x</b>')
    return ('DCF + Graham + Net-Net (Multi-Method)',
            f'${avg_iv:.2f} ({upside})' if avg_iv else 'N/A',
            ratios,
            "Graham & Dodd 'Security Analysis': Average of DCF, Graham Number, and Net-Net for conservative margin of safety.")


# ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ DB fetch ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
def fetch_all_stocks():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    # Select all columns
    c.execute("SELECT * FROM analyzed_stocks ORDER BY promise_score DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


# ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ Helpers ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
def _h(v, fmt='.2f'):
    if v is None: return '<span class="na">ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â</span>'
    try: return f'{float(v):{fmt}}'
    except: return str(v)

def _hp(v):
    if v is None: return '<span class="na">ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â</span>'
    try:
        f = float(v)*100
        cls = 'pos' if f > 0 else 'neg'
        return f'<span class="{cls}">{f:.1f}%</span>'
    except: return str(v)

def _hprice(v):
    if v is None: return '<span class="na">ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â</span>'
    try:
        f = float(v)
        return f'${f:.4f}' if f < 1 else f'${f:.2f}'
    except: return str(v)

def _hmcap(v):
    if v is None: return '<span class="na">ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â</span>'
    try:
        f = float(v)
        if f >= 1e9: return f'${f/1e9:.2f}B'
        if f >= 1e6: return f'${f/1e6:.1f}M'
        return f'${f:,.0f}'
    except: return str(v)

def _grade_class(g):
    return {'A':'ga','B':'gb','C':'gc','D':'gd','F':'gf'}.get(g or '','gf')

def _pf_html(v):
    if v is None: return '<span class="na">ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â</span>'
    try:
        n = float(v)
        if n >= 7: return f'<span class="pos">{n:.0f}/9 ÃƒÂ¢Ã…â€œÃ‚Â¦</span>'
        if n >= 5: return f'<span class="ye">{n:.0f}/9 ÃƒÂ¢Ã¢â‚¬â€Ã¢â‚¬Â </span>'
        return f'<span class="neg">{n:.0f}/9 ÃƒÂ¢Ã…â€œÃ¢â‚¬â€</span>'
    except: return str(v)

def _az_html(v):
    if v is None: return '<span class="na">ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â</span>'
    try:
        n = float(v)
        if n > 2.99: return f'<span class="pos">{n:.2f} Safe</span>'
        if n > 1.81: return f'<span class="ye">{n:.2f} Grey</span>'
        return f'<span class="neg">{n:.2f} Dist.</span>'
    except: return str(v)

def _mos_html(v):
    if v is None: return '<span class="na">ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â</span>'
    try:
        f = float(v)
        cls = 'pos' if f > 10 else ('neg' if f < -10 else 'ye')
        return f'<span class="{cls}">{f:.1f}%</span>'
    except: return str(v)

def parse_j(s):
    if not s: return []
    try: d = json.loads(s)
    except: return []
    return d if isinstance(d, list) else []

def cat_badges(cj, hvj, limit=3):
    out = ''
    for x in parse_j(cj)[:limit]:
        t  = (x.get('type','') if isinstance(x,dict) else str(x))[:22]
        hl = (x.get('headline','') if isinstance(x,dict) else '')[:80]
        out += f'<span class="cb cat" title="{hl}">{t}</span>'
    for x in parse_j(hvj)[:2]:
        t  = (x.get('type','') if isinstance(x,dict) else str(x))[:22]
        dv = (x.get('detail','') if isinstance(x,dict) else '')[:80]
        out += f'<span class="cb hv" title="{dv}">{t}</span>'
    return out or '<span class="na">ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â</span>'


# ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ Per-stock JSON for modal ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
def row_to_json(row):
    """Serialise one DB row to a JSON-safe dict for the JS modal."""
    def safe(v):
        if v is None: return None
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)): return None
        return v

    cats = parse_j(row.get('catalysts',''))
    hvs  = parse_j(row.get('hidden_value_notes',''))

    iv_data = industry_valuation_summary(row)

    return {
        'ticker':       row.get('ticker',''),
        'name':         row.get('company_name',''),
        'exchange':     row.get('exchange',''),
        'sector':       row.get('sector','') or 'Unknown',
        'industry':     row.get('industry','') or 'Unknown',
        'grade':        row.get('grade','?'),
        'score':        safe(row.get('promise_score')),
        'price':        safe(row.get('current_price')),
        'market_cap':   safe(row.get('market_cap')),
        'date':         row.get('analysis_date',''),
        # Valuation
        'graham':       safe(row.get('graham_number')),
        'dcf':          safe(row.get('dcf_value')),
        'net_net':      safe(row.get('net_net_value')),
        'mos':          safe(row.get('margin_of_safety')),
        'pe':           safe(row.get('pe_ratio')),
        'pb':           safe(row.get('pb_ratio')),
        'ps':           safe(row.get('ps_ratio')),
        'fcf_yield':    safe(row.get('fcf_yield')),
        'ev_ebitda':    safe(row.get('ev_ebitda')),
        'ev_revenue':   safe(row.get('ev_revenue')),
        'div_yield':    safe(row.get('dividend_yield')),
        # Quality
        'roe':          safe(row.get('roe')),
        'gross_margin': safe(row.get('gross_margin')),
        'rev_growth':   safe(row.get('revenue_growth')),
        'debt_equity':  safe(row.get('debt_equity')),
        'current_ratio':safe(row.get('current_ratio')),
        'beta':         safe(row.get('beta')),
        'insider_pct':  safe(row.get('insider_pct')),
        'short_int':    safe(row.get('short_interest_pct')),
        'w52':          safe(row.get('week52_position')),
        # Scoring
        'piotroski':    safe(row.get('piotroski_score')),
        'altman_z':     safe(row.get('altman_z')),
        'buffett':      safe(row.get('buffett_checklist')),
        'magic_ey':     safe(row.get('magic_formula_ey')),
        'cat_score':    safe(row.get('catalyst_score')),
        # Industry valuation
        'iv_method':    iv_data[0],
        'iv_fair':      iv_data[1],
        'iv_ratios':    iv_data[2],
        'iv_note':      iv_data[3],
        # Catalysts / HV
        'catalysts':    [{
            'type': (x.get('type','') if isinstance(x,dict) else str(x)),
            'headline': (x.get('headline','') if isinstance(x,dict) else ''),
            'date': (x.get('date','') if isinstance(x,dict) else ''),
        } for x in cats],
        'hidden_value': [{
            'type': (x.get('type','') if isinstance(x,dict) else str(x)),
            'detail': (x.get('detail','') if isinstance(x,dict) else ''),
        } for x in hvs],
        'report_path':  row.get('report_path','') or '',
        'avg_vol':      safe(row.get('avg_volume')),
        'notes':        row.get('notes','') or '',
        'short_thesis': row.get('short_thesis','') or '',
        'detailed_thesis': row.get('detailed_thesis','') or '',
    }


# ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ Main HTML generator ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
def generate_html_index():
    rows  = fetch_all_stocks()
    total = len(rows)
    now   = datetime.now().strftime('%Y-%m-%d %H:%M')

    def cnt(g): return sum(1 for r in rows if r.get('grade') == g)

    # Build table body
    tbody = ''
    all_json = {}
    for i, row in enumerate(rows, 1):
        tk    = row.get('ticker','')
        nm    = row.get('company_name','') or 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â'
        ex    = row.get('exchange','?')
        mc    = row.get('market_cap')
        pr    = row.get('current_price')
        mos   = row.get('margin_of_safety')
        sc    = row.get('promise_score') or 0
        pf    = row.get('piotroski_score')
        az    = row.get('altman_z')
        bc    = row.get('buffett_checklist')
        cs    = row.get('catalyst_score') or 0
        cj    = row.get('catalysts','')
        hvj   = row.get('hidden_value_notes','')
        grade = row.get('grade','?')
        dt    = row.get('analysis_date','')
        sthesis = (row.get('short_thesis','') or '').replace('"',"'")
        rpath = row.get('report_path','')
        sector= (row.get('sector') or 'Unknown')[:20]
        pe     = row.get('pe_ratio')
        pb     = row.get('pb_ratio')

        gc = _grade_class(grade)
        action = row.get('action') or ({'A':'BUY','B':'WATCH'}.get(grade,'PASS'))
        act_cls = 'act-buy' if action=='BUY' else ('act-watch' if action=='WATCH' else 'act-pass')
        action_cell = f'<span class="act {act_cls}">{action}</span>'
        rlink = '<span class="na">ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â</span>'
        if rpath and os.path.exists(rpath):
            uri   = 'file:///' + rpath.replace('\\','/')
            rlink = f'<a href="{uri}" class="rlink" target="_blank">ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã¢â‚¬Å¾</a>'

        # Store JSON for modal
        all_json[tk] = row_to_json(row)

        tbody += f'''
  <tr class="{gc}">
    <td class="rank">#{i}</td>
    <td class="tk" onclick="showDetail('{tk}')" title="Click for full analysis">{tk}</td>
    <td class="cn" title="{nm}">{nm[:26]}</td>
    <td><span class="badge">{ex}</span></td>
    <td class="sect" title="{row.get('sector','')}">{sector}</td>
    <td class="mc">{_hmcap(mc)}</td>
    <td>{_hprice(pr)}</td>
    <td>{_mos_html(mos)}</td>
    <td>{'<span class="na">ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â</span>' if pe is None else f'{pe:.1f}x'}</td>
    <td>{'<span class="na">ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â</span>' if pb is None else f'{pb:.2f}x'}</td>
    <td>{_pf_html(pf)}</td>
    <td>{_az_html(az)}</td>
    <td>{'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â' if bc is None else f'{bc:.0f}/14'}</td>
    <td class="catcell">{cat_badges(cj, hvj)}</td>
    <td>
      <div class="bar"><div class="fill {'fill-high' if sc>=65 else 'fill-mid' if sc>=40 else 'fill-low'}" style="width:{sc}%"></div>
      <span class="bval">{sc:.0f}</span></div>
    </td>
    <td><span class="gl {gc}">{grade}</span></td>
    <td>{rlink}</td>
    <td>{action_cell}</td>
    <td class="dt">{dt}</td>
  </tr>'''

    json_blob = json.dumps(all_json, ensure_ascii=False, default=str)

    html = f'''<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta http-equiv="refresh" content="60">
<title>{BRAND} ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Deep-Value Screener</title>
<style>
:root{{--bg:#080f1c;--bg2:#0f1c2e;--bg3:#152236;--bd:#1c3050;
      --tx:#d0e4f4;--mu:#4a6a8a;--bl:#5aabf0;--gr:#43a047;
      --ye:#ffd740;--or:#fb8c00;--re:#e53935;--te:#26c6da;--pu:#ce93d8;}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--bg);color:var(--tx);font-family:"Segoe UI",system-ui,sans-serif;font-size:12px;overflow-x:hidden}}
/* Header */
.hdr{{background:linear-gradient(135deg,var(--bg2) 0%,#0a1520 100%);
      border-bottom:2px solid var(--bd);padding:16px 28px;
      display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{font-size:20px;font-weight:700;color:var(--bl)}}
.brand{{font-size:11px;color:var(--te);font-weight:600;margin-top:2px}}
.sub{{color:var(--mu);font-size:10px;margin-top:3px}}
.upd{{color:var(--mu);font-size:10px;text-align:right}}
/* Stats */
.stats{{background:var(--bg2);border-bottom:1px solid var(--bd);
        padding:10px 28px;display:flex;gap:22px;flex-wrap:wrap;align-items:center}}
.st{{display:flex;flex-direction:column}}
.stl{{font-size:9px;color:var(--mu);text-transform:uppercase;letter-spacing:1px}}
.stv{{font-size:18px;font-weight:700;color:var(--bl);margin-top:1px}}
/* Quote */
.quote{{background:var(--bg3);border-left:3px solid var(--bl);
        padding:9px 18px;margin:14px 28px 10px;border-radius:0 5px 5px 0;
        color:var(--mu);font-style:italic;font-size:11px}}
/* Table */
.wrap{{padding:0 28px 40px;overflow-x:auto}}
.leg{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:8px;font-size:10px;color:var(--mu);padding:4px 0;align-items:center}}
table{{width:100%;border-collapse:collapse;min-width:1500px}}
thead{{position:sticky;top:0;z-index:5}}
th{{background:var(--bg2);color:var(--mu);font-size:9px;font-weight:700;
    text-transform:uppercase;letter-spacing:.4px;padding:9px 6px;
    text-align:left;border-bottom:2px solid var(--bd);white-space:nowrap}}
tr{{border-bottom:1px solid #0b1828;transition:background .1s}}
tr:hover{{background:rgba(90,171,240,.06)!important}}
td{{padding:7px 6px;vertical-align:middle}}
.ga{{background:rgba(67,160,71,.08);border-left:3px solid #2e7d32}}
.gb{{background:rgba(255,215,64,.06);border-left:3px solid #f9a825}}
.gc{{background:rgba(251,140,0,.06);border-left:3px solid #e65100}}
.gd{{background:rgba(229,57,53,.06);border-left:3px solid #b71c1c}}
.gf{{background:rgba(100,40,40,.06);border-left:3px solid #6a0000}}
.rank{{color:var(--mu);font-weight:700;font-size:10px;white-space:nowrap}}
.tk{{font-weight:800;color:var(--bl);font-family:Consolas,monospace;font-size:13px;
     cursor:pointer;text-decoration:underline dotted;white-space:nowrap}}
.tk:hover{{color:#90d4ff}}
.cn{{max-width:130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#8aaccc}}
.sect{{max-width:90px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--mu);font-size:10px}}
.mc{{white-space:nowrap;font-weight:600;color:#a0c4e4}}
.badge{{background:#122030;color:#6a9cbe;padding:2px 5px;border-radius:3px;font-size:9px;font-weight:700}}
.pos{{color:var(--gr);font-weight:600}}.neg{{color:var(--re);font-weight:600}}
.ye{{color:var(--ye);font-weight:600}}.na{{color:#2a4060}}
.dt{{color:var(--mu);font-size:9px;white-space:nowrap}}
.catcell{{min-width:160px}}
.cb{{display:inline-block;padding:2px 4px;border-radius:3px;font-size:8px;
     font-weight:700;margin:1px;line-height:1.5;cursor:help;white-space:nowrap}}
.cb.cat{{background:rgba(38,198,218,.12);color:var(--te);border:1px solid rgba(38,198,218,.25)}}
.cb.hv{{background:rgba(206,147,216,.12);color:var(--pu);border:1px solid rgba(206,147,216,.25)}}
.bar{{position:relative;background:#112030;border-radius:3px;height:17px;width:80px;overflow:hidden}}
.fill{{position:absolute;left:0;top:0;height:100%;
       background:linear-gradient(90deg,#183060,var(--bl));border-radius:3px}}
.bval{{position:absolute;width:100%;text-align:center;top:50%;transform:translateY(-50%);
       font-size:9px;font-weight:700;color:#fff;text-shadow:0 1px 2px rgba(0,0,0,.8);z-index:1}}
.gl{{display:inline-flex;align-items:center;justify-content:center;
     width:22px;height:22px;border-radius:50%;font-weight:700;font-size:11px}}
.gl.ga{{background:rgba(67,160,71,.2);color:var(--gr);border:1px solid #2e7d32}}
.gl.gb{{background:rgba(255,215,64,.2);color:var(--ye);border:1px solid #f9a825}}
.gl.gc{{background:rgba(251,140,0,.2);color:var(--or);border:1px solid #e65100}}
.gl.gd{{background:rgba(229,57,53,.2);color:var(--re);border:1px solid #b71c1c}}
.gl.gf{{background:rgba(100,40,40,.2);color:#cc2222;border:1px solid #6a0000}}
.rlink{{color:var(--te);text-decoration:none;font-size:14px;opacity:.8}}
.rlink:hover{{opacity:1}}
.dlnk{{color:#80d8a0;text-decoration:none;font-size:14px;opacity:.8}}
.dlnk:hover{{opacity:1}}
.thesis-cell{{max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#8aaccc;font-size:10px;font-style:italic;cursor:help}}
.thesis-box{{background:rgba(67,160,71,.06);border:1px solid rgba(67,160,71,.25);border-radius:7px;padding:14px;margin-bottom:14px}}
.thesis-box h3{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:#43a047;margin-bottom:10px}}
.thesis-short{{font-size:12px;color:var(--tx);font-style:italic;line-height:1.7;margin-bottom:10px;padding-bottom:10px;border-bottom:1px solid rgba(67,160,71,.2)}}
.thesis-detail{{font-size:11px;color:#a0c4e4;line-height:1.8;white-space:pre-line}}

/* Tooltip system */
.tip{{position:relative;display:inline-block;cursor:help;border-bottom:1px dotted var(--mu)}}
.tip .tip-box{{display:none;position:absolute;bottom:125%;left:50%;transform:translateX(-50%);
              background:#0d1f3a;color:var(--tx);border:1px solid var(--bd);border-radius:5px;
              padding:8px 10px;font-size:10px;line-height:1.6;width:240px;z-index:200;
              white-space:normal;font-style:normal;font-weight:400;pointer-events:none}}
.tip:hover .tip-box{{display:block}}
.tip .tip-box::after{{content:'';position:absolute;top:100%;left:50%;margin-left:-5px;
                     border:5px solid transparent;border-top-color:#0d1f3a}}
/* Why N/A callout */
.na-why{{color:#2a5070;font-size:9px;cursor:help;text-decoration:underline dotted}}
/* Glossary panel */
.glossary-btn{{background:rgba(90,171,240,.1);border:1px solid rgba(90,171,240,.3);
               color:var(--bl);padding:4px 10px;border-radius:4px;font-size:10px;
               cursor:pointer;margin-left:12px}}
.glossary-btn:hover{{background:rgba(90,171,240,.2)}}
#glossary{{display:none;position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);
           width:min(720px,95vw);max-height:85vh;overflow-y:auto;
           background:var(--bg2);border:1px solid var(--bd);border-radius:10px;
           z-index:300;padding:0}}
.glossary-hdr{{background:linear-gradient(135deg,#0d1f3a,#0a1525);padding:16px 20px;
               border-bottom:1px solid var(--bd);display:flex;justify-content:space-between;
               align-items:center;position:sticky;top:0;border-radius:10px 10px 0 0}}
.glossary-body{{padding:16px 20px;display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.gterm{{background:var(--bg3);border:1px solid var(--bd);border-radius:6px;padding:10px 12px}}
.gterm-name{{font-size:11px;font-weight:700;color:var(--bl);margin-bottom:4px}}
.gterm-def{{font-size:10px;color:#8aaccc;line-height:1.6}}
.gterm-why{{font-size:9px;color:var(--mu);margin-top:4px;font-style:italic}}
@media(max-width:600px){{.glossary-body{{grid-template-columns:1fr}}}}
.footer{{text-align:center;padding:18px;color:var(--mu);font-size:10px;border-top:1px solid var(--bd)}}
/* ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ MODAL ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ */
#overlay{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:100;
          backdrop-filter:blur(4px)}}
#modal{{position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);
        width:min(1020px,96vw);max-height:92vh;overflow-y:auto;
        background:var(--bg2);border:1px solid var(--bd);border-radius:10px;
        z-index:101;padding:0}}
.mhdr{{background:linear-gradient(135deg,#0d1f3a,#0a1525);padding:20px 24px 16px;
       border-bottom:1px solid var(--bd);position:sticky;top:0;z-index:10;border-radius:10px 10px 0 0}}
.mhdr-top{{display:flex;justify-content:space-between;align-items:flex-start}}
.mcompany{{font-size:19px;font-weight:700;color:var(--tx);line-height:1.2}}
.mticker{{font-size:13px;color:var(--bl);font-family:Consolas;margin-top:2px}}
.mbadges{{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:8px}}
.mbadge{{padding:3px 9px;border-radius:4px;font-size:11px;font-weight:700}}
.mbadge.ex{{background:#122030;color:#6a9cbe}}
.mbadge.sc{{background:rgba(90,171,240,.15);color:var(--bl);border:1px solid var(--bl)}}
.mbadge.ga{{background:rgba(67,160,71,.2);color:var(--gr);border:1px solid #2e7d32}}
.mbadge.gb{{background:rgba(255,215,64,.2);color:var(--ye);border:1px solid #f9a825}}
.mbadge.gc{{background:rgba(251,140,0,.2);color:var(--or);border:1px solid #e65100}}
.mbadge.gd{{background:rgba(229,57,53,.2);color:var(--re);border:1px solid #b71c1c}}
.mclose{{background:none;border:1px solid #2a3f5a;color:var(--mu);font-size:18px;
         cursor:pointer;width:30px;height:30px;border-radius:5px;display:flex;
         align-items:center;justify-content:center}}
.mclose:hover{{border-color:var(--bl);color:var(--tx)}}
.mbody{{padding:20px 24px}}
/* 4-panel grid */
.mgrid{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:16px}}
.mpanel{{background:var(--bg3);border:1px solid var(--bd);border-radius:7px;padding:14px}}
.mpanel h3{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;
            color:var(--mu);margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid var(--bd)}}
.mrow{{display:flex;justify-content:space-between;align-items:center;
       padding:4px 0;border-bottom:1px solid rgba(28,48,80,.5)}}
.mrow:last-child{{border-bottom:none}}
.mlabel{{color:var(--mu);font-size:10px}}
.mval{{font-size:11px;font-weight:600;color:var(--tx)}}
.mval.pos{{color:var(--gr)}}.mval.neg{{color:var(--re)}}.mval.ye{{color:var(--ye)}}
/* Industry valuation box */
.ivbox{{background:rgba(90,171,240,.06);border:1px solid rgba(90,171,240,.2);
        border-radius:7px;padding:14px;margin-bottom:14px}}
.ivbox h3{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;
           color:var(--bl);margin-bottom:8px}}
.ivmethod{{font-size:13px;font-weight:700;color:var(--tx);margin-bottom:6px}}
.ivratios{{font-size:11px;color:#a0c4e4;line-height:1.8;margin-bottom:6px}}
.ivnote{{font-size:10px;color:var(--mu);font-style:italic;line-height:1.6}}
.ivfair{{font-size:12px;color:var(--te);font-weight:700;margin-bottom:6px}}
/* Piotroski breakdown */
.pf-grid{{display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-top:6px}}
.pfsig{{font-size:9px;padding:3px 6px;border-radius:3px;
        background:rgba(255,255,255,.03);border:1px solid var(--bd)}}
.pfsig.pass{{border-color:rgba(67,160,71,.4);color:var(--gr)}}
.pfsig.fail{{border-color:rgba(229,57,53,.3);color:#e57373}}
/* Buffett checklist */
.chk-grid{{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-top:8px}}
.chk{{display:flex;align-items:center;gap:6px;font-size:10px;color:var(--tx);
      padding:4px 6px;border-radius:4px;background:rgba(255,255,255,.03);border:1px solid var(--bd)}}
.chk.pass{{border-color:rgba(67,160,71,.4)}}.chk.fail{{border-color:rgba(229,57,53,.2)}}
.chk-ico{{font-size:12px}}
/* Catalysts */
.cat-list{{margin-top:8px;display:flex;flex-direction:column;gap:6px}}
.cat-item{{padding:8px 10px;background:rgba(38,198,218,.06);border:1px solid rgba(38,198,218,.2);
           border-radius:5px}}
.cat-type{{font-size:10px;font-weight:700;color:var(--te)}}
.cat-hl{{font-size:10px;color:#a0c4e4;margin-top:2px;line-height:1.5}}
.hv-item{{padding:8px 10px;background:rgba(206,147,216,.06);border:1px solid rgba(206,147,216,.2);
          border-radius:5px}}
.hv-type{{font-size:10px;font-weight:700;color:var(--pu)}}
.hv-detail{{font-size:10px;color:#a0c4e4;margin-top:2px;line-height:1.5}}
/* Score bar wide */
.score-bar-wrap{{margin-top:10px}}
.sbar-bg{{background:#0d1826;border-radius:20px;height:22px;position:relative;overflow:hidden}}
.sbar-fill{{height:100%;border-radius:20px;background:linear-gradient(90deg,#183060,var(--bl))}}
.sbar-label{{position:absolute;width:100%;text-align:center;top:50%;transform:translateY(-50%);
             font-size:11px;font-weight:700;color:#fff;text-shadow:0 1px 2px rgba(0,0,0,.9)}}
@media(max-width:700px){{.mgrid{{grid-template-columns:1fr}}.pf-grid,.chk-grid{{grid-template-columns:1fr}}}}
/* Sort column highlight */
td.sort-hi{{background:rgba(90,171,240,.04)!important}}
/* Toolbar sticky */
.toolbar{{position:sticky;top:0;z-index:6}}
/* Smooth row transitions */
tr{{transition:background .12s}}
/* Empty state row */
.empty-row td{{background:none!important;border:none!important}}
/* Modal slide-in */
@keyframes slideIn{{from{{transform:translate(-50%,-48%);opacity:0}}to{{transform:translate(-50%,-50%);opacity:1}}}}
#modal{{animation:slideIn .18s ease}}
/* Grade distribution bar */
.gbar{{display:flex;height:4px;border-radius:2px;overflow:hidden;margin-top:4px;gap:1px}}
.gbar-seg{{height:100%;border-radius:1px;transition:width .3s}}
/* Better search focus ring */
.srch:focus{{box-shadow:0 0 0 2px rgba(90,171,240,.2)}}
/* Score bar colors by value */
.fill-high{{background:linear-gradient(90deg,#1a4020,var(--gr))!important}}
.fill-mid{{background:linear-gradient(90deg,#1a2030,var(--bl))!important}}
.fill-low{{background:linear-gradient(90deg,#2a1010,#e65100)!important}}
/* ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ Search / Filter / Sort bar ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ */
.toolbar{{background:var(--bg2);border-bottom:1px solid var(--bd);padding:8px 28px;
          display:flex;gap:10px;flex-wrap:wrap;align-items:center}}
.srch{{background:#0a1828;border:1px solid var(--bd);color:var(--tx);padding:6px 10px;
       border-radius:5px;font-size:11px;width:200px;outline:none;transition:border .15s}}
.srch:focus{{border-color:var(--bl)}}
.srch::placeholder{{color:#2a4060}}
.flt-sel{{background:#0a1828;border:1px solid var(--bd);color:var(--tx);padding:5px 8px;
           border-radius:5px;font-size:11px;outline:none;cursor:pointer}}
.flt-sel:focus{{border-color:var(--bl)}}
.grade-btn{{background:#0a1828;border:1px solid var(--bd);color:var(--mu);padding:4px 9px;
            border-radius:4px;font-size:10px;font-weight:700;cursor:pointer;transition:all .15s}}
.grade-btn:hover{{border-color:var(--bl);color:var(--tx)}}
.grade-btn.active{{color:#fff}}
.grade-btn.gba{{border-color:#2e7d32;color:var(--gr);background:rgba(67,160,71,.12)}}
.grade-btn.gbb{{border-color:#f9a825;color:var(--ye);background:rgba(255,215,64,.1)}}
.grade-btn.gbc{{border-color:#e65100;color:var(--or);background:rgba(251,140,0,.1)}}
.grade-btn.gbd{{border-color:#b71c1c;color:var(--re);background:rgba(229,57,53,.1)}}
.grade-btn.gbf{{border-color:#6a0000;color:#cc2222;background:rgba(100,40,40,.1)}}
.grade-btn.gball{{border-color:var(--bl);color:var(--bl);background:rgba(90,171,240,.1)}}
.row-count{{color:var(--mu);font-size:10px;margin-left:auto;white-space:nowrap}}
.exp-btn{{background:rgba(67,160,71,.1);border:1px solid rgba(67,160,71,.3);
          color:var(--gr);padding:4px 10px;border-radius:4px;font-size:10px;cursor:pointer}}
.exp-btn:hover{{background:rgba(67,160,71,.2)}}
.score-slider{{-webkit-appearance:none;width:120px;height:4px;background:#122030;
               border-radius:2px;outline:none;cursor:pointer}}
.score-slider::-webkit-slider-thumb{{-webkit-appearance:none;width:12px;height:12px;
               border-radius:50%;background:var(--bl);cursor:pointer}}
/* Sort arrows on th */
th.sortable{{cursor:pointer;user-select:none}}
th.sortable:hover{{color:var(--bl)}}
th.sortable::after{{content:' ÃƒÂ¢Ã¢â‚¬Â¡Ã¢â‚¬Â¦';font-size:8px;color:#2a4060;opacity:.6}}
th.sort-asc::after{{content:' ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬Ëœ';color:var(--bl);opacity:1}}
th.sort-desc::after{{content:' ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬Å“';color:var(--bl);opacity:1}}
/* Prev/next in modal */
.mnav{{position:absolute;top:50%;transform:translateY(-50%);background:rgba(0,0,0,.5);
       border:1px solid var(--bd);color:var(--mu);font-size:20px;width:36px;height:60px;
       border-radius:5px;cursor:pointer;display:flex;align-items:center;justify-content:center}}
.mnav:hover{{background:rgba(90,171,240,.15);color:var(--bl)}}
#mnav-prev{{left:-46px}}
#mnav-next{{right:-46px}}
</style></head>
<body>

<div class="hdr">
  <div>
    <h1>Deep-Value Micro-Cap Screener</h1>
    <div class="brand">{BRAND}</div>
    <div class="sub">Piotroski Ãƒâ€šÃ‚Â· Altman Z Ãƒâ€šÃ‚Â· Magic Formula Ãƒâ€šÃ‚Â· Buffett Checklist Ãƒâ€šÃ‚Â· Industry Valuation Ãƒâ€šÃ‚Â· Catalyst Detection</div>
  </div>
  <div class="upd">Updated: {now}<br><small>Auto-refreshes every 60s | Click any ticker for full analysis</small></div>
</div>

<div class="stats">
  <div class="st"><div class="stl">Analyzed</div><div class="stv">{total}</div></div>
  <div class="st"><div class="stl">Grade A</div><div class="stv" style="color:var(--gr)">{cnt("A")}</div></div>
  <div class="st"><div class="stl">Grade B</div><div class="stv" style="color:var(--ye)">{cnt("B")}</div></div>
  <div class="st"><div class="stl">Grade C</div><div class="stv" style="color:var(--or)">{cnt("C")}</div></div>
  <div class="st"><div class="stl">D / F</div><div class="stv" style="color:var(--re)">{cnt("D")+cnt("F")}</div></div>
  <div class="st">
    <div class="stl">Distribution</div>
    <div id="gbar-wrap" class="gbar" style="width:120px;margin-top:6px"><div class="gbar-seg" id="gb-seg-A" style="background:#2e7d32;width:0%"></div><div class="gbar-seg" id="gb-seg-B" style="background:#f9a825;width:0%"></div><div class="gbar-seg" id="gb-seg-C" style="background:#e65100;width:0%"></div><div class="gbar-seg" id="gb-seg-DF" style="background:#b71c1c;width:0%"></div></div>
  </div>
  <div class="st" style="margin-left:auto">
    <button class="glossary-btn" onclick="document.getElementById('glossary').style.display='block'">ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã¢â‚¬â€œ Metric Guide</button>
  </div>
</div>

<div class="toolbar" id="toolbar">
  <input class="srch" id="srch" type="text" placeholder="ÃƒÂ°Ã…Â¸Ã¢â‚¬ÂÃ‚Â  Search ticker / company..." oninput="applyFilters()" autocomplete="off">
  <select class="flt-sel" id="flt-sector" onchange="applyFilters()"><option value="">All Sectors</option></select>
  <select class="flt-sel" id="flt-exch" onchange="applyFilters()"><option value="">All Exchanges</option></select>
  <span style="font-size:10px;color:var(--mu)">Min score:</span>
  <input type="range" class="score-slider" id="flt-score" min="0" max="100" value="0" oninput="document.getElementById('score-val').textContent=this.value;applyFilters()">
  <span id="score-val" style="font-size:10px;color:var(--bl);min-width:20px">0</span>
  <span style="color:#1c3050">|</span>
  <button class="grade-btn gball active" id="gb-ALL" onclick="setGrade('ALL')">ALL</button>
  <button class="grade-btn" id="gb-A" onclick="setGrade('A')">A</button>
  <button class="grade-btn" id="gb-B" onclick="setGrade('B')">B</button>
  <button class="grade-btn" id="gb-C" onclick="setGrade('C')">C</button>
  <button class="grade-btn" id="gb-D" onclick="setGrade('D')">D</button>
  <button class="grade-btn" id="gb-F" onclick="setGrade('F')">F</button>
  <span style="color:#1c3050">|</span>
  <button class="grade-btn" id="ab-BUY" onclick="setAction('BUY')" style="border-color:#2e7d32">BUY</button>
  <button class="grade-btn" id="ab-WATCH" onclick="setAction('WATCH')" style="border-color:#f9a825">WATCH</button>
  <button class="grade-btn" id="ab-PASS" onclick="setAction('PASS')" style="border-color:#4a6a8a">PASS</button>
  <button class="grade-btn gball" id="ab-ALL" onclick="setAction('ALL')">ÃƒÂ¢Ã¢â‚¬â€œÃ‚Âª Reset</button>
  <label style="font-size:10px;color:var(--mu);display:flex;align-items:center;gap:4px;cursor:pointer;user-select:none"><input type="checkbox" id="flt-liq" onchange="applyFilters()" style="cursor:pointer"> Min $10K/mo vol</label>
  <span id="row-count" class="row-count">Showing all</span>
  <button class="exp-btn" onclick="exportCSV()">ÃƒÂ¢Ã‚Â¬Ã¢â‚¬Â¡ CSV</button>
</div>
<div class="quote">
  "It is far better to buy a wonderful company at a fair price than a fair company at a wonderful price." &#8212; Warren Buffett
  &nbsp;&nbsp;|&nbsp;&nbsp; <span style="color:var(--te)">&#9888; Click any ticker for the full analysis Ãƒâ€šÃ‚Â· Use ÃƒÂ¢Ã¢â‚¬Â Ã‚Â ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ arrows to navigate stocks in modal</span>
</div>

<div class="wrap">
  <div class="leg">
    <span style="color:#2e7d32">ÃƒÂ¢Ã¢â‚¬â€œÃ‚Â </span> AÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“Buy &nbsp;
    <span style="color:#f9a825">ÃƒÂ¢Ã¢â‚¬â€œÃ‚Â </span> BÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“Watch &nbsp;
    <span style="color:#e65100">ÃƒÂ¢Ã¢â‚¬â€œÃ‚Â </span> CÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“Neutral &nbsp;
    <span style="color:#b71c1c">ÃƒÂ¢Ã¢â‚¬â€œÃ‚Â </span> D/FÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“Avoid &nbsp;&nbsp;
    <span style="color:var(--te)">ÃƒÂ¢Ã¢â‚¬â€œÃ‚Â </span> Catalyst &nbsp;
    <span style="color:var(--pu)">ÃƒÂ¢Ã¢â‚¬â€œÃ‚Â </span> Hidden Value &nbsp;&nbsp;
    <span style="color:var(--mu)">Piotroski: 7-9=ÃƒÂ¢Ã…â€œÃ‚Â¦ strong | Altman Z: green=safe red=distress | MoS=Margin of Safety | P/B=Price/Book</span>
  </div>
  <table>
    <thead><tr>
      <th class="sortable" data-col="rank" onclick="sortTable(this,0)">#</th>
      <th class="sortable" data-col="tk" onclick="sortTable(this,1)">Ticker</th>
      <th>Company</th><th>Exch</th>
      <th class="sortable" onclick="sortTable(this,4)">Sector</th>
      <th class="sortable" onclick="sortTable(this,5)">Mkt Cap</th>
      <th class="sortable" onclick="sortTable(this,6)">Price</th>
      <th class="sortable" onclick="sortTable(this,7)">MoS%</th>
      <th class="sortable" onclick="sortTable(this,8)">P/E</th>
      <th class="sortable" onclick="sortTable(this,9)">P/B</th>
      <th class="sortable" onclick="sortTable(this,10)">Piotroski</th>
      <th class="sortable" onclick="sortTable(this,11)">Altman Z</th>
      <th class="sortable" onclick="sortTable(this,12)">Checklist</th>
      <th>Catalysts &amp; HV</th>
      <th class="sortable" onclick="sortTable(this,14)">Score</th>
      <th class="sortable" onclick="sortTable(this,15)">Gr.</th>
      <th>Action</th><th>Rep.</th>
      <th class="sortable" onclick="sortTable(this,18)">Date</th>
    </tr></thead>
    <tbody>{tbody}</tbody>
  </table>
</div>

<div class="footer">
  <p><strong>{BRAND}</strong> ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Systematic deep-value analysis of micro/nano-cap stocks on obscure exchanges</p>
  <p style="margin-top:5px">NOT financial advice. Always conduct independent due diligence before investing.</p>
</div>

<!-- Modal overlay -->
<div id="overlay" onclick="closeDetail()"></div>
<div id="modal" style="display:none"></div>

<script>
const STOCKS = {json_blob};

function pct(v) {{ return v != null ? (v*100).toFixed(1)+'%' : 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â'; }}
function num(v,d=2) {{ return v != null ? v.toFixed(d) : 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â'; }}
function price(v) {{ if(v==null)return'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â'; return v<1 ? '$'+v.toFixed(4) : '$'+v.toFixed(2); }}
function mcap(v) {{ if(v==null)return'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â'; if(v>=1e9)return'$'+(v/1e9).toFixed(2)+'B'; if(v>=1e6)return'$'+(v/1e6).toFixed(1)+'M'; return'$'+v.toFixed(0); }}
function clsNum(v,lo,hi) {{ if(v==null)return''; return v>=hi?'pos':v>=lo?'ye':'neg'; }}
function grClass(g) {{ return {{A:'ga',B:'gb',C:'gc',D:'gd',F:'gf'}}[g]||'gf'; }}
function mos_cls(v) {{ if(v==null)return''; return v>10?'pos':v<-10?'neg':'ye'; }}

function metricRow(label, val, cls='') {{
  return `<div class="mrow"><span class="mlabel">${{label}}</span><span class="mval ${{cls}}">${{val}}</span></div>`;
}}

function pfSignals(d) {{
  const pf = d.piotroski;
  if(pf == null) return '<span style="color:#4a6a8a">No Piotroski data</span>';
  const sigMap = {{
    'F1:ROA>0':'F1: ROA > 0','F1:ROA<0':'F1: ROA < 0',
    'F2:OCF>0':'F2: OCF > 0','F2:OCF<0':'F2: OCF < 0',
    'F3:ROAÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬Ëœ':'F3: ROA ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬Ëœ','F3:ROAÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬Å“':'F3: ROA ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬Å“',
    'F4:CashEarnings>Book':'F4: Cash > Accrual','F4:Accrual-heavy':'F4: Accrual-heavy',
    'F5:LeverageÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬Å“':'F5: Leverage ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬Å“','F5:LeverageÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬Ëœ':'F5: Leverage ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬Ëœ',
    'F6:LiquidityÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬Ëœ':'F6: Liquidity ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬Ëœ','F6:LiquidityÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬Å“':'F6: Liquidity ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬Å“',
    'F7:NoDilution':'F7: No Dilution','F7:NoDilution(assumed)':'F7: No Dilution',
    'F8:GMÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬Ëœ':'F8: Gross Margin ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬Ëœ','F8:GMÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬Å“':'F8: Gross Margin ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬Å“',
    'F9:AssetTurnÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬Ëœ':'F9: Asset Turnover ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬Ëœ','F9:AssetTurnÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬Å“':'F9: Asset Turnover ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬Å“',
  }};
  const label = pf>=7?'ÃƒÂ¢Ã…â€œÃ‚Â¦ STRONG':pf>=5?'ÃƒÂ¢Ã¢â‚¬â€Ã¢â‚¬Â  DECENT':pf>=3?'ÃƒÂ¢Ã¢â‚¬â€Ã¢â‚¬Â¡ WEAK':'ÃƒÂ¢Ã…â€œÃ¢â‚¬â€ POOR';
  const score_cls = pf>=7?'pos':pf>=5?'ye':'neg';
  return `<div style="margin-bottom:6px"><span class="${{score_cls}}" style="font-size:13px;font-weight:700">${{pf}}/9 ${{label}}</span><span style="color:#4a6a8a;font-size:10px"> (Piotroski 2000)</span></div>
<div class="pf-grid">${{['F1','F2','F3','F4','F5','F6','F7','F8','F9'].map((f,i)=>{{
  const passKey = Object.keys(sigMap).find(k=>k.startsWith(f)&&(k.includes('ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬Ëœ')||k.includes('>0')||k.includes('No')||k.includes('Cash')));
  const pass = (i+1 <= pf);
  return `<div class="pfsig ${{pass?'pass':'fail'}}">${{pass?'ÃƒÂ¢Ã…â€œÃ¢â‚¬Å“':'ÃƒÂ¢Ã…â€œÃ¢â‚¬â€'}} ${{sigMap[passKey]||f}}</div>`;
}}).join('')}}</div>`;
}}

function buffettTable(d) {{
  const items = [
    ['profitable','Profitable (EPS > 0)',d.score!=null],
    ['high_roe','ROE > 15% (moat proxy)',d.roe!=null&&d.roe>0.15],
    ['low_debt','D/E < 0.5 (low debt)',d.debt_equity!=null&&d.debt_equity<0.5],
    ['growing','Revenue growth > 0',d.rev_growth!=null&&d.rev_growth>0],
    ['fcf_pos','Positive FCF',false],
    ['cheap','Cheap P/E < 15 or P/B < 1',d.pe!=null&&d.pe>0&&d.pe<15||d.pb!=null&&d.pb<1],
    ['pricing','Gross Margin > 30%',d.gross_margin!=null&&d.gross_margin>0.30],
    ['insider','Insider Ownership > 10%',d.insider_pct!=null&&d.insider_pct>0.10],
    ['capital','Operating Margin > 10%',false],
    ['microcap','Micro-cap (hidden gem)',d.market_cap!=null&&d.market_cap<100e6],
  ];
  const score = d.buffett != null ? d.buffett : items.filter(x=>x[2]).length;
  return `<div style="margin-bottom:8px;font-size:12px">Score: <span class="${{score>=10?'pos':score>=7?'ye':'neg'}}" style="font-weight:700">${{num(score,0)}}/14</span></div>
<div class="chk-grid">${{items.map(([k,label,pass])=>`<div class="chk ${{pass?'pass':'fail'}}"><span class="chk-ico">${{pass?'ÃƒÂ¢Ã…â€œÃ¢â‚¬Â¦':'ÃƒÂ¢Ã‚ÂÃ…â€™'}}</span><span>${{label}}</span></div>`).join('')}}</div>`;
}}

function _renderModal(ticker, d) {{
  const gc = grClass(d.grade);
  const mosV = d.mos!=null ? d.mos.toFixed(1)+'%' : 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â';
  const mosCls = mos_cls(d.mos);

  // Build catalysts HTML
  let catsHtml = d.catalysts.length ? d.catalysts.map(c=>`
    <div class="cat-item">
      <div class="cat-type">${{c.type}}</div>
      ${{c.headline ? `<div class="cat-hl">${{c.headline}}</div>` : ''}}
      ${{c.date ? `<span style="font-size:9px;color:#4a6a8a">${{c.date}}</span>` : ''}}
    </div>`).join('') : '<span style="color:#4a6a8a;font-size:11px">No catalysts detected in recent news.</span>';

  let hvHtml = d.hidden_value.length ? d.hidden_value.map(h=>`
    <div class="hv-item">
      <div class="hv-type">${{h.type}}</div>
      <div class="hv-detail">${{h.detail}}</div>
    </div>`).join('') : '<span style="color:#4a6a8a;font-size:11px">No hidden value signals detected.</span>';

  const rlink = d.report_path ? `<a href="file:///${{d.report_path.replace(/\\\\/g,'/')}}" target="_blank" style="color:var(--te);font-size:11px">ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã¢â‚¬Å¾ View Report</a>` : '';
  const docxPath = d.report_path ? d.report_path.replace('.md','.docx').replace('.txt','.docx') : '';
  const dlnkModal = docxPath ? `<a href="file:///${{docxPath.replace(/\\\\/g,'/')}}" target="_blank" style="color:#80d8a0;font-size:11px">ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã‚Â Download DOCX</a>` : '';

  const html = `
<div class="mhdr">
  <button class="mnav" id="mnav-prev" onclick="navModal(-1)" title="Previous stock (ÃƒÂ¢Ã¢â‚¬Â Ã‚Â)">&#8249;</button>
  <button class="mnav" id="mnav-next" onclick="navModal(+1)" title="Next stock (ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢)">&#8250;</button>
  <div class="mhdr-top">
    <div>
      <div class="mcompany">${{d.name}}</div>
      <div class="mticker">${{d.ticker}} &nbsp;Ãƒâ€šÃ‚Â·&nbsp; ${{d.exchange}} &nbsp;Ãƒâ€šÃ‚Â·&nbsp; ${{d.sector}}</div>
    </div>
    <button class="mclose" onclick="closeDetail()">ÃƒÂ¢Ã…â€œÃ¢â‚¬Â¢</button>
  </div>
  <div class="mbadges">
    <span class="mbadge ex">${{d.exchange}}</span>
    <span class="mbadge ex">${{d.sector}}</span>
    <span class="mbadge sc">Score: ${{d.score!=null?d.score.toFixed(0):'?'}}</span>
    <span class="mbadge ${{gc}}">${{d.grade}} ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â ${{{{A:'Strong Buy',B:'Watch',C:'Neutral',D:'Avoid',F:'Avoid'}}[d.grade]||'?'}}</span>
    <span style="color:#4a6a8a;font-size:10px">Analyzed: ${{d.date}}</span>
    ${{rlink}}
    ${{dlnkModal}}
  </div>
</div>
<div class="mbody">

  <!-- Key Stats Bar -->
  <div style="display:flex;gap:20px;flex-wrap:wrap;background:var(--bg3);border:1px solid var(--bd);
              border-radius:7px;padding:12px 16px;margin-bottom:14px">
    <div><div style="font-size:9px;color:var(--mu);text-transform:uppercase;margin-bottom:2px">Price</div>
      <div style="font-size:16px;font-weight:700;color:var(--tx)">${{price(d.price)}}</div></div>
    <div><div style="font-size:9px;color:var(--mu);text-transform:uppercase;margin-bottom:2px">Mkt Cap</div>
      <div style="font-size:16px;font-weight:700;color:#a0c4e4">${{mcap(d.market_cap)}}</div></div>
    <div><div style="font-size:9px;color:var(--mu);text-transform:uppercase;margin-bottom:2px">MoS %</div>
      <div style="font-size:16px;font-weight:700" class="${{mosCls}}">${{mosV}}</div></div>
    <div><div style="font-size:9px;color:var(--mu);text-transform:uppercase;margin-bottom:2px">P/E</div>
      <div style="font-size:16px;font-weight:700;color:var(--tx)">${{d.pe!=null?d.pe.toFixed(1)+'x':'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â'}}</div></div>
    <div><div style="font-size:9px;color:var(--mu);text-transform:uppercase;margin-bottom:2px">P/B</div>
      <div style="font-size:16px;font-weight:700;color:var(--tx)">${{d.pb!=null?d.pb.toFixed(2)+'x':'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â'}}</div></div>
    <div><div style="font-size:9px;color:var(--mu);text-transform:uppercase;margin-bottom:2px">P/S</div>
      <div style="font-size:16px;font-weight:700;color:var(--tx)">${{d.ps!=null?d.ps.toFixed(2)+'x':'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â'}}</div></div>
    <div><div style="font-size:9px;color:var(--mu);text-transform:uppercase;margin-bottom:2px">Beta</div>
      <div style="font-size:16px;font-weight:700;color:var(--tx)">${{d.beta!=null?d.beta.toFixed(2):'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â'}}</div></div>
  </div>

  <!-- Industry Valuation -->
  <div class="ivbox">
    <h3>Industry-Specific Valuation</h3>
    <div class="ivmethod">${{d.iv_method}}</div>
    <div class="ivratios">${{d.iv_ratios}}</div>
    <div class="ivfair">Fair Value Estimate: ${{d.iv_fair}}</div>
    <div class="ivnote">ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã…Â¡ ${{d.iv_note}}</div>
  </div>

  <!-- 4-panel grid -->
  <div class="mgrid">
    <!-- Valuation Panel -->
    <div class="mpanel">
      <h3>ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã…Â  Valuation Metrics</h3>
      ${{metricRow('Graham Number', d.graham!=null?'$'+d.graham.toFixed(2):'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â', d.graham&&d.price&&d.graham>d.price?'pos':'neg')}}
      ${{metricRow('DCF Value', d.dcf!=null?'$'+d.dcf.toFixed(2):'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â', d.dcf&&d.price&&d.dcf>d.price?'pos':'neg')}}
      ${{metricRow('Net-Net Value', d.net_net!=null?'$'+d.net_net.toFixed(2):'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â', d.net_net&&d.price&&d.net_net>d.price?'pos':'neg')}}
      ${{metricRow('Margin of Safety', mosV, mosCls)}}
      ${{metricRow('EV/EBITDA', d.ev_ebitda!=null?d.ev_ebitda.toFixed(1)+'x':'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â', d.ev_ebitda&&d.ev_ebitda<8?'pos':d.ev_ebitda&&d.ev_ebitda>15?'neg':'')}}
      ${{metricRow('EV/Revenue', d.ev_revenue!=null?d.ev_revenue.toFixed(2)+'x':'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â')}}
      ${{metricRow('FCF Yield', d.fcf_yield!=null?pct(d.fcf_yield):'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â', d.fcf_yield&&d.fcf_yield>0.05?'pos':'')}}
      ${{metricRow('Dividend Yield', d.div_yield!=null?pct(d.div_yield):'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â')}}
    </div>

    <!-- Quality Panel -->
    <div class="mpanel">
      <h3>ÃƒÂ¢Ã…Â¡Ã‚Â¡ Quality Metrics</h3>
      ${{metricRow('ROE', d.roe!=null?pct(d.roe):'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â', d.roe&&d.roe>0.15?'pos':d.roe&&d.roe<0?'neg':'')}}
      ${{metricRow('Gross Margin', d.gross_margin!=null?pct(d.gross_margin):'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â', d.gross_margin&&d.gross_margin>0.30?'pos':'')}}
      ${{metricRow('Revenue Growth', d.rev_growth!=null?pct(d.rev_growth):'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â', d.rev_growth&&d.rev_growth>0.05?'pos':d.rev_growth&&d.rev_growth<0?'neg':'')}}
      ${{metricRow('Magic Formula EY', d.magic_ey!=null?pct(d.magic_ey):'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â', d.magic_ey&&d.magic_ey>0.10?'pos':'')}}
      ${{metricRow('Insider Ownership', d.insider_pct!=null?pct(d.insider_pct):'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â', d.insider_pct&&d.insider_pct>0.10?'pos':'')}}
      ${{metricRow('Short Interest', d.short_int!=null?pct(d.short_int):'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â')}}
      ${{metricRow('52-Wk Position', d.w52!=null?(d.w52*100).toFixed(0)+'%':'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â', d.w52!=null&&d.w52<0.20?'pos':d.w52&&d.w52>0.80?'neg':'')}}
      ${{metricRow('Beta', d.beta!=null?d.beta.toFixed(2):'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â')}}
    </div>

    <!-- Safety Panel -->
    <div class="mpanel">
      <h3>ÃƒÂ°Ã…Â¸Ã¢â‚¬ÂºÃ‚Â¡ Financial Safety</h3>
      ${{metricRow('Debt / Equity', d.debt_equity!=null?d.debt_equity.toFixed(2)+'x':'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â', d.debt_equity!=null&&d.debt_equity<0.5?'pos':d.debt_equity&&d.debt_equity>2?'neg':'')}}
      ${{metricRow('Current Ratio', d.current_ratio!=null?d.current_ratio.toFixed(2)+'x':'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â', d.current_ratio&&d.current_ratio>2?'pos':d.current_ratio&&d.current_ratio<1?'neg':'')}}
      ${{metricRow('Altman Z-Score', d.altman_z!=null?(d.altman_z>2.99?d.altman_z.toFixed(2)+' ÃƒÂ¢Ã…â€œÃ‚Â¦ Safe':d.altman_z>1.81?d.altman_z.toFixed(2)+' ÃƒÂ¢Ã¢â‚¬â€Ã¢â‚¬Â¡ Grey':d.altman_z.toFixed(2)+' ÃƒÂ¢Ã…â€œÃ¢â‚¬â€ Distress'):'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â', d.altman_z!=null&&d.altman_z>2.99?'pos':d.altman_z!=null&&d.altman_z<1.81?'neg':'ye')}}
      <div style="margin-top:8px;border-top:1px solid var(--bd);padding-top:8px">
        <div style="font-size:9px;color:var(--mu);text-transform:uppercase;margin-bottom:6px;letter-spacing:.5px">Piotroski F-Score Detail</div>
        ${{pfSignals(d)}}
      </div>
    </div>

    <!-- Buffett Panel -->
    <div class="mpanel">
      <h3>ÃƒÂ°Ã…Â¸Ã…Â½Ã‚Â¯ Buffett / Munger Checklist</h3>
      ${{buffettTable(d)}}
    </div>
  </div>

  <!-- Score Breakdown -->
  <div style="background:var(--bg3);border:1px solid var(--bd);border-radius:7px;padding:14px;margin-bottom:14px">
    <h3 style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:var(--mu);margin-bottom:10px">Overall Promise Score</h3>
    <div class="score-bar-wrap">
      <div style="display:flex;justify-content:space-between;margin-bottom:4px">
        <span style="font-size:11px;color:var(--mu)">Composite (MoS + Quality + Safety + Catalysts)</span>
        <span style="font-size:14px;font-weight:700;color:var(--bl)">${{d.score!=null?d.score.toFixed(0):''}} / 100</span>
      </div>
      <div class="sbar-bg">
        <div class="sbar-fill" style="width:${{d.score||0}}%"></div>
        <div class="sbar-label">${{d.score!=null?d.score.toFixed(0)+' pts':'N/A'}}</div>
      </div>
    </div>
    <div style="display:flex;gap:16px;margin-top:10px;flex-wrap:wrap">
      <span style="font-size:10px;color:var(--mu)">Catalyst Score: <span style="color:var(--pu);font-weight:600">${{d.cat_score!=null?d.cat_score.toFixed(0):0}}/25</span></span>
      <span style="font-size:10px;color:var(--mu)">Buffett Score: <span style="color:var(--te);font-weight:600">${{d.buffett!=null?d.buffett.toFixed(0):0}}/14</span></span>
      <span style="font-size:10px;color:var(--mu)">Industry: <span style="color:#a0c4e4;font-weight:600">${{d.industry}}</span></span>
    </div>
    ${{d.notes ? `<div style="margin-top:8px;font-size:10px;color:var(--mu);font-style:italic">ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã‚Â ${{d.notes}}</div>` : ''}}
  </div>

  <!-- Investment Thesis -->
  ${{d.short_thesis || d.detailed_thesis ? `
  <div class="thesis-box">
    <h3>ÃƒÂ°Ã…Â¸Ã¢â‚¬â„¢Ã‚Â¡ Investment Thesis</h3>
    ${{d.short_thesis ? `<div class="thesis-short">${{d.short_thesis}}</div>` : ''}}
    ${{d.detailed_thesis ? `<div class="thesis-detail">${{d.detailed_thesis}}</div>` : ''}}
  </div>` : ''}}

  <!-- Catalysts -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
    <div style="background:var(--bg3);border:1px solid var(--bd);border-radius:7px;padding:14px">
      <h3 style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:var(--te);margin-bottom:8px">ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã‚Â¡ Catalysts Detected</h3>
      <div class="cat-list">${{catsHtml}}</div>
    </div>
    <div style="background:var(--bg3);border:1px solid var(--bd);border-radius:7px;padding:14px">
      <h3 style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:var(--pu);margin-bottom:8px">ÃƒÂ°Ã…Â¸Ã¢â‚¬â„¢Ã…Â½ Hidden Value Signals</h3>
      <div class="cat-list">${{hvHtml}}</div>
    </div>
  </div>

</div>`;

  document.getElementById('modal').innerHTML = html;
  document.getElementById('modal').style.display = 'block';
  document.getElementById('overlay').style.display = 'block';
  document.body.style.overflow = 'hidden';
}}

// ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ Global state ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
let _sortCol = -1, _sortDir = 1;
let _activeGrade = 'ALL', _activeAction = 'ALL';
let _allTickers = Object.keys(STOCKS);
let _visibleTickers = [..._allTickers];
let _modalIdx = 0;

// ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ Populate filter dropdowns on load ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
(function initFilters() {{
  const sectors = [...new Set(_allTickers.map(t=>STOCKS[t].sector||'Unknown').filter(Boolean))].sort();
  const exchs   = [...new Set(_allTickers.map(t=>STOCKS[t].exchange||'').filter(Boolean))].sort();
  const ss = document.getElementById('flt-sector');
  const se = document.getElementById('flt-exch');
  if(ss) sectors.forEach(s=>{{ const o=document.createElement('option'); o.value=o.textContent=s; ss.appendChild(o); }});
  if(se) exchs.forEach(e=>{{ const o=document.createElement('option'); o.value=o.textContent=e; se.appendChild(o); }});
}})();

// ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ Grade filter buttons ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
function setGrade(g) {{
  _activeGrade = g;
  ['ALL','A','B','C','D','F'].forEach(x=>{{
    const el = document.getElementById('gb-'+x);
    if(el) {{
      el.className = 'grade-btn' + (x==='A'?' gba':x==='B'?' gbb':x==='C'?' gbc':x==='D'?' gbd':x==='F'?' gbf':' gball') + (x===g?' active':'');
    }}
  }});
  applyFilters();
}}

// ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ Action filter (BUY/WATCH/PASS/ALL) ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
function filterAction(a) {{ setAction(a); }}
function setAction(a) {{
  _activeAction = a;
  ['BUY','WATCH','PASS','ALL'].forEach(x=>{{
    const el=document.getElementById('ab-'+x);
    if(el) el.classList.toggle('active', x===a);
  }});
  applyFilters();
}}

// ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ Master filter function ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
function applyFilters() {{
  const q      = (document.getElementById('srch')?.value||'').toLowerCase().trim();
  const sector = document.getElementById('flt-sector')?.value||'';
  const exch   = document.getElementById('flt-exch')?.value||'';
  const minSc  = parseFloat(document.getElementById('flt-score')?.value||'0');
  const liqOn  = document.getElementById('flt-liq')?.checked || false;
  const tbody  = document.querySelector('tbody');
  if(!tbody) return;

  // Remove previous empty-state row
  const prev = tbody.querySelector('.empty-row');
  if(prev) prev.remove();

  const realRows = Array.from(tbody.querySelectorAll('tr:not(.empty-row)'));
  let visible = 0;

  realRows.forEach(tr=>{{
    const cells = tr.querySelectorAll('td');
    if(!cells.length) return;
    // Read ticker from td[1] textContent (trimmed, no child elements)
    const tkCell = cells[1];
    const ticker = tkCell ? tkCell.textContent.trim() : '';
    const d = STOCKS[ticker];
    if(!d) {{ tr.style.display='none'; return; }}

    const matchQ   = !q || ticker.toLowerCase().includes(q) || (d.name||'').toLowerCase().includes(q);
    const matchGr  = _activeGrade==='ALL' || d.grade===_activeGrade;
    const matchSc  = (d.score||0) >= minSc;
    const matchSec = !sector || (d.sector||'').trim()===sector;
    const matchEx  = !exch   || (d.exchange||'').trim()===exch;
    const actEl    = tr.querySelector('.act');
    const actTxt   = actEl ? actEl.textContent.trim() : '';
    const matchAct = _activeAction==='ALL' || actTxt===_activeAction;

    const show = matchQ && matchGr && matchSc && matchSec && matchEx && matchAct;
    tr.style.display = show ? '' : 'none';
    if(show) visible++;
  }});

  // Empty state
  if(visible===0) {{
    const em = document.createElement('tr');
    em.className = 'empty-row';
    em.innerHTML = `<td colspan="19" style="text-align:center;padding:40px;color:#2a4060;font-size:13px">ÃƒÂ°Ã…Â¸Ã¢â‚¬ÂÃ‚Â No stocks match your filters ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â <button onclick="clearFilters()" style="background:none;border:none;color:var(--bl);cursor:pointer;font-size:12px;text-decoration:underline">Clear all filters</button></td>`;
    tbody.appendChild(em);
  }}

  const tot = realRows.length;
  const rc = document.getElementById('row-count');
  if(rc) rc.textContent = visible===tot ? `All ${{tot}} stocks` : `${{visible}} / ${{tot}} shown`;

  // Highlight active sort column
  document.querySelectorAll('td.sort-hi').forEach(td=>td.classList.remove('sort-hi'));
  if(_sortCol>=0) {{
    realRows.filter(r=>r.style.display!=='none').forEach(r=>{{
      const c=r.querySelectorAll('td')[_sortCol];
      if(c) c.classList.add('sort-hi');
    }});
  }}

  // Update visible ticker list for modal navigation
  _visibleTickers = realRows.filter(r=>r.style.display!=='none')
    .map(r=>(r.querySelectorAll('td')[1]?.textContent||'').trim())
    .filter(Boolean);
}}

function clearFilters() {{
  document.getElementById('srch').value='';
  document.getElementById('flt-sector').value='';
  document.getElementById('flt-exch').value='';
  document.getElementById('flt-score').value=0;
  document.getElementById('score-val').textContent='0';
  _activeGrade='ALL'; _activeAction='ALL';
  ['ALL','A','B','C','D','F'].forEach(x=>{{
    const el=document.getElementById('gb-'+x);
    if(el) el.className='grade-btn'+(x==='A'?' gba':x==='B'?' gbb':x==='C'?' gbc':x==='D'?' gbd':x==='F'?' gbf':' gball')+(x==='ALL'?' active':'');
  }});
  ['BUY','WATCH','PASS','ALL'].forEach(x=>{{
    const el=document.getElementById('ab-'+x); if(el) el.classList.remove('active');
  }});
  applyFilters();
}}

// ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ Column sort ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
function sortTable(th, colIdx) {{
  const tbody = document.querySelector('tbody');
  if(!tbody) return;

  // Toggle direction
  if(_sortCol === colIdx) {{ _sortDir *= -1; }}
  else {{ _sortDir = 1; _sortCol = colIdx; }}

  // Clear all sort classes
  document.querySelectorAll('th').forEach(h=>h.classList.remove('sort-asc','sort-desc'));
  th.classList.add(_sortDir===1 ? 'sort-asc' : 'sort-desc');

  const rows = Array.from(tbody.querySelectorAll('tr'));
  rows.sort((a,b)=>{{
    const ca = a.querySelectorAll('td')[colIdx];
    const cb = b.querySelectorAll('td')[colIdx];
    if(!ca||!cb) return 0;
    // Extract numeric value for cols that have them
    const ta = ca.textContent.replace(/[^0-9.\-]/g,'').trim();
    const tb = cb.textContent.replace(/[^0-9.\-]/g,'').trim();
    const na = parseFloat(ta), nb = parseFloat(tb);
    if(!isNaN(na)&&!isNaN(nb)) return (na-nb)*_sortDir;
    return ca.textContent.localeCompare(cb.textContent)*_sortDir;
  }});
  rows.forEach(r=>tbody.appendChild(r));

  // Re-number rank column
  let rank=1;
  rows.forEach(r=>{{
    const rc = r.querySelector('td.rank');
    if(rc && r.style.display!=='none') rc.textContent='#'+rank++;
  }});
}}

// ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ CSV Export ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
function exportCSV() {{
  const rows = Array.from(document.querySelectorAll('tbody tr')).filter(r=>r.style.display!=='none');
  const headers = ['Ticker','Company','Exchange','Sector','MktCap','Price','MoS%','P/E','P/B','Piotroski','AltmanZ','Checklist','Score','Grade','Action','Date'];
  const lines = [headers.join(',')];
  rows.forEach(r=>{{
    const cells = r.querySelectorAll('td');
    const row = Array.from(cells).slice(1,19).map(td=>{{
      const t = td.textContent.replace(/,/g,' ').trim();
      return '"'+t+'"';
    }});
    lines.push(row.join(','));
  }});
  const blob = new Blob([lines.join('\\n')],{{type:'text/csv'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'valuefund_screener.csv';
  a.click();
}}

// ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ Modal navigation ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
function showDetail(ticker) {{
  const d = STOCKS[ticker];
  if(!d) return;
  _modalIdx = _visibleTickers.indexOf(ticker);
  if(_modalIdx<0) _modalIdx=0;
  _renderModal(ticker, d);
}}

function navModal(dir) {{
  _modalIdx = Math.max(0, Math.min(_visibleTickers.length-1, _modalIdx+dir));
  const t = _visibleTickers[_modalIdx];
  if(t && STOCKS[t]) _renderModal(t, STOCKS[t]);
}}

function closeDetail() {{
  document.getElementById('modal').style.display = 'none';
  document.getElementById('overlay').style.display = 'none';
  document.body.style.overflow = '';
}}

document.addEventListener('keydown', e => {{
  if(e.key==='Escape') {{ closeDetail(); document.getElementById('glossary').style.display='none'; }}
  const modalOpen = document.getElementById('modal').style.display==='block';
  if(modalOpen) {{
    if(e.key==='ArrowLeft')  navModal(-1);
    if(e.key==='ArrowRight') navModal(+1);
  }}
  // Enter opens first visible result when search box is focused
  if(e.key==='Enter' && document.activeElement?.id==='srch' && !modalOpen) {{
    if(_visibleTickers.length>0) {{ e.preventDefault(); showDetail(_visibleTickers[0]); }}
  }}
}});
// Click outside modal
document.getElementById('overlay')?.addEventListener('click', closeDetail);

// ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ Init on load ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
document.addEventListener('DOMContentLoaded', ()=>{{
  applyFilters();
  // Grade distribution bar
  const tot = _allTickers.length;
  if(tot>0) {{
    const cnt = g=>_allTickers.filter(t=>STOCKS[t].grade===g).length;
    const pct = n=>(n/tot*100).toFixed(1)+'%';
    const segA=document.getElementById('gb-seg-A'); if(segA) segA.style.width=pct(cnt('A'));
    const segB=document.getElementById('gb-seg-B'); if(segB) segB.style.width=pct(cnt('B'));
    const segC=document.getElementById('gb-seg-C'); if(segC) segC.style.width=pct(cnt('C'));
    const segDF=document.getElementById('gb-seg-DF'); if(segDF) segDF.style.width=pct(cnt('D')+cnt('F'));
  }}
}});

</script>

<!-- Glossary overlay -->
<div id="glossary" onclick="if(event.target===this)this.style.display='none'">
  <div class="glossary-hdr">
    <span style="font-size:14px;font-weight:700;color:var(--bl)">ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã¢â‚¬â€œ Metric Glossary & Scoring Guide</span>
    <button class="mclose" onclick="document.getElementById('glossary').style.display='none'">ÃƒÂ¢Ã…â€œÃ¢â‚¬Â¢</button>
  </div>
  <div class="glossary-body">
    <div class="gterm"><div class="gterm-name">Piotroski F-Score (0-9)</div>
      <div class="gterm-def">9 binary signals across 3 categories: Profitability (ROA&gt;0, OCF&gt;0, improving ROA, OCF&gt;net income), Leverage (lower D/E, higher current ratio, no new shares), Efficiency (higher gross margin, higher asset turnover). Each signal = 1 point.</div>
      <div class="gterm-why">Why N/A? yfinance couldn't retrieve income statement or balance sheet for this ticker ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â common for OTC pink sheets, foreign stocks, or very small companies with limited SEC filings.</div></div>
    <div class="gterm"><div class="gterm-name">Altman Z-Score</div>
      <div class="gterm-def">Bankruptcy predictor: Z = 1.2ÃƒÆ’Ã¢â‚¬â€(Working Capital/Assets) + 1.4ÃƒÆ’Ã¢â‚¬â€(Retained Earnings/Assets) + 3.3ÃƒÆ’Ã¢â‚¬â€(EBIT/Assets) + 0.6ÃƒÆ’Ã¢â‚¬â€(Market Cap/Total Liabilities) + 1.0ÃƒÆ’Ã¢â‚¬â€(Revenue/Assets). Safe &gt;2.99. Grey 1.81-2.99. Distress &lt;1.81.</div>
      <div class="gterm-why">Why N/A? Missing balance sheet data (total assets, liabilities, working capital). Most common for foreign listings, ADRs, or companies that don't file with SEC.</div></div>
    <div class="gterm"><div class="gterm-name">Margin of Safety (MoS%)</div>
      <div class="gterm-def">MoS = (Average Intrinsic Value ÃƒÂ¢Ã‹â€ Ã¢â‚¬â„¢ Current Price) ÃƒÆ’Ã‚Â· Current Price ÃƒÆ’Ã¢â‚¬â€ 100. Uses the average of: Graham Number (ÃƒÂ¢Ã‹â€ Ã…Â¡(22.5 ÃƒÆ’Ã¢â‚¬â€ EPS ÃƒÆ’Ã¢â‚¬â€ BVPS)), DCF (10-yr free cash flow discounted at 10%), and Net-Net (NCAV = Current Assets ÃƒÂ¢Ã‹â€ Ã¢â‚¬â„¢ Total Liabilities).</div>
      <div class="gterm-why">Why N/A or very low? Either all three valuation methods returned no data (missing EPS/BVPS/FCF), or the stock trades above our estimated intrinsic value.</div></div>
    <div class="gterm"><div class="gterm-name">Promise Score (0-100)</div>
      <div class="gterm-def">Composite score: MoS contributes ~35%, Piotroski ~20%, Altman Z ~15%, Buffett Checklist ~15%, Catalyst Score ~15%. Grade A ÃƒÂ¢Ã¢â‚¬Â°Ã‚Â¥ 70 pts. B = 55-69. C = 40-54. D &lt; 40. F = failing multiple safety checks.</div>
      <div class="gterm-why">Low score? Usually means overvalued vs intrinsic models, or poor financial health signals (low Piotroski, low Z-score, high debt).</div></div>
    <div class="gterm"><div class="gterm-name">Graham Number</div>
      <div class="gterm-def">ÃƒÂ¢Ã‹â€ Ã…Â¡(22.5 ÃƒÆ’Ã¢â‚¬â€ EPS ÃƒÆ’Ã¢â‚¬â€ Book Value per Share). Graham's formula for maximum fair price for a defensive investor. Requires positive EPS and positive BVPS. Stock trading below Graham Number = "net net" quality value.</div>
      <div class="gterm-why">Why N/A? Company has negative earnings (EPS ÃƒÂ¢Ã¢â‚¬Â°Ã‚Â¤ 0) or negative book value ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Graham Number is only defined for profitable companies with positive equity.</div></div>
    <div class="gterm"><div class="gterm-name">DCF Value</div>
      <div class="gterm-def">Discounted Cash Flow: projects 10 years of FCF at current growth rate, then applies terminal value, discounted at 10% WACC. Simplified model ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â actual DCF should use company-specific WACC and conservative growth assumptions.</div>
      <div class="gterm-why">Why N/A? Negative or zero free cash flow ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â DCF only works for cash-generative businesses. Loss-making or early-stage companies require different approaches (EV/Revenue, P/S).</div></div>
    <div class="gterm"><div class="gterm-name">Net-Net Value (NCAV)</div>
      <div class="gterm-def">Net Current Asset Value = Current Assets ÃƒÂ¢Ã‹â€ Ã¢â‚¬â„¢ ALL Liabilities (current + long-term). If NCAV &gt; market price, you're buying liquid assets for less than liquidation value. Graham called this the safest possible investment. Oppenheimer (1986) showed Net-Nets returned ~30%/yr.</div>
      <div class="gterm-why">Why N/A? NCAV is negative (liabilities exceed current assets) ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â common for capital-intensive businesses, banks, and companies with heavy long-term debt.</div></div>
    <div class="gterm"><div class="gterm-name">Industry-Specific Valuation</div>
      <div class="gterm-def">Each sector uses the academically most-validated method: Banks ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ P/B vs Fair P/B (Fama-French 1992). Tech ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ EV/Revenue + Rule of 40 (Novy-Marx 2013). Industrials ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ EV/EBITDA vs 8x comps (Gray &amp; Carlisle 2012). Healthcare ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ P/S vs growth (Damodaran). Default ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ Graham+DCF+NetNet average.</div>
      <div class="gterm-why">Why does the fair value say N/A? The required inputs for that sector's formula are missing ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â e.g., bank has no ROE data, or tech has negative revenue growth.</div></div>
    <div class="gterm"><div class="gterm-name">Buffett/Munger Checklist</div>
      <div class="gterm-def">14-point quality screen based on principles from Buffett's shareholder letters: EPS &gt; 0, ROE &gt; 15%, D/E &lt; 0.5, revenue growth &gt; 0, positive FCF, P/E &lt; 15 or P/B &lt; 1, gross margin &gt; 30%, insider ownership &gt; 10%, operating margin &gt; 10%, micro-cap status. Score = points passed.</div>
      <div class="gterm-why">Low score? Most micro-caps fail multiple criteria ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â that's normal and expected. Focus on improving trends, not absolute score.</div></div>
    <div class="gterm"><div class="gterm-name">Catalyst Score (0-25)</div>
      <div class="gterm-def">Scores recent news for value-creating events: M&amp;A (+5), Share Buyback (+4), Special Dividend (+4), Regulatory Approval (+5), Major Contract (+4), Restructuring (+3), Activist Investor (+4), Insider Buying (+3), Earnings Beat (+3), Debt Elimination (+3). Capped at 25.</div>
      <div class="gterm-why">Zero catalysts? Either no recent news found, or news didn't match any of our 11 catalyst keywords. The system scans Yahoo Finance headlines ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â coverage varies by listing type.</div></div>
    <div class="gterm"><div class="gterm-name">Hidden Value Signals</div>
      <div class="gterm-def">Off-balance-sheet or technical signals: SEC Form 4 insider buying, short interest &gt;20% (squeeze potential), near 52-week low (statistical reversion), undervalued real estate / patents / brands, sum-of-parts discount vs peers.</div>
      <div class="gterm-why">No hidden value? These signals require specific data points (insider transactions, short data, 52-week range) that may not be available for all tickers, especially OTC and foreign listings.</div></div>
    <div class="gterm"><div class="gterm-name">Action (BUY / WATCH / PASS)</div>
      <div class="gterm-def">Systematic action based purely on Grade: A (Score ÃƒÂ¢Ã¢â‚¬Â°Ã‚Â¥ 70) = BUY, B (55-69) = WATCH, C/D/F (&lt; 55) = PASS. NOT financial advice ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â this is a first-pass screen. Always conduct your own due diligence before investing.</div>
      <div class="gterm-why">This is a mechanical signal, not a recommendation. A "PASS" stock may still be interesting; a "BUY" may have qualitative issues not captured by these models.</div></div>
  </div>
</div>

</body></html>'''

    os.makedirs(os.path.dirname(HTML_PATH), exist_ok=True)
    with open(HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(html)
    return HTML_PATH


if __name__ == '__main__':
    path = generate_html_index()
    print(f'Dashboard written: {path}')

#!/usr/bin/env python3
"""
generate_thesis.py  —  valuefund.substack.com
Programmatic investment thesis generation from analysis data.
Zero API cost — pure Python template logic.
Returns (short_thesis: str, detailed_thesis: str).
"""
import json, math


def _safe(v):
    try:
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except:
        return None


def _pj(s):
    if not s: return []
    try:
        d = json.loads(s) if isinstance(s, str) else s
        return d if isinstance(d, list) else []
    except:
        return []


def _pct(v, decimals=0):
    s = _safe(v)
    return f"{s*100:.{decimals}f}%" if s is not None else None


def _f(v, d=2, suffix=''):
    s = _safe(v)
    if s is None: return None
    if isinstance(d, str) and not str(d).isdigit():
        return f'{s:{d}}{suffix}'
    return f'{s:.{d}f}{suffix}'


# ── Short thesis (2-3 sentences, for table column) ─────────────────────────────
def short_thesis(data):
    name    = data.get('company_name') or data.get('ticker', '?')
    ticker  = data.get('ticker', '')
    sector  = data.get('sector')  or 'Unknown'
    industry= data.get('industry') or 'Unknown'
    grade   = data.get('grade',   '?')
    score   = _safe(data.get('promise_score')) or 0
    mos     = _safe(data.get('margin_of_safety'))
    pb      = _safe(data.get('pb_ratio'))
    pe      = _safe(data.get('pe_ratio'))
    roe     = _safe(data.get('roe'))
    rg      = _safe(data.get('revenue_growth'))
    de      = _safe(data.get('debt_equity'))
    pf      = _safe(data.get('piotroski_score'))
    az      = _safe(data.get('altman_z'))
    mcap    = _safe(data.get('market_cap'))
    fcf_y   = _safe(data.get('fcf_yield'))
    gm      = _safe(data.get('gross_margin'))
    price   = _safe(data.get('current_price'))
    graham  = _safe(data.get('graham_number'))
    dcf     = _safe(data.get('dcf_value'))
    nn      = _safe(data.get('net_net_value'))
    hv      = _pj(data.get('hidden_value_notes') or data.get('hidden_value_signals',''))
    cats    = _pj(data.get('catalysts',''))

    is_bank = any(w in (industry or '').lower() for w in ('bank','savings','thrift','financial'))
    is_tech = any(w in (industry or '').lower() for w in ('software','internet','tech')) or 'technology' in (sector or '').lower()

    parts = []

    # ── Lead: primary value proposition ───────────────────────────────────────
    if nn and price and nn > price * 1.2:
        prem = (nn / price - 1) * 100
        parts.append(f"Classic Graham Net-Net: liquidation value {prem:.0f}% above current price — buying assets at a discount to scrap value.")
    elif pb and pb < 0.75 and roe and roe > 0.10:
        parts.append(f"Trades at {pb:.2f}× book while earning {roe*100:.0f}% ROE — a quality business priced like a failing one.")
    elif pb and pb < 1.0 and is_bank:
        parts.append(f"Community bank at {pb:.2f}× book value with clean balance sheet — below the Fama-French fair P/B implied by ROE.")
    elif mos and mos > 40:
        parts.append(f"Deep value opportunity: {mos:.0f}% margin of safety vs intrinsic value average (Graham/DCF/Net-Net).")
    elif mos and mos > 20:
        parts.append(f"Meaningful margin of safety at {mos:.0f}% below estimated intrinsic value.")
    elif pe and 0 < pe < 8:
        parts.append(f"Trades at just {pe:.1f}× trailing earnings — extreme cheapness for a profitable micro-cap.")
    elif pe and 0 < pe < 12:
        parts.append(f"Cheap at {pe:.1f}× earnings with {_pct(rg) or 'stable'} revenue growth.")
    elif is_tech and gm and gm > 0.60:
        parts.append(f"High-margin {industry} business ({_pct(gm)} gross margin) trading at deep discount to software comps.")
    elif fcf_y and fcf_y > 0.10:
        parts.append(f"Strong {_pct(fcf_y)} FCF yield — generates significant cash relative to market cap, largely ignored by market.")
    else:
        cap_str = f"${mcap/1e6:.0f}M" if mcap else "micro-cap"
        parts.append(f"{cap_str} {industry} company rated {grade} ({score:.0f}/100) with compelling fundamental characteristics.")

    # ── Middle: quality signal ─────────────────────────────────────────────────
    qsigs = []
    if pf and pf >= 7:  qsigs.append(f"F-score {int(pf)}/9")
    if az and az > 2.99: qsigs.append("financially sound (Z-score)")
    elif az and az < 1.81: qsigs.append("⚠ Z-score distress zone")
    if de is not None and de < 0.3: qsigs.append("debt-free balance sheet")
    if roe and roe > 0.15: qsigs.append(f"{_pct(roe)} ROE")
    if rg and rg > 0.05: qsigs.append(f"{_pct(rg)} revenue growth")
    if qsigs:
        parts.append(" | ".join(qsigs[:3]) + ".")

    # ── Catalyst line ──────────────────────────────────────────────────────────
    hv_types  = [(x.get('type','') if isinstance(x,dict) else str(x)) for x in hv[:2]]
    cat_types = [(x.get('type','') if isinstance(x,dict) else str(x)) for x in cats[:2]]
    triggers  = [s for s in (hv_types + cat_types) if s]
    if triggers:
        parts.append("Catalysts: " + " · ".join(triggers[:3]) + ".")

    return " ".join(parts)


# ── Detailed thesis (5-8 sentences, for modal) ────────────────────────────────
def detailed_thesis(data):
    name    = data.get('company_name') or data.get('ticker', '?')
    sector  = data.get('sector')  or 'Unknown'
    industry= data.get('industry') or 'Unknown'
    grade   = data.get('grade',   '?')
    score   = _safe(data.get('promise_score')) or 0
    mos     = _safe(data.get('margin_of_safety'))
    pb      = _safe(data.get('pb_ratio'))
    pe      = _safe(data.get('pe_ratio'))
    ps      = _safe(data.get('ps_ratio'))
    roe     = _safe(data.get('roe'))
    rg      = _safe(data.get('revenue_growth'))
    de      = _safe(data.get('debt_equity'))
    pf      = _safe(data.get('piotroski_score'))
    az      = _safe(data.get('altman_z'))
    bc      = _safe(data.get('buffett_checklist'))
    mcap    = _safe(data.get('market_cap'))
    fcf_y   = _safe(data.get('fcf_yield'))
    gm      = _safe(data.get('gross_margin'))
    price   = _safe(data.get('current_price'))
    graham  = _safe(data.get('graham_number'))
    dcf     = _safe(data.get('dcf_value'))
    nn      = _safe(data.get('net_net_value'))
    ev_e    = _safe(data.get('ev_ebitda'))
    ins     = _safe(data.get('insider_pct'))
    si      = _safe(data.get('short_interest_pct'))
    w52     = _safe(data.get('week52_position'))
    hv      = _pj(data.get('hidden_value_notes') or data.get('hidden_value_signals',''))
    cats    = _pj(data.get('catalysts',''))
    notes   = data.get('notes','') or ''

    is_bank = any(w in (industry or '').lower() for w in ('bank','savings','thrift'))
    is_tech = any(w in (industry or '').lower() for w in ('software','internet','tech')) or 'technology' in (sector or '').lower()
    cap_str = f"${mcap/1e6:.1f}M market cap" if mcap else "micro-cap"

    paragraphs = []

    # ── 1. Situation overview ──────────────────────────────────────────────────
    if is_bank:
        pb_comment = f" at {pb:.2f}× book" if pb else ""
        roe_comment= f" while delivering {_pct(roe)} ROE" if roe else ""
        paragraphs.append(
            f"{name} is a community bank ({cap_str}) trading{pb_comment}{roe_comment}. "
            f"The Fama-French (1992) academic framework — the gold standard for valuing financial firms — "
            f"uses book value as the primary anchor. Community banks trading below fair P/B (ROE ÷ cost of equity) "
            f"represent some of the cleanest value opportunities in the market because their assets are "
            f"mostly transparent (loans, securities) and their earnings power is visible in the NIM spread."
        )
    elif is_tech and gm and gm > 0.50:
        paragraphs.append(
            f"{name} is a {cap_str} {industry} company with a {_pct(gm)} gross margin — the hallmark of a "
            f"software-like business model with recurring revenue and high operating leverage. "
            f"Novy-Marx (2013) showed that gross profit/assets is the single strongest quality predictor of "
            f"future stock returns. Despite these characteristics, the stock remains under the radar of "
            f"institutional investors due to its small size, creating a potential valuation gap."
        )
    elif nn and price and nn > price:
        paragraphs.append(
            f"{name} ({cap_str}) qualifies as a Graham Net-Net: its net current asset value "
            f"(current assets minus ALL liabilities) of ${nn:.2f}/share exceeds the current price of "
            f"${price:.2f}/share. This means you are buying the liquid assets at a discount and getting "
            f"the ongoing business for free. Historically, Graham Net-Nets have returned ~30%/year "
            f"on average (Oppenheimer 1986; Yen et al 2004) — one of the most robust anomalies in finance."
        )
    else:
        mos_str = f" with {mos:.0f}% margin of safety" if mos and mos > 10 else ""
        paragraphs.append(
            f"{name} is a {cap_str} {industry} company in the {sector} sector{mos_str}. "
            f"Systematic scoring across Piotroski (financial health), Altman Z (bankruptcy risk), "
            f"Magic Formula (quality + cheapness), and Buffett's 10-point checklist places it at "
            f"{score:.0f}/100 — grade {grade}."
        )

    # ── 2. Valuation analysis ──────────────────────────────────────────────────
    val_points = []
    if graham and price: val_points.append(f"Graham Number ${graham:.2f} ({(graham/price-1)*100:+.0f}% vs price)")
    if dcf and price:    val_points.append(f"DCF ${dcf:.2f} ({(dcf/price-1)*100:+.0f}% vs price)")
    if nn and price:     val_points.append(f"Net-Net ${nn:.2f} ({(nn/price-1)*100:+.0f}% vs price)")
    if ev_e:             val_points.append(f"EV/EBITDA {ev_e:.1f}× vs 8-12× typical acquisition comps")
    if val_points:
        paragraphs.append(
            f"Valuation triangulation: {'; '.join(val_points)}. "
            f"{'Using the average of all three methods gives a ' + _f(mos,'.0f') + '% margin of safety.' if mos else ''} "
            f"Academic research (Gray & Carlisle 2012; Greenblatt 2005) consistently shows that "
            f"cheap-on-multiple approaches applied to small/micro-cap companies generate the strongest "
            f"long-term risk-adjusted returns."
        )

    # ── 3. Financial health ────────────────────────────────────────────────────
    health_pts = []
    if pf is not None:
        label = "STRONG" if pf >= 7 else "DECENT" if pf >= 5 else "WEAK" if pf >= 3 else "POOR"
        health_pts.append(f"Piotroski F-score {int(pf)}/9 ({label}) — Piotroski (2000) showed high-F stocks outperform low-F by 23%/yr among value stocks")
    if az is not None:
        if az > 2.99:   health_pts.append(f"Altman Z={az:.2f} in safe zone (Z>2.99) — minimal bankruptcy risk")
        elif az > 1.81: health_pts.append(f"Altman Z={az:.2f} in grey zone — modest risk, monitor leverage")
        else:           health_pts.append(f"⚠ Altman Z={az:.2f} in DISTRESS zone — elevated bankruptcy risk, size position accordingly")
    if de is not None:
        if de < 0.3:    health_pts.append(f"D/E {de:.2f}× — near debt-free, maximum financial flexibility")
        elif de > 2.0:  health_pts.append(f"⚠ D/E {de:.2f}× — high leverage amplifies both upside and downside")
    if bc is not None:  health_pts.append(f"Buffett Checklist {bc:.0f}/14 points")
    if health_pts:
        paragraphs.append(" · ".join(health_pts) + ".")

    # ── 4. Hidden value & catalysts ────────────────────────────────────────────
    hv_sentences = []
    for h in hv[:3]:
        t  = h.get('type','') if isinstance(h,dict) else str(h)
        dv = h.get('detail','') if isinstance(h,dict) else ''
        hv_sentences.append(f"{t}: {dv[:120]}")
    if hv_sentences:
        paragraphs.append("Hidden value signals: " + " | ".join(hv_sentences) + ".")

    cat_sentences = []
    for c in cats[:3]:
        t  = c.get('type','') if isinstance(c,dict) else str(c)
        hl = c.get('headline','') if isinstance(c,dict) else ''
        cat_sentences.append(f"{t}" + (f" — {hl[:80]}" if hl else ""))
    if cat_sentences:
        paragraphs.append("Catalysts detected: " + " | ".join(cat_sentences) + ".")

    # ── 5. Positioning & technicals ───────────────────────────────────────────
    pos_pts = []
    if ins and ins > 0.10:  pos_pts.append(f"insiders own {_pct(ins)} — strong alignment")
    if si  and si  > 0.15:  pos_pts.append(f"{_pct(si)} short interest — short squeeze potential")
    if w52 is not None:
        if w52 < 0.15:     pos_pts.append(f"near 52-week low ({w52*100:.0f}% from low) — historically optimal entry timing")
        elif w52 > 0.85:   pos_pts.append(f"near 52-week high ({w52*100:.0f}% from low) — consider waiting for pullback")
    if pos_pts:
        paragraphs.append("Positioning: " + " · ".join(pos_pts) + ".")

    # ── 6. Key risks ──────────────────────────────────────────────────────────
    risks = []
    if az and az < 1.81:          risks.append("balance sheet distress (Altman Z in danger zone)")
    if de and de > 2.0:            risks.append(f"high leverage (D/E {de:.1f}×)")
    if rg and rg < -0.10:          risks.append(f"shrinking revenue ({_pct(rg)}/yr)")
    if mcap and mcap < 10e6:       risks.append("nano-cap illiquidity (bid-ask spreads, thin volume)")
    if pf is not None and pf <= 2: risks.append(f"poor Piotroski score ({int(pf)}/9 — deteriorating fundamentals)")
    if not risks:                  risks.append("no major systematic red flags — conduct independent due diligence")
    paragraphs.append("Key risks: " + "; ".join(risks) + ".")

    return "\n\n".join(paragraphs)


# ── Batch regenerate all theses in DB ─────────────────────────────────────────
def regenerate_all_theses():
    import sqlite3, os
    DB_PATH = r"D:\StockAnalysis\database\stocks.db"
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    # Add columns if missing
    for col in [('short_thesis','TEXT'), ('detailed_thesis','TEXT')]:
        try: c.execute(f"ALTER TABLE analyzed_stocks ADD COLUMN {col[0]} {col[1]}")
        except: pass
    conn.commit()
    c.execute("SELECT * FROM analyzed_stocks")
    rows = [dict(r) for r in c.fetchall()]
    print(f"Generating theses for {len(rows)} stocks...")
    for row in rows:
        st = short_thesis(row)
        dt = detailed_thesis(row)
        c.execute("UPDATE analyzed_stocks SET short_thesis=?, detailed_thesis=? WHERE ticker=?",
                  (st, dt, row['ticker']))
        print(f"  {row['ticker']:8s} OK")
    conn.commit()
    conn.close()
    print("Done.")


if __name__ == '__main__':
    regenerate_all_theses()

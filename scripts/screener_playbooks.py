#!/usr/bin/env python3
"""
screener_playbooks.py -- which factors value each kind of company (from MASTER.md section 4).

build(row, history, fx_rates, enrich) -> (playbook, group, factors, metrics, review, notes)
  factors  {"value"|"quality"|"safety": {key: (label, number where higher is better, text shown)}}
  metrics  [(label, text)] sector figures shown on the stock page
  review   [text] reasons to open the filings
  notes    [text] adjustments made to the data

Banks, insurers, REITs, biotech and software get their own factors and are compared inside their group.
Mining, energy, shipping and everything else use the general factors plus a sector review trigger.
"""
import math, re

COST_OF_EQUITY = 0.10
MINING = re.compile(r"Gold|Silver|Metals & Mining|Copper|Coal|Uranium|Precious Metals|Aluminum", re.I)
NAMES = {"bank": "Bank", "insurance": "Insurer", "reit": "REIT", "biotech": "Biotech", "software": "Software",
         "mining": "Mining", "energy": "Oil and gas", "shipping": "Shipping", "generic": "General"}
OWN_GROUP = {"bank", "insurance", "reit", "biotech", "software"}

def num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None

def clip(v, lo, hi):
    return None if v is None else max(lo, min(hi, v))

def pct(v):  return "–" if v is None else "%.1f%%" % (v * 100)
def x2(v):   return "–" if v is None else "%.2f" % v
def x1(v):   return "–" if v is None else "%.1f" % v

def which(r):
    ind = r.get("industry") or ""
    if "Banks" in ind: return "bank"
    if ind.startswith("Insurance"): return "insurance"
    if ind.startswith("REIT"): return "reit"
    if ind == "Biotechnology": return "biotech"
    if ind.startswith("Software"): return "software"
    if MINING.search(ind): return "mining"
    if "Oil & Gas" in ind: return "energy"
    if "Marine Shipping" in ind: return "shipping"
    return "generic"

def build(r, h, rates, enrich):
    g = lambda k: num(r.get(k))
    notes, review, metrics = [], [], []
    h = h or {}
    x, rows, rcur = h.get("x") or {}, h.get("rows") or [], h.get("cur")
    last = rows[-1] if rows else None                      # [year, revenue, net income, eps, fcf, equity, debt]
    usd = lambda v: enrich.to_usd(v, rcur, rates) if (enrich and v is not None and rcur) else None
    mc = r.get("_mc_usd")

    de = g("debt_equity")
    if last and last[5] and last[6] and last[5] > 0 and last[6] > 0:
        bs = last[6] / last[5]
        if de is None or de == 0 or (bs > 0.1 and 0 <= de < bs / 5):
            notes.append("Debt to equity (%.2f) comes from the %d balance sheet; the database had %s" % (bs, last[0], "none" if de is None else "%.2f" % de))
            de = bs
            r["debt_equity"] = round(de, 3)
    dy = g("dividend_yield")
    if dy is not None and dy > 1: r["dividend_yield"] = dy / 100.0     # stored as a percentage for some rows

    pe, pb, ev = g("pe_ratio"), g("pb_ratio"), g("ev_ebitda")
    ey = None if pe is None else (1.0 / pe if pe > 0 else -1.0)
    G = {
      "ey":   ("Earnings yield", ey, pct(1.0 / pe) if pe and pe > 0 else "–"),
      "mos":  ("Margin of safety", clip(g("margin_of_safety"), -100, 90), "–" if g("margin_of_safety") is None else "%.0f%%" % g("margin_of_safety")),
      "pb":   ("Price to book", None if pb is None else (-pb if pb > 0 else -1e9), x2(pb)),
      "fcfy": ("Free cash flow yield", clip(g("fcf_yield"), -1, 1), pct(g("fcf_yield"))),
      "evebitda": ("EV / EBITDA", None if ev is None else (-ev if ev > 0 else -1e9), x1(ev)),
      "piotroski": ("Piotroski", g("piotroski_score"), "–" if g("piotroski_score") is None else "%d/9" % g("piotroski_score")),
      "roe":  ("Return on equity", clip(g("roe"), -1, 1), pct(g("roe"))),
      "gm":   ("Gross margin", clip(g("gross_margin"), -1, 1), pct(g("gross_margin"))),
      "om":   ("Operating margin", clip(g("operating_margin"), -1, 1), pct(g("operating_margin"))),
      "revg": ("Revenue growth", clip(g("revenue_growth"), -0.5, 1), pct(g("revenue_growth"))),
      "altman": ("Altman Z", clip(g("altman_z"), -10, 30), x1(g("altman_z"))),
      "de":   ("Debt to equity", None if de is None else (-de if de >= 0 else -1e9), x2(de)),
      "curr": ("Current ratio", clip(g("current_ratio"), 0, 10), x2(g("current_ratio"))),
    }
    pick = lambda *ks: {k: G[k] for k in ks}
    generic = {"value": pick("ey", "mos", "pb", "fcfy", "evebitda"),
               "quality": pick("piotroski", "roe", "gm", "om", "revg"),
               "safety": pick("altman", "de", "curr")}

    pb_name = which(r)
    eq, ni, debt = (usd(last[5]), usd(last[2]), usd(last[6])) if last else (None, None, None)
    fcf, rev = (usd(last[4]), usd(last[1])) if last else (None, None)
    assets, cash = usd(x.get("assets")), usd(x.get("cash"))
    yrs = [w[2] for w in rows if w[2] is not None]
    stab = (sum(1 for v in yrs if v > 0) / len(yrs)) if len(yrs) >= 3 else None
    STAB = ("Profitable years", stab, "–" if stab is None else "%d of %d" % (sum(1 for v in yrs if v > 0), len(yrs)))
    EQA = ("Equity / assets", (eq / assets) if eq is not None and assets else None, pct(eq / assets) if eq is not None and assets else "–")
    F = None

    if pb_name == "bank" and mc and eq is not None:
        tbv = eq - (usd(x.get("gw")) or 0)
        if tbv > 0 and ni is not None:
            ptbv, rote = mc / tbv, ni / tbv
            fair = max(rote, 0) / COST_OF_EQUITY
            metrics += [("Price / tangible book", x2(ptbv)), ("Return on tangible equity", pct(rote)),
                        ("Fair P/TBV at 10% cost of equity", x2(fair)), ("Implied upside", "%+.0f%%" % clip((fair / ptbv - 1) * 100, -99, 999))]
            if ptbv < 0.7 and rote > 0.08: review.append("P/TBV under 0.7 with ROTE above 8%: read the loan book in the annual report")
            F = {"value": {"tbvp": ("Tangible book / price", clip(1 / ptbv, 0, 10), "P/TBV " + x2(ptbv)), "ey": G["ey"]},
                 "quality": {"rote": ("Return on tangible equity", clip(rote, -1, 1), pct(rote)),
                             "roa": ("Return on assets", clip(ni / assets, -0.2, 0.2) if assets else None, pct(ni / assets) if assets else "–"),
                             "piotroski": G["piotroski"]},
                 "safety": {"eqa": EQA, "stab": STAB}}
    elif pb_name == "insurance":
        if pb is not None and 0 < pb < 0.8 and (g("operating_margin") or 0) > 0:
            review.append("P/B under 0.8 with an underwriting profit: check reserves and float in the annual report")
        F = {"value": pick("pb", "ey"), "quality": pick("roe", "om", "piotroski"), "safety": {"eqa": EQA, "stab": STAB}}
    elif pb_name == "reit" and mc and ni is not None:
        ffo = ni + (usd(x.get("da")) or 0)
        ebitda, evu = usd(x.get("ebitda")), mc + (debt or 0) - (cash or 0)
        cap = (ebitda / evu) if ebitda and evu > 0 else None
        dte = (debt / ebitda) if debt is not None and ebitda and ebitda > 0 else None
        dy = g("dividend_yield")
        metrics += [("Price / FFO", x1(mc / ffo) if ffo > 0 else "–"), ("Implied cap rate", pct(cap)), ("Debt / EBITDA", x1(dte))]
        if cap is not None and cap > 0.09: review.append("Implied cap rate above 9%: possible discount to property value")
        F = {"value": {"ffoy": ("FFO yield", clip(ffo / mc, -1, 1), pct(ffo / mc)), "pb": G["pb"],
                       "divy": ("Dividend yield", clip(dy, 0, 0.3), pct(dy))},
             "quality": pick("om", "revg", "piotroski"),
             "safety": {"de": G["de"], "dte": ("Debt / EBITDA", None if dte is None else -clip(dte, 0, 30), x1(dte)), "stab": STAB}}
    elif pb_name == "biotech" and mc and cash is not None:
        net = cash - (debt or 0)
        run = None if fcf is None else (10.0 if fcf >= 0 else clip(cash / -fcf, 0, 10))
        metrics += [("Net cash / market cap", pct(net / mc)), ("Cash runway", "–" if run is None else ("10+ years" if run >= 10 else "%.1f years" % run))]
        if net > mc: review.append("Market cap is below net cash: the market pays you to own the pipeline")
        F = {"value": {"ncm": ("Net cash / market cap", clip(net / mc, -2, 3), pct(net / mc)), "pb": G["pb"]},
             "quality": pick("revg", "gm", "piotroski"),
             "safety": {"run": ("Cash runway", run, metrics[-1][1]), "de": G["de"], "curr": G["curr"]}}
    elif pb_name == "software" and mc:
        gp, evu = usd(x.get("gp")), mc + (debt or 0) - (cash or 0)
        evgp = (evu / gp) if gp and gp > 0 and evu > 0 else None
        r40 = (g("revenue_growth") + fcf / rev) if g("revenue_growth") is not None and fcf is not None and rev else None
        metrics += [("EV / gross profit", x1(evgp)), ("Rule of 40", "–" if r40 is None else "%.0f" % (r40 * 100))]
        if evgp is not None and evgp < 4 and r40 is not None and r40 > 0.30: review.append("EV under 4 times gross profit with Rule of 40 above 30")
        F = {"value": {"gpy": ("Gross profit / EV", None if evgp is None else clip(1 / evgp, 0, 5), "EV/GP " + x1(evgp)), "fcfy": G["fcfy"], "ey": G["ey"]},
             "quality": {"r40": ("Rule of 40", clip(r40, -1, 1.5), metrics[-1][1]), "gm": G["gm"], "piotroski": G["piotroski"]},
             "safety": pick("altman", "de", "curr")}
    elif pb_name == "mining":
        if ev is not None and 0 < ev < 4: review.append("EV under 4 times EBITDA: check reserves in the technical report")
    elif pb_name == "energy":
        if (g("fcf_yield") or 0) > 0.20: review.append("Free cash flow yield above 20%: check reserve life (PV-10) in the annual report")
    elif pb_name == "shipping":
        if pb is not None and 0 < pb < 0.6: review.append("P/B under 0.6: the fleet may be worth more than the market value")
    px, nn = g("current_price"), g("net_net_value")
    if px and nn and nn > px: review.append("Trades below net-net value (Graham net-net)")

    group = pb_name if F is not None else "*"
    if F is None:
        if pb_name in OWN_GROUP: notes.append("Sector figures missing: general factors used")
        F = generic
    return pb_name, group, F, metrics, review, notes
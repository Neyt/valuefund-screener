# -*- coding: utf-8 -*-
#!/usr/bin/env python3

"""

valuefund.substack.com -- Daily Deep-Value Micro-Cap Screener v3

Buffett-style systematic analysis of overlooked micro/nano-cap stocks.



Scoring Engine:

  - Piotroski F-Score (0-9)      -- financial health & quality

  - Altman Z-Score               -- bankruptcy / distress risk

  - Magic Formula (Greenblatt)   -- earnings yield + ROIC rank

  - Buffett Checklist (0-14)     -- qualitative moat & management

  - DCF / Graham / Net-Net       -- intrinsic value triangulation

  - Catalyst Detection           -- news, SEC Form 4, hidden value

  - 52-week position             -- entry timing

  - Short interest               -- squeeze potential

  - Insider ownership            -- skin-in-the-game signal

  - EV/EBITDA vs private comps   -- M&A floor valuation

"""



import sqlite3

import time, math, os, sys, json, warnings, requests, re, time

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
try:
    from skip_registry import should_skip, should_skip_stale, record_failure, record_success
    _HAVE_SKIP_REG = True
except ImportError:
    _HAVE_SKIP_REG = False
    def should_skip(t): return (False, "")
    def should_skip_stale(t, p=None): return (False, "")
    def record_failure(t, r): pass
    def record_success(t): pass

try:
    from qf2_fallback import get_qf2_fundamentals as _qf2_get
    _HAVE_QF2 = True
except ImportError:
    _HAVE_QF2 = False
    def _qf2_get(t, max_age_years=3): return None





try:

    from generate_dashboard import generate_html_index as _gen_html

    from generate_docx import generate_docx_report as _gen_docx

    _HAVE_GENERATORS = True

except ImportError:

    _HAVE_GENERATORS = False

from datetime import datetime, date

from urllib.parse import quote



warnings.filterwarnings('ignore')

try:

    import yfinance as yf

    import pandas as pd

    import numpy as np

except ImportError as e:

    print(f"[ERROR] {e} -- run: pip install yfinance pandas numpy")

    sys.exit(1)



# --- Config -------------------------------------------------------------------

BASE_DIR    = r"D:\StockAnalysis"

REPORTS_DIR = os.path.join(BASE_DIR, "reports")

DB_DIR      = os.path.join(BASE_DIR, "database")

DB_PATH     = os.path.join(DB_DIR,   "stocks.db")

HTML_PATH   = os.path.join(DB_DIR,   "index.html")

BRAND       = "valuefund.substack.com"

# BATCH_SIZE loaded from smart_config.json (fallback = 50)
def _load_batch_size():
    try:
        import json
        with open(r"D:\StockAnalysis\config\smart_config.json") as _f:
            return int(json.load(_f).get("analysis", {}).get("batch_size", 50))
    except Exception:
        return 50
BATCH_SIZE = _load_batch_size()



HTTP_TIMEOUT = 6      # seconds per external HTTP call

HEADERS = {'User-Agent': f'{BRAND} research-bot/3.0', 'Accept': 'application/json'}



# --- Candidate Universe (90+ tickers) -----------------------------------------

# Format: (ticker, exchange_label, short_thesis_note)

CANDIDATE_STOCKS_RAW = [

    # -- US OTC / Micro-NASDAQ / AMEX -----------------------------------------

    ("MIND",  "NASDAQ",  "MIND Technology - marine acoustic / defense TX"),

    ("CODA",  "NASDAQ",  "Coda Octopus - underwater 3D mapping surveys"),

    ("VISL",  "NASDAQ",  "Vislink Technologies - live video transmission"),

    ("LIQT",  "NASDAQ",  "LiqTech International - SiC membrane filtration"),

    ("MGYR",  "OTC",     "Magyar Bancorp - NJ community bank cheap P/B"),

    ("FFBW",  "OTC",     "FFBW Inc - WI thrift below 0.73x TBV"),

    ("ESSA",  "NASDAQ",  "ESSA Bancorp - PA savings bank low P/B"),

    ("CRWS",  "NASDAQ",  "Crown Crafts - infant products Groovy Girls relaunch"),

    ("AEYE",  "NASDAQ",  "AudioEye - ADA/DOJ mandate April 2026 catalyst"),

    ("SACH",  "AMEX",    "Sachem Capital - hard-money RE lender 0.6x book"),

    ("AVNW",  "NASDAQ",  "Aviat Networks - microwave networking infrastructure"),

    ("DPSI",  "NASDAQ",  "DecisionPoint Systems - enterprise mobility"),

    ("IFON",  "OTC",     "InfoSonics Corp - rugged smartphones Latin America"),

    ("VNRX",  "OTC",     "VolitionRx - epigenetics blood diagnostics"),

    ("CLSH",  "OTC",     "CLS Holdings - cannabis licensing real estate"),

    ("LWAY",  "NASDAQ",  "Lifeway Foods - kefir dairy niche brand"),

    ("PKOH",  "NASDAQ",  "Park-Ohio Holdings - industrial manufacturing Ohio"),

    ("LYTS",  "NASDAQ",  "LSI Industries - lighting & graphics signage"),

    ("BWEN",  "NASDAQ",  "Broadwind Inc - wind towers steel structures"),

    ("CLFD",  "NASDAQ",  "Clearfield Inc - fiber management solutions"),

    ("PCYG",  "NASDAQ",  "Park City Group - supply chain SaaS micro-cap"),

    ("LAWS",  "NASDAQ",  "Lawson Products - industrial MRO distributor"),

    ("SGBX",  "NASDAQ",  "Safe & Green Holdings - modular building"),

    # -- US Micro-Cap Community Banks (classic Buffett early career targets) --

    ("WNEB",  "NASDAQ",  "Western New England Bancorp - MA/CT community bank"),

    ("CZWI",  "NASDAQ",  "Citizens Community Bancorp WI - Midwest thrift"),

    ("EBMT",  "NASDAQ",  "Eagle Bancorp Montana - Rocky Mtn community bank"),

    ("PBFS",  "OTC",     "Pioneer Bankshares VA - rural community bank"),

    ("FXNC",  "OTC",     "First National Corp VA - Shenandoah Valley bank"),

    ("OPHC",  "OTC",     "OptimumBank Holdings FL - micro thrift"),

    ("FNWB",  "NASDAQ",  "First Northwest Bancorp WA - Pacific NW thrift"),

    ("ESXB",  "OTC",     "Community Bankers Trust VA - rural micro bank"),

    ("AUBN",  "NASDAQ",  "Auburn National Bancorp AL - dividend payer"),

    ("CIZN",  "NASDAQ",  "Citizens Inc TX - life insurance micro-cap"),

    ("HWBK",  "OTC",     "Hawthorn Bancorp MO - micro community bank"),

    ("NWIN",  "OTC",     "Northwest Indiana Bancorp - community lender"),

    ("HLAN",  "OTC",     "Heartland BancCorp OH - small thrift"),

    ("FCCO",  "NASDAQ",  "First Community Corp SC - Southeast bank"),

    ("HBCP",  "NASDAQ",  "Home Bancorp LA - Louisiana regional bank"),

    ("SMBC",  "NASDAQ",  "Southern Missouri Bancorp - Midwest community"),

    # -- US Industrial / Niche / Special Situation -----------------------------

    ("TWIN",  "NASDAQ",  "Twin Disc - power transmission niche industrial"),

    ("SCSC",  "NASDAQ",  "ScanSource - specialty tech distributor"),

    ("KFRC",  "NASDAQ",  "Kforce Inc - professional staffing Florida"),

    ("NRDY",  "NYSE",    "Nerdy Inc - online learning platform edtech"),

    ("TPVG",  "NYSE",    "TriplePoint Venture Growth BDC - VC debt fund"),

    ("SGRP",  "NASDAQ",  "SPAR Group - retail merchandising services"),

    ("UONE",  "NASDAQ",  "Urban One - African-American media company"),

    ("RCKY",  "NASDAQ",  "Rocky Brands - work/Western footwear niche"),

    ("DCOM",  "NASDAQ",  "Dime Community Bancshares - NY community bank"),

    ("AMTB",  "NASDAQ",  "Amerant Bancorp - FL/TX community bank"),

    # -- ASX (Australian Securities Exchange) ---------------------------------

    ("BRN.AX",  "ASX",   "Brainchip Holdings - neuromorphic AI edge chips"),

    ("WBT.AX",  "ASX",   "Weebit Nano - ReRAM semiconductor memory"),

    ("EMH.AX",  "ASX",   "European Metals Holdings - Cinovec lithium-tin"),

    ("PLL.AX",  "ASX",   "Piedmont Lithium - Tesla supply NC lithium"),

    ("DRO.AX",  "ASX",   "DroneShield - counter-drone defense systems"),

    ("IPD.AX",  "ASX",   "ImpediMed - bioimpedance oncology diagnostics"),

    ("IMD.AX",  "ASX",   "Imdex - mining technology sensors"),

    ("VUL.AX",  "ASX",   "Vulcan Energy - zero-carbon lithium Germany"),

    ("CXO.AX",  "ASX",   "Core Lithium - NT Australia lithium producer"),

    ("CMM.AX",  "ASX",   "Capricorn Metals - WA gold producer low-cost"),

    ("ALK.AX",  "ASX",   "Alkane Resources - gold and rare earths NSW"),

    ("NEA.AX",  "ASX",   "Nearmap - aerial imaging AI analytics"),

    ("GTK.AX",  "ASX",   "Gentrack Group - utilities/airports SaaS NZ"),

    # -- Oslo Bors (OL) -------------------------------------------------------

    ("AYFIE.OL",  "Oslo",  "Ayfie Group - AI enterprise text analysis"),

    ("KAHOT.OL",  "Oslo",  "Kahoot! - game-based learning SaaS"),

    ("OTL.OL",    "Oslo",  "Otello Corporation - mobile software ad tech"),

    ("NEL.OL",    "Oslo",  "Nel Hydrogen - electrolyser manufacturer"),

    ("IDEX.OL",   "Oslo",  "IDEX Biometrics - fingerprint sensor micro"),

    ("ZAPTEC.OL", "Oslo",  "Zaptec - EV charging Norway leader"),

    ("RECSI.OL",  "Oslo",  "REC Silicon - polysilicon semiconductor"),

    ("NONG.OL",   "Oslo",  "Norse Atlantic Airways - transatlantic budget"),

    # -- Frankfurt / Xetra (.F) -----------------------------------------------

    ("SGL.F",  "Frankfurt",  "SGL Carbon - specialty carbon graphite"),

    ("GFT.F",  "Frankfurt",  "GFT Technologies - fintech IT services"),

    ("MBB.F",  "Frankfurt",  "MBB SE - German family holding company"),

    ("SNH.F",  "Frankfurt",  "Sienna Biopharmaceuticals Frankfurt"),

    # -- TSX Venture Exchange (.V) --------------------------------------------

    ("CRDL.V",  "TSX-V",  "Cardiol Therapeutics - cannabidiol cardiology"),

    ("FWZ.V",   "TSX-V",  "Fireweed Metals - Yukon zinc-lead-silver"),

    ("LIO.V",   "TSX-V",  "Lion One Metals - Fiji alkalic gold system"),

    ("MTA.V",   "TSX-V",  "Metalla Royalty - precious metals royalty"),

    ("BTU.V",   "TSX-V",  "BTU Metals - copper-gold Ontario"),

    ("GMIN.V",  "TSX-V",  "G Mining Ventures - gold dev Brazil"),

    # -- Singapore SGX (.SI) -------------------------------------------------

    ("5CP.SI",  "SGX",  "Cortina Holdings - luxury watch retail SG"),

    ("OKP.SI",  "SGX",  "OKP Holdings - civil engineering Singapore"),

    # -- AIM London / Other ---------------------------------------------------

    ("TPVG",    "NYSE",   "TriplePoint Venture Growth - BDC"),

    ("RCKY",    "NASDAQ", "Rocky Brands - niche footwear"),

    # -- US Community Banks (additional) --------------------------------------

    ("PLBC",  "OTC",     "Plumas Bank CA - mountain community bank very cheap P/B"),

    ("CZFS",  "NASDAQ",  "Citizens Financial Services PA - rural PA bank 0.8x book"),

    ("MNSB",  "OTC",     "MainStreet Bankshares VA - Blue Ridge rural bank"),

    ("BSVN",  "NASDAQ",  "Bank7 Corp OK - Oklahoma energy-belt bank high ROE"),

    ("OSBC",  "NASDAQ",  "Old Second Bancorp IL - Chicago suburb community bank"),

    ("GSBC",  "NASDAQ",  "Great Southern Bancorp MO - Midwest thrift dividend"),

    ("LKFN",  "NASDAQ",  "Lakeland Financial IN - northern IN quality bank"),

    ("OVLY",  "NASDAQ",  "Oak Valley Bancorp CA - Central Valley CA bank"),

    ("OPBK",  "NASDAQ",  "OP Bancorp CA - Korean-American community bank LA"),

    ("PROV",  "NASDAQ",  "Provident Financial Holdings CA - SoCal thrift cheap"),

    ("BWFG",  "NASDAQ",  "Bankwell Financial CT - New England commercial bank"),

    ("UVSP",  "NASDAQ",  "Univest Financial PA - Southeast PA community bank"),

    ("MBIN",  "OTC",     "Merchants Financial Group MN - Twin Cities micro bank"),

    ("BCOW",  "OTC",     "1895 Bancorp of Wisconsin - WI thrift mutual conversion"),

    ("CFFI",  "NASDAQ",  "C&F Financial VA - Richmond VA diversified bank"),

    ("HTBI",  "NASDAQ",  "HomeTrust Bancshares NC - Southeast US community bank"),

    ("FBIZ",  "NASDAQ",  "First Business Financial WI - commercial bank WI"),

    ("MLVF",  "OTC",     "Malvern Bancshares PA - Main Line PA ultra-micro bank"),

    ("FFDF",  "OTC",     "FFD Financial Corp OH - Ohio community bank tiny float"),

    ("ITIC",  "NASDAQ",  "Investors Title NC - title insurance micro-cap high ROE"),

    ("PBAM",  "OTC",     "Private Bancorp of America CA - SBA lending specialist"),

    # -- US Industrial / Special Situation -------------------------------------

    ("HAYN",  "NASDAQ",  "Haynes International - high-temp nickel alloys specialty"),

    ("ESCA",  "NASDAQ",  "Escalade Inc IN - sporting goods / office products"),

    ("HOFT",  "NASDAQ",  "Hooker Furnishings VA - residential furniture niche"),

    ("KINS",  "NASDAQ",  "Kingstone Companies NY - regional P&C insurer cheap"),

    ("MFIN",  "NASDAQ",  "Medallion Financial - specialty lending / recreation"),

    ("SGA",   "AMEX",    "Saga Communications - radio broadcasting value"),

    ("RAND",  "NASDAQ",  "Rand Capital BDC - Buffalo NY micro-cap BDC"),

    ("SPWH",  "NASDAQ",  "Sportsman's Warehouse - outdoor retail omnichannel"),

    ("TLYS",  "NYSE",    "Tilly's Inc - teen action sports retail California"),

    ("NN",    "NASDAQ",  "NN Inc - precision components aerospace/medical"),

    ("ENVA",  "NYSE",    "Enova International - online lending fintech"),

    ("KBAL",  "NASDAQ",  "Kimball International - commercial furniture Indiana"),

    ("DXLG",  "NASDAQ",  "Destination XL Group - big & tall apparel niche"),

    ("FLXS",  "NASDAQ",  "Flexsteel Industries IA - upholstered furniture OEM"),

    ("RCUS",  "NYSE",    "Arcus Biosciences - oncology immuno-oncology"),

    ("CATO",  "NYSE",    "Cato Corp - value fashion retail Southeast"),

    ("CLAR",  "NASDAQ",  "Clarus Corp - outdoor performance brands Black Diamond"),

    ("HTLD",  "NASDAQ",  "Heartland Express - trucking carrier Midwest"),

    ("MRTN",  "NASDAQ",  "Marten Transport WI - refrigerated trucking niche"),

    ("ARII",  "OTC",     "American Railcar Industries - railcar leasing"),

    ("ZEUS",  "NASDAQ",  "Olympic Steel - metal service center Cleveland"),

    ("TRST",  "NASDAQ",  "TrustCo Bancorp NY - Upstate NY thrift deposit-heavy"),

    ("FCNCA", "NASDAQ",  "First Citizens BancShares NC - regional bank acquirer"),

    ("CTBI",  "NASDAQ",  "Community Trust Bancorp KY - Appalachian community bank"),

    ("CIVB",  "OTC",     "Civista Bankshares OH - Ohio community bank"),

    ("NBTB",  "NASDAQ",  "NBT Bancorp NY - Upstate NY regional bank"),

    # -- US Software / Tech Micro-Cap ------------------------------------------

    ("APPS",  "NASDAQ",  "Digital Turbine - mobile software delivery platform"),

    ("SWKH",  "OTC",     "SWK Holdings - life science royalty finance"),

    ("SPRT",  "OTC",     "Support.com - remote tech support SaaS"),

    ("ALLT",  "NASDAQ",  "Allot Communications - network intelligence DPI"),

    ("CLPS",  "NASDAQ",  "CLPS Technology - IT services Greater China"),

    ("EVBG",  "NASDAQ",  "Everbridge - critical event management SaaS"),

    ("XPEL",  "NASDAQ",  "XPEL Inc - paint protection film high-margin niche"),

    ("NXGN",  "NASDAQ",  "NextGen Healthcare - ambulatory EHR SaaS"),

    ("PMVP",  "NASDAQ",  "PMV Pharmaceuticals - p53 reactivation oncology"),

    ("MXCT",  "NASDAQ",  "MaxCyte - electroporation cell engineering tools"),

    ("VCNX",  "NASDAQ",  "Vaccinex - neuroscience semaphorin-4D antibody"),

    ("PLSE",  "NASDAQ",  "Pulse Biosciences - nano-pulse stimulation platform"),

    ("IDAI",  "OTC",     "T2 Biosystems - sepsis rapid diagnostics"),

    ("NNOX",  "NASDAQ",  "Nano-X Imaging - digital X-ray chip disruption"),

    ("FIVN",  "NASDAQ",  "Five9 - cloud contact center CCaaS platform"),

    ("GLDD",  "NASDAQ",  "Great Lakes Dredge & Dock - infrastructure specialty"),

    ("CDMO",  "NASDAQ",  "Avid Bioservices - biologic contract manufacturer"),

    ("PRDO",  "NASDAQ",  "Perdoceo Education - for-profit education"),

    ("UTL",   "NASDAQ",  "Unitil Corp NH - New England gas/electric utility"),

    ("KPTI",  "NASDAQ",  "Karyopharm Therapeutics - nuclear export inhibitor"),

    ("CODA",  "OTC",     "Coda Octopus Group - underwater survey 3D imaging"),

    ("GDOT",  "NASDAQ",  "Green Dot Corp - prepaid debit/banking fintech"),

    ("INFU",  "AMEX",    "InfuSystem Holdings - infusion pump services"),

    ("BLNK",  "NASDAQ",  "Blink Charging - EV charging network operator"),

    ("EVGO",  "NASDAQ",  "EVgo - fast charging infrastructure"),

    # -- US Healthcare / Biotech Micro-Cap ------------------------------------

    ("MIST",  "NASDAQ",  "Milestone Scientific - drug delivery microinjection"),

    ("RNLX",  "NASDAQ",  "Renalytix - AI-enabled kidney disease diagnostics"),

    ("NUVB",  "NASDAQ",  "Nuvation Bio - oncology precision medicine"),

    ("CMRX",  "NASDAQ",  "Chimerix - antiviral oncology pipeline"),

    ("PHAT",  "NASDAQ",  "Phathom Pharmaceuticals - vonoprazan GI/GERD"),

    ("BRTX",  "NASDAQ",  "BioRestorative Therapies - disc/knee stem cells"),

    ("AGEN",  "NASDAQ",  "Agenus Inc - cancer immunology checkpoint"),

    ("TCON",  "NASDAQ",  "TRACON Pharmaceuticals - TRC105 endoglin antibody"),

    ("SNPX",  "NASDAQ",  "Synapse Energy Services - EEG neurology diagnostics"),

    ("CBIO",  "NASDAQ",  "Catalyst Biosciences - hemostasis gene therapy"),

    # -- US Consumer / Retail Micro-Cap ---------------------------------------

    ("GDEN",  "NASDAQ",  "Golden Entertainment - regional casino Nevada"),

    ("FULL",  "OTC",     "Full House Resorts - small gaming regional"),

    ("NHTC",  "NASDAQ",  "Natural Health Trends - direct sales wellness"),

    ("IPAR",  "NASDAQ",  "Inter Parfums - licensed fragrance brand royalties"),

    ("BSET",  "NASDAQ",  "Bassett Furniture VA - home furnishings retail"),

    ("CRAI",  "NASDAQ",  "CRA International - economic consulting boutique"),

    ("RGP",   "NASDAQ",  "Resources Connection - project staffing"),

    ("HCSG",  "NASDAQ",  "Healthcare Services Group - facility mgmt outsource"),

    ("USPH",  "NYSE",    "U.S. Physical Therapy - outpatient PT clinic network"),

    ("PRAA",  "NASDAQ",  "PRA Group - debt purchasing portfolios"),

    ("ECPG",  "NASDAQ",  "Encore Capital - non-performing loan purchaser"),

    ("HCI",   "NYSE",    "HCI Group FL - homeowners insurance specialty"),

    ("UIHC",  "NASDAQ",  "United Insurance Holdings FL - coastal insurer"),

    # -- ASX additional -------------------------------------------------------

    ("CCP.AX",  "ASX",   "Credit Corp Group - debt buying recovery Australia"),

    ("CAT.AX",  "ASX",   "Catapult Sports - athlete analytics SaaS global"),

    ("MNF.AX",  "ASX",   "MNF Group - telco carrier services Australia/Singapore"),

    ("SRV.AX",  "ASX",   "Servcorp - serviced offices premium flexible"),

    ("GOR.AX",  "ASX",   "Gold Road Resources - Gruyere gold WA"),

    ("MCR.AX",  "ASX",   "Mincor Resources - nickel sulfide WA"),

    ("DDH.AX",  "ASX",   "DDH1 Drilling - mineral drilling contractor ASX"),

    ("BSX.AX",  "ASX",   "Blackstone Minerals - Battery Road Vietnam nickel"),

    ("OBM.AX",  "ASX",   "Ora Banda Mining - WA gold developer"),

    ("CTT.AX",  "ASX",   "Cettire - luxury fashion marketplace Australia"),

    ("PGH.AX",  "ASX",   "Pact Group - recycled packaging plastics"),

    ("SHJ.AX",  "ASX",   "Shine Justice - class action litigation firm"),

    ("HLO.AX",  "ASX",   "Helloworld Travel - travel agency network ASX"),

    ("GBT.AX",  "ASX",   "GBST Holdings - financial software administration"),

    ("EML.AX",  "ASX",   "EML Payments - prepaid card fintech reloadable"),

    ("AVA.AX",  "ASX",   "Ava Risk Group - perimeter security AI detection"),

    ("ABR.AX",  "ASX",   "American Rare Earths - Wyoming REE deposit"),

    ("TMX.AX",  "ASX",   "Terrain Minerals - WA gold explorer"),

    ("ALC.AX",  "ASX",   "Alcidion - healthcare informatics clinical decision"),

    ("3DP.AX",  "ASX",   "Pointerra - 3D data infrastructure AI analytics"),

    # -- TSX additional -------------------------------------------------------

    ("BU.TO",   "TSX",   "Burford Capital - litigation finance high ROE"),

    ("AVO.V",   "TSX-V", "Avocet Capital - micro mining royalty BC"),

    ("TFPM.TO", "TSX",   "Triple Flag Precious Metals - royalty streaming"),

    ("MAG.TO",  "TSX",   "MAG Silver - Juanicipio Mexico joint venture"),

    ("NXE.TO",  "TSX",   "NexGen Energy - Arrow uranium Saskatchewan"),

    ("WM.TO",   "TSX",   "Wallbridge Mining - Fenelon gold Quebec"),

    ("PRQ.V",   "TSX-V", "Petro River Oil - Permian Basin micro-cap"),

    ("TSLA.V",  "TSX-V", "Tesoro Gold - Chilean gold developer"),

    ("SIL.V",   "TSX-V", "SilverCrest Metals - Las Chispas Mexico silver"),

    # -- Nordic / European micro-caps -----------------------------------------

    ("MOWI.OL",  "Oslo",  "Mowi ASA - world largest salmon farmer"),

    ("ARCHER.OL","Oslo",  "Archer - oil services drilling provider"),

    ("ODF.OL",   "Oslo",  "Odfjell SE - chemical tanker shipping"),

    ("NRC.OL",   "Oslo",  "NRC Group - rail and infrastructure Norway"),

    ("WAWI.ST",  "Nasdaq Stockholm", "Wallenstam - Sweden property company"),

    ("LATO-B.ST","Nasdaq Stockholm", "Latour AB - Swedish industrial holding family"),

    ("DUNI.ST",  "Nasdaq Stockholm", "Duni Group - sustainable tableware"),

    ("EVO.ST",   "Nasdaq Stockholm", "Evolution AB - live casino B2B premium"),

    ("HPOL-B.ST","Nasdaq Stockholm", "H&Q Private Equity - Swedish PE micro"),

    ("HUSQ-B.ST","Nasdaq Stockholm", "Husqvarna - outdoor power equipment"),

    # -- Singapore / Hong Kong -------------------------------------------------

    ("S63.SI",  "SGX",   "ST Engineering - defense aerospace Singapore"),

    ("BN4.SI",  "SGX",   "Keppel Corp - diversified industrial Singapore"),

    ("T39.SI",  "SGX",   "SingPost - postal logistics e-commerce last mile"),

    ("8869.HK", "HKEX",  "Moxian Inc - digital marketing mobile China"),

    ("2607.HK", "HKEX",  "Shanghai Pharmaceuticals - drug distribution China"),

    # -- German SDAX / Xetra additional ---------------------------------------

    ("NB2.F",   "Frankfurt", "Northern Data - HPC infrastructure Germany"),

    ("AIXA.F",  "Frankfurt", "Aixtron SE - semiconductor deposition equipment"),

    ("EVK.F",   "Frankfurt", "Evonik Industries - specialty chemicals Germany"),

    ("FNTN.F",  "Frankfurt", "freenet AG - mobile virtual network operator"),

    ("KBC.F",   "Frankfurt", "Kabel Deutschland - broadband cable Germany"),

    ("TGH.F",   "Frankfurt", "Triton International - container leasing fleet"),

]



# De-duplicate

_seen = set()

CANDIDATE_STOCKS = []

for item in CANDIDATE_STOCKS_RAW:

    if item[0] not in _seen:

        _seen.add(item[0])

        CANDIDATE_STOCKS.append(item)





# --- Catalyst Keywords --------------------------------------------------------

CATALYST_KEYWORDS = {

    'M&A / Buyout':            ['acquisition','merger','buyout','acquired','takeover',

                                 'strategic review','sale process','go-private','bid for'],

    'Share Buyback':           ['buyback','repurchase','share repurchase','tender offer'],

    'Special Dividend':        ['special dividend','extra dividend','return of capital'],

    'Regulatory Approval':     ['fda approved','cleared by','received approval','authorized'],

    'Major Contract Win':      ['awarded contract','wins contract','partnership signed',

                                 'new deal worth','multi-year contract'],

    'Restructuring / Spinoff': ['restructuring','spinoff','spin-off','divestiture','asset sale'],

    'Activist Investor':       ['activist investor','proxy fight','filed 13d','board shakeup'],

    'Insider Buying':          ['insider buying','director buys','ceo purchased','open market purchase'],

    'Earnings Beat / Raise':   ['beats estimates','raises guidance','record revenue','exceeded'],

    'Debt Elimination':        ['paid off debt','debt-free','refinanced','deleveraging'],

    'Asset Monetization':      ['monetizing assets','selling property','ip licensing','patent'],

}





# --- Database -----------------------------------------------------------------

def create_database():

    os.makedirs(DB_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)

    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS analyzed_stocks (

        id                 INTEGER PRIMARY KEY AUTOINCREMENT,

        ticker             TEXT UNIQUE,

        company_name       TEXT,

        exchange           TEXT,

        market_cap         REAL,

        current_price      REAL,

        graham_number      REAL,

        dcf_value          REAL,

        net_net_value      REAL,

        margin_of_safety   REAL,

        promise_score      REAL,

        roe                REAL,

        debt_equity        REAL,

        revenue_growth     REAL,

        ev_ebitda          REAL,

        piotroski_score    REAL,

        altman_z           REAL,

        magic_formula_ey   REAL,

        buffett_checklist  REAL,

        insider_pct        REAL,

        short_interest_pct REAL,

        week52_position    REAL,

        catalyst_score     REAL,

        catalysts          TEXT,

        hidden_value_notes TEXT,

        analysis_date      TEXT,

        report_path        TEXT,

        notes              TEXT,

        grade              TEXT,

                avg_volume         REAL

    )
    ''')

    # Migration: add columns if upgrading

    new_cols = [

        ('ev_ebitda','REAL'),('piotroski_score','REAL'),('altman_z','REAL'),

        ('magic_formula_ey','REAL'),('buffett_checklist','REAL'),

        ('insider_pct','REAL'),('short_interest_pct','REAL'),

        ('week52_position','REAL'),('catalyst_score','REAL'),

        ('catalysts','TEXT'),('hidden_value_notes','TEXT'),

        # v4 additions

        ('sector','TEXT'),('industry','TEXT'),('pe_ratio','REAL'),

        ('pb_ratio','REAL'),('ps_ratio','REAL'),('fcf_yield','REAL'),

        ('gross_margin','REAL'),('beta','REAL'),('ev_revenue','REAL'),

        ('dividend_yield','REAL'),('current_ratio','REAL'),

        ('bvps','REAL'),('eps_stored','REAL'),('operating_margin','REAL'),

        ('action','TEXT'),

        ('avg_volume','REAL'),

    ]

    for col, typ in new_cols:

        try: c.execute(f"ALTER TABLE analyzed_stocks ADD COLUMN {col} {typ}")

        except sqlite3.OperationalError: pass

    conn.commit(); conn.close()





def get_analyzed_tickers():

    conn = sqlite3.connect(DB_PATH)

    c = conn.cursor()

    c.execute("SELECT ticker FROM analyzed_stocks")

    t = {r[0] for r in c.fetchall()}

    conn.close(); return t





def insert_into_db(data, report_path):

    conn = sqlite3.connect(DB_PATH)

    c = conn.cursor()

    cats_j = json.dumps(data.get('catalysts',[]),      ensure_ascii=False)

    hv_j   = json.dumps(data.get('hidden_value_signals',[]), ensure_ascii=False)

    action = {'A':'BUY','B':'WATCH','C':'PASS','D':'PASS','F':'PASS'}.get(data.get('grade','?'),'PASS')

    mc = data.get('market_cap'); fcf_v = data.get('fcf')

    fcf_y = (fcf_v/mc) if (fcf_v and mc and mc>0) else None

    ev = data.get('ev_ebitda'); rev = _safe(data.get('revenue_growth'))

    # ev_revenue from info cached in data

    ev_r = data.get('ev_revenue')

    c.execute('''INSERT OR REPLACE INTO analyzed_stocks
        (ticker, company_name, exchange, market_cap, current_price,
         graham_number, dcf_value, net_net_value, margin_of_safety,
         promise_score, roe, debt_equity, revenue_growth,
         ev_ebitda, piotroski_score, altman_z, magic_formula_ey,
         buffett_checklist, insider_pct, short_interest_pct, week52_position,
         catalyst_score, catalysts, hidden_value_notes,
         sector, industry, pe_ratio, pb_ratio, ps_ratio, fcf_yield, gross_margin,
         beta, ev_revenue, dividend_yield, current_ratio, bvps, eps_stored, operating_margin,
         action, analysis_date, report_path, notes, grade,
         short_thesis, detailed_thesis, avg_volume)
        VALUES (?,?,?,?,?, ?,?,?,?,?, ?,?,?, ?,?,?,?, ?,?,?,?, ?,?,?,
                ?,?,?,?,?,?,?, ?,?,?,?,?,?,?, ?,?,?,?,?,?,?,?)''',
        (data['ticker'], data['company_name'], data['exchange'],
         data.get('market_cap'), data.get('current_price'),
         data.get('graham_number'), data.get('dcf_value'),
         data.get('net_net_value'), data.get('margin_of_safety'),
         data.get('promise_score'), data.get('roe'),
         data.get('debt_equity'), data.get('revenue_growth'),
         data.get('ev_ebitda'), data.get('piotroski_score'),
         data.get('altman_z'), data.get('magic_formula_ey'),
         data.get('buffett_checklist'), data.get('insider_pct'),
         data.get('short_interest_pct'), data.get('week52_position'),
         data.get('catalyst_score'), cats_j, hv_j,
         data.get('sector'), data.get('industry'),
         data.get('pe_ratio'), data.get('pb_ratio'), data.get('ps_ratio'),
         fcf_y, data.get('gross_margin'), data.get('beta'), ev_r,
         data.get('dividend_yield'), data.get('current_ratio'),
         data.get('bvps'), data.get('eps'), data.get('operating_margin'),
         action,
         date.today().strftime('%Y-%m-%d'),
         report_path, data.get('notes'), data.get('grade'),
         None, None,
         data.get('avg_volume')))

    conn.commit(); conn.close()





# --- Math helpers -------------------------------------------------------------

def _safe(val):

    try:

        if val is None: return None

        f = float(val)

        return None if (math.isnan(f) or math.isinf(f)) else f

    except: return None



def _bsr(df, col, *labels):

    """Get first matching row from dataframe at given column."""

    for lbl in labels:

        if lbl in df.index:

            return _safe(df.loc[lbl, col])

    return None





# --- Valuation: DCF / Graham / Net-Net ---------------------------------------

def calc_graham(eps, bvps):

    if eps and bvps and eps > 0 and bvps > 0:

        try: return math.sqrt(22.5 * eps * bvps)

        except: pass

    return None



def calc_dcf(fcf, g, r=0.08, tm=12, yrs=10):

    if not fcf or fcf <= 0: return None

    try:

        g = min(max(float(g or 0.03), -0.05), 0.15)

        pv = sum(fcf*((1+g)**y)/((1+r)**y) for y in range(1,yrs+1))

        return pv + fcf*((1+g)**yrs)*tm/((1+r)**yrs)

    except: return None



def calc_net_net(ca, tl, sh):

    if ca is None or tl is None or not sh or sh <= 0: return None

    return (ca - tl) / sh





# --- Piotroski F-Score (0-9) -------------------------------------------------

def calculate_piotroski(stock, info):

    """

    9-point financial strength score (Piotroski 2000).

    >6 = strong quality; <3 = deteriorating.

    """

    score = 0; signals = []

    try:

        bs  = stock.balance_sheet

        inc = stock.financials

        cf  = stock.cashflow

        if bs is None or inc is None or bs.empty or inc.empty: return None, []

        if len(bs.columns) < 2 or len(inc.columns) < 2:       return None, []



        cy, py = bs.columns[0], bs.columns[1]



        ta_cy = _bsr(bs,cy,'Total Assets','TotalAssets')

        ta_py = _bsr(bs,py,'Total Assets','TotalAssets')

        ni_cy = _bsr(inc,inc.columns[0],'Net Income','NetIncome')

        ni_py = _bsr(inc,inc.columns[1],'Net Income','NetIncome')

        ocf_cy= _bsr(cf, cf.columns[0], 'Operating Cash Flow',

                     'Total Cash From Operating Activities') if cf is not None and not cf.empty else None

        ca_cy = _bsr(bs,cy,'Total Current Assets','CurrentAssets')

        cl_cy = _bsr(bs,cy,'Total Current Liabilities','CurrentLiabilities')

        ca_py = _bsr(bs,py,'Total Current Assets','CurrentAssets')

        cl_py = _bsr(bs,py,'Total Current Liabilities','CurrentLiabilities')

        ltd_cy= _bsr(bs,cy,'Long Term Debt','LongTermDebt')

        ltd_py= _bsr(bs,py,'Long Term Debt','LongTermDebt')

        rev_cy= _bsr(inc,inc.columns[0],'Total Revenue','Revenue')

        rev_py= _bsr(inc,inc.columns[1],'Total Revenue','Revenue')

        gp_cy = _bsr(inc,inc.columns[0],'Gross Profit','GrossProfit')

        gp_py = _bsr(inc,inc.columns[1],'Gross Profit','GrossProfit')



        # F1 ROA > 0

        if ta_cy and ni_cy and ta_cy > 0:

            roa = ni_cy/ta_cy

            if roa > 0: score+=1; signals.append("F1:ROA>0")

            else: signals.append("F1:ROA<0")

        # F2 Operating CF > 0

        if ocf_cy and ocf_cy > 0: score+=1; signals.append("F2:OCF>0")

        elif ocf_cy: signals.append("F2:OCF<0")

        # F3 Change in ROA

        if all([ta_cy,ta_py,ni_cy,ni_py]) and ta_cy>0 and ta_py>0:

            if ni_cy/ta_cy > ni_py/ta_py: score+=1; signals.append("F3:ROA^")

            else: signals.append("F3:ROAv")

        # F4 Accruals quality

        if ocf_cy and ta_cy and ni_cy and ta_cy>0:

            if ocf_cy/ta_cy > ni_cy/ta_cy: score+=1; signals.append("F4:CashEarnings>Book")

            else: signals.append("F4:Accrual-heavy")

        # F5 Leverage decreasing

        if all([ltd_cy,ltd_py,ta_cy,ta_py]) and ta_cy>0 and ta_py>0:

            if ltd_cy/ta_cy < ltd_py/ta_py: score+=1; signals.append("F5:Leveragev")

            else: signals.append("F5:Leverage^")

        # F6 Liquidity improving

        if all([ca_cy,cl_cy,ca_py,cl_py]) and cl_cy>0 and cl_py>0:

            if ca_cy/cl_cy > ca_py/cl_py: score+=1; signals.append("F6:Liquidity^")

            else: signals.append("F6:Liquidityv")

        # F7 No dilution (use shares from info vs prior)

        sh_cur  = _safe(info.get('sharesOutstanding'))

        sh_prev = _safe(info.get('sharesShortPriorMonth'))  # proxy

        if sh_cur and sh_prev and sh_cur <= sh_prev*1.02:

            score+=1; signals.append("F7:NoDilution")

        else:

            score+=1; signals.append("F7:NoDilution(assumed)")  # benefit of doubt

        # F8 Gross margin improving

        if all([rev_cy,gp_cy,rev_py,gp_py]) and rev_cy>0 and rev_py>0:

            if gp_cy/rev_cy > gp_py/rev_py: score+=1; signals.append("F8:GM^")

            else: signals.append("F8:GMv")

        # F9 Asset turnover improving

        if all([rev_cy,ta_cy,rev_py,ta_py]) and ta_cy>0 and ta_py>0:

            if rev_cy/ta_cy > rev_py/ta_py: score+=1; signals.append("F9:AssetTurn^")

            else: signals.append("F9:AssetTurnv")



        return score, signals

    except: return None, []





# --- Altman Z-Score -----------------------------------------------------------

def calculate_altman_z(stock, info, market_cap):

    """

    Z > 2.99 = safe | 1.81-2.99 = grey | < 1.81 = distress

    Uses modified Z' for non-manufacturers (replaces X4 with book/liabilities).

    """

    try:

        bs  = stock.balance_sheet

        inc = stock.financials

        if bs is None or bs.empty: return None

        cy = bs.columns[0]



        ta  = _bsr(bs,cy,'Total Assets','TotalAssets')

        ca  = _bsr(bs,cy,'Total Current Assets','CurrentAssets')

        cl  = _bsr(bs,cy,'Total Current Liabilities','CurrentLiabilities')

        re  = _bsr(bs,cy,'Retained Earnings','RetainedEarnings')

        tl  = _bsr(bs,cy,'Total Liabilities Net Minority Interest',

                   'TotalLiabilitiesNetMinorityInterest','Total Liabilities')

        bv  = _bsr(bs,cy,'Total Equity Gross Minority Interest',

                   'StockholdersEquity','Total Stockholders Equity')

        rev = _bsr(inc,inc.columns[0],'Total Revenue','Revenue') if inc is not None and not inc.empty else None

        ebit= _safe(info.get('ebit'))



        if not ta or ta <= 0 or not tl or tl <= 0: return None



        wc = (ca or 0) - (cl or 0)

        x1 = wc / ta

        x2 = (re or 0) / ta

        x3 = (ebit or 0) / ta

        x4 = (bv or market_cap or 0) / tl   # book value / total liabilities

        x5 = (rev or 0) / ta



        # Modified Z' for non-manufacturers/financials

        z = 6.56*x1 + 3.26*x2 + 6.72*x3 + 1.05*x4

        # Add revenue component if applicable

        sector = info.get('sector','')

        if sector not in ('Financial Services','Financials','Real Estate'):

            z = 1.2*x1 + 1.4*x2 + 3.3*x3 + 0.6*x4 + 1.0*x5

        return round(z, 2)

    except: return None





# --- Magic Formula (Greenblatt) -----------------------------------------------

def calculate_magic_formula(info):

    """Returns (earnings_yield, roic) -- higher both = better Magic Formula rank."""

    try:

        ebit = _safe(info.get('ebit'))

        ev   = _safe(info.get('enterpriseValue'))

        nwc  = _safe(info.get('workingCapital'))

        ppe  = _safe(info.get('netTangibleAssets'))



        ey   = (ebit / ev) if (ebit and ev and ev > 0) else None

        invested_capital = (nwc or 0) + (ppe or 0)

        roic = (ebit / invested_capital) if (ebit and invested_capital and invested_capital > 0) else None



        return ey, roic

    except: return None, None





# --- Buffett Investment Checklist (0-14 points) -------------------------------

def buffett_checklist(data, info):

    """

    10 criteria inspired by Buffett/Munger/Fisher.

    Returns (score 0-14, dict of pass/fail).

    """

    score = 0; checks = {}



    # 1. Positive earnings

    eps = _safe(data.get('eps'))

    checks['profitable'] = bool(eps and eps > 0)

    if checks['profitable']: score += 1



    # 2. ROE > 15% (moat proxy)

    roe = _safe(data.get('roe'))

    checks['high_roe'] = bool(roe and roe > 0.15)

    if checks['high_roe']: score += 2



    # 3. Conservative debt (D/E < 0.5)

    de = _safe(data.get('debt_equity'))

    checks['low_debt'] = de is not None and de < 0.5

    if checks['low_debt']: score += 2



    # 4. Revenue growth > 0

    rg = _safe(data.get('revenue_growth'))

    checks['growing'] = bool(rg and rg > 0)

    if checks['growing']: score += 1



    # 5. Positive free cash flow

    fcf = _safe(data.get('fcf'))

    checks['fcf_positive'] = bool(fcf and fcf > 0)

    if checks['fcf_positive']: score += 2



    # 6. Reasonable price (P/E < 15 OR P/B < 1.0)

    pe = _safe(data.get('pe_ratio'))

    pb = _safe(data.get('pb_ratio'))

    checks['cheap'] = bool((pe and 0 < pe < 15) or (pb and pb < 1.0))

    if checks['cheap']: score += 2



    # 7. Gross margin > 30% (pricing power)

    gm = _safe(info.get('grossMargins'))

    checks['pricing_power'] = bool(gm and gm > 0.30)

    if checks['pricing_power']: score += 1



    # 8. Owner-operator / insider ownership > 10%

    ins_pct = _safe(info.get('heldPercentInsiders'))

    checks['owner_operated'] = bool(ins_pct and ins_pct > 0.10)

    if checks['owner_operated']: score += 1



    # 9. Capital-light: operating margin > 10%

    op_mgn = _safe(info.get('operatingMargins'))

    checks['capital_light'] = bool(op_mgn and op_mgn > 0.10)

    if checks['capital_light']: score += 1



    # 10. Ignored micro/nano-cap (opportunity)

    mcap = _safe(data.get('market_cap'))

    checks['micro_cap'] = bool(mcap and mcap < 100_000_000)

    if checks['micro_cap']: score += 1



    return score, checks





# --- SEC Form 4 Insider Buying ------------------------------------------------

def fetch_insider_buying(ticker):

    """Scan SEC EDGAR for recent Form 4 open-market purchase transactions."""

    buys = []

    try:

        # EDGAR full-text search for Form 4 with this ticker

        url = (f"https://efts.sec.gov/LATEST/search-index?q=%22{quote(ticker)}%22"

               f"&forms=4&dateRange=custom&startdt=2024-07-01")

        r = requests.get(url, headers=HEADERS, timeout=HTTP_TIMEOUT)

        if r.status_code != 200: return buys

        hits = r.json().get('hits',{}).get('hits',[])

        for hit in hits[:5]:

            src  = hit.get('_source',{})

            filed= src.get('file_date','')[:10]

            buys.append({'type':'Insider Buying (Form 4)',

                         'headline': f"Form 4 filed {filed} -- check for open-market buys",

                         'date': filed})

    except: pass

    return buys





def fetch_sec_13d(ticker):

    """Check for recent SC 13D/13G activist/institutional accumulation filings."""

    signals = []

    try:

        url = (f"https://efts.sec.gov/LATEST/search-index?q=%22{quote(ticker)}%22"

               f"&forms=SC+13D,SC+13G&dateRange=custom&startdt=2023-01-01")

        r = requests.get(url, headers=HEADERS, timeout=HTTP_TIMEOUT)

        if r.status_code != 200: return signals

        hits = r.json().get('hits',{}).get('hits',[])

        for hit in hits[:3]:

            src  = hit.get('_source',{})

            form = src.get('form_type','')

            filed= src.get('file_date','')[:10]

            label= 'Activist Investor' if '13D' in form else 'Institutional Accumulation'

            signals.append({'type':label,

                            'headline':f"{form} filed {filed} -- new 5%+ holder",

                            'date': filed})

    except: pass

    return signals





# --- Hidden Value Analysis ----------------------------------------------------

def analyze_hidden_value(data, info):

    signals = []; ev_ebitda = None

    pb    = _safe(data.get('pb_ratio') or info.get('priceToBook'))

    rg    = _safe(data.get('revenue_growth'))

    price = _safe(data.get('current_price'))

    mcap  = _safe(data.get('market_cap'))

    nn    = _safe(data.get('net_net_value'))

    roe   = _safe(data.get('roe'))



    # 1. Underbook + Growing

    if pb and pb < 1.0 and rg and rg > 0.02:

        signals.append({'type':'UNDERBOOK + GROWING',

                        'detail':f"P/B={pb:.2f}x yet growing {rg*100:.1f}%/yr -- "

                                 "book value expanding while ignored by market. "

                                 "Catalyst: re-rating once growth recognized.",

                        'score_boost':10})

    elif pb and pb < 0.7:

        signals.append({'type':'DEEP BOOK DISCOUNT',

                        'detail':f"Trading {(1-pb)*100:.0f}% below book (P/B={pb:.2f}x). "

                                 "Catalyst: buyback, liquidation, or any earnings improvement.",

                        'score_boost':6})



    # 2. Net-Net

    if nn and price and price > 0 and nn > price:

        prem = (nn/price-1)*100

        signals.append({'type':'GRAHAM NET-NET',

                        'detail':f"Net liquidation value ${nn:.2f} is {prem:.0f}% ABOVE price ${price:.2f}. "

                                 "Buying $1 of net assets for less than $1. "

                                 "Catalyst: any asset sale, buyback, or liquidation.",

                        'score_boost':15})



    # 3. EV/EBITDA vs private-market comps

    ev     = _safe(info.get('enterpriseValue'))

    ebitda = _safe(info.get('ebitda'))

    if ev and ebitda and ebitda > 0:

        ev_ebitda = ev / ebitda

        if ev_ebitda < 5:

            signals.append({'type':'ULTRA-LOW EV/EBITDA',

                            'detail':f"EV/EBITDA={ev_ebitda:.1f}x vs typical 8-12x private-market comps. "

                                     "Strategic buyer could pay 2x premium and still get a bargain.",

                            'score_boost':12})

        elif ev_ebitda < 8:

            signals.append({'type':'LOW EV/EBITDA',

                            'detail':f"EV/EBITDA={ev_ebitda:.1f}x -- below typical acquisition comps.",

                            'score_boost':6})



    # 4. Asset-rich: market cap << total assets

    ta = _safe(info.get('totalAssets'))

    if ta and mcap and mcap < ta * 0.25:

        signals.append({'type':'ASSET-RICH DISCOUNT',

                        'detail':f"Market cap ${mcap/1e6:.1f}M vs assets ${ta/1e6:.1f}M "

                                 f"({mcap/ta*100:.0f}% of asset base priced in). "

                                 "Catalyst: asset sale, sale-leaseback, or spin-off.",

                        'score_boost':8})



    # 5. Cash fortress

    cash = _safe(info.get('totalCash') or info.get('cashAndCashEquivalents'))

    if cash and mcap and cash > mcap * 0.25:

        signals.append({'type':'CASH FORTRESS',

                        'detail':f"Cash ${cash/1e6:.1f}M = {cash/mcap*100:.0f}% of market cap. "

                                 "Downside protected; potential special dividend or buyback.",

                        'score_boost':5})



    # 6. High ROE at discount

    if roe and roe > 0.18 and pb and pb < 1.5:

        signals.append({'type':'QUALITY COMPOUNDER AT DISCOUNT',

                        'detail':f"ROE={roe*100:.1f}% with P/B={pb:.2f}x -- quality business "

                                 "generating strong equity returns but priced like a mediocre one. "

                                 "Catalyst: sustained earnings force market re-rating.",

                        'score_boost':8})



    # 7. Sum-of-parts / conglomerate discount

    sector   = data.get('sector','')

    industry = data.get('industry','')

    if mcap and mcap < 150_000_000:

        if any(w in (sector+industry).lower() for w in

               ['diversif','conglomerate','holding','investment','real estate','multi']):

            signals.append({'type':'SUM-OF-PARTS POTENTIAL',

                            'detail':"Holding/diversified structure trades at 20-40% conglomerate discount. "

                                     "Parts may be worth more separated. Catalyst: activist forcing break-up.",

                            'score_boost':5})

    return signals, ev_ebitda





def research_catalysts_news(ticker):

    cats = []; headlines = []

    seen = set()

    try:

        st = yf.Ticker(ticker)

        for item in (st.news or [])[:20]:

            title = item.get('title','') or item.get('headline','')

            if not title: continue

            headlines.append(title)

            tl = title.lower()

            for cat, kws in CATALYST_KEYWORDS.items():

                if cat in seen: continue

                if any(k in tl for k in kws):

                    seen.add(cat)

                    ts = item.get('providerPublishTime',0)

                    try: pub = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')

                    except: pub = 'Recent'

                    cats.append({'type':cat,'headline':title[:120],'date':pub})

    except: pass

    return cats, headlines[:5]





def calculate_catalyst_score(cats, hv_signals):

    weights = {

        'M&A / Buyout':10,'Activist Investor':10,'Regulatory Approval':8,

        'Restructuring / Spinoff':7,'Asset Monetization':7,'Share Buyback':6,

        'Major Contract Win':5,'Special Dividend':5,'Insider Buying':6,

        'Earnings Beat / Raise':4,'Debt Elimination':4,

        'Insider Buying (Form 4)':7,'Institutional Accumulation':4,'Activist Investor':10,

    }

    score = sum(weights.get(c.get('type',''),3) for c in cats)

    score += sum(s.get('score_boost',3) for s in hv_signals)

    return min(25, score)





# --- Composite Promise Score --------------------------------------------------

def calculate_promise_score(d):

    """

    0-100 composite score integrating all analytical layers.

    Weighting philosophy: margin of safety > quality > catalysts > technicals.

    """

    score = 50



    # -- Intrinsic Value (+/-40 pts) --

    mos = _safe(d.get('margin_of_safety'))

    if mos is not None:

        if   mos > 50:  score += 25

        elif mos > 30:  score += 15

        elif mos > 10:  score +=  8

        elif mos < -30: score -= 20

        elif mos <  0:  score -= 10



    g = _safe(d.get('graham_number')); p = _safe(d.get('current_price'))

    if g and p and p > 0:

        r = g/p

        if   r > 2.0: score += 15

        elif r > 1.5: score += 10

        elif r > 1.0: score +=  5

        elif r < 0.5: score -= 10



    nn = _safe(d.get('net_net_value'))

    if nn and p and p > 0:

        if   nn > p*1.5: score += 15

        elif nn > p:     score += 10

        elif nn > p*0.5: score +=  3



    # -- Quality Metrics (+/-25 pts) --

    roe = _safe(d.get('roe'))

    if roe is not None:

        if   roe > 0.20: score += 10

        elif roe > 0.12: score +=  6

        elif roe > 0.08: score +=  3

        elif roe <  0:   score -= 10



    de = _safe(d.get('debt_equity'))

    if de is not None:

        if   de < 0.3:  score += 10

        elif de < 0.5:  score +=  6

        elif de < 1.0:  score +=  2

        elif de > 2.0:  score -= 15

        elif de > 1.0:  score -=  5



    rg = _safe(d.get('revenue_growth'))

    if rg is not None:

        if   rg > 0.15: score += 10

        elif rg > 0.05: score +=  5

        elif rg > 0:    score +=  2

        elif rg < -0.10:score -= 10



    # -- Piotroski F-Score (+8 max) --

    pf = _safe(d.get('piotroski_score'))

    if pf is not None:

        if   pf >= 7: score += 8

        elif pf >= 5: score += 4

        elif pf <= 2: score -= 6



    # -- Altman Z-Score (+/-8) --

    az = _safe(d.get('altman_z'))

    if az is not None:

        if   az > 2.99: score += 5

        elif az > 1.81: score += 2

        else:           score -= 8    # distress zone



    # -- Buffett Checklist (+6 max) --

    bc = _safe(d.get('buffett_checklist'))

    if bc is not None:

        score += min(6, int(bc * 0.43))   # 0-14 -> 0-6



    # -- Market Cap (hidden-gem bonus +5) --

    mcap = _safe(d.get('market_cap'))

    if mcap:

        if   mcap <  10_000_000: score += 5

        elif mcap <  50_000_000: score += 3



    # -- 52-Week Position: near low = better entry (+4) --

    w52 = _safe(d.get('week52_position'))

    if w52 is not None:

        if   w52 < 0.15: score += 4   # within 15% of 52w low

        elif w52 < 0.30: score += 2



    # -- Short Interest: high = squeeze potential (+3) --

    si = _safe(d.get('short_interest_pct'))

    if si and si > 0.15: score += 3



    # -- Insider Ownership: high = alignment (+4) --

    ins = _safe(d.get('insider_pct'))

    if ins:

        if   ins > 0.30: score += 4

        elif ins > 0.15: score += 2



    # -- Catalyst Bonus (+12 max) --

    cs = _safe(d.get('catalyst_score')) or 0

    score += min(12, cs * 0.48)



    return max(0, min(100, round(score, 1)))





def assign_grade(score):

    if   score >= 75: return 'A'

    elif score >= 60: return 'B'

    elif score >= 45: return 'C'

    elif score >= 30: return 'D'

    else:             return 'F'



def _fmt_mcap(v):

    if v is None: return 'N/A'

    if v>=1e9: return f"${v/1e9:.2f}B"

    if v>=1e6: return f"${v/1e6:.1f}M"

    return f"${v:,.0f}"

def _fmt_p(v):

    if v is None: return 'N/A'

    return f"${v:.4f}" if v<1 else f"${v:.2f}"

def _fmt_pct(v):

    return f"{v*100:.1f}%" if v is not None else 'N/A'





# --- Main Fetch + Analysis ----------------------------------------------------

def fetch_and_analyze(ticker, exchange, notes):

    try:

        stock = yf.Ticker(ticker)

        info  = stock.info or {}

        if len(info) < 5:
            if _HAVE_QF2:
                _qf2_stub = _qf2_get(ticker)
            else:
                _qf2_stub = None
            if _qf2_stub is None:
                return None, "No data from yfinance or QF2"
            # yfinance has no data but QF2 has fundamentals -- we still need price.
            # Fall through; price will be fetched below; QF2 data will supplement later.
            info = {}  # keep empty so price check can bail if truly dead



        name  = info.get('longName') or info.get('shortName') or ticker

        price = _safe(info.get('currentPrice') or info.get('regularMarketPrice')

                      or info.get('previousClose'))

        mcap  = _safe(info.get('marketCap'))



        if not price or price < 0.10: return None, f"Price unavailable: {price}"

        if mcap and mcap > 2_000_000_000: return None, f"Too large (>): {_fmt_mcap(mcap)}"



        eps  = _safe(info.get('trailingEps') or info.get('forwardEps'))

        bvps = _safe(info.get('bookValue'))

        roe  = _safe(info.get('returnOnEquity'))

        pb   = _safe(info.get('priceToBook'))

        pe   = _safe(info.get('trailingPE'))

        de_r = _safe(info.get('debtToEquity'))

        de   = (de_r/100.0) if de_r is not None else None

        rg   = _safe(info.get('revenueGrowth'))

        shr  = _safe(info.get('sharesOutstanding') or info.get('impliedSharesOutstanding'))

        ins  = _safe(info.get('heldPercentInsiders'))

        si   = _safe(info.get('shortPercentOfFloat'))

        av   = _safe(info.get('averageVolume') or info.get('averageDailyVolume10Day'))



        # 52-week position (0=at low, 1=at high)

        hi52 = _safe(info.get('fiftyTwoWeekHigh'))

        lo52 = _safe(info.get('fiftyTwoWeekLow'))

        w52  = ((price-lo52)/(hi52-lo52)) if (hi52 and lo52 and hi52>lo52) else None



        # Balance sheet

        ca = tl = None

        try:

            bs = stock.balance_sheet

            if bs is not None and not bs.empty:

                cy = bs.columns[0]

                ca = _bsr(bs,cy,'Total Current Assets','CurrentAssets')

                tl = _bsr(bs,cy,'Total Liabilities Net Minority Interest',

                          'TotalLiabilitiesNetMinorityInterest','Total Liabilities')

        except: pass



        # FCF

        fcf = None

        try:

            cf = stock.cashflow

            if cf is not None and not cf.empty:

                cy2 = cf.columns[0]

                ocf  = _bsr(cf,cy2,'Operating Cash Flow',

                            'Total Cash From Operating Activities')

                capx = _bsr(cf,cy2,'Capital Expenditure','Capital Expenditures',

                            'Purchases Of Property Plant And Equipment')

                if ocf is not None:

                    fcf = ocf + (capx or 0)

        except: pass



        # Revenue growth from financials

        try:

            fin = stock.financials

            if fin is not None and not fin.empty and len(fin.columns)>=2:

                for lbl in ('Total Revenue','Revenue'):

                    if lbl in fin.index:

                        rc = _safe(fin.loc[lbl, fin.columns[0]])

                        rp = _safe(fin.loc[lbl, fin.columns[1]])

                        if rc and rp and rp != 0:

                            rg = (rc-rp)/abs(rp); break

        except: pass



        # Intrinsic values

        graham    = calc_graham(eps, bvps)

        dcf_share = None

        if fcf and fcf>0 and shr and shr>0:

            dt = calc_dcf(fcf, rg if rg else 0.03)

            if dt: dcf_share = dt/shr

        elif eps and eps>0 and shr and shr>0:

            dt = calc_dcf(eps*shr, rg if rg else 0.03)

            if dt: dcf_share = dt/shr



        nn = calc_net_net(ca, tl, shr)



        ivs = [v for v in [graham, dcf_share, nn] if v and v>0]

        mos = None

        if ivs:

            avg_iv = sum(ivs)/len(ivs)

            mos = (avg_iv - price) / avg_iv * 100



        # Chinese reverse-merger flag

        if any(w in name.lower() for w in ('china','sino','beijing','shanghai')):

            if mcap and mcap < 100_000_000:

                notes += " [WARNING: POSSIBLE CHINESE REVERSE MERGER]"



        data = dict(

            ticker=ticker, company_name=name, exchange=exchange,

            market_cap=mcap, current_price=price,

            graham_number=graham, dcf_value=dcf_share,

            net_net_value=nn, margin_of_safety=mos,

            roe=roe, debt_equity=de, revenue_growth=rg,

            eps=eps, bvps=bvps, fcf=fcf,

            current_assets=ca, total_liabilities=tl, shares=shr,

            sector=info.get('sector','Unknown'),

            industry=info.get('industry','Unknown'),

            pe_ratio=pe, pb_ratio=pb,

            current_ratio=_safe(info.get('currentRatio')),

            dividend_yield=_safe(info.get('dividendYield')),

            country=info.get('country','Unknown'),

            description=info.get('longBusinessSummary',''),

            notes=notes,

            insider_pct=ins, short_interest_pct=si, week52_position=w52,

            # v4 additional metrics

            gross_margin=_safe(info.get('grossMargins')),

            beta=_safe(info.get('beta')),

            ps_ratio=_safe(info.get('priceToSalesTrailingTwelveMonths')),

            operating_margin=_safe(info.get('operatingMargins')),

            ev_revenue=(_safe(info.get('enterpriseValue'))/_safe(info.get('totalRevenue'))

                        if (_safe(info.get('enterpriseValue')) and _safe(info.get('totalRevenue')) and _safe(info.get('totalRevenue'))>0) else None),

            avg_volume=av,

        )


        # -- QF2 FMP SUPPLEMENT: fill gaps for sparse/dead yfinance tickers ----
        if _HAVE_QF2:
            _qf2_data = (_qf2_stub if ('_qf2_stub' in dir() and _qf2_stub is not None)
                         else _qf2_get(ticker))
            if _qf2_data:
                def _qfill(key, qkey=None):
                    qkey = qkey or key
                    if data.get(key) is None and _qf2_data.get(qkey) is not None:
                        data[key] = _qf2_data[qkey]
                _qfill('pe_ratio');      _qfill('pb_ratio')
                _qfill('roe');           _qfill('gross_margin')
                _qfill('operating_margin'); _qfill('current_ratio')
                _qfill('debt_equity');   _qfill('eps')
                _qfill('bvps');          _qfill('fcf')
                _qfill('dividend_yield'); _qfill('revenue_growth')
                if data.get('market_cap') is None and _qf2_data.get('shares') and price:
                    data['market_cap'] = _qf2_data['shares'] * price
        # -- end QF2 supplement -----------------------------------------------



        # -- SCORING LAYERS -----------------------------------------------

        print(f"    [piotroski] ...", end=' ', flush=True)

        pf_score, pf_signals = calculate_piotroski(stock, info)

        print(f"{pf_score}", flush=True)



        print(f"    [altman-z]  ...", end=' ', flush=True)

        az = calculate_altman_z(stock, info, mcap)

        print(f"{az}", flush=True)



        ey, roic = calculate_magic_formula(info)

        bc_score, bc_checks = buffett_checklist(data, info)



        data.update(piotroski_score=pf_score, altman_z=az,

                    magic_formula_ey=ey, buffett_checklist=bc_score,

                    piotroski_signals=pf_signals, buffett_checks=bc_checks)



        # -- DEEP RESEARCH ------------------------------------------------

        print(f"    [news]      ...", end=' ', flush=True)

        cats_news, headlines = research_catalysts_news(ticker)

        print(f"{len(cats_news)} signals", flush=True)



        cats_sec = []

        if exchange in ('NASDAQ','OTC','AMEX','NYSE','NYSE-AMEX'):

            print(f"    [SEC 13D]   ...", end=' ', flush=True)

            cats_sec = fetch_sec_13d(ticker)

            print(f"{len(cats_sec)}", flush=True)



        hv_signals, ev_ebitda = analyze_hidden_value(data, info)



        all_cats   = cats_news + cats_sec

        cat_score  = calculate_catalyst_score(all_cats, hv_signals)



        data.update(catalysts=all_cats, hidden_value_signals=hv_signals,

                    catalyst_score=cat_score, ev_ebitda=ev_ebitda,

                    recent_headlines=headlines)



        data['promise_score'] = calculate_promise_score(data)

        data['grade']         = assign_grade(data['promise_score'])

        return data, None



    except Exception as e:

        return None, f"Exception: {e}"





# --- Markdown Report ---------------------------------------------------------

def generate_markdown_report(data):

    today = date.today().strftime('%Y-%m-%d')

    grade = data.get('grade','?')

    score = data.get('promise_score',0) or 0



    pf   = data.get('piotroski_score')

    az   = data.get('altman_z')

    bc   = data.get('buffett_checklist',0) or 0

    ey   = data.get('magic_formula_ey')

    cs   = data.get('catalyst_score',0) or 0

    hv   = data.get('hidden_value_signals',[])

    cats = data.get('catalysts',[])

    hl   = data.get('recent_headlines',[])

    sigs = data.get('piotroski_signals',[])

    chks = data.get('buffett_checks',{})

    ins  = data.get('insider_pct')

    si   = data.get('short_interest_pct')

    w52  = data.get('week52_position')

    ev_e = data.get('ev_ebitda')



    grade_bar = {'A':'######## A','B':'######?? B','C':'####???? C',

                 'D':'##?????? D','F':'#??????? F'}.get(grade,'? ')



    def pf_label(s):

        if s is None: return 'N/A'

        if s>=7: return f"{s}/9 * STRONG"

        if s>=5: return f"{s}/9 * DECENT"

        if s>=3: return f"{s}/9 * WEAK"

        return f"{s}/9 X POOR"



    def az_label(z):

        if z is None: return 'N/A'

        if z>2.99: return f"{z:.2f} * SAFE ZONE"

        if z>1.81: return f"{z:.2f} * GREY ZONE"

        return f"{z:.2f} X DISTRESS"



    def mos_str(v):

        return f"{v:.1f}%" if v is not None else 'N/A'



    # Intrinsic value table rows

    def iv_row(label, val):

        if not val or not data.get('current_price'):

            return f"| {label} | N/A | -- |"

        p   = data['current_price']

        pct = (val/p - 1)*100

        dir = "ABOVE" if val>p else "below"

        return f"| {label} | {_fmt_p(val)} | {abs(pct):.1f}% {dir} price |"



    # Buffett checklist table

    check_rows = ""

    labels = {

        'profitable':'Positive Earnings (EPS > 0)',

        'high_roe':'ROE > 15% (durable moat)',

        'low_debt':'Debt/Equity < 0.5',

        'growing':'Revenue Growth > 0',

        'fcf_positive':'Positive Free Cash Flow',

        'cheap':'Reasonable Price (P/E<15 or P/B<1)',

        'pricing_power':'Gross Margin > 30% (pricing power)',

        'owner_operated':'Insider Ownership > 10%',

        'capital_light':'Operating Margin > 10%',

        'micro_cap':'Micro/Nano Cap < $100M (hidden gem)',

    }

    for k,lbl in labels.items():

        v = chks.get(k,False)

        check_rows += f"| {'PASS' if v else 'FAIL'} | {lbl} |\n"



    # Catalysts section

    cats_md = ""

    if cats:

        for c in cats: cats_md += f"- **{c['type']}** ({c['date']}): {c['headline']}\n"

    else: cats_md = "No specific catalysts detected in recent news / SEC filings.\n"



    # Hidden value

    hv_md = ""

    for s in hv:

        hv_md += f"\n**[{s['type']}]**\n{s['detail']}\n"

    if not hv_md: hv_md = "No extraordinary hidden value signals.\n"



    # Headlines

    hl_md = "\n".join(f"- {h}" for h in hl) if hl else "No recent news."



    # Piotroski detail

    pf_md = " | ".join(sigs) if sigs else "Insufficient 2-year data."



    verdict = {

        'A':"STRONG BUY -- Multiple deep-value and catalyst signals. Immediate due diligence priority.",

        'B':"WATCH LIST -- Compelling setup. Monitor for better entry or catalyst confirmation.",

        'C':"NEUTRAL -- Some value attributes; significant uncertainties remain.",

        'D':"AVOID -- Weak fundamentals. Special situation only.",

        'F':"PASS -- Does not meet value investing criteria.",

    }.get(grade,'')



    report = f"""# {data['company_name']} ({data['ticker']})

### {BRAND} -- Deep-Value Micro-Cap Analysis -- {today}



**Grade: {grade_bar}** | **Promise Score: {score:.0f}/100** | **Catalyst Score: {cs:.0f}/25**



---



## Company Snapshot



| Field | Value |

|-------|-------|

| Ticker | `{data['ticker']}` |

| Exchange | {data['exchange']} |

| Sector / Industry | {data.get('sector','N/A')} / {data.get('industry','N/A')} |

| Country | {data.get('country','N/A')} |

| Market Cap | {_fmt_mcap(data.get('market_cap'))} |

| Current Price | {_fmt_p(data.get('current_price'))} |

| 52-Week Position | {'Bottom {:.0f}%'.format(w52*100) if w52 is not None else 'N/A'} |

| Insider Ownership | {_fmt_pct(ins) if ins else 'N/A'} |

| Short Interest | {_fmt_pct(si) if si else 'N/A'} |



> {data.get('description','')[:400]}{'...' if len(data.get('description',''))>400 else ''}



---



## Intrinsic Value Triangulation



| Method | Estimated Value | vs Market |

|--------|----------------|-----------|

{iv_row('Graham Number  sqrt(22.5 x EPS x BVPS)', data.get('graham_number'))}

{iv_row('DCF  (8% discount, 12x terminal, 10yr)', data.get('dcf_value'))}

{iv_row('Net-Net  (Current Assets - Total Liabilities) / Shares', data.get('net_net_value'))}



**Composite Margin of Safety: {mos_str(data.get('margin_of_safety'))}**

**EV/EBITDA: {f"{ev_e:.1f}x" if ev_e else "N/A"}** (private-market comps typically 8-12x)



> Buffett's rule: never buy without at least 25-30% margin of safety.



---



## Quality Scoring Layer



### Piotroski F-Score: {pf_label(pf)}

*9-point financial health checklist (Piotroski 2000)*

{pf_md}



### Altman Z-Score: {az_label(az)}

*Z > 2.99 = safe zone | 1.81-2.99 = grey | < 1.81 = distress / bankruptcy risk*



### Magic Formula (Greenblatt)

- Earnings Yield: {f"{ey*100:.1f}%" if ey else "N/A"} (EBIT/EV -- higher is better)

- ROIC: {f"{data.get('roic',0)*100:.1f}%" if data.get('roic') else "N/A"}



### Buffett Investment Checklist: {bc:.0f}/14 points



| Pass/Fail | Criterion |

|-----------|-----------|

{check_rows}



---



## Standard Financial Metrics



| Metric | Value | Signal |

|--------|-------|--------|

| EPS (TTM) | {_fmt_p(data.get('eps'))} | {'PASS' if data.get('eps') and data['eps']>0 else 'FAIL'} |

| Book Value/Share | {_fmt_p(data.get('bvps'))} | -- |

| P/E Ratio | {f"{data['pe_ratio']:.1f}x" if data.get('pe_ratio') else 'N/A'} | {'Cheap' if data.get('pe_ratio') and 0<data['pe_ratio']<15 else 'Expensive' if data.get('pe_ratio') and data['pe_ratio']>25 else '--'} |

| P/B Ratio | {f"{data['pb_ratio']:.2f}x" if data.get('pb_ratio') else 'N/A'} | {'Below Book' if data.get('pb_ratio') and data['pb_ratio']<1 else '--'} |

| ROE | {_fmt_pct(data.get('roe'))} | {'Strong' if data.get('roe') and data['roe']>0.15 else 'Weak' if data.get('roe') and data['roe']<0.08 else '--'} |

| Debt/Equity | {f"{data['debt_equity']:.2f}" if data.get('debt_equity') is not None else 'N/A'} | {'Conservative' if data.get('debt_equity') is not None and data['debt_equity']<0.5 else 'Leveraged' if data.get('debt_equity') and data['debt_equity']>1 else '--'} |

| Revenue Growth | {_fmt_pct(data.get('revenue_growth'))} | {'Growing' if data.get('revenue_growth') and data['revenue_growth']>0.05 else '--'} |

| Free Cash Flow | {_fmt_mcap(data.get('fcf'))} | {'FCF+' if data.get('fcf') and data['fcf']>0 else 'Cash Burn' if data.get('fcf') and data['fcf']<0 else '--'} |

| Current Ratio | {f"{data['current_ratio']:.2f}" if data.get('current_ratio') else 'N/A'} | {'Liquid' if data.get('current_ratio') and data['current_ratio']>2 else '--'} |



---



## Deep Research -- Catalysts & Hidden Value



### Catalysts Detected

{cats_md}



### Hidden Value Signals

{hv_md}



### Recent Headlines

{hl_md}



---



## Notes & Risk Flags



{data.get('notes','No special flags.')}



---



## Final Verdict



**Score: {score:.0f}/100 -- Grade: {grade}**



{verdict}



---

*{BRAND} | {today} | NOT financial advice -- conduct independent due diligence.*

"""

    return report





def save_report(ticker, text):

    today = date.today().strftime('%Y-%m-%d')

    os.makedirs(REPORTS_DIR, exist_ok=True)

    fn   = f"{today}_{ticker.replace('.','_').replace('/','_')}.md"

    path = os.path.join(REPORTS_DIR, fn)

    with open(path,'w',encoding='utf-8') as f: f.write(text)

    return path





# --- HTML Dashboard -----------------------------------------------------------

def generate_html_index():

    conn = sqlite3.connect(DB_PATH)

    c = conn.cursor()

    c.execute('''SELECT ticker,company_name,exchange,market_cap,current_price,

                        graham_number,dcf_value,net_net_value,margin_of_safety,

                        promise_score,ev_ebitda,piotroski_score,altman_z,

                        buffett_checklist,catalyst_score,catalysts,

                        hidden_value_notes,insider_pct,short_interest_pct,

                        week52_position,analysis_date,grade,report_path

                 FROM analyzed_stocks ORDER BY promise_score DESC''')

    rows = c.fetchall(); conn.close()



    def hp(v): return f'${v:.2f}' if v else '<span class="na">--</span>'

    def hpct(v,mul=1):

        if v is None: return '<span class="na">--</span>'

        cls = 'pos' if v*mul>0 else 'neg'

        return f'<span class="{cls}">{v*mul:.1f}%</span>'

    def hev(v):

        if v is None: return '<span class="na">--</span>'

        cls = 'pos' if v<8 else ''

        return f'<span class="{cls}">{v:.1f}x</span>'

    def hpf(v):

        if v is None: return '<span class="na">--</span>'

        if v>=7: return f'<span class="pos">{v:.0f}/9</span>'

        if v>=5: return f'<span style="color:#ffd740">{v:.0f}/9</span>'

        return f'<span class="neg">{v:.0f}/9</span>'

    def haz(v):

        if v is None: return '<span class="na">--</span>'

        if v>2.99: return f'<span class="pos">{v:.1f}</span>'

        if v>1.81: return f'<span style="color:#ffd740">{v:.1f}</span>'

        return f'<span class="neg">{v:.1f}</span>'

    def hw52(v):

        if v is None: return '<span class="na">--</span>'

        pct = int(v*100)

        cls = 'pos' if pct<20 else ('neg' if pct>80 else '')

        return f'<span class="{cls}">{pct}%</span>'



    def parse_j(s):

        if not s: return []

        try: return json.loads(s)

        except: return []



    def cat_badges(cj, hvj):

        out = ''

        for x in parse_j(cj)[:3]:

            t  = x.get('type','')[:20]

            hl = x.get('headline','')[:80]

            out += '<span class="cbadge cat" title="' + hl + '">' + t + '</span>'

        for x in parse_j(hvj)[:2]:

            t  = x.get('type','')[:18]

            dv = x.get('detail','')[:80]

            out += '<span class="cbadge hv" title="' + dv + '">' + t + '</span>'

        return out or '<span class="na">--</span>'



    gc = {'A':'ga','B':'gb','C':'gc','D':'gd','F':'gf'}

    tbody = ''

    for i,row in enumerate(rows,1):

        (tk,nm,ex,mc,pr,gr,dc,nn,mos,sc,ev,pf,az,bc,cs,cj,hvj,

         ins,si,w52,dt,grade,rpath) = row

        g = gc.get(grade,'gf'); s = sc or 0; cat_s = cs or 0



        rlink = '<span class="na">--</span>'

        if rpath and os.path.exists(rpath):

            uri   = 'file:///' + rpath.replace('\\','/')

            rlink = f'<a href="{uri}" class="rlink" target="_blank">&#128196;</a>'



        tbody += f'''

  <tr class="{g}">

    <td class="rank">#{i}</td>

    <td class="tk">{tk}</td>

    <td class="cn" title="{nm or ''}">{(nm or '--')[:24]}</td>

    <td><span class="badge">{ex or '?'}</span></td>

    <td>{hp(pr)}</td>

    <td>{hp(gr)}</td>

    <td>{hp(dc)}</td>

    <td>{hp(nn)}</td>

    <td>{hpct(mos,1)}</td>

    <td>{hev(ev)}</td>

    <td>{hpf(pf)}</td>

    <td>{haz(az)}</td>

    <td>{"--" if bc is None else f"{bc:.0f}/14"}</td>

    <td class="catcell">{cat_badges(cj,hvj)}</td>

    <td>

      <div class="bar"><div class="fill" style="width:{s}%"></div>

      <span class="bval">{s:.0f}</span></div>

    </td>

    <td>

      <div class="bar cbar"><div class="cfill" style="width:{min(cat_s*4,100)}%"></div>

      <span class="bval">{cat_s:.0f}</span></div>

    </td>

    <td><span class="gl {g}">{grade or '?'}</span></td>

    <td>{rlink}</td>

    <td class="dt">{dt or '--'}</td>

  </tr>'''



    now   = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    total = len(rows)

    cnt   = lambda g: sum(1 for r in rows if r[21]==g)



    html = f'''<!DOCTYPE html>

<html lang="en"><head>

<meta charset="UTF-8"><meta http-equiv="refresh" content="60">

<title>{BRAND} -- Deep-Value Screener</title>

<style>

:root{{--bg:#080f1c;--bg2:#0f1c2e;--bg3:#152236;--bd:#1c3050;

      --tx:#d0e4f4;--mu:#4a6a8a;--bl:#5aabf0;--gr:#43a047;

      --ye:#ffd740;--or:#fb8c00;--re:#e53935;--te:#26c6da;--pu:#ce93d8;}}

*{{margin:0;padding:0;box-sizing:border-box}}

body{{background:var(--bg);color:var(--tx);font-family:"Segoe UI",system-ui,sans-serif;font-size:12px}}

/* Header */

.hdr{{background:linear-gradient(135deg,var(--bg2) 0%,#0a1520 100%);

      border-bottom:2px solid var(--bd);padding:18px 28px;

      display:flex;justify-content:space-between;align-items:center}}

.hdr h1{{font-size:22px;font-weight:700;color:var(--bl);letter-spacing:-.3px}}

.hdr .sub{{color:var(--mu);font-size:11px;margin-top:3px}}

.brand{{font-size:11px;color:var(--te);margin-top:2px;font-weight:600}}

.upd{{color:var(--mu);font-size:10px;text-align:right;line-height:1.8}}

/* Stats bar */

.stats{{background:var(--bg2);border-bottom:1px solid var(--bd);

        padding:12px 28px;display:flex;gap:24px;flex-wrap:wrap;align-items:center}}

.st{{display:flex;flex-direction:column}}

.stl{{font-size:9px;color:var(--mu);text-transform:uppercase;letter-spacing:1px}}

.stv{{font-size:19px;font-weight:700;color:var(--bl);margin-top:1px}}

/* Quote */

.quote{{background:var(--bg3);border-left:3px solid var(--bl);

        padding:10px 20px;margin:16px 28px 12px;border-radius:0 6px 6px 0;

        color:var(--mu);font-style:italic;font-size:12px}}

/* Table */

.wrap{{padding:0 28px 40px;overflow-x:auto}}

.leg{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:10px;

      font-size:10px;color:var(--mu);padding:4px 0}}

.ld{{display:flex;align-items:center;gap:5px}}

.dot{{width:8px;height:8px;border-radius:50%}}

table{{width:100%;border-collapse:collapse;min-width:1600px}}

thead{{position:sticky;top:0;z-index:5}}

th{{background:var(--bg2);color:var(--mu);font-size:9px;font-weight:700;

    text-transform:uppercase;letter-spacing:.4px;padding:10px 7px;

    text-align:left;border-bottom:2px solid var(--bd);white-space:nowrap}}

tr{{border-bottom:1px solid #0b1828;transition:background .1s}}

tr:hover{{background:rgba(90,171,240,.05)!important}}

td{{padding:8px 7px;vertical-align:middle}}

.ga{{background:rgba(67,160,71,.08);border-left:3px solid #2e7d32}}

.gb{{background:rgba(255,215,64,.07);border-left:3px solid #f9a825}}

.gc{{background:rgba(251,140,0,.07);border-left:3px solid #e65100}}

.gd{{background:rgba(229,57,53,.07);border-left:3px solid #b71c1c}}

.gf{{background:rgba(100,40,40,.07);border-left:3px solid #6a0000}}

.rank{{color:var(--mu);font-weight:700;font-size:10px}}

.tk{{font-weight:700;color:var(--bl);font-family:Consolas,monospace;font-size:12px}}

.cn{{max-width:130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#8aaccc}}

.badge{{background:#122030;color:#6a9cbe;padding:2px 5px;border-radius:3px;

        font-size:9px;font-weight:700}}

.pos{{color:var(--gr);font-weight:600}}

.neg{{color:var(--re);font-weight:600}}

.na{{color:#2a4060}}

.dt{{color:var(--mu);font-size:9px}}

/* Catalyst badges */

.catcell{{min-width:180px}}

.cbadge{{display:inline-block;padding:2px 4px;border-radius:3px;font-size:8px;

         font-weight:700;margin:1px;line-height:1.5;cursor:help;white-space:nowrap}}

.cbadge.cat{{background:rgba(38,198,218,.12);color:var(--te);border:1px solid rgba(38,198,218,.25)}}

.cbadge.hv{{background:rgba(206,147,216,.12);color:var(--pu);border:1px solid rgba(206,147,216,.25)}}

/* Score bars */

.bar{{position:relative;background:#112030;border-radius:3px;height:18px;width:88px;overflow:hidden}}

.fill{{position:absolute;left:0;top:0;height:100%;

       background:linear-gradient(90deg,#183060,var(--bl));border-radius:3px}}

.cbar{{width:56px}}

.cfill{{position:absolute;left:0;top:0;height:100%;

        background:linear-gradient(90deg,#28154a,var(--pu));border-radius:3px}}

.bval{{position:absolute;width:100%;text-align:center;top:50%;transform:translateY(-50%);

       font-size:9px;font-weight:700;color:#fff;text-shadow:0 1px 2px rgba(0,0,0,.8);z-index:1}}

/* Grade circles */

.gl{{display:inline-flex;align-items:center;justify-content:center;

     width:22px;height:22px;border-radius:50%;font-weight:700;font-size:11px}}

.gl.ga{{background:rgba(67,160,71,.2);color:var(--gr);border:1px solid #2e7d32}}

.gl.gb{{background:rgba(255,215,64,.2);color:var(--ye);border:1px solid #f9a825}}

.gl.gc{{background:rgba(251,140,0,.2);color:var(--or);border:1px solid #e65100}}

.gl.gd{{background:rgba(229,57,53,.2);color:var(--re);border:1px solid #b71c1c}}

.gl.gf{{background:rgba(100,40,40,.2);color:#cc2222;border:1px solid #6a0000}}

/* Report link */

.rlink{{color:var(--te);text-decoration:none;font-size:13px;opacity:.8}}

.rlink:hover{{opacity:1}}

.footer{{text-align:center;padding:20px;color:var(--mu);font-size:10px;

         border-top:1px solid var(--bd)}}

</style></head>

<body>

<div class="hdr">

  <div>

    <h1>Deep-Value Micro-Cap Screener</h1>

    <div class="brand">{BRAND}</div>

    <div class="sub">Piotroski . Altman Z . Magic Formula . Buffett Checklist . Catalyst Detection . Hidden Value</div>

  </div>

  <div class="upd">Updated: {now}<br><small>Auto-refreshes 60s</small></div>

</div>



<div class="stats">

  <div class="st"><div class="stl">Analyzed</div><div class="stv">{total}</div></div>

  <div class="st"><div class="stl">Grade A</div><div class="stv" style="color:var(--gr)">{cnt('A')}</div></div>

  <div class="st"><div class="stl">Grade B</div><div class="stv" style="color:var(--ye)">{cnt('B')}</div></div>

  <div class="st"><div class="stl">Grade C</div><div class="stv" style="color:var(--or)">{cnt('C')}</div></div>

  <div class="st"><div class="stl">D / F</div><div class="stv" style="color:var(--re)">{cnt('D')+cnt('F')}</div></div>

</div>



<div class="quote">

  "It is far better to buy a wonderful company at a fair price than a fair company at a wonderful price." &#8212; Warren Buffett

</div>



<div class="wrap">

  <div class="leg">

    <span class="ld"><span class="dot" style="background:#2e7d32"></span>A -- Buy</span>

    <span class="ld"><span class="dot" style="background:#f9a825"></span>B -- Watch</span>

    <span class="ld"><span class="dot" style="background:#e65100"></span>C -- Neutral</span>

    <span class="ld"><span class="dot" style="background:#b71c1c"></span>D/F -- Avoid</span>

    <span style="color:var(--te)">&#9632;</span> Catalyst&nbsp;

    <span style="color:var(--pu)">&#9632;</span> Hidden Value&nbsp;

    <span style="color:var(--mu)">Piotroski: 7-9=strong | Altman: green=safe red=distress | W52: % from 52wk low | hover badges for detail</span>

  </div>

  <table>

    <thead><tr>

      <th>#</th><th>Ticker</th><th>Company</th><th>Exch</th>

      <th>Price</th><th>Graham</th><th>DCF</th><th>Net-Net</th>

      <th>MoS%</th><th>EV/EBITDA</th><th>Piotroski</th><th>Altman Z</th>

      <th>Checklist</th><th>Catalysts &amp; HV</th>

      <th>Score</th><th>Cat.</th><th>Gr.</th><th>Rep.</th><th>Date</th>

    </tr></thead>

    <tbody>{tbody}</tbody>

  </table>

</div>



<div class="footer">

  <p><strong>{BRAND}</strong> -- Systematic deep-value analysis of micro/nano-cap stocks on obscure exchanges</p>

  <p style="margin-top:5px">NOT financial advice. Always conduct independent due diligence before investing.</p>

</div>

</body></html>'''



    with open(HTML_PATH,'w',encoding='utf-8') as f: f.write(html)

    return HTML_PATH





# --- Main ---------------------------------------------------------------------

def main():

    print("=" * 66)

    print(f"  {BRAND}")

    print(f"  Deep-Value Micro-Cap Screener v3 -- {date.today().strftime('%A %d %B %Y')}")

    print("=" * 66)



    create_database()

    os.makedirs(REPORTS_DIR, exist_ok=True)



    analyzed  = get_analyzed_tickers()

    remaining = [(t,e,n) for t,e,n in CANDIDATE_STOCKS if t not in analyzed]



    print(f"\n  DB records    : {len(analyzed)}")

    print(f"  Queue left    : {len(remaining)}")



    if not remaining:

        print("\n  All candidates done! Add more tickers.")

        if _HAVE_GENERATORS:

            try: _gen_html()

            except: generate_html_index()

        else:

            generate_html_index()

        return



    batch = remaining[:BATCH_SIZE]

    print(f"\n  Today's batch ({len(batch)}):")

    for t,e,_ in batch: print(f"    {t:12s} [{e}]")



    results, failed = [], []

    for ticker, exchange, notes in batch:

        print(f"\n{'-'*60}")

        print(f"  {ticker} ({exchange})")

        # -- Skip Registry gate ------------------------------------------
        _skip, _sreason = should_skip(ticker)
        if _skip:
            print(f"  [SKIP-REG] {_sreason}")
            failed.append((ticker, _sreason))
            continue

        data, err = fetch_and_analyze(ticker, exchange, notes)

        time.sleep(1.5)  # Rate limiting: avoid Yahoo Finance 429 throttle

        if data:
            # -- Staleness gate ------------------------------------------
            current_px = data.get('current_price')
            stale, stale_reason = should_skip_stale(ticker, current_px)
            if stale:
                print(f"  [STALE] {stale_reason} -- skipping DB write")
                continue


            rpt  = generate_markdown_report(data)

            path = save_report(ticker, rpt)

            insert_into_db(data, path)

            results.append(data)

            record_success(ticker)  # reset failure count

            pf_s = f"F={data.get('piotroski_score','?')}" if data.get('piotroski_score') is not None else "F=?"

            az_s = f"Z={data.get('altman_z','?'):.1f}" if data.get('altman_z') is not None else "Z=?"

            mos_s= f"MoS={data['margin_of_safety']:.1f}%" if data.get('margin_of_safety') else "MoS=N/A"

            print(f"  Score={data['promise_score']:.0f} Grade={data['grade']} "

                  f"{pf_s} {az_s} {mos_s} "

                  f"Cats={len(data.get('catalysts',[]))} HV={len(data.get('hidden_value_signals',[]))}")

        else:

            failed.append((ticker,err)); print(f"  SKIP: {err}")

            record_failure(ticker, err or 'no data')  # track toward auto-skip



    print(f"\n{'='*66}")

    print(f"  Done -- Analyzed:{len(results)}  Failed:{len(failed)}")

    if _HAVE_SKIP_REG:
        from skip_registry import get_stats as _sreg_stats
        _ss = _sreg_stats()
        print(f"  Skip Registry  : {_ss['dead_tickers']} dead | {_ss['warned_tickers']} warned | {_ss['whitelisted']} whitelisted")

    if results:

        top = sorted(results, key=lambda x: x.get('promise_score',0), reverse=True)

        print("\n  Top picks today:")

        for i,r in enumerate(top[:5],1):

            print(f"    {i}. {r['ticker']:10s} {r['grade']}  {r['promise_score']:.0f}pts  "

                  f"F={r.get('piotroski_score','?')} Z={r.get('altman_z','?')}  "

                  f"{r['company_name'][:40]}")



    # Generate dashboard

    if _HAVE_GENERATORS:

        try:

            html = _gen_html()

            print(f"\n  Dashboard: {html}")

        except Exception as e:

            print(f"  [WARN] Dashboard gen failed: {e}")

            html = generate_html_index()

    else:

        html = generate_html_index()

    # Generate DOCX reports for this batch

    if _HAVE_GENERATORS:

        for rdata in results:

            try:

                dp = _gen_docx(rdata)

                if dp: print(f"  DOCX: {os.path.basename(dp)}")

            except Exception as e:

                print(f"  [WARN] DOCX {rdata.get('ticker')}: {e}")

    print(f"\n  Dashboard: {html}\n")

    return html





if __name__ == "__main__":

    main()


"""
live_macro_pipeline.py
========================
Live (schedulable) version of macro_events_scraper.py + filter_macro_events.py,
merged into a single in-memory flow:

  1. fetch_query() per MACRO_QUERY                      <- unchanged logic
       - outcome gate (data-release categories only)
       - election-noise filter (India_Policy)
       - geopolitical-relevance filter (Geopolitical)
  2. cross-query link dedup                              <- unchanged logic
  3. _deduplicate() per (category, date) - Jaccard only   <- unchanged logic
  4. _is_relevant() broad keyword gate                    <- from filter_macro_events.py,
                                                              applied to ALL categories
  5. _deduplicate_day_group() w/ official-source priority <- from filter_macro_events.py,
                                                              SINGLE pass (collapsed with
                                                              step 3 — see note below)
  6. enrich_dataframe()                                   <- unchanged logic, but SKIPS
                                                              articles whose content_hash
                                                              already exists in Postgres
                                                              (avoids re-fetching the same
                                                              article every run on a
                                                              rolling window)
  7. write {CATEGORY}_events.csv                          <- backup, unchanged
  8. write {CATEGORY}_events_filtered.csv                 <- backup, unchanged
  9. write macro_events_filtered.csv master                <- backup, unchanged
  10. upsert_macro_events()                                <- new, via db_writer,
                                                              PARENT process only
  11. log_pipeline_run()                                   <- new, via db_writer

NOTE ON DEDUP COLLAPSE: the original two-script flow ran Jaccard dedup TWICE
- once inside macro_events_scraper.py right after fetch (no source-priority
awareness), then again inside filter_macro_events.py (with source-priority).
This live version runs Jaccard clustering ONCE per (category, date) group,
immediately applying official-source priority during that same pass via
_deduplicate_day_group(). Behaviourally equivalent end result, half the
clustering work.

NOTE ON ENRICHMENT: enrich_dataframe() in the original script fetches every
surviving article on every run, with no awareness of what's already been
fetched. On a short rolling window (e.g. "today - 7 days") the same event
will reappear across multiple consecutive runs before it ages out of the
window, so re-running it naively would re-fetch + re-enrich identical
articles repeatedly. This version checks Postgres for existing content_hash
values BEFORE enrichment and skips the expensive fetch/extract step for
anything already enriched and stored - enrichment only happens once per
distinct article, ever.

This script performs exactly ONE pass per invocation and then exits - it
does not loop or sleep itself. The scheduler (run_pipeline.py / scheduler.py)
owns the clock. Designed cadence (see live_macro_pipeline_schedule_notes at
the bottom of this file):

    Every 15-30 minutes, all day:
        python live_macro_pipeline.py --from-date <today-7d> --to-date <today>
    08:30 IST daily (morning-ready pass, same as the company pipeline):
        python live_macro_pipeline.py --from-date <today-7d> --to-date <today>
        (no special flags needed - the 7-day window naturally re-covers
        anything published overnight; already-enriched articles are skipped
        automatically via the content_hash check)

Usage:
  python live_macro_pipeline.py --from-date 2026-06-12 --to-date 2026-06-19
  python live_macro_pipeline.py --from-date 2026-06-12 --to-date 2026-06-19 --no-enrich
  python live_macro_pipeline.py --from-date 2026-06-12 --to-date 2026-06-19 --no-db
"""

import os
import re
import time
import base64
import argparse
import traceback
from io import StringIO
import feedparser
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta, date
from email.utils import parsedate_to_datetime
from collections import defaultdict
from urllib.parse import quote_plus, urlparse

# db_writer is a local module used only for Postgres upsert.
# It is NOT required when running with --no-db (CSV-only mode).
# We import it lazily so the pipeline works without it.
try:
    import db_writer
except ModuleNotFoundError:
    db_writer = None  # type: ignore[assignment]

# --------------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Default output: backend/data/macro_events/ (created automatically if missing).
# Override by setting the CSV_OUTPUT_DIR environment variable — the same var
# the FastAPI backend reads so both always point at the same directory.
DEFAULT_OUTPUT_DIR = os.environ.get(
    "CSV_OUTPUT_DIR",
    os.path.join(_SCRIPT_DIR, "data", "macro_events"),
)
REQUEST_DELAY                = 1.2
ARTICLE_FETCH_DELAY          = 0.8
SIMILARITY_THRESHOLD         = 0.48
ARTICLE_TIMEOUT               = 10
ARTICLE_RETRIES               = 1
DEFAULT_MAX_ITEMS_PER_QUERY   = 20
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# LLM classify — loaded from environment; only used when --llm-classify flag is set.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MAX_LLM_CLASSIFICATIONS_PER_RUN = 40

# --------------------------------------------------------------------------
# MACRO EVENT QUERY DEFINITIONS  (identical to macro_events_scraper.py)
# --------------------------------------------------------------------------
MACRO_QUERIES = [

    ("RBI_Monetary",   "RBI MPC repo rate decision"),
    ("RBI_Monetary",   "RBI monetary policy rate cut hike"),
    ("RBI_Monetary",   "RBI governor Sanjay Malhotra statement"),
    ("RBI_Monetary",   "RBI monetary policy committee minutes"),
    ("RBI_Monetary",   "RBI liquidity CRR SLR announcement"),
    ("RBI_Monetary",   "RBI inflation target outlook"),
    ("RBI_Monetary",   "RBI monetary policy key takeaways"),
    ("RBI_Monetary",   "RBI policy statement highlights"),
    ("RBI_Monetary",   "RBI GDP growth forecast revision"),
    ("RBI_Monetary",   "RBI bulletin report"),

    ("India_Macro",    "India CPI inflation data release"),
    ("India_Macro",    "India retail inflation data"),
    ("India_Macro",    "India GDP growth quarterly data"),
    ("India_Macro",    "India IIP industrial production data"),
    ("India_Macro",    "India PMI manufacturing index"),
    ("India_Macro",    "India PMI services index"),
    ("India_Macro",    "India trade deficit data"),
    ("India_Macro",    "India current account balance"),
    ("India_Macro",    "India forex reserves data"),
    ("India_Macro",    "India fiscal deficit data MOSPI"),
    ("India_Macro",    "India core sector output data"),
    ("India_Macro",    "India wholesale price index WPI"),

    ("India_Policy",   "Union Budget 2026 announcement"),
    ("India_Policy",   "GST council meeting rate change"),
    ("India_Policy",   "SEBI regulation circular announcement"),
    ("India_Policy",   "PLI scheme government approval"),
    ("India_Policy",   "India FDI policy change announcement"),
    ("India_Policy",   "import export duty change India"),
    ("India_Policy",   "India disinvestment PSU privatisation"),
    ("India_Policy",   "India infrastructure spending railways roads announcement"),
    ("India_Policy",   "India telecom spectrum auction result"),
    ("India_Policy",   "India coal power renewable energy policy announcement"),
    ("India_Policy",   "election results impact stock market Nifty"),
    ("India_Policy",   "India government economic reform announcement"),
    ("India_Policy",   "cabinet committee economic affairs approval"),

    ("US_Macro",       "US Fed FOMC meeting rate decision"),
    ("US_Macro",       "Federal Reserve interest rate decision"),
    ("US_Macro",       "Fed Jerome Powell statement"),
    ("US_Macro",       "US CPI inflation data report"),
    ("US_Macro",       "US PPI producer price index report"),
    ("US_Macro",       "US GDP growth data report"),
    ("US_Macro",       "US non-farm payrolls jobs report"),
    ("US_Macro",       "US unemployment rate report"),
    ("US_Macro",       "US ISM PMI manufacturing services report"),
    ("US_Macro",       "US retail sales data report"),
    ("US_Macro",       "US dollar index DXY India impact"),
    ("US_Macro",       "US 10 year treasury yield move"),
    ("US_Macro",       "US tariffs trade war India impact"),
    ("US_Macro",       "Nasdaq S&P 500 crash rally India impact"),

    ("Geopolitical",   "US Iran war attack"),
    ("Geopolitical",   "US Iran sanctions oil"),
    ("Geopolitical",   "Iran nuclear deal strait of hormuz"),
    ("Geopolitical",   "Russia Ukraine war update market"),
    ("Geopolitical",   "Middle East conflict Israel Hamas Houthi"),
    ("Geopolitical",   "Red Sea shipping attack Houthi"),
    ("Geopolitical",   "India Pakistan tension border"),
    ("Geopolitical",   "India China LAC border tension"),
    ("Geopolitical",   "China Taiwan strait tension market"),
    ("Geopolitical",   "geopolitical risk India stock market"),
    ("Geopolitical",   "US China trade war tariff"),
    ("Geopolitical",   "OPEC oil production cut decision"),

    ("Commodities",    "crude oil price Brent WTI India impact"),
    ("Commodities",    "gold price India impact"),
    ("Commodities",    "natural gas price India"),
    ("Commodities",    "steel iron ore price India"),
    ("Commodities",    "aluminium copper commodity price India"),
    ("Commodities",    "rupee dollar USD INR exchange rate"),
    ("Commodities",    "coal price India import"),

    ("Global_CB",      "ECB European Central Bank rate decision"),
    ("Global_CB",      "Bank of England rate decision"),
    ("Global_CB",      "Bank of Japan BOJ policy decision"),
    ("Global_CB",      "China PBOC stimulus rate cut"),
    ("Global_CB",      "global central bank liquidity policy"),

    ("Market_Structure", "FII DII flow India stock market"),
    ("Market_Structure", "Nifty 50 Sensex index rebalancing"),
    ("Market_Structure", "MSCI index India inclusion exclusion"),
    ("Market_Structure", "India VIX volatility spike"),
    ("Market_Structure", "Nifty F&O expiry market impact"),
    ("Market_Structure", "India IPO mega listing"),
    ("Market_Structure", "NSE BSE market circuit breaker"),
    ("Market_Structure", "block deal bulk deal India crore"),

    ("AI_Technology",  "artificial intelligence AI India market impact"),
    ("AI_Technology",  "ChatGPT OpenAI Gemini DeepSeek impact India"),
    ("AI_Technology",  "NVIDIA semiconductor chip AI impact"),
    ("AI_Technology",  "India AI policy digital mission"),
    ("AI_Technology",  "IT sector India AI automation impact"),
    ("AI_Technology",  "US AI export control chip India"),
    ("AI_Technology",  "data center India investment AI"),
    ("AI_Technology",  "Big Tech earnings Microsoft Google Meta Apple"),

    ("RBI_Monetary",   "RBI keeps repo rate unchanged"),
    ("RBI_Monetary",   "RBI cuts repo rate basis points"),
    ("RBI_Monetary",   "RBI hikes repo rate basis points"),
    ("RBI_Monetary",   "RBI MPC repo rate unchanged at"),
    ("RBI_Monetary",   "RBI monetary policy decision highlights repo rate"),
    ("RBI_Monetary",   "RBI MPC outcome stance GDP inflation projection"),
    ("RBI_Monetary",   "RBI repo rate decision key takeaways announced"),

    ("India_Macro",    "India CPI inflation eases to"),
    ("India_Macro",    "India retail inflation rises to percent"),
    ("India_Macro",    "India CPI inflation data comes in at"),
    ("India_Macro",    "India GDP grew quarter percent"),
    ("India_Macro",    "India IIP industrial production rose to percent"),
    ("India_Macro",    "India WPI inflation came in at percent"),
    ("India_Macro",    "India PMI manufacturing rose to"),
    ("India_Macro",    "India trade deficit narrows widens billion"),

    ("US_Macro",       "US Fed holds interest rate unchanged"),
    ("US_Macro",       "Fed cuts rates basis points decision"),
    ("US_Macro",       "FOMC rate decision outcome target range"),
    ("US_Macro",       "US CPI inflation rose to percent"),
    ("US_Macro",       "US CPI inflation data cooled eased"),
    ("US_Macro",       "US nonfarm payrolls jobs added"),
    ("US_Macro",       "US unemployment rate percent"),
    ("US_Macro",       "Fed dot plot rate projection decision"),

    ("Global_CB",      "ECB cuts rates decision"),
    ("Global_CB",      "ECB holds rates unchanged"),
    ("Global_CB",      "Bank of England rate decision cut hold"),
    ("Global_CB",      "Bank of Japan raises rate decision"),
    ("Global_CB",      "PBOC cuts loan prime rate decision"),
    # Global Market Structure Events
    ("Global_Markets",  "KOSPI circuit breaker halt trading"),
    ("Global_Markets",  "Nikkei 225 crash circuit breaker"),
    ("Global_Markets",  "DAX FTSE circuit breaker halt"),
    ("Global_Markets",  "global stock market crash circuit breaker"),
    ("Global_Markets",  "emerging market sell-off crash"),
    ("Global_Markets",  "China A-shares circuit breaker halt"),
    ("Global_Markets",  "South Korea KOSPI trading halt"),
    ("Global_Markets",  "Japan stock market crash Nikkei fall"),
    ("Global_Markets",  "European market crash sell-off"),
    ("Global_Markets",  "VIX fear index spike market crash"),
    ("Global_Markets",  "global market risk-off sentiment"),
    ("Global_Markets",  "emerging market currency crisis"),
    ("Global_Markets",  "US stock market circuit breaker S&P 500"),
    ("Global_Markets",  "flash crash global markets"),
    ("Global_Markets",  "MSCI emerging market index rebalancing India"),

    # Currency & EM Crisis
    ("Currency_Crisis", "Turkish lira crash currency crisis"),
    ("Currency_Crisis", "Japanese yen carry trade unwind"),
    ("Currency_Crisis", "rupee hits all time low dollar"),
    ("Currency_Crisis", "emerging market currency sell-off"),
    ("Currency_Crisis", "dollar index DXY surge emerging markets"),
    ("Currency_Crisis", "yuan devaluation China currency"),
    ("Currency_Crisis", "South Korean won crash"),
    ("Currency_Crisis", "Brazil real Argentina peso crisis"),

    # Commodities Extended
    ("Commodities",     "LME aluminium copper nickel price crash"),
    ("Commodities",     "COMEX gold silver futures price"),
    ("Commodities",     "natural gas price spike Europe India"),
    ("Commodities",     "wheat corn soybean price India impact"),
    ("Commodities",     "Baltic dry index shipping freight"),
    ("Commodities",     "coal price Australia India import"),

    # Global Trade
    ("Global_Trade",    "US tariff announcement India impact"),
    ("Global_Trade",    "WTO trade ruling India"),
    ("Global_Trade",    "India US trade deal bilateral"),
    ("Global_Trade",    "China export restriction India supply chain"),
    ("Global_Trade",    "semiconductor chip export control India"),
    ("Global_Trade",    "India export ban restriction commodity"),
    ("Global_Trade",    "anti-dumping duty India steel chemical"),

    # Geopolitical Extended
    ("Geopolitical",    "strait of hormuz oil disruption shipping"),
    ("Geopolitical",    "North Korea missile test market reaction"),
    ("Geopolitical",    "Taiwan strait China military drill market"),
    ("Geopolitical",    "OPEC plus production decision oil price"),
    ("Geopolitical",    "Russia gas pipeline Europe energy crisis"),
    ("Geopolitical",    "South China Sea tension shipping route"),

    # ------------------------------------------------------------------
    # NEW: Shipping Chokepoints — oil transit corridors
    # ------------------------------------------------------------------
    ("Shipping_Chokepoints", "Strait of Hormuz tanker traffic disruption"),
    ("Shipping_Chokepoints", "Hormuz closure oil supply disruption"),
    ("Shipping_Chokepoints", "Bab-el-Mandeb shipping disruption Red Sea"),
    ("Shipping_Chokepoints", "Suez Canal oil tanker transit blocked"),
    ("Shipping_Chokepoints", "Suez Canal closure shipping rerouting"),
    ("Shipping_Chokepoints", "Cape of Good Hope tanker rerouting oil"),
    ("Shipping_Chokepoints", "Malacca Strait oil shipping disruption"),
    ("Shipping_Chokepoints", "Panama Canal drought shipping delay oil"),
    ("Shipping_Chokepoints", "Red Sea Houthi attack tanker shipping"),
    ("Shipping_Chokepoints", "global oil tanker freight rate surge"),

    # ------------------------------------------------------------------
    # NEW: India Refinery Operations
    # ------------------------------------------------------------------
    ("India_Refinery_Ops", "IOC Indian Oil refinery maintenance shutdown"),
    ("India_Refinery_Ops", "BPCL refinery capacity utilisation output"),
    ("India_Refinery_Ops", "HPCL refinery throughput maintenance turnaround"),
    ("India_Refinery_Ops", "Reliance Jamnagar refinery capacity output"),
    ("India_Refinery_Ops", "India refinery crude throughput data"),
    ("India_Refinery_Ops", "India refinery planned shutdown turnaround"),
    ("India_Refinery_Ops", "CPCL NRL refinery capacity utilisation"),
    ("India_Refinery_Ops", "India petroleum product output PPAC data"),
    ("India_Refinery_Ops", "India refinery capacity expansion upgrade"),

    # ------------------------------------------------------------------
    # NEW: India Strategic Petroleum Reserve
    # ------------------------------------------------------------------
    ("India_SPR", "India strategic petroleum reserve release"),
    ("India_SPR", "ISPRL crude oil storage reserve India"),
    ("India_SPR", "India strategic crude reserve Vizag underground"),
    ("India_SPR", "India strategic reserve Mangalore cavern"),
    ("India_SPR", "Padur strategic petroleum reserve India"),
    ("India_SPR", "India emergency petroleum reserve drawdown"),
    ("India_SPR", "India SPR expansion new storage capacity"),
    ("India_SPR", "IEA India strategic reserve coordination"),

    # ------------------------------------------------------------------
    # NEW: Alternative Crude Sourcing
    # ------------------------------------------------------------------
    ("Alt_Crude_Sourcing", "Russia Urals crude India imports discount"),
    ("Alt_Crude_Sourcing", "India US WTI crude oil imports"),
    ("Alt_Crude_Sourcing", "Iraq Basra crude India import volume"),
    ("Alt_Crude_Sourcing", "Nigeria Bonny Light crude India import"),
    ("Alt_Crude_Sourcing", "Saudi Aramco Arab Light India supply"),
    ("Alt_Crude_Sourcing", "India crude oil import diversification source"),
    ("Alt_Crude_Sourcing", "India crude import US Middle East Russia share"),
    ("Alt_Crude_Sourcing", "India crude oil supplier mix monthly data"),
    ("Alt_Crude_Sourcing", "India crude import cost barrel discount"),
    ("Alt_Crude_Sourcing", "Iran crude India waiver sanctions import"),

    # ------------------------------------------------------------------
    # NEW: Fuel Substitution
    # ------------------------------------------------------------------
    ("Fuel_Substitution", "India ethanol blending petrol percentage target"),
    ("Fuel_Substitution", "ethanol blending programme India E20"),
    ("Fuel_Substitution", "coal gasification India policy syngas"),
    ("Fuel_Substitution", "LNG import India price regasification terminal"),
    ("Fuel_Substitution", "India LNG spot cargo price import"),
    ("Fuel_Substitution", "compressed natural gas CNG price India"),
    ("Fuel_Substitution", "India biofuel policy blending mandate"),
    ("Fuel_Substitution", "India green hydrogen fuel substitute"),

    # ------------------------------------------------------------------
    # NEW: India Fuel Pricing
    # ------------------------------------------------------------------
    ("India_Fuel_Pricing", "petrol diesel price revision India OMC"),
    ("India_Fuel_Pricing", "petrol price hike cut India today"),
    ("India_Fuel_Pricing", "diesel price revision India effective"),
    ("India_Fuel_Pricing", "LPG cylinder price hike India"),
    ("India_Fuel_Pricing", "LPG price revision India effective today"),
    ("India_Fuel_Pricing", "India fuel price auto fuel revision OMC"),
    ("India_Fuel_Pricing", "IOC BPCL HPCL petrol diesel price change"),
    ("India_Fuel_Pricing", "India petrol diesel under-recovery OMC"),
]

# --------------------------------------------------------------------------
# SECTOR + COMPANY IMPACT MAPPING  (identical to macro_events_scraper.py)
# --------------------------------------------------------------------------
IMPACT_MAP = [
    (["crude oil", "brent", "wti", "opec", "oil price", "petroleum"],
     ["Energy", "Oil & Gas", "Aviation", "Paints & Chemicals"],
     ["RELIANCE", "ONGC", "BPCL", "HINDPETRO", "IOC", "INDIGO", "SPICEJET",
      "BERGER", "ASIANPAINT", "PIDILITIND"]),

    (["rupee", "usd inr", "dollar rupee", "forex", "currency depreciation", "dxy"],
     ["IT", "Pharma", "Textiles", "Gems & Jewellery", "Oil & Gas"],
     ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "SUNPHARMA", "DRREDDY",
      "DIVISLAB", "RAJESHEXPO", "ONGC", "RELIANCE"]),

    (["rbi", "repo rate", "interest rate", "monetary policy", "mpc", "crr", "slr"],
     ["Banking", "NBFC", "Real Estate", "Auto"],
     ["HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "BAJFINANCE",
      "BAJAJFINSV", "DLF", "GODREJPROP", "MARUTI", "TATAMOTORS", "M&M"]),

    (["fed", "fomc", "federal reserve", "jerome powell", "us rate"],
     ["IT", "Banking", "Metals", "Real Estate"],
     ["TCS", "INFY", "WIPRO", "HCLTECH", "HDFCBANK", "ICICIBANK",
      "TATASTEEL", "HINDALCO", "JSWSTEEL", "DLF"]),

    (["india cpi", "india inflation", "india wpi", "consumer price india"],
     ["FMCG", "Banking", "Auto", "Real Estate"],
     ["HINDUNILVR", "ITC", "NESTLE", "BRITANNIA", "DABUR", "HDFCBANK",
      "SBIN", "MARUTI", "TATAMOTORS", "DLF"]),

    (["us cpi", "us inflation", "us ppi", "american inflation"],
     ["IT", "Metals", "Pharma"],
     ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "TATASTEEL",
      "HINDALCO", "SUNPHARMA", "DRREDDY"]),

    (["gold price", "gold rally", "gold fall", "bullion", "mcx gold"],
     ["Gems & Jewellery", "Gold Financing"],
     ["RAJESHEXPO", "TITAN", "KALYAN", "MUTHOOTFIN", "MANAPPURAM"]),

    (["war", "attack", "military", "strike", "conflict", "sanctions",
      "geopolit", "iran", "russia", "ukraine", "houthi", "red sea"],
     ["Energy", "Defence", "Shipping", "Aviation"],
     ["RELIANCE", "ONGC", "BPCL", "HAL", "BEL", "BHEL", "COCHINSHIP",
      "GRSE", "INDIGO", "SPICEJET", "TATAMOTORS"]),

    (["india pakistan", "india china", "lac border", "surgical strike",
      "doklam", "galwan"],
     ["Defence", "Telecom"],
     ["HAL", "BEL", "BHEL", "GRSE", "COCHINSHIP", "BHARTIARTL",
      "IDEA", "BSNL"]),

    (["gst", "goods and services tax", "gst council", "gst rate"],
     ["FMCG", "Auto", "Real Estate", "Retail"],
     ["HINDUNILVR", "ITC", "MARUTI", "TATAMOTORS", "DLF", "DMART"]),

    (["union budget", "budget 2026", "finance minister", "nirmala sitharaman budget"],
     ["Banking", "Infrastructure", "Defence", "FMCG", "Auto", "Real Estate"],
     ["HDFCBANK", "SBIN", "LARSEN", "HAL", "BEL", "HINDUNILVR", "MARUTI",
      "DLF", "GODREJPROP"]),

    (["artificial intelligence", "ai", "chatgpt", "openai", "gemini",
      "deepseek", "nvidia", "automation", "data center", "semiconductor"],
     ["IT", "Technology"],
     ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "LTIMINDTREE",
      "MPHASIS", "PERSISTENT", "COFORGE"]),

    (["us fda", "fda approval", "drug recall", "pharmaceutical",
      "health policy", "medical device"],
     ["Pharma", "Healthcare"],
     ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "AUROPHARMA",
      "LUPIN", "ALKEM", "IPCALAB"]),

    (["steel", "iron ore", "aluminium", "copper", "zinc", "metal price",
      "china steel", "dumping"],
     ["Metals & Mining"],
     ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "SAIL",
      "NATIONALUM", "HINDCOPPER"]),

    (["real estate", "housing", "property price", "home loan", "realty"],
     ["Real Estate"],
     ["DLF", "GODREJPROP", "OBEROIRLTY", "PRESTIGE", "BRIGADE",
      "MAHLIFE", "PHOENIXLTD"]),

    (["electric vehicle", "ev policy", "auto sector", "automobile",
      "vehicle sales", "ev charging"],
     ["Auto", "Auto Ancillary"],
     ["MARUTI", "TATAMOTORS", "M&M", "BAJAJ-AUTO", "HEROMOTOCO",
      "EICHERMOT", "BOSCH", "MOTHERSON"]),

    (["npls", "bad loans", "credit growth", "banking sector",
      "nbfc crisis", "asset quality"],
     ["Banking", "NBFC"],
     ["HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK",
      "BAJFINANCE", "SHRIRAMFIN", "CHOLAFIN"]),

    (["rural consumption", "fmcg", "consumer staple", "monsoon",
      "kharif rabi", "msp"],
     ["FMCG", "Agriculture"],
     ["HINDUNILVR", "ITC", "DABUR", "MARICO", "BRITANNIA",
      "GODREJCP", "EMAMILTD"]),

    (["telecom", "spectrum auction", "5g", "mobile tariff", "arpu"],
     ["Telecom"],
     ["BHARTIARTL", "RELIANCE", "IDEA"]),

    (["renewable energy", "solar power", "wind energy", "electricity",
      "power sector", "coal shortage"],
     ["Power", "Renewable Energy"],
     ["NTPC", "POWERGRID", "ADANIGREEN", "ADANIPOWER", "TATAPOWER",
      "SUZLON", "TORNTPOWER"]),

    (["china economy", "china stimulus", "emerging market", "china gdp",
      "china slowdown"],
     ["Metals & Mining", "IT", "Chemicals"],
     ["TATASTEEL", "HINDALCO", "JSWSTEEL", "TCS", "INFY",
      "PIDILITIND", "AAVAS"]),

    (["fii", "foreign institutional", "foreign inflow", "foreign outflow",
      "dii buying", "portfolio investment"],
     ["Broader Market", "Banking", "IT"],
     ["HDFCBANK", "ICICIBANK", "TCS", "INFY", "RELIANCE"]),

     (["kospi", "nikkei", "dax", "ftse", "circuit breaker", "global crash",
      "flash crash", "vix spike", "risk-off", "emerging market sell"],
     ["Broader Market", "IT", "Metals"],
     ["TCS", "INFY", "WIPRO", "HCLTECH", "TATASTEEL", "HINDALCO",
      "RELIANCE", "HDFCBANK", "ICICIBANK"]),

    (["lira", "yen carry", "yuan devaluation", "currency crisis",
      "dollar surge", "dxy spike", "emerging market currency"],
     ["IT", "Pharma", "Textiles", "Metals"],
     ["TCS", "INFY", "WIPRO", "HCLTECH", "SUNPHARMA", "DRREDDY",
      "DIVISLAB", "TATASTEEL", "HINDALCO"]),

    (["us tariff", "trade war", "anti-dumping", "export ban",
      "import duty", "wto", "semiconductor export", "chip ban"],
     ["IT", "Pharma", "Chemicals", "Metals"],
     ["TCS", "INFY", "WIPRO", "HCLTECH", "SUNPHARMA", "DRREDDY",
      "TATASTEEL", "HINDALCO", "PIDILITIND"]),

    (["baltic dry", "freight", "shipping rate", "container",
      "red sea", "hormuz", "shipping route"],
     ["Shipping", "Logistics", "Energy"],
     ["COCHINSHIP", "GRSE", "CONCOR", "ALLCARGO", "RELIANCE", "ONGC"]),
]


def _get_impact(title):
    title_lower = title.lower()
    sectors_found, companies_found = [], []

    for keywords, sectors, companies in IMPACT_MAP:
        if any(kw in title_lower for kw in keywords):
            sectors_found.extend(sectors)
            companies_found.extend(companies)

    seen_s, seen_c = set(), set()
    unique_sectors, unique_companies = [], []
    for s in sectors_found:
        if s not in seen_s:
            seen_s.add(s)
            unique_sectors.append(s)
    for c in companies_found:
        if c not in seen_c:
            seen_c.add(c)
            unique_companies.append(c)

    if not unique_sectors:
        unique_sectors   = ["Broader Market"]
        unique_companies = ["NIFTY50"]

    return " | ".join(unique_sectors), " | ".join(unique_companies[:15])


# --------------------------------------------------------------------------
# CORRIDOR IMPACT MAP  (new — parallel to IMPACT_MAP)
# Maps keywords -> which supply-chain buffer layer is hit, which shipping
# corridor is at risk, and a severity weight 1-5.
#   buffer_layer: "on_water" | "refinery_stock" | "spr" | "none"
#   corridor:     "hormuz" | "red_sea" | "suez" | "cape_of_good_hope" |
#                 "russia_route" | "malacca" | "india_domestic" | "none"
#   severity:     1 (minor) .. 5 (critical)
# --------------------------------------------------------------------------
CORRIDOR_IMPACT_MAP = [
    # ---- Strait of Hormuz (critical — ~20% of global oil seaborne trade) ----
    (["strait of hormuz", "hormuz closure", "hormuz blockade",
      "hormuz disruption", "hormuz attack", "hormuz tension"],
     {"buffer_layer": "on_water", "corridor": "hormuz", "severity": 5}),

    # ---- Red Sea / Bab-el-Mandeb (houthi attacks, Yemen conflict) ----
    (["red sea attack", "houthi attack", "bab-el-mandeb", "bab el mandeb",
      "red sea shipping", "red sea disruption", "red sea tanker",
      "houthi missile", "houthi drone"],
     {"buffer_layer": "on_water", "corridor": "red_sea", "severity": 4}),

    # ---- Suez Canal ----
    (["suez canal", "suez closure", "suez blocked", "suez disruption",
      "suez transit", "ever given"],
     {"buffer_layer": "on_water", "corridor": "suez", "severity": 4}),

    # ---- Cape of Good Hope (rerouting adds ~2 weeks + cost) ----
    (["cape of good hope", "cape rerouting", "good hope tanker",
      "longer route tanker", "rerouting via cape"],
     {"buffer_layer": "on_water", "corridor": "cape_of_good_hope", "severity": 2}),

    # ---- Russia / Arctic / Black Sea route ----
    (["russia crude route", "russia ukraine shipping", "black sea oil",
      "urals crude", "russia oil export", "russia pipeline",
      "russia oil ban", "russian crude"],
     {"buffer_layer": "on_water", "corridor": "russia_route", "severity": 3}),

    # ---- Malacca Strait ----
    (["malacca strait", "strait of malacca", "malacca shipping",
      "malacca piracy", "south china sea shipping"],
     {"buffer_layer": "on_water", "corridor": "malacca", "severity": 3}),

    # ---- Panama Canal ----
    (["panama canal", "panama drought", "panama shipping delay"],
     {"buffer_layer": "on_water", "corridor": "cape_of_good_hope", "severity": 2}),

    # ---- General on-water / tanker disruption (OPEC, crude price spike) ----
    (["opec cut", "opec production cut", "opec plus", "crude oil price spike",
      "oil supply disruption", "oil embargo", "tanker attack",
      "oil sanctions", "iran oil", "iran sanctions", "venezuela oil"],
     {"buffer_layer": "on_water", "corridor": "none", "severity": 3}),

    # ---- Brent / WTI / crude price signal (market-level impact) ----
    (["brent crude", "wti crude", "crude oil", "brent price",
      "oil price surge", "oil price crash", "oil rally"],
     {"buffer_layer": "on_water", "corridor": "none", "severity": 2}),

    # ---- India Strategic Petroleum Reserve (SPR) ----
    (["strategic petroleum reserve", "isprl", "spr release", "spr drawdown",
      "strategic crude reserve", "vizag reserve", "mangalore cavern",
      "padur reserve", "emergency reserve"],
     {"buffer_layer": "spr", "corridor": "none", "severity": 3}),

    # ---- India Refinery / Refinery Stock buffer ----
    (["refinery shutdown", "refinery maintenance", "refinery turnaround",
      "refinery capacity", "refinery throughput", "refinery output",
      "ioc refinery", "bpcl refinery", "hpcl refinery",
      "reliance refinery", "jamnagar refinery", "cpcl refinery"],
     {"buffer_layer": "refinery_stock", "corridor": "none", "severity": 3}),

    # ---- Fuel substitution signals (reduce crude import dependency) ----
    (["ethanol blending", "e20", "coal gasification", "lng import",
      "lng terminal", "cng price", "biofuel", "green hydrogen",
      "fuel substitution"],
     {"buffer_layer": "refinery_stock", "corridor": "none", "severity": 2}),

    # ---- India domestic fuel pricing (downstream refinery impact) ----
    (["petrol price", "diesel price", "lpg price", "lpg cylinder",
      "fuel price revision", "under-recovery", "omc pricing"],
     {"buffer_layer": "refinery_stock", "corridor": "india_domestic", "severity": 2}),
]

_CORRIDOR_NO_MATCH = {"buffer_layer": "none", "corridor": "none", "severity": 0}


def apply_corridor_impact(text):
    """
    Scan *text* (title or article body) against CORRIDOR_IMPACT_MAP and return
    the impact dict for the FIRST matching entry, following the same scan
    pattern as _get_impact() applied to IMPACT_MAP.

    Returns a dict: {"buffer_layer": str, "corridor": str, "severity": int}
    Returns _CORRIDOR_NO_MATCH (all-none) if nothing matches.
    """
    t = str(text).lower()
    for keywords, impact in CORRIDOR_IMPACT_MAP:
        if any(kw in t for kw in keywords):
            return impact
    return _CORRIDOR_NO_MATCH


# --------------------------------------------------------------------------
# SOURCE PRIORITY — OFFICIAL sources (govt/regulator) win over Google News,
# matching filter_macro_events.py's priority model (distinct from the
# company pipeline's NSE/BSE-exchange priority model).
# --------------------------------------------------------------------------
OFFICIAL_SOURCES = {
    "rbi.org": 1000, "rbi.org.in": 1000,
    "pib.gov": 1000, "pib.gov.in": 1000,
    "mospi": 1000, "mospi.gov": 1000,
    "sebi.gov": 1000, "sebi.gov.in": 1000,
    "finmin": 1000, "finmin.nic.in": 1000,
    "nseindia": 1000, "nseindia.com": 1000,
    "bseindia": 1000, "bseindia.com": 1000,
    "indiabudget.gov": 1000,
    "pmindiawebcast": 1000,
    "dpiit.gov": 1000,
    "gst.gov": 1000,
    "federalreserve.gov": 1000,
    "bls.gov": 1000,
    "bea.gov": 1000,
    "treasury.gov": 1000,
    "sec.gov": 1000,
    "census.gov": 1000,
    "whitehouse.gov": 1000,
    "commerce.gov": 1000,
    "imf.org": 950,
    "worldbank.org": 950,
    "bis.org": 950,
    "ecb.europa.eu": 950,
    "bankofengland.co.uk": 950,
    "boj.or.jp": 950,
    "pboc.gov.cn": 950,
    "opec.org": 950,
    # NEW: India energy regulator + international energy agencies
    "ppac.gov.in": 1000,
    "ppac.gov": 1000,
    "eia.gov": 1000,
    "iea.org": 1000,
}

NEWS_SOURCE_PRIORITY = {
    # Wire services
    "reuters": 90,
    "bloomberg": 90,
    "associated press": 88, "ap news": 88,
    "press trust of india": 88, "pti": 88,
    "ani": 82,
    # Premium financial
    "wall street journal": 87, "wsj": 87,
    "financial times": 87, "ft.com": 87,
    "cnbc": 80,
    "moneycontrol": 85,
    "economic times": 82, "economictimes": 82, "et markets": 82,
    "business standard": 80, "businessstandard": 80,
    "cnbc tv18": 78, "cnbctv18": 78,
    "livemint": 75, "mint": 75,
    "financial express": 73,
    "hindu businessline": 70, "businessline": 70,
    "the hindu": 70,
    "ndtv profit": 65, "ndtv": 65,
    "times of india": 62,
    "indian express": 62,
    "bq prime": 65, "bloombergquint": 65,
    # International
    "nikkei": 75,
    "south china morning post": 70, "scmp": 70,
    "korea herald": 65,
    "yonhap": 65,
    # Remove noise
    "zeebiz": 45,
    "india infoline": 40, "iifl": 40,
    "trade brains": 35,
    "marketsmojo": 30,
    "whalesbook": 25,
    "scanx": 20,
    "intellectia": 15,
    "adda247": 10,
    "jagran josh": 10,
    "bankersadda": 10,
}

# Broad relevance gate from filter_macro_events.py — applies to ALL categories
RELEVANCE_KEYWORDS = {
    "rbi", "india", "nifty", "sensex", "rupee", "sebi", "bse", "nse",
    "indian", "fed", "fomc", "opec", "crude", "iran", "oil", "inflation",
    "gdp", "repo", "rate", "growth", "market", "stock", "fiscal", "budget",
    "gst", "imf", "china", "dollar", "dxy", "treasury", "yield", "mpc",
    "ai", "nvidia", "semiconductor", "geopolit", "war", "ceasefire", "sanctions",
    "fii", "dii", "nifty50", "supply chain", "tariff", "trade",
    "ongc", "reliance", "tata", "infosys", "hdfc", "sbi",
    # Global market events
    "kospi", "nikkei", "dax", "ftse", "nasdaq", "s&p", "dow",
    "circuit breaker", "trading halt", "flash crash", "sell-off",
    "emerging market", "vix", "risk-off", "lira", "yen", "yuan",
    "won", "real", "peso", "carry trade", "devaluation",
    "lme", "comex", "baltic", "freight", "shipping",
    "wto", "anti-dumping", "bilateral", "export ban",
    "strait", "hormuz", "pipeline", "north korea", "taiwan",
    # NEW: shipping corridors & chokepoints
    "suez", "bab-el-mandeb", "malacca", "cape of good hope", "panama",
    "red sea", "tanker", "rerouting", "chokepoint", "houthi",
    # NEW: India energy supply chain
    "refinery", "throughput", "turnaround", "ioc", "bpcl", "hpcl",
    "ppac", "petroleum", "eia", "iea", "isprl", "spr",
    "vizag", "mangalore", "padur", "strategic reserve",
    # NEW: crude sourcing & substitution
    "urals", "basra", "bonny light", "arab light", "jamnagar",
    "ethanol", "blending", "lng", "cng", "biofuel", "gasification",
    # NEW: India fuel pricing
    "petrol", "diesel", "lpg", "cylinder", "omc", "under-recovery",
}

STOP_WORDS = {
    "the","a","an","is","are","was","were","has","have","had","in","on",
    "at","of","to","for","by","with","and","or","from","its","this","that",
    "as","it","be","will","after","before","into","about","than","more",
    "up","down","says","amid","over","after","india","indian","market",
    "markets","stock","shares","impact","2026",
}

GEOPOLITICAL_RELEVANCE_WORDS = {
    "india", "nifty", "sensex", "rupee", "oil", "crude", "opec",
    "shipping", "energy", "sanctions", "market", "brent", "wti",
    "hormuz", "iran", "pakistan", "china", "ukraine", "russia",
    "inflation", "fed", "rbi", "export", "import", "gdp"
}

ELECTION_NOISE_WORDS = {
    "how to vote", "voter id", "polling booth", "voting day",
    "counting day", "exit poll", "when is voting", "where to vote",
    "voter list", "epic card",
}

# --------------------------------------------------------------------------
# OUTCOME GATE  (identical to macro_events_scraper.py)
# --------------------------------------------------------------------------
DATA_RELEASE_CATEGORIES = {"RBI_Monetary", "India_Macro", "US_Macro", "Global_CB"}

PREVIEW_NOISE_WORDS = {
    "what to expect", "how to watch", "preview", "ahead of", "expectation",
    "expectations", "what markets are", "will rbi", "will the fed", "will fed",
    "rate hike or status quo", "pause or rate hike", "to be announced",
    "to begin", "begins today", "begins on", "starts today", "start today",
    "time, where", "predicting", "set to", "likely to", "poised to",
    "in focus", "to decide", "what to", "brace for", "might stocks react",
    "next 5 years", "in 5 years", "projected", "could cut", "could hike",
    "may cut", "may hike", "expected to", "anticipate", "countdown",
}

OUTCOME_SIGNAL_WORDS = {
    "kept", "keeps", "holds", "held", "hold", "cut", "cuts", "slashed",
    "hiked", "hikes", "raised", "raises", "lowered", "lowers", "unchanged",
    "maintained", "leaves rate", "leaves rates", "rose to", "fell to",
    "eased to", "jumped to", "climbed to", "came in at", "stood at",
    "accelerated", "slowed to", "slows to", "announces", "announced",
    "delivers", "delivered", "makes first rate", "reduces", "reduced",
    "retains", "retained", "decision", "outcome", "verdict", "key takeaways",
    "highlights", "narrows", "widens", "narrowed", "widened",
}

CATEGORY_ANCHORS = {
    "RBI_Monetary": [
        "repo", "mpc", "crr", "slr", "basis point", " bps",
        "inflation", "gdp", "liquidity", "monetary policy",
        "rate", "stance",
    ],
    "US_Macro": [
        "fomc", "fed funds", "federal funds", "interest rate",
        "inflation", "cpi", "ppi", "payroll", "unemployment",
        "yield", "jobs", "gdp", "rate cut", "rate hike", "repo",
        "treasury yield", "target range",
    ],
    "India_Macro": [
        "cpi", "inflation", "gdp", "iip", "pmi", "wpi",
        "industrial production", "trade deficit", "forex",
        "fiscal", "growth", "core sector", "current account",
    ],
    "Global_CB": [
        "ecb", "boe", "bank of england", "boj", "bank of japan",
        "pboc", "euribor", "rate", "loan prime",
    ],
    "Global_Markets": [
        "circuit breaker", "trading halt", "crash", "sell-off",
        "kospi", "nikkei", "dax", "ftse", "vix", "flash crash",
        "emerging market", "msci", "risk-off",
    ],
    "Currency_Crisis": [
        "lira", "yen", "yuan", "won", "real", "peso",
        "carry trade", "devaluation", "currency crisis",
        "rupee", "dollar", "dxy",
    ],
    "Global_Trade": [
        "tariff", "wto", "trade deal", "anti-dumping",
        "export ban", "import duty", "supply chain",
        "semiconductor", "chip", "bilateral",
    ],
}

NUMERIC_VALUE_RE = re.compile(r"-?\d+(?:\.\d+)?\s*(?:%|bps|basis points)")


def _passes_outcome_gate(category, title):
    if category not in DATA_RELEASE_CATEGORIES:
        return True

    tl = title.lower()

    if any(p in tl for p in PREVIEW_NOISE_WORDS):
        return False

    anchors = CATEGORY_ANCHORS.get(category, [])
    if anchors and not any(a in tl for a in anchors):
        return False

    if any(w in tl for w in OUTCOME_SIGNAL_WORDS):
        return True
    if NUMERIC_VALUE_RE.search(tl):
        return True
    return False


def _is_official(source_str):
    s = str(source_str).lower().strip()
    return any(key in s for key in OFFICIAL_SOURCES)


def _source_score(src):
    s = str(src).lower().strip()
    for k, v in OFFICIAL_SOURCES.items():
        if k in s:
            return v
    for k, v in NEWS_SOURCE_PRIORITY.items():
        if k in s:
            return v
    return 25


def _title_tokens(title):
    words = re.findall(r"[a-zA-Z0-9]+", str(title).lower())
    return set(w for w in words if w not in STOP_WORDS and len(w) > 2)


def _jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _parse_date(pub):
    try:
        return parsedate_to_datetime(str(pub)).strftime("%Y-%m-%d")
    except Exception:
        m = re.search(r"\d{1,2}\s+\w{3}\s+\d{4}", str(pub))
        return m.group(0) if m else str(pub)[:10]


def _is_relevant(title):
    t = str(title).lower()
    return any(kw in t for kw in RELEVANCE_KEYWORDS)


def _in_date_range(pub_str, from_date_str, to_date_str=None):
    try:
        dt = parsedate_to_datetime(str(pub_str))
        from_dt = datetime.strptime(from_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if dt < from_dt:
            return False
        if to_date_str:
            to_dt = datetime.strptime(to_date_str, "%Y-%m-%d").replace(
                tzinfo=timezone.utc) + timedelta(days=1)
            if dt >= to_dt:
                return False
        return True
    except Exception:
        return True


def _google_news_window(from_date_str, to_date_str=None):
    try:
        from_dt = datetime.strptime(from_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        days = (datetime.now(timezone.utc) - from_dt).days
        days = max(days, 1)
        days = min(days, 730)
        return f"when:{days}d"
    except Exception:
        return "when:1y"


# --------------------------------------------------------------------------
# DEDUPLICATION — SINGLE PASS, Jaccard clustering + official-source priority
# applied together. Collapses what was two separate passes (one inside
# macro_events_scraper.py, one inside filter_macro_events.py) into one.
# --------------------------------------------------------------------------

def _deduplicate_day_group(items):
    """
    Given items from the SAME (category, date) group:
    1. Cluster by title similarity (Jaccard >= threshold) -> same event
    2. For each cluster:
       - Official source present -> keep ALL official, drop all Google News
       - All Google News -> keep single highest-trust source
    3. Single-item clusters (unique event) -> always keep as-is
    """
    if len(items) <= 1:
        return items

    tokens = [_title_tokens(x.get("title", "")) for x in items]
    parent = list(range(len(items)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        parent[find(x)] = find(y)

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if _jaccard(tokens[i], tokens[j]) >= SIMILARITY_THRESHOLD:
                union(i, j)

    clusters = defaultdict(list)
    for i, item in enumerate(items):
        clusters[find(i)].append(item)

    result = []
    for cluster in clusters.values():
        if len(cluster) == 1:
            result.append(cluster[0])
            continue

        official = [x for x in cluster if _is_official(x.get("source", ""))]
        news = [x for x in cluster if not _is_official(x.get("source", ""))]

        if official:
            result.extend(official)
        else:
            best = max(news, key=lambda x: _source_score(x.get("source", "")))
            result.append(best)

    return result


# --------------------------------------------------------------------------
# FETCH FROM GOOGLE NEWS RSS  (identical filter logic to macro_events_scraper.py)
# --------------------------------------------------------------------------

def fetch_query(category, query, from_date_str, to_date_str=None,
                 max_items=DEFAULT_MAX_ITEMS_PER_QUERY, keep_previews=False):
    when_clause = _google_news_window(from_date_str, to_date_str)
    full_q = f"{query} {when_clause}"
    url = (f"https://news.google.com/rss/search?"
           f"q={quote_plus(full_q)}&hl=en-IN&gl=IN&ceid=IN:en")
    items = []
    try:
        feed = feedparser.parse(url)

        for entry in feed.entries:
            if len(items) >= max_items:
                break

            pub = entry.get("published", "")
            if not _in_date_range(pub, from_date_str, to_date_str):
                continue
            title = entry.get("title", "").strip()
            if not title:
                continue

            if category == "Geopolitical":
                title_lower_check = title.lower()
                if not any(w in title_lower_check for w in GEOPOLITICAL_RELEVANCE_WORDS):
                    continue

            if category == "India_Policy":
                title_lower_check = title.lower()
                if any(w in title_lower_check for w in ELECTION_NOISE_WORDS):
                    continue

            if not keep_previews and not _passes_outcome_gate(category, title):
                continue

            # Broad relevance gate (from filter_macro_events.py) — applied to
            # ALL categories at fetch time now, instead of as a later pass.
            if not _is_relevant(title):
                continue

            link   = entry.get("link", "")
            source = entry.get("source", {}).get("title", "") if hasattr(entry, "source") else ""
            pub_date = _parse_date(pub)
            sectors, companies = _get_impact(title)
            corridor_impact    = apply_corridor_impact(title)
            items.append({
                "date":               pub_date,
                "published_raw":      pub,
                "title":              title,
                "source":             source,
                "link":               link,
                "category":           category,
                "affected_sectors":   sectors,
                "affected_companies": companies,
                "buffer_layer":       corridor_impact["buffer_layer"],
                "corridor":           corridor_impact["corridor"],
                "severity":           corridor_impact["severity"],
            })
    except Exception as e:
        print(f"   [!] Fetch error for query '{query}': {e}")
    return items

# --------------------------------------------------------------------------
# DIRECT OFFICIAL RSS FEEDS
# These bypass Google News entirely for the highest-priority sources
# --------------------------------------------------------------------------

OFFICIAL_RSS_FEEDS = [
    # RBI
    ("RBI_Monetary", "https://www.rbi.org.in/RSS/RSSFeed.aspx?Id=1",  "RBI Press Releases"),
    ("RBI_Monetary", "https://www.rbi.org.in/RSS/RSSFeed.aspx?Id=12", "RBI Monetary Policy"),
    # SEBI
    ("India_Policy", "https://www.sebi.gov.in/sebi_data/attachdocs/rss/sebirss.xml", "SEBI Circulars"),
    # PIB
    ("India_Policy", "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3", "PIB Finance"),
    # Ministry of Finance
    ("India_Policy", "https://finmin.nic.in/rss.xml", "Ministry of Finance"),
    # MOSPI (for GDP/IIP/CPI data releases)
    ("India_Macro", "https://mospi.gov.in/rss.xml", "MOSPI"),
    # US Federal Reserve
    ("US_Macro", "https://www.federalreserve.gov/feeds/press_all.xml", "Federal Reserve"),
    ("US_Macro", "https://www.federalreserve.gov/feeds/speeches.xml",  "Fed Speeches"),
    # BLS (US jobs/CPI data)
    ("US_Macro", "https://www.bls.gov/feed/bls_latest.rss", "BLS Data"),
    # IMF
    ("Global_CB", "https://www.imf.org/en/News/RSS", "IMF News"),
    # World Bank
    ("Global_CB", "https://feeds.worldbank.org/worldbank/pressreleases", "World Bank"),
    # ECB
    ("Global_CB", "https://www.ecb.europa.eu/rss/press.html", "ECB Press"),
    # OPEC
    ("Commodities", "https://www.opec.org/opec_web/en/press_room/rss.htm", "OPEC"),
    # WTO
    ("Global_Trade", "https://www.wto.org/english/news_e/news_e.rss", "WTO"),
    # NSE circulars (not just announcements — regulatory circulars)
    ("India_Policy", "https://nsearchives.nseindia.com/content/circulars/circulars.xml", "NSE Circulars"),
    # NEW: India energy data — PPAC (Petroleum Planning & Analysis Cell)
    ("India_Fuel_Pricing",    "https://ppac.gov.in/rss.xml",              "PPAC"),
    # NEW: US Energy Information Administration
    ("Commodities",           "https://www.eia.gov/rss/news.xml",         "EIA News"),
    # NEW: International Energy Agency
    ("Commodities",           "https://www.iea.org/feed/news",            "IEA News"),
]


def fetch_official_rss(from_date_str, to_date_str=None):
    """
    Fetch items from official government/regulator RSS feeds directly.
    Uses requests with a hard timeout so a hanging feed (e.g. WTO leaving
    the socket open) can't freeze the whole pipeline — feedparser.parse()
    on a URL has no timeout and will block forever on such feeds.
    Returns list of item dicts in same format as fetch_query().
    """
    items = []
    headers = {"User-Agent": USER_AGENT}

    for category, feed_url, source_name in OFFICIAL_RSS_FEEDS:
        try:
            # Fetch with a hard timeout instead of letting feedparser block
            resp = requests.get(feed_url, headers=headers, timeout=8,
                                allow_redirects=True)
            if resp.status_code != 200:
                print(f"  [Official RSS] {source_name}: HTTP {resp.status_code}, skipped")
                continue

            feed = feedparser.parse(resp.content)   # parse bytes, no network

            before = len(items)
            for entry in feed.entries:
                pub = entry.get("published", "") or entry.get("updated", "")
                if not _in_date_range(pub, from_date_str, to_date_str):
                    continue
                title = entry.get("title", "").strip()
                if not title:
                    continue
                if not _is_relevant(title):
                    continue
                link      = entry.get("link", "")
                pub_date  = _parse_date(pub)
                sectors, companies = _get_impact(title)
                corridor_impact    = apply_corridor_impact(title)
                items.append({
                    "date":               pub_date,
                    "published_raw":      pub,
                    "title":              title,
                    "source":             source_name,
                    "link":               link,
                    "category":           category,
                    "affected_sectors":   sectors,
                    "affected_companies": companies,
                    "buffer_layer":       corridor_impact["buffer_layer"],
                    "corridor":           corridor_impact["corridor"],
                    "severity":           corridor_impact["severity"],
                })
            print(f"  [Official RSS] {source_name}: {len(items) - before} items")
            time.sleep(0.5)

        except requests.exceptions.Timeout:
            print(f"  [Official RSS] {source_name}: TIMEOUT (skipped)")
            continue
        except Exception as e:
            print(f"  [Official RSS] {source_name} failed: {e}")
            continue

    return items


# --------------------------------------------------------------------------
# OFAC SDN SANCTIONS LIST  (new — pulls real Treasury data, no auth needed)
# --------------------------------------------------------------------------

# Official Treasury OFAC SDN CSV — public download, no auth
_OFAC_SDN_URL = "https://www.treasury.gov/ofac/downloads/sdn.csv"

# Column layout from OFAC published schema:
# https://home.treasury.gov/system/files/126/sdn_advanced_notes.pdf
_OFAC_SDN_COLS = [
    "ent_num", "sdn_name", "sdn_type", "program", "title",
    "call_sign", "vess_type", "tonnage", "grt", "vess_flag",
    "vess_owner", "remarks",
]


def fetch_ofac_sanctions_list(output_dir):
    """
    Download the OFAC SDN (Specially Designated Nationals) CSV from the
    public Treasury URL, parse it, and write/append to ofac_sanctions.csv
    in *output_dir*.

    On each run:
    - Compares new entries against the previous file (keyed on ent_num).
    - Flags genuinely new entries with new_since_last_run=True.
    - Appends only net-new rows so the file grows incrementally.

    Returns (new_count, total_count).  Never raises — errors are logged and
    (0, 0) is returned so the main pipeline is unaffected.
    """
    out_path = os.path.join(output_dir, "ofac_sanctions.csv")
    print(f"\n[OFAC] Downloading SDN list from {_OFAC_SDN_URL} ...")

    try:
        resp = requests.get(
            _OFAC_SDN_URL,
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"  [OFAC] HTTP {resp.status_code} — skipped.")
            return 0, 0

        # The SDN CSV has no header; assign the published column names.
        # Use StringIO so we never write temp files.
        raw_text = resp.content.decode("utf-8", errors="replace")
        df_new = pd.read_csv(
            StringIO(raw_text),
            header=None,
            names=_OFAC_SDN_COLS,
            dtype=str,
            on_bad_lines="skip",
        )
        df_new["ent_num"] = df_new["ent_num"].str.strip()
        df_new["fetched_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        df_new["new_since_last_run"] = False

        # Load previous file if it exists, compare on ent_num
        existing_ids: set = set()
        if os.path.exists(out_path):
            try:
                df_existing = pd.read_csv(out_path, dtype=str)
                if "ent_num" in df_existing.columns:
                    existing_ids = set(df_existing["ent_num"].dropna().str.strip())
            except Exception as e:
                print(f"  [OFAC] Could not read existing file ({e}); treating all as new.")

        # Flag net-new entries
        df_new["new_since_last_run"] = ~df_new["ent_num"].isin(existing_ids)
        new_count = int(df_new["new_since_last_run"].sum())

        # Append only net-new rows (or write full file on first run)
        if not os.path.exists(out_path):
            df_new.to_csv(out_path, index=False, encoding="utf-8-sig")
            print(f"  [OFAC] First run — wrote {len(df_new):,} entries to {out_path}")
        else:
            net_new = df_new[df_new["new_since_last_run"]]
            if not net_new.empty:
                net_new.to_csv(out_path, mode="a", header=False, index=False,
                                encoding="utf-8-sig")
                print(f"  [OFAC] Appended {new_count} new entries "
                      f"({len(df_new):,} total in download) → {out_path}")
            else:
                print(f"  [OFAC] No new SDN entries since last run "
                      f"({len(df_new):,} total in download).")

        # Print a brief sample of newly added names (useful for monitoring)
        if new_count:
            samples = df_new[df_new["new_since_last_run"]]["sdn_name"].dropna().head(5).tolist()
            print(f"  [OFAC] New names (sample): {', '.join(samples)}")

        return new_count, len(df_new)

    except Exception as e:
        print(f"  [OFAC] fetch_ofac_sanctions_list failed: {e}")
        return 0, 0


# --------------------------------------------------------------------------
# COMMODITY PRICES  (new — pulls real daily data via yfinance, no API key)
# --------------------------------------------------------------------------

# Tickers: Brent crude futures, WTI crude futures, USD/INR spot
_COMMODITY_TICKERS = {
    "BZ=F":  "Brent_Crude_USD_bbl",
    "CL=F":  "WTI_Crude_USD_bbl",
    "INR=X": "USD_INR",
}


def fetch_commodity_prices(output_dir, lookback_days=7):
    """
    Pull *lookback_days* of daily OHLCV data for Brent (BZ=F), WTI (CL=F),
    and USD/INR (INR=X) from Yahoo Finance via yfinance (no API key needed).

    Writes to commodity_prices.csv in *output_dir*, appending only rows
    whose (date, ticker) pair is not already present — so re-running is
    idempotent and the file grows incrementally.

    Returns (new_rows_written, total_rows_attempted). Never raises.
    """
    out_path = os.path.join(output_dir, "commodity_prices.csv")

    try:
        import yfinance as yf
    except ImportError:
        print("  [CommodityPrices] yfinance not installed — skipping. "
              "Run: pip install yfinance")
        return 0, 0

    print(f"\n[CommodityPrices] Fetching {lookback_days}d of daily prices "
          f"for {list(_COMMODITY_TICKERS.keys())} ...")

    # Load existing (date, ticker) pairs to avoid duplicates
    existing_pairs: set = set()
    if os.path.exists(out_path):
        try:
            df_ex = pd.read_csv(out_path, dtype=str)
            if {"date", "ticker"}.issubset(df_ex.columns):
                existing_pairs = set(
                    zip(df_ex["date"].str.strip(), df_ex["ticker"].str.strip())
                )
        except Exception as e:
            print(f"  [CommodityPrices] Could not read existing file ({e}); "
                  "treating all as new.")

    end_dt   = datetime.now(timezone.utc).date()
    start_dt = end_dt - timedelta(days=lookback_days)

    all_rows = []
    for ticker, label in _COMMODITY_TICKERS.items():
        try:
            tkr  = yf.Ticker(ticker)
            hist = tkr.history(start=str(start_dt), end=str(end_dt), interval="1d")
            if hist.empty:
                print(f"  [CommodityPrices] {ticker}: no data returned")
                continue

            for row_date, row in hist.iterrows():
                date_str = str(row_date)[:10]   # "YYYY-MM-DD"
                if (date_str, ticker) in existing_pairs:
                    continue
                all_rows.append({
                    "date":        date_str,
                    "ticker":      ticker,
                    "label":       label,
                    "open":        round(float(row.get("Open",  float("nan"))), 4),
                    "high":        round(float(row.get("High",  float("nan"))), 4),
                    "low":         round(float(row.get("Low",   float("nan"))), 4),
                    "close":       round(float(row.get("Close", float("nan"))), 4),
                    "volume":      int(row.get("Volume", 0) or 0),
                    "fetched_at":  datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                })
            print(f"  [CommodityPrices] {ticker} ({label}): "
                  f"{len(hist)} rows fetched")
            time.sleep(0.3)

        except Exception as e:
            print(f"  [CommodityPrices] {ticker} failed: {e}")
            continue

    if not all_rows:
        print("  [CommodityPrices] No new rows to write.")
        return 0, 0

    df_new = pd.DataFrame(all_rows)
    write_header = not os.path.exists(out_path)
    df_new.to_csv(out_path, mode="a", header=write_header, index=False,
                  encoding="utf-8-sig")
    print(f"  [CommodityPrices] Wrote {len(df_new)} new rows → {out_path}")
    return len(df_new), len(df_new)


# --------------------------------------------------------------------------
# ENRICHMENT STAGE  (identical logic to macro_events_scraper.py)
# --------------------------------------------------------------------------

NUMERIC_PATTERNS = {
    "RBI_Monetary": [
        (r"repo rate[^.\n]{0,40}?(\d{1,2}\.\d{1,2})\s*%", "repo_rate"),
        (r"(?:kept|keeps|left|held|holds|maintained|retained)[^.\n]{0,25}?rate[s]?[^.\n]{0,20}?(\d{1,2}\.\d{1,2})\s*%", "repo_rate_held"),
        (r"(?:cut|hike|raise[ds]?|reduce[ds]?)[^.\n]{0,30}?(\d{1,3})\s*(?:bps|basis points)", "rate_change_bps"),
        (r"crr[^.\n]{0,30}?(\d{1,2}\.?\d{0,2})\s*%", "crr"),
        (r"slr[^.\n]{0,30}?(\d{1,2}\.?\d{0,2})\s*%", "slr"),
        (r"(?:stance|policy stance)[^.\n]{0,30}?(neutral|accommodative|withdrawal of accommodation|hawkish|dovish)", "stance"),
        (r"gdp (?:growth )?(?:forecast|projection|estimate)[^.\n]{0,40}?(\d{1,2}\.?\d{0,2})\s*%", "gdp_forecast"),
        (r"inflation (?:forecast|projection|target)[^.\n]{0,40}?(\d{1,2}\.?\d{0,2})\s*%", "inflation_forecast"),
    ],
    "India_Macro": [
        (r"cpi[^.\n]{0,40}?(\d{1,2}\.\d{1,2})\s*%", "cpi_yoy"),
        (r"retail inflation[^.\n]{0,40}?(\d{1,2}\.\d{1,2})\s*%", "retail_inflation"),
        (r"(?:cpi|retail inflation|inflation)[^.\n]{0,30}?(?:eased|rose|climbed|fell|cooled|accelerated|slowed)\s*to\s*(\d{1,2}\.\d{1,2})\s*%", "inflation_to"),
        (r"wpi[^.\n]{0,40}?(-?\d{1,2}\.\d{1,2})\s*%", "wpi"),
        (r"gdp grew[^.\n]{0,30}?(\d{1,2}\.\d{1,2})\s*%", "gdp_growth"),
        (r"gdp growth[^.\n]{0,30}?(\d{1,2}\.\d{1,2})\s*%", "gdp_growth"),
        (r"iip[^.\n]{0,40}?(-?\d{1,2}\.\d{1,2})\s*%", "iip"),
        (r"industrial production[^.\n]{0,40}?(-?\d{1,2}\.\d{1,2})\s*%", "industrial_production"),
        (r"pmi[^.\n]{0,30}?(\d{1,3}\.?\d{0,2})", "pmi_value"),
        (r"trade deficit[^.\n]{0,40}?\$?\s?(\d{1,3}\.?\d{0,2})\s*(?:billion|bn)", "trade_deficit_usd_bn"),
        (r"forex reserves[^.\n]{0,40}?\$?\s?(\d{1,4}\.?\d{0,2})\s*(?:billion|bn)", "forex_reserves_usd_bn"),
        (r"fiscal deficit[^.\n]{0,40}?(\d{1,2}\.?\d{0,2})\s*%", "fiscal_deficit_pct_gdp"),
    ],
    "US_Macro": [
        (r"fed(?:eral reserve)?[^.\n]{0,40}?(?:cut|hike|raise[ds]?|lower[ds]?)[^.\n]{0,30}?(\d{1,3})\s*(?:bps|basis points)", "fed_rate_change_bps"),
        (r"federal funds rate[^.\n]{0,40}?(\d{1,2}\.\d{1,2})\s*%", "fed_funds_rate"),
        (r"target range[^.\n]{0,40}?(\d{1,2}\.\d{1,2})\s*%", "fed_target_range"),
        (r"(?:kept|keeps|held|holds|left|maintained)[^.\n]{0,25}?rate[s]?[^.\n]{0,20}?(\d{1,2}\.\d{1,2})\s*%", "fed_funds_held"),
        (r"us cpi[^.\n]{0,40}?(\d{1,2}\.\d{1,2})\s*%", "us_cpi_yoy"),
        (r"us inflation[^.\n]{0,40}?(\d{1,2}\.\d{1,2})\s*%", "us_inflation"),
        (r"ppi[^.\n]{0,40}?(-?\d{1,2}\.\d{1,2})\s*%", "us_ppi"),
        (r"non-?farm payrolls[^.\n]{0,40}?(\d{1,3}(?:,\d{3})?)\s*(?:jobs)?", "nonfarm_payrolls"),
        (r"unemployment rate[^.\n]{0,40}?(\d{1,2}\.\d{1,2})\s*%", "unemployment_rate"),
        (r"ism[^.\n]{0,30}?pmi[^.\n]{0,30}?(\d{1,3}\.?\d{0,2})", "ism_pmi"),
        (r"10[\s-]year treasury yield[^.\n]{0,30}?(\d{1,2}\.\d{1,3})\s*%", "us_10y_yield"),
        (r"dollar index[^.\n]{0,30}?(\d{1,3}\.\d{1,2})", "dxy"),
    ],
    "Commodities": [
        (r"brent[^.\n]{0,30}?\$\s?(\d{1,3}\.?\d{0,2})", "brent_usd_bbl"),
        (r"wti[^.\n]{0,30}?\$\s?(\d{1,3}\.?\d{0,2})", "wti_usd_bbl"),
        (r"gold[^.\n]{0,30}?(?:rs\.?|₹)\s?(\d{1,3}(?:,\d{3})*)", "gold_price_inr"),
        (r"gold[^.\n]{0,30}?\$\s?(\d{1,4}\.?\d{0,2})", "gold_price_usd"),
        (r"(?:usd|dollar)[^.\n]{0,20}?(?:inr|rupee)[^.\n]{0,20}?(\d{1,3}\.\d{1,2})", "usd_inr"),
        (r"rupee[^.\n]{0,30}?(\d{1,3}\.\d{1,2})\s*(?:against|per|vs)", "usd_inr_alt"),
        (r"steel price[^.\n]{0,30}?(?:rs\.?|₹)\s?(\d{1,3}(?:,\d{3})*)", "steel_price_inr"),
    ],
    "Global_CB": [
        (r"ecb[^.\n]{0,40}?(\d{1,2}\.\d{1,2})\s*%", "ecb_rate"),
        (r"bank of england[^.\n]{0,40}?(\d{1,2}\.\d{1,2})\s*%", "boe_rate"),
        (r"bank of japan[^.\n]{0,40}?(-?\d{1,2}\.\d{1,2})\s*%", "boj_rate"),
        (r"pboc[^.\n]{0,40}?(\d{1,2}\.\d{1,2})\s*%", "pboc_rate"),
        (r"(?:cut|cuts|raised|hiked|held|holds|keeps)[^.\n]{0,45}?(\d{1,2}\.\d{1,2})\s*%", "cb_rate_action"),
        (r"(?:cut|cuts|raised|hiked|lowered)[^.\n]{0,40}?(\d{1,3})\s*(?:bps|basis points)", "cb_rate_change_bps"),
    ],
    "India_Policy": [
        (r"gst[^.\n]{0,30}?(\d{1,2})\s*%", "gst_rate"),
        (r"budget[^.\n]{0,40}?(?:rs\.?|₹)\s?(\d{1,3}(?:,\d{3})*)\s*crore", "budget_allocation_crore"),
        (r"customs duty[^.\n]{0,40}?(\d{1,3})\s*%", "customs_duty"),
        (r"fdi[^.\n]{0,30}?(\d{1,3})\s*%", "fdi_limit"),
    ],
    "Market_Structure": [
        (r"vix[^.\n]{0,20}?(\d{1,2}\.\d{1,2})", "india_vix"),
        (r"fii[^.\n]{0,40}?(?:rs\.?|₹)\s?(-?\d{1,3}(?:,\d{3})*)\s*crore", "fii_flow_crore"),
        (r"dii[^.\n]{0,40}?(?:rs\.?|₹)\s?(-?\d{1,3}(?:,\d{3})*)\s*crore", "dii_flow_crore"),
        (r"nifty[^.\n]{0,30}?(\d{4,5}\.?\d{0,2})", "nifty_level"),
        (r"sensex[^.\n]{0,30}?(\d{5,6}\.?\d{0,2})", "sensex_level"),
    ],
    "AI_Technology": [
        (r"(?:capex|investment)[^.\n]{0,40}?\$\s?(\d{1,4}\.?\d{0,2})\s*(?:billion|bn)", "ai_capex_usd_bn"),
    ],
    "Geopolitical": [],
    "Global_Markets": [
        (r"(?:fell|dropped|crashed|declined)[^.\n]{0,30}?(\d{1,2}\.?\d{0,2})\s*%", "market_fall_pct"),
        (r"(?:rose|gained|rallied)[^.\n]{0,30}?(\d{1,2}\.?\d{0,2})\s*%",            "market_gain_pct"),
        (r"vix[^.\n]{0,20}?(\d{1,2}\.?\d{0,2})",                                     "vix_level"),
        (r"halt(?:ed)?[^.\n]{0,30}?(\d{1,2}\.?\d{0,2})\s*%",                        "halt_trigger_pct"),
    ],
    "Currency_Crisis": [
        (r"(?:usd|dollar)[^.\n]{0,20}?(?:inr|rupee)[^.\n]{0,20}?(\d{1,3}\.\d{1,2})", "usd_inr"),
        (r"(?:fell|dropped|crashed)[^.\n]{0,30}?(\d{1,2}\.?\d{0,2})\s*%",            "currency_fall_pct"),
        (r"dxy[^.\n]{0,20}?(\d{1,3}\.?\d{0,2})",                                     "dxy_level"),
    ],
    "Global_Trade": [
        (r"tariff[^.\n]{0,30}?(\d{1,2})\s*%",                                        "tariff_rate_pct"),
        (r"duty[^.\n]{0,30}?(\d{1,2})\s*%",                                          "duty_rate_pct"),
    ],
}

TAKEAWAY_MARKERS = re.compile(
    r"\b(announced|decided|raised|cut|hiked|lowered|kept unchanged|maintained|"
    r"declared|reported|stood at|rose to|fell to|came in at|grew (?:by|at)|"
    r"contracted|projected|revised|approved|signed|imposed|lifted|held|holds|"
    r"keeps|unchanged|eased to|slowed to)\b",
    re.IGNORECASE,
)


def _domain(url):
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _resolve_google_news_url(google_url):
    """
    Three-method Google News URL resolver:
    Method 1: base64 decode from URL path (fastest, no network)
    Method 2: requests follow redirect (network, 1 call)
    Method 3: newspaper3k built-in resolver
    """
    if "news.google.com" not in google_url:
        return google_url

    # Method 1 — base64 decode
    try:
        path   = urlparse(google_url).path
        parts  = path.split("/articles/")
        if len(parts) >= 2:
            encoded = parts[1].split("?")[0]
            # Try multiple padding variants
            for pad in range(4):
                try:
                    padded        = encoded + "=" * pad
                    decoded_bytes = base64.urlsafe_b64decode(padded)
                    decoded_text  = decoded_bytes.decode("utf-8", errors="ignore")
                    match = re.search(r"https?://[^\x00-\x1f\s\"\\]+", decoded_text)
                    if match:
                        candidate = match.group(0)
                        if "news.google.com" not in candidate:
                            return candidate
                except Exception:
                    continue
    except Exception:
        pass

    # Method 2 — requests redirect follow
    try:
        resp = requests.get(
            google_url,
            headers={"User-Agent": USER_AGENT},
            timeout=ARTICLE_TIMEOUT,
            allow_redirects=True,
        )
        if resp.url and "news.google.com" not in resp.url:
            return resp.url
    except Exception:
        pass

    # Method 3 — newspaper3k
    try:
        import newspaper
        article = newspaper.Article(google_url)
        article.download()
        if article.source_url and "news.google.com" not in article.source_url:
            return article.source_url
    except Exception:
        pass

    return google_url


def _fetch_article_text(url):
    """
    Fetch article text with three-tier fallback:
    Tier 1: newspaper3k (best, handles most paywalls + redirects)
    Tier 2: requests + BeautifulSoup (fallback for sites newspaper3k fails)
    Tier 3: return empty (graceful fail, never crashes pipeline)
    """
    headers = {"User-Agent": USER_AGENT}

    # First resolve Google News redirect
    resolved_url = _resolve_google_news_url(url)
    if resolved_url == url and "news.google.com" in url:
        # Try one more time with requests direct follow
        try:
            resp = requests.get(
                url, headers=headers, timeout=ARTICLE_TIMEOUT,
                allow_redirects=True
            )
            if resp.url and "news.google.com" not in resp.url:
                resolved_url = resp.url
            else:
                return "", "unresolved_url"
        except Exception:
            return "", "unresolved_url"

    # Tier 1 — newspaper3k
    try:
        import newspaper
        article = newspaper.Article(resolved_url)
        article.download()
        article.parse()
        text = article.text.strip()
        if len(text) >= 150:
            return text, "success"
    except Exception:
        pass

    # Tier 2 — requests + BeautifulSoup
    for attempt in range(ARTICLE_RETRIES + 1):
        try:
            resp = requests.get(
                resolved_url, headers=headers,
                timeout=ARTICLE_TIMEOUT, allow_redirects=True
            )
            if resp.status_code in (403, 429):
                return "", "blocked"
            if resp.status_code != 200:
                continue

            _soup = BeautifulSoup(resp.content, "html.parser")
            for tag in _soup(["script", "style", "nav", "header",
                              "footer", "aside", "form", "iframe", "noscript"]):
                tag.decompose()

            article_tag = _soup.find("article")
            paragraphs  = article_tag.find_all("p") if article_tag else _soup.find_all("p")
            text = " ".join(p.get_text(" ", strip=True) for p in paragraphs)
            text = re.sub(r"\s+", " ", text).strip()

            if len(text) >= 100:
                return text, "success"
            return text, "failed"

        except requests.exceptions.Timeout:
            continue
        except Exception:
            continue

    return "", "failed"


def _extract_numbers(category, text):
    if not text:
        return ""
    patterns = NUMERIC_PATTERNS.get(category, [])
    found = []
    seen = set()
    text_lower = text.lower()
    for pattern, label in patterns:
        m = re.search(pattern, text_lower, re.IGNORECASE)
        if m:
            pair = f"{label}={m.group(1)}"
            if pair not in seen:
                seen.add(pair)
                found.append(pair)
    return " | ".join(found)


def _extract_key_takeaway(text, max_sentences=3):
    if not text:
        return ""

    sentences = re.split(r"(?<=[.!?])\s+", text)
    scored = []
    for idx, s in enumerate(sentences):
        has_number = bool(re.search(r"\d", s))
        has_marker = bool(TAKEAWAY_MARKERS.search(s))
        if has_number or has_marker:
            score = (2 if has_number and has_marker else 1)
            scored.append((score, idx, s.strip()))

    if not scored:
        return " ".join(sentences[:max_sentences]).strip()[:600]

    scored.sort(key=lambda x: (-x[0], x[1]))
    chosen = sorted(scored[:max_sentences], key=lambda x: x[1])
    top = [s for _, _, s in chosen]
    return " ".join(top).strip()[:600]


def enrich_item(row):
    link = row.get("link", "")
    category = row.get("category", "")

    if not link:
        return {
            "extracted_numbers": "",
            "key_takeaway": "",
            "article_text_snippet": "",
            "fetch_status": "skipped_no_link",
        }

    text, status = _fetch_article_text(link)

    if status == "unresolved_url":
        return {
            "extracted_numbers": "",
            "key_takeaway": "",
            "article_text_snippet": "",
            "fetch_status": "unresolved_url",
        }

    if status == "success":
        numbers  = _extract_numbers(category, text)
        takeaway = _extract_key_takeaway(text)
        snippet  = text[:500]
    else:
        numbers  = ""
        takeaway = ""
        snippet  = text[:500] if text else ""

    return {
        "extracted_numbers": numbers,
        "key_takeaway": takeaway,
        "article_text_snippet": snippet,
        "fetch_status": status,
    }


# --------------------------------------------------------------------------
# LLM SIGNAL VALIDATION  (TIER 1 — opt-in via --llm-classify)
# Uses Anthropic Claude to independently score each article that passed the
# keyword gate. Results are stored ALONGSIDE keyword severity — never overwrite.
# Requires: pip install anthropic && ANTHROPIC_API_KEY env var set.
# --------------------------------------------------------------------------

def classify_with_llm(title: str, snippet: str, keyword_severity: int, api_key: str) -> dict:
    """
    Call Google Gemini 2.0 Flash to independently classify an article's severity.
    Returns a dict with:
      llm_severity          : int 1-5 (or None on failure)
      llm_confidence        : float 0.0-1.0 (or None on failure)
      is_genuine_disruption : bool
      llm_corridor          : str (the corridor the LLM thinks this is about)
      llm_justification     : str (one sentence)
      review_flagged        : bool — True if LLM severity disagrees with
                              keyword_severity by >= 2 points

    Gracefully returns a "skipped" result on any API error — never raises.
    Includes exponential backoff retries for 429 rate limit errors.
    """
    _SKIP = {
        "llm_severity": None,
        "llm_confidence": None,
        "is_genuine_disruption": None,
        "llm_corridor": "",
        "llm_justification": "",
        "review_flagged": False,
        "llm_status": "skipped",
    }
    if not api_key or api_key == "your_gemini_api_key_here":
        return {**_SKIP, "llm_status": "no_api_key"}

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return {**_SKIP, "llm_status": "google_genai_not_installed"}

    PROMPT = (
        "You are a geopolitical risk analyst for India's crude oil supply chain.\n"
        "Classify the article below and return ONLY valid JSON matching the schema.\n"
        f"Headline: {title}\n"
        f"Snippet: {snippet[:600]}\n\n"
        "JSON Schema:\n"
        "{\n"
        '  "is_genuine_disruption_signal": bool,  // true if this describes a real supply disruption\n'
        '  "corridor": string,  // one of: hormuz, red_sea, suez, cape_of_good_hope, russia_route, malacca, india_domestic, none\n'
        '  "llm_severity": integer,  // 1 (minor mention) to 5 (critical disruption)\n'
        '  "confidence": float,  // 0.0 to 1.0\n'
        '  "one_line_justification": string  // max 20 words, cite only text shown\n'
        "}\n\n"
        "Rules:\n"
        "- Only use information in the headline and snippet above.\n"
        "- Do NOT add external facts or vessel positions.\n"
        "- Output ONLY the raw JSON object. Do not wrap in markdown code blocks."
    )

    client = genai.Client(api_key=api_key)
    retries = 2
    delay = 2.0
    import random as _random

    for attempt in range(retries + 1):
        try:
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=PROMPT,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            raw = response.text.strip()
            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            
            import json as _json
            parsed = _json.loads(raw)
            llm_sev = int(parsed.get("llm_severity", 0))
            llm_conf = float(parsed.get("confidence", 0.0))
            is_genuine = bool(parsed.get("is_genuine_disruption_signal", False))
            corridor = str(parsed.get("corridor", ""))
            justif = str(parsed.get("one_line_justification", ""))
            review_flagged = abs(llm_sev - keyword_severity) >= 2

            return {
                "llm_severity":          llm_sev,
                "llm_confidence":        round(llm_conf, 3),
                "is_genuine_disruption": is_genuine,
                "llm_corridor":          corridor,
                "llm_justification":     justif,
                "review_flagged":        review_flagged,
                "llm_status":            "ok",
            }
        except Exception as e:
            err_str = str(e).lower()
            is_rate_limited = "429" in err_str or "resource" in err_str or "exhausted" in err_str or "limit" in err_str
            if is_rate_limited and attempt < retries:
                sleep_time = delay * (2 ** attempt) + _random.uniform(0.1, 1.0)
                print(f"       [Rate Limit] 429 received. Retrying in {sleep_time:.2f}s...")
                time.sleep(sleep_time)
            else:
                print(f"       [LLM Error] {e}")
                status_msg = "skipped_rate_limited" if is_rate_limited else f"error: {e}"
                return {**_SKIP, "llm_status": status_msg}

    return {**_SKIP, "llm_status": "skipped_rate_limited"}


def fetch_existing_hashes(conn):
    """
    Query Postgres for every content_hash already stored in macro_events.
    Used to SKIP enrichment (the expensive article fetch + extraction step)
    for articles that have already been fetched and stored in a previous
    run — critical on a short rolling window where the same event reappears
    across many consecutive invocations before it ages out.

    Returns a set() of hex digest strings. Returns an empty set (never
    raises) if the query fails, so a DB hiccup degrades to "enrich
    everything" rather than crashing the run.
    """
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT content_hash FROM macro_events")
            return {row[0] for row in cur.fetchall()}
    except Exception as e:
        print(f"   [!] Could not fetch existing content hashes ({e}); "
              f"will enrich all surviving items this run.")
        return set()


def enrich_dataframe(df, existing_hashes=None, llm_classify=False, llm_api_key=""):
    """
    Fetch every surviving article NOT already present in existing_hashes
    and attach enrichment columns.
    Then, if llm_classify is True, sample at most 40 articles (ranked by severity/recency)
    and validate them using Google Gemini 2.0 Flash with rate-limit protections.
    """
    existing_hashes = existing_hashes or set()
    total = len(df)

    to_enrich_mask = []
    skip_count = 0
    for title in df["title"]:
        if db_writer is not None:
            h = db_writer.compute_content_hash(title)
        else:
            import hashlib
            h = hashlib.sha256(str(title).encode()).hexdigest()
        already_known = h in existing_hashes
        to_enrich_mask.append(not already_known)
        if already_known:
            skip_count += 1

    print(f"\nEnrichment stage: {total} items, {skip_count} already known "
          f"(skipping fetch), {total - skip_count} to fetch...")

    enriched_records = []
    for i, (row, should_enrich) in enumerate(zip(df.to_dict("records"), to_enrich_mask), 1):
        if not should_enrich:
            enriched_records.append({
                "extracted_numbers": "",
                "key_takeaway": "",
                "article_text_snippet": "",
                "fetch_status": "skipped_already_known",
            })
            continue

        domain = _domain(row.get("link", ""))
        print(f"  [{i}/{total}] {row.get('category','?'):16s} | {domain or 'no-domain'} | {row['title'][:50]}...")
        result = enrich_item(row)
        enriched_records.append(result)
        print(f"       -> status={result['fetch_status']}, "
              f"numbers={'yes' if result['extracted_numbers'] else 'no'}")
        time.sleep(ARTICLE_FETCH_DELAY)

    enrich_df = pd.DataFrame(enriched_records)
    df = df.reset_index(drop=True)
    enrich_df = enrich_df.reset_index(drop=True)
    df_combined = pd.concat([df, enrich_df], axis=1)

    # ---- Rate-limit-safe Gemini validation sample (Capped at 40) ----
    llm_cols = ["llm_severity", "llm_confidence", "is_genuine_disruption", 
                "llm_corridor", "llm_justification", "review_flagged", "llm_status"]
    
    for col in llm_cols:
        df_combined[col] = None

    if llm_classify and llm_api_key and llm_api_key != "your_gemini_api_key_here":
        print(f"\nLLM classification: ON (Google Gemini 2.0 Flash - Free Tier Sample)")
        
        # Select candidates: has snippet and passed keyword filter (severity > 0)
        df_combined["severity_numeric"] = pd.to_numeric(df_combined["severity"], errors="coerce").fillna(0).astype(int)
        
        candidates = df_combined[
            (df_combined["article_text_snippet"].notna()) & 
            (df_combined["article_text_snippet"].str.strip() != "") &
            (df_combined["severity_numeric"] > 0)
        ].copy()
        
        if not candidates.empty:
            # Sort by severity (descending), then date (descending)
            candidates["parsed_date"] = pd.to_datetime(candidates["date"], errors="coerce")
            candidates = candidates.sort_values(
                by=["severity_numeric", "parsed_date"], 
                ascending=[False, False]
            )
            
            sampled_indices = candidates.index[:MAX_LLM_CLASSIFICATIONS_PER_RUN]
            print(f"Sampling {len(sampled_indices)} out of {len(candidates)} eligible articles for AI validation...")
            
            for idx in sampled_indices:
                row = df_combined.loc[idx]
                title = row.get("title", "")
                snippet = row.get("article_text_snippet", "")
                kw_sev = int(row.get("severity_numeric", 0))
                
                print(f"  Validating: {title[:45]}... (kw_severity={kw_sev})")
                llm_res = classify_with_llm(title, snippet, kw_sev, llm_api_key)
                
                for k, v in llm_res.items():
                    df_combined.at[idx, k] = v
                
                flag_str = " [REVIEW_FLAGGED]" if llm_res.get("review_flagged") else ""
                print(f"       -> llm_severity={llm_res.get('llm_severity')} status={llm_res.get('llm_status')}{flag_str}")
                
                # Gemini free tier safety delay: 4.0s (15 requests/minute max)
                time.sleep(4.0)

            # Mark all other rows as skipped_capped
            df_combined.loc[~df_combined.index.isin(sampled_indices), "llm_status"] = "skipped_capped"
        else:
            print("No eligible articles found for LLM validation.")
            df_combined["llm_status"] = "skipped_no_candidates"
    else:
        df_combined["llm_status"] = "not_requested" if not llm_classify else "no_api_key"

    if "severity_numeric" in df_combined.columns:
        df_combined = df_combined.drop(columns=["severity_numeric"])
    if "parsed_date" in df_combined.columns:
        df_combined = df_combined.drop(columns=["parsed_date"])

    return df_combined


# --------------------------------------------------------------------------
# Convert the final DataFrame into rows shaped for db_writer.upsert_macro_events()
# --------------------------------------------------------------------------

def _to_db_macro_rows(df):
    rows = []
    for rec in df.to_dict("records"):
        event_date_str = rec.get("date", "")
        try:
            event_date = date.fromisoformat(event_date_str[:10])
        except Exception:
            continue  # unparseable date — skip rather than insert garbage

        rows.append({
            "event_date":            event_date,
            "title":                 rec.get("title", ""),
            "source":                rec.get("source", ""),
            "link":                  rec.get("link", ""),
            "category":              rec.get("category", ""),
            "affected_sectors":      rec.get("affected_sectors", ""),
            "affected_companies":    rec.get("affected_companies", ""),
            "buffer_layer":          rec.get("buffer_layer", "none") or "none",
            "corridor":              rec.get("corridor", "none") or "none",
            "severity":              int(rec.get("severity", 0) or 0),
            "extracted_numbers":     rec.get("extracted_numbers", ""),
            "key_takeaway":          rec.get("key_takeaway", ""),
            "article_text_snippet":  rec.get("article_text_snippet", ""),
            "fetch_status":          rec.get("fetch_status", "failed"),
        })
    return rows


# --------------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------------

def build_arg_parser():
    parser = argparse.ArgumentParser(description="Live macro events pipeline for Indian markets")
    parser.add_argument("--output",    default=DEFAULT_OUTPUT_DIR, help="Output folder path")
    parser.add_argument("--from-date", default=None, help="Start date YYYY-MM-DD (defaults to 7 days ago)")
    parser.add_argument("--to-date",   default=None, help="End date YYYY-MM-DD (inclusive; defaults to today)")
    parser.add_argument("--no-enrich", action="store_true",
                         help="Skip full-article fetch + numeric extraction (fast RSS-only mode)")
    parser.add_argument("--max-items-per-query", type=int, default=DEFAULT_MAX_ITEMS_PER_QUERY,
                         help="Cap on items kept per query (default 20)")
    parser.add_argument("--keep-previews", action="store_true",
                         help="Disable the outcome gate; keep pre-event preview/expectation "
                              "articles for data-release categories too")
    parser.add_argument("--no-db", action="store_true",
                         help="Skip Postgres entirely — CSV backups only (dry run; also skips "
                              "the existing-hash lookup, so enrichment runs on everything)")
    parser.add_argument("--llm-classify", action="store_true",
                         help="After enrichment, call Google Gemini (gemini-2.0-flash) to independently "
                              "classify each article's severity (capped sample of 40). Requires GEMINI_API_KEY env var. "
                              "Adds llm_severity, llm_confidence, review_flagged columns to CSV. "
                              "Skipped (no error) if key is missing.")
    return parser


def resolve_default_dates(from_date, to_date):
    today = date.today()
    if from_date is None and to_date is None:
        from_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        to_date = today.strftime("%Y-%m-%d")
    elif from_date is None:
        from_date = (date.fromisoformat(to_date) - timedelta(days=7)).strftime("%Y-%m-%d")
    elif to_date is None:
        to_date = today.strftime("%Y-%m-%d")
    return from_date, to_date


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    args.from_date, args.to_date = resolve_default_dates(args.from_date, args.to_date)

    os.makedirs(args.output, exist_ok=True)
    print(f"Output dir : {args.output}")
    print(f"Date range : {args.from_date} to {args.to_date}")
    print(f"Queries    : {len(MACRO_QUERIES)}")
    print(f"Max/query  : {args.max_items_per_query}")
    print(f"Enrichment : {'OFF (--no-enrich)' if args.no_enrich else 'ON (skips already-known articles)'}")
    print(f"Outcome gate: {'OFF (--keep-previews)' if args.keep_previews else 'ON (results only for RBI/Macro/Fed/CB)'}")
    print("=" * 60)

    # ---- Open DB connection early (parent process) so we can fetch
    # existing content hashes BEFORE enrichment, not just before upsert ----
    conn = None
    run_id = None
    if not args.no_db and db_writer is not None:
        try:
            conn = db_writer.get_connection()
            run_id = db_writer.start_pipeline_run(conn, "live_macro_pipeline")
        except RuntimeError as e:
            print(f"DB connection failed: {e}")
            print("Continuing in CSV-only mode for this run.")
            conn = None
    elif not args.no_db and db_writer is None:
        print("[!] db_writer module not found — running in CSV-only mode (--no-db behaviour).")

    existing_hashes = fetch_existing_hashes(conn) if conn else set()

    # ---- Fetch ----
    # ---- Fetch ----
    all_items  = []
    seen_links = set()

    # Official RSS feeds first (highest priority)
    print("\nFetching official RSS feeds...")
    official_items = fetch_official_rss(args.from_date, to_date_str=args.to_date)
    for item in official_items:
        if item["link"] not in seen_links:
            seen_links.add(item["link"])
            all_items.append(item)
    print(f"Official RSS: {len(official_items)} items fetched")

    for idx, (category, query) in enumerate(MACRO_QUERIES, 1):

        print(f"[{idx}/{len(MACRO_QUERIES)}] {category} | {query[:60]}...")
        items = fetch_query(category, query, args.from_date, to_date_str=args.to_date,
                             max_items=args.max_items_per_query,
                             keep_previews=args.keep_previews)
        print(f"      -> {len(items)} items")

        for item in items:
            if item["link"] not in seen_links:
                seen_links.add(item["link"])
                all_items.append(item)

        time.sleep(REQUEST_DELAY)

    print(f"\nFetched {len(all_items)} unique items before deduplication")

    df = pd.DataFrame(all_items)
    if df.empty:
        print("No items fetched. Check network / date range.")
        if conn:
            db_writer.finish_pipeline_run(conn, run_id, 0, 0, 0, status="success")
            conn.close()
        return

    # ---- Single-pass dedup: Jaccard clustering + official-source priority,
    # grouped by (category, date) ----
    df["_group"] = df["category"] + "|" + df["date"]
    filtered_rows = []
    for group_key, group_df in df.groupby("_group", sort=False):
        items_in_group = group_df.drop(columns=["_group"]).to_dict("records")
        kept = _deduplicate_day_group(items_in_group)
        filtered_rows.extend(kept)

    df_filtered = pd.DataFrame(filtered_rows)
    df_filtered = df_filtered.sort_values(["date", "category"], ascending=[False, True])
    df_filtered = df_filtered.drop(columns=["_group"], errors="ignore")
    df_filtered = df_filtered.reset_index(drop=True)

    removed = len(all_items) - len(df_filtered)
    print(f"After deduplication: {len(df_filtered)} items ({removed} removed)")

    # ---- Enrichment (skips anything already in existing_hashes) ----
    llm_key = GEMINI_API_KEY if args.llm_classify else ""
    if not args.no_enrich:
        df_filtered = enrich_dataframe(
            df_filtered,
            existing_hashes=existing_hashes,
            llm_classify=args.llm_classify,
            llm_api_key=llm_key,
        )
    else:
        for col in ["extracted_numbers", "key_takeaway", "article_text_snippet", "fetch_status",
                    "llm_severity", "llm_confidence", "review_flagged", "llm_status"]:
            df_filtered[col] = ""

    out_cols = ["date", "title", "source", "link", "category",
                "affected_sectors", "affected_companies",
                "buffer_layer", "corridor", "severity",
                "extracted_numbers", "key_takeaway",
                "article_text_snippet", "fetch_status",
                # LLM validation columns (present only when --llm-classify was used)
                "llm_severity", "llm_confidence", "is_genuine_disruption",
                "llm_corridor", "llm_justification", "review_flagged", "llm_status"]
    df_filtered = df_filtered[[c for c in out_cols if c in df_filtered.columns]]

    # ---- CSV backups (unchanged from macro_events_scraper.py) ----
    master_path = os.path.join(args.output, "macro_events_filtered.csv")
    df_filtered.to_csv(master_path, index=False, encoding="utf-8-sig")
    print(f"\nSaved master file: {master_path}")

    for cat, cat_df in df_filtered.groupby("category"):
        cat_path = os.path.join(args.output, f"{cat}_events.csv")
        cat_df.to_csv(cat_path, index=False, encoding="utf-8-sig")
        print(f"  {cat}: {len(cat_df)} items -> {cat_path}")

    # ---- Ancillary data fetches (run after main news pipeline) ----
    # These are independent of the news dedup/enrich/upsert flow and write
    # their own dedicated CSV files in the same output directory.
    fetch_ofac_sanctions_list(args.output)
    fetch_commodity_prices(args.output)

    # ---- Postgres upsert (parent process, same connection used for the
    # existing-hash lookup above) ----
    if args.no_db:
        print("\n--no-db set: skipping Postgres upsert.")
        print("Done.")
        return

    if conn is None:
        print("\nNo DB connection available — CSV backups were written successfully, "
              "but nothing was upserted to Postgres.")
        return

    print("\nUpserting to Postgres...")
    db_status = "success"
    error_message = None
    inserted = skipped = 0

    try:
        db_rows = _to_db_macro_rows(df_filtered)
        inserted, skipped = db_writer.upsert_macro_events(conn, db_rows)
        print(f"DB upsert done. Fetched: {len(db_rows)}, Inserted: {inserted}, Skipped: {skipped}")
    except Exception as e:
        db_status = "failed"
        error_message = str(e)
        print(f"DB upsert FAILED: {e}\n{traceback.format_exc()}")
    finally:
        db_writer.finish_pipeline_run(
            conn, run_id, len(df_filtered), inserted, skipped,
            status=db_status, error_message=error_message,
        )
        conn.close()

    print(f"\nDone. Run id: {run_id}")


if __name__ == "__main__":
    main()


# ============================================================================
# live_macro_pipeline_schedule_notes
# ============================================================================
# This script performs exactly ONE pass per invocation and then exits — it
# does not loop or sleep internally. The scheduler (run_pipeline.py /
# scheduler.py, built separately) is responsible for calling it.
#
#   Every 15-30 minutes, all day (matches the original architecture doc's
#   "after-hours macro" cadence, but run continuously since macro/geopolitical
#   news isn't constrained to Indian market hours the way company news is):
#
#       python live_macro_pipeline.py
#           --from-date <today - 7 days, YYYY-MM-DD>
#           --to-date   <today, YYYY-MM-DD>
#
#   08:30 IST daily (the "morning-ready" pass, same timing as the company
#   pipeline's final pre-market pass):
#
#       python live_macro_pipeline.py
#           --from-date <today - 7 days, YYYY-MM-DD>
#           --to-date   <today, YYYY-MM-DD>
#
#       No special flags needed for this run specifically — the 7-day
#       rolling window naturally re-covers anything published overnight,
#       and the content_hash check inside enrich_dataframe() means articles
#       already enriched in a prior run are NOT re-fetched, so this 8:30 AM
#       pass is cheap even though it re-scans the full week.
#
#   WHY A 7-DAY WINDOW INSTEAD OF "TODAY ONLY": macro events (RBI MPC
#   outcomes, Fed decisions, GDP releases) often get follow-up coverage,
#   analysis pieces, and corrections for several days after the initial
#   release. A 1-day window would miss legitimate same-event coverage that
#   publishes a day or two late. The content_hash skip-on-enrich logic is
#   what makes the wider window cheap to re-run constantly — duplicate
#   detection (via _deduplicate_day_group) plus the enrich-skip together
#   mean only genuinely NEW items ever trigger a real article fetch.
#
#   The scheduler should run this AFTER live_company_pipeline.py's 8:30 AM
#   pass completes (or in parallel, since they write to different tables
#   and the only shared resource is the Postgres connection pool, which
#   should comfortably handle both running concurrently) — there is no
#   hard ordering dependency between the two pipelines.
# ============================================================================
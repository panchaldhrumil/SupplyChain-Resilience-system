================================================================================
         INDIA ENERGY RESILIENCE DASHBOARD — PS2 HACKATHON
    AI-Driven Supply Chain Resilience for India's Crude Oil Ecosystem
================================================================================

                     "Know the disruption before it hits the refinery gate."

================================================================================
WHAT WE HAVE BUILT
================================================================================

We have built a full-stack, AI-powered energy intelligence platform that monitors
geopolitical disruptions to India's crude oil supply chain in real-time, assesses
their financial and operational impact, and autonomously recommends procurement
responses — all without a single analyst needing to touch a keyboard.

India imports approximately 88% of its crude oil from overseas. Every barrel
crosses at least one of the world's seven critical maritime chokepoints —
Strait of Hormuz, Red Sea / Bab-el-Mandeb, Suez Canal, Cape of Good Hope,
Strait of Malacca, the Russia Black Sea route, or domestic coastal logistics.
When any of these corridors is disrupted, India's refineries have a finite
window — roughly 87 days of combined SPR + refinery stock + crude-on-water
buffer — before they face feedstock shortfalls.

Our platform turns that 87-day window into an actionable decision surface by:

  * Ingesting thousands of real-time geopolitical, sanctions, and commodity
    news articles every day from 40+ global news sources
  * Scoring each shipping corridor's risk using a time-decay model (articles
    from this morning matter more than articles from last week)
  * Firing an autonomous alert the moment any corridor score crosses a
    critical threshold — and attaching a ranked alternative sourcing list
    to that alert, automatically
  * Showing policymakers and procurement teams exactly how many days of buffer
    they have, which suppliers can fill the gap, and at what transit cost

The platform is live, all data is real, and the autonomous agent has already
fired three disruption alerts — including Hormuz reaching a risk score of 100.0.

--------------------------------------------------------------------------------
THE FOUR DASHBOARD TABS
--------------------------------------------------------------------------------

TAB 1: RISK AGENT MAP
-----------------------
The first thing a user sees is a dark-themed, interactive world map built on
Leaflet.js. Overlaid on the map are colour-coded risk corridors — red for
critical (score >=66), amber for elevated (>=33), green for nominal (<33).
Eleven Indian refinery pins show capacity on hover; four major crude import
ports (Mumbai, Vadinar, Paradip, Kandla) are marked.

To the right of the map are two live panels:
  * Riskometer — an arc gauge showing the highest-risk corridor score (currently
    Hormuz at 100.0)
  * All Corridor Scores — a ranked list of all 7 corridors with their numeric
    score and a trend arrow (rising / falling / stable)

Below the map, three intelligence panels run in parallel:
  * LIVE ALERTS — cards that fire when a corridor newly crosses the threshold.
    Each card shows the score jump (e.g. 9.4 -> 100.0), the top procurement
    recommendation, buffer coverage in days, and sub-step latency breakdown.
    Every alert card has an expandable "Why was this triggered?" section that
    pulls the top 3 supporting news articles on demand.
  * INTELLIGENCE BRIEF — a Gemini 2.0 Flash AI-generated analyst narrative
    (2-3 sentences) grounded exclusively in real scraped articles from the
    last 48 hours. Users select a corridor and receive an instant prose brief
    with numbered source citations. No hallucinations — the model is explicitly
    instructed to use only the provided articles.
  * LIVE INTELLIGENCE FEED — a scrollable, filterable list of all scraped
    articles. Filter by corridor (Hormuz, Red Sea, etc.) or by category
    (Sanctions, Commodities, Geopolitics, Alt Crude Sourcing, etc.)

TAB 2: SCENARIO SIMULATOR
---------------------------
Policymakers can model specific disruption scenarios: What happens if the Strait
of Hormuz is fully blocked? What if Red Sea transits drop by 60%? The simulator
returns three numbers instantly:
  * Supply gap as % of India's daily crude intake
  * Refinery run-rate impact as % reduction in throughput
  * Projected retail fuel price impact in % terms
These are backed by documented elasticity assumptions (IEA methodology) and
India's actual import mix percentages (MoPNG Annual Report data).

TAB 3: PROCUREMENT ENGINE
---------------------------
When a disruption is confirmed, the Procurement Engine answers: "Who do we
buy from instead?" The user selects the disrupted source country or corridor,
sets how much volume needs replacing (5-100% of that source's contribution)
and the maximum acceptable transit time (5-45 days). The engine then ranks up
to 7 alternative crude-source countries using a weighted multi-criteria model:
  * Transit speed and sailing distance (40% weight)
  * Chokepoint safety of the alternative route (40% weight)
  * Historical supply reliability score (20% weight)
Google Gemini AI then generates a procurement justification for each ranked
alternative in a single bulk API call (optimized to avoid 7 separate calls).
While the 10-12 second Gemini call runs, the UI shows animated skeleton cards,
a "Controls Locked" indicator, and cycling status messages so the user always
knows the system is working.

TAB 4: RESERVE OPTIMIZER
--------------------------
The Reserve Optimizer answers: "How long do we actually have?" It displays
India's national energy buffer in three layers:
  * Strategic Petroleum Reserve (SPR): 6.1 days at 64% fill
    (Source: PIB press release, March 2026)
  * Refinery + Depot Stock: 64.5 days
    (Source: PPAC Annual Report FY2024-25)
  * Crude on Water (tankers in transit): 16.7 days (modeled estimate)
  Total verified buffer: 87.3 days

An interactive SPR Drawdown Calculator lets users input a supply gap % and
disruption duration to see exactly how many days the SPR covers and whether
the total buffer is sufficient. A live commodity prices chart (Brent Crude,
WTI, USD/INR) from Yahoo Finance sits alongside the calculator, providing
real-time market context for procurement cost estimates.

================================================================================
HOW THE TECHNOLOGY WORKS
================================================================================

--------------------------------------------------------------------------------
DATA FETCHING -- NEWS PARSING AND WEB SCRAPING
--------------------------------------------------------------------------------

Every article in the system comes from real published sources. We use two
primary ingestion mechanisms:

  RSS FEED PARSER
  We built a custom RSS feed collector (backend/pipeline/collectors/rss.py)
  using the Python feedparser library. We have configured 40+ RSS feed URLs
  spanning Google News, Reuters, The Economic Times, Bloomberg, The Hindu
  Business Line, OilPrice.com, S&P Global Platts, and Financial Times.
  Each feed is categorized into thematic buckets:
    - Geopolitics (sanctions, wars, naval incidents)
    - Commodities (crude price, refinery margins)
    - Alt_Crude_Sourcing (supply diversification)
    - AI_Technology (energy transition signals)
    - Green_Transition (renewable energy context)
  The collector runs in parallel across all feeds and captures title, source,
  publication timestamp, and article link. feedparser handles malformed XML
  gracefully and the collector de-duplicates titles using hash fingerprinting
  before any further processing.

  OFAC SANCTIONS SCRAPER
  The sanctions collector (backend/pipeline/collectors/sanctions.py) downloads
  the US Treasury OFAC SDN (Specially Designated Nationals) list in CSV format
  directly from https://www.treasury.gov/ofac/downloads/sdn.csv. This is a
  live, official government endpoint. The download uses a custom User-Agent
  header and a (10s connect, 30s read) timeout to handle the ~7MB file
  reliably. The 19,173 SDN entities are batch-upserted into PostgreSQL using
  execute_values for performance.

  COMMODITY PRICE FETCHER
  Live commodity prices (Brent crude BZ=F, WTI CL=F, USD/INR INR=X) are
  fetched from Yahoo Finance using the yfinance Python library. This gives us
  a real 7-day OHLCV time series for all three instruments at zero cost.

--------------------------------------------------------------------------------
NLP -- CORRIDOR TAGGING AND KEYWORD CLASSIFICATION
--------------------------------------------------------------------------------

Once articles are collected, they are assigned to one or more shipping corridors
using a keyword-rules classifier (backend/pipeline/processors/corridor_tagger.py).
This is a deterministic NLP approach:

  For each article title, we run regex pattern matching against a curated
  vocabulary per corridor:
    hormuz      : ["hormuz", "strait of hormuz", "iran", "persian gulf", "oman gulf", ...]
    red_sea     : ["red sea", "bab-el-mandeb", "houthi", "yemen", "aden", ...]
    suez        : ["suez", "suez canal", "egypt", "mediterranean", ...]
    russia_route: ["russia", "black sea", "caspian", "ural blend", "espo crude", ...]
    india_domestic: ["petrol price", "diesel price", "lpg", "iocl", "bpcl", ...]
    malacca     : ["malacca", "singapore", "strait of malacca", ...]
    cape_of_good_hope: ["cape of good hope", "cape route", "south africa", ...]

  Articles that match no corridor are tagged as "global" and still stored for
  the general intelligence feed but excluded from corridor scoring.
  Articles can match multiple corridors (e.g., an Iran sanctions article tags
  both hormuz and russia_route).

  Severity is pre-assigned by category (Geopolitics = 4, Commodities = 3,
  etc.) and optionally overridden by Gemini LLM classification (see below).

--------------------------------------------------------------------------------
CORRIDOR RISK SCORING -- TIME-DECAY MODEL
--------------------------------------------------------------------------------

The risk score for each corridor is computed from all articles tagged to it
using an exponential time-decay model:

  Raw Score = Sum( severity_i * e^(-lambda * hours_since_published_i) )
  where lambda = ln(2) / 36   (half-life of 36 hours)

  Normalized Score = min( raw / 25.0 * 100, 100 )

This means:
  - A severity-5 article published 1 hour ago contributes nearly full weight
  - The same article published 36 hours ago contributes half weight
  - After 5 days, its contribution is negligible (~3%)

The denominator 25.0 was calibrated so that ~5 high-severity concurrent
articles push a corridor to 100. This maps cleanly to real-world events:
the Hormuz corridor hit exactly 100 during our hackathon period due to
Houthi escalation, Iran posturing, and tanker diversion reports arriving
simultaneously in the news stream.

--------------------------------------------------------------------------------
LARGE LANGUAGE MODEL USAGE -- GEMINI 2.0 FLASH
--------------------------------------------------------------------------------

We use Google Gemini 2.0 Flash for three distinct AI tasks:

  1. INTELLIGENCE BRIEF GENERATION (RAG-Grounded)
     When a user requests a corridor brief, the system retrieves the top
     8-10 most recent articles for that corridor from PostgreSQL, formats
     them with their titles, sources, and key takeaways, and passes them
     as context to Gemini with this instruction:
       "Write a 2-3 sentence analyst-grade narrative for [corridor].
        Base it ONLY on the articles provided. Do NOT invent any facts,
        numbers, or events not present in the source material."
     This is Retrieval-Augmented Generation (RAG) -- the model is anchored
     to real data, not generating from its training weights. The response
     is displayed with numbered citations in the UI.

  2. PROCUREMENT JUSTIFICATION (BULK BATCHING)
     After the weighted scoring algorithm ranks alternative suppliers, Gemini
     generates a one-paragraph justification for each supplier. Instead of
     making 7 separate API calls (one per supplier), we batch all 7 into a
     single prompt with a structured JSON output format. This reduces latency
     from ~70 seconds to ~10-12 seconds and conserves API quota.

  3. LLM SIGNAL VALIDATION (OPTIONAL, --llm-classify FLAG)
     When the pipeline runs with --llm-classify, Gemini evaluates each
     scraped article and returns:
       * is_genuine_disruption: True/False
       * llm_severity: 1-5 (overrides keyword-based severity if higher)
       * llm_confidence: 0.0-1.0
       * llm_justification: one-sentence reason
     This builds an audit trail of LLM decision-making visible in the
     LLM Validation stats panel on the dashboard.

  GEMINI KEY ROTATION (4-KEY ROUND-ROBIN POOL)
  To avoid hitting per-key rate limits (429 quota errors), we maintain a
  thread-safe pool of 4 Gemini API keys in backend/pipeline/gemini_pool.py.
  Keys are used in round-robin order. On any 429 error, the pool immediately
  rotates to the next key and retries. If all 4 keys are exhausted, the
  corridor brief falls back to auto-compiled prose from article key_takeaways,
  labeled clearly in the UI.

--------------------------------------------------------------------------------
VECTOR STORE -- SEMANTIC SEARCH (QDRANT CLOUD)
--------------------------------------------------------------------------------

For semantic similarity search beyond keyword matching, we use Qdrant Cloud
as our vector database. Each article is embedded as a 768-dimensional vector
using Gemini text-embedding-004 and stored in a collection named "macro_events"
with cosine similarity distance.

When the corridor brief endpoint is called, Qdrant retrieves the semantically
closest articles to the corridor query (e.g., "Strait of Hormuz crude oil
tanker disruption") — catching articles that match conceptually even if they
don't contain exact keywords like "hormuz". This makes the intelligence brief
richer and more accurate than pure keyword retrieval.

If the qdrant-client package is not installed, the system transparently falls
back to PostgreSQL ILIKE full-text search. This graceful degradation means
the platform works fully even without the vector layer.

--------------------------------------------------------------------------------
DATABASE -- NEON POSTGRESQL (CLOUD-NATIVE)
--------------------------------------------------------------------------------

All structured data is stored in Neon PostgreSQL, a serverless cloud
PostgreSQL database with connection pooling via SSL. We chose Neon because:
  * No infrastructure management (serverless, auto-scales to zero)
  * PostgreSQL-compatible (standard psycopg2 works directly)
  * Free tier supports the full prototype data volume
  * SSL pooler URL works behind corporate firewalls

We use six tables:
  macro_events          -- 2,087 scraped articles with all metadata
  corridor_score_history -- 371 score snapshots for trend analysis
  alerts                -- 3 real disruption alerts with full latency breakdown
  sanctions             -- 19,173 OFAC SDN entities
  commodity_prices      -- 7-day price history for Brent, WTI, USD/INR
  agent_state           -- single-row persistent state for the agent

Batch writes use psycopg2's execute_values for bulk INSERT performance:
  * 19,173 sanctions rows inserted in ~3 seconds
  * 2,087 news articles inserted in a single transaction

For read operations (API layer), we use thin helper functions:
  * query_df(sql)  -- returns a pandas DataFrame
  * query_rows(sql)-- returns a list of dict rows

--------------------------------------------------------------------------------
BACKGROUND SCHEDULER -- AUTOMATED PIPELINE CRON
--------------------------------------------------------------------------------

The scheduler (backend/scheduler.py) runs two recurring jobs using APScheduler:

  JOB 1: DAILY PIPELINE (every 24 hours)
  Runs the full data pipeline: RSS collection, OFAC download, commodity
  prices, deduplication, corridor tagging, DB upsert, and Qdrant vector
  upsert. Protected by a threading lock so a slow pipeline run never
  overlaps with the next scheduled run. Every run is logged to a JSONL
  audit file: backend/data/scheduler_runs.jsonl.

  JOB 2: DISRUPTION RESPONSE AGENT (every 5 minutes)
  Calls the autonomous agent to compute current corridor scores, compare
  with the previous cycle, detect threshold crossings, and fire alerts.
  After each cycle, the agent writes a new row to corridor_score_history
  for trend analysis. The 5-minute interval is configurable via the
  AGENT_INTERVAL_SECONDS environment variable.

  The scheduler can be started independently of the API server:
    python scheduler.py
  This allows it to run as a background service or systemd unit in production.

--------------------------------------------------------------------------------
THE AUTONOMOUS DISRUPTION RESPONSE AGENT
--------------------------------------------------------------------------------

The agent (backend/agent/response_agent.py) is the core intelligence engine.
It follows a Perceive -> Compare -> Detect -> Act -> Save -> Log loop:

  PERCEIVE: Query macro_events for all articles in the last 48 hours,
            compute corridor scores using the decay formula.

  COMPARE:  Load the previous cycle's scores from agent_state.

  DETECT:   Find any corridor where prev_score < 66 <= current_score
            (first-time threshold crossing only -- no duplicate alerts).

  ACT:      For each detected crossing:
            1. Load the knowledge graph (country to chokepoint mapping)
            2. Identify all countries whose crude routes through that corridor
            3. Sum their import_share_pct from import_mix.json = supply_gap
            4. Calculate buffer_days from buffer_config.json
            5. Rank alternative suppliers (weighted algorithm)
            6. Record timestamps at each sub-step for latency audit

  SAVE:     Write current scores to agent_state for the next cycle.

  LOG:      Insert alert row into DB alerts table. This is what the
            /api/auto-alerts endpoint serves to the frontend.

The entire Detect -> Act cycle for Hormuz completed in 142ms (without LLM)
and 10,844ms (with LLM procurement justification). This means a policymaker
sees the alert and recommendation within 11 seconds of the score crossing
the threshold -- far faster than any human monitoring workflow.

================================================================================
THE FINANCIAL DIMENSION
================================================================================

This platform was designed with direct financial decision support in mind.
Every feature has a rupee or dollar figure attached to it.

IMPORT COST EXPOSURE
  India imports ~4.8 million barrels of crude per day. At current Brent prices
  of approximately $90/barrel, that is ~$432 million of daily crude exposure.
  A 25% Hormuz disruption for 30 days = $3.24 billion in alternative sourcing
  costs at premium prices. Our Scenario Simulator computes this exposure directly.

BUFFER MONETIZATION
  The SPR Drawdown Calculator tells policymakers the exact cost of releasing
  strategic reserves vs. paying spot market premiums for alternative crude.
  At a $15/barrel premium over benchmark for emergency diversification to
  West African crude, a 25% gap for 30 days adds ~$540 million to import costs.

PROCUREMENT COST RANKING
  The Procurement Engine does not just rank by risk -- it implicitly ranks by
  cost. Transit days are a direct proxy for shipping cost (VLCC at $50,000/day
  over 22 days Nigeria to Vadinar = ~$1.1M freight per cargo). Shorter transit
  alternatives score higher, saving procurement cost.

COMMODITY PRICE INTEGRATION
  The live Brent/WTI/USD-INR chart on the Reserve Optimizer tab provides
  real-time context for all procurement decisions. A weakening rupee
  (higher USD/INR) means the same barrel costs more in domestic currency.
  The chart makes this visible alongside buffer calculations.

SANCTIONS RISK
  Procuring from sanctioned entities exposes India to secondary sanctions
  under the US OFAC framework. Our 19,173-entity sanctions database helps
  procurement teams screen alternative suppliers before deal closure,
  potentially avoiding billions in penalty exposure.

REFINERY EFFICIENCY IMPACT
  The Scenario Simulator quantifies refinery run-rate impact as a percentage.
  A 15% run-rate reduction at India's 258.1 MMTPA refinery capacity costs
  the downstream industry approximately $2.1 billion annually in lost margins
  (at a $6/barrel refinery margin). Early alert = earlier substitution =
  higher run-rate preservation = direct financial gain.

================================================================================
WHO CAN USE THIS PRODUCT
================================================================================

--------------------------------------------------------------------------------
FOR THE MINISTRY OF PETROLEUM AND NATURAL GAS (MoPNG)
--------------------------------------------------------------------------------

The platform gives the Ministry a live operational view of India's crude supply
chain risk that currently does not exist in a single unified system.

  SITUATION ROOM USE:
  The Risk Agent Map can run on a large display in a ministry situation room
  or war room, auto-refreshing every 60 seconds. During a Hormuz crisis, the
  duty officer sees the score jump in real time and receives an immediate
  procurement recommendation without waiting for an analyst report.

  POLICY DECISION SUPPORT:
  The Scenario Simulator lets ministry officials run "what-if" analysis:
  "If Hormuz is blocked for 30 days, how many days does our SPR cover?
  What is the retail price impact? Do we need to mandate refinery rationing?"
  These questions currently take days to answer. The platform answers them
  in seconds, backed by cited data sources.

  SPR POLICY:
  The Reserve Optimizer directly supports SPR drawdown decisions by showing
  how many days of coverage exist across three buffer layers and at what gap
  percentage the SPR becomes insufficient. The formulas and data sources are
  all cited (PIB, PPAC, ISPRL) for policy memo justification.

  SANCTIONS COMPLIANCE:
  When considering alternative crude purchases from non-traditional suppliers,
  the ministry team can search the 19,173-entity OFAC database within the
  dashboard to check for sanctions exposure before any deal is signed.

  DAILY INTELLIGENCE BRIEF:
  The corridor intelligence brief can replace or supplement daily analyst
  reports. Each brief is Gemini-generated from real articles, takes ~8 seconds
  to generate, and includes source citations. This saves 2-4 analyst hours per
  corridor per day.

--------------------------------------------------------------------------------
FOR INDIA'S MAJOR REFINERIES (IOCL, BPCL, HPCL, RIL, MRPL, CPCL, OMPL)
--------------------------------------------------------------------------------

Refinery procurement teams work on 30-90 day crude purchase horizons. They need
to know about disruption signals before VLCC freight rates spike and spot market
supply tightens.

  EARLY WARNING ADVANTAGE:
  A refinery team monitoring the dashboard would have seen Hormuz's score
  begin rising from 9.4 before it hit 100.0. This provides a procurement
  window to begin sourcing alternative crude before freight premiums spike.
  Industry data shows that early alternative sourcing (10-15 days ahead)
  saves $3-8/barrel on spot premiums on emergency cargoes.

  ALTERNATIVE SOURCE RANKING:
  The Procurement Engine directly serves refinery procurement teams. When
  they need to replace Saudi or Iraqi crude, they input the volume and transit
  preference and receive a ranked shortlist of Nigeria, USA, UAE, Kazakhstan,
  etc. with transit times and route safety scores. This shortens the sourcing
  decision cycle from days to minutes.

  FEEDSTOCK PLANNING:
  The SPR Drawdown Calculator helps refinery planning teams understand how
  much time they have before feedstock shortfalls hit the gate. Combined with
  their own inventory data, they can optimize crude switching timelines to
  minimize refinery configuration costs (hydrotreater adjustments, etc.).

  COMMODITY PRICE ALERTS:
  The live Brent/WTI/USD-INR dashboard gives traders and pricing desks a
  real-time context panel linked directly to supply disruption signals. A
  Brent price spike on the chart alongside a rising Hormuz score provides
  corroborating evidence for hedging decisions.

  SANCTIONS SCREENING:
  When a refinery's trading desk is evaluating a spot purchase from a
  non-traditional counterparty, the sanctions search tool provides instant
  OFAC SDN list verification.

================================================================================
FURTHER ENHANCEMENTS AND FUTURE SCOPE
================================================================================

The current prototype demonstrates full end-to-end capability with real data.
The following enhancements would take it to an enterprise-grade product:

--------------------------------------------------------------------------------
NEAR-TERM ENHANCEMENTS (1-3 Months)
--------------------------------------------------------------------------------

  AIS VESSEL TRACKING INTEGRATION
  Replace the "Estimated" crude-on-water figure with real AIS (Automatic
  Identification System) vessel tracking data via providers like MarineTraffic
  or FleetMon APIs. This would give actual tanker positions, ETAs, and cargo
  declarations for the ~53 VLCCs in transit to India at any given time.

  AUTOMATED SANCTIONS SCREENING
  Build a fuzzy-matching pipeline that automatically checks article-mentioned
  entities (companies, individuals, vessels) against the OFAC SDN list and
  flags matches in the intelligence feed with a warning badge.

  PRICE FORECASTING MODEL
  Integrate a time-series forecasting model (Prophet or LSTM) trained on
  historical Brent/WTI data, corridor risk scores, and OPEC production data
  to project crude prices 7-30 days out under different disruption scenarios.

  EMAIL / SMS ALERT DELIVERY
  Extend the autonomous agent to deliver disruption alerts via email (SMTP)
  and SMS (Twilio) to registered ministry and refinery stakeholders, so they
  receive alerts even when the dashboard is not open.

  REFINERY-SPECIFIC DASHBOARDS
  Build role-based views: a ministry dashboard (macro policy view) vs. a
  refinery dashboard (feedstock procurement view). Each refinery could input
  its own crude processing slate (which grades it can run) and get
  recommendations filtered to compatible crude types.

  FREIGHT RATE INTEGRATION
  Pull live VLCC freight rates (Baltic Dirty Tanker Index) and factored transit
  cost into the Procurement Engine's final score, giving procurement teams a
  direct total landed cost estimate per alternative source.

--------------------------------------------------------------------------------
MEDIUM-TERM ENHANCEMENTS (3-6 Months)
--------------------------------------------------------------------------------

  MULTI-MODAL DATA INGESTION
  Extend ingestion beyond text articles to include:
    * Satellite imagery analysis (port congestion, tanker queue detection)
    * Social media monitoring (Twitter/X for breaking geopolitical signals)
    * METAR weather data for Cape of Good Hope and Bab-el-Mandeb
      (seasonal weather affects route safety scoring)

  ADVANCED KNOWLEDGE GRAPH
  Replace the current LightweightKnowledgeGraph with a full graph database
  (Neo4j or Amazon Neptune) connecting: Countries <-> Corridors <-> Refineries
  <-> Crude Grades <-> Geopolitical Events. This enables multi-hop reasoning:
  "A US sanction on Iran affects Hormuz which affects IOCL Panipat's
  Basra Light intake which affects automotive LPG pricing in Punjab."

  LLM FINE-TUNING FOR ENERGY DOMAIN
  Fine-tune a smaller open-source LLM (Mistral 7B or LLaMA 3) on India
  energy policy documents, MoPNG reports, and PPAC data to create a
  domain-specialist model for corridor briefs. This reduces Gemini API
  dependency and improves India-specific contextual accuracy.

  SCENARIO PLANNING WORKBENCH
  Allow ministry analysts to create, save, and share custom disruption
  scenarios with named parameters (e.g., "Iran-US War Scenario Q3 2026")
  including probability weights and confidence intervals on each impact
  figure. Saved scenarios become a policy library.

  HISTORICAL BACKTESTING
  Run the corridor scoring model against the full historical article archive
  (2020-present) to show how the system would have scored events like the
  2021 Suez Canal blockage (Ever Given), 2022 Russia sanctions, and 2023-24
  Red Sea Houthi escalation. This validates the model's lead-time advantage.

--------------------------------------------------------------------------------
LONG-TERM VISION (6-18 Months)
--------------------------------------------------------------------------------

  NATIONAL ENERGY DIGITAL TWIN
  Build a complete digital twin of India's energy supply chain: upstream
  (international crude producers), midstream (shipping corridors, tanker
  fleet), and downstream (refineries, depot network, retail distribution).
  The twin would run Monte Carlo simulations of supply shocks and output
  probability distributions over price and availability impacts.

  AUTOMATED PROCUREMENT EXECUTION
  With regulatory approval, connect the procurement recommendation engine
  directly to India's strategic crude oil procurement workflow. When a
  disruption alert fires, the system could auto-draft term sheet parameters
  for alternative suppliers for human review and approval.

  MULTI-COMMODITY EXTENSION
  Extend the platform beyond crude oil to cover LNG (critical as India's
  gas import dependency grows), fertilizer feedstocks (urea/ammonia, heavily
  dependent on Russia and the Middle East), and semiconductor supply chains
  (India's growing fab sector).

  REGIONAL ASEAN-PLUS DEPLOYMENT
  License the platform to other emerging-economy energy ministries: Indonesia,
  Vietnam, Bangladesh, Sri Lanka. All face similar crude import dependency
  and chokepoint exposure. The corridor model is geography-agnostic; only
  the import_mix.json and buffer_config.json need to change per country.

  CARBON AND TRANSITION INTEGRATION
  As India transitions under its 2070 net-zero commitment, integrate a
  carbon intensity tracker per crude source into the Procurement Engine.
  Future procurement optimization will balance price, security of supply,
  and Scope 3 emissions per barrel -- giving green-transition co-benefits
  alongside energy security.

================================================================================
                         END OF DOCUMENT
================================================================================

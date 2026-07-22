import re

# --------------------------------------------------------------------------
# MACRO EVENT QUERY DEFINITIONS
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

    ("Currency_Crisis", "Turkish lira crash currency crisis"),
    ("Currency_Crisis", "Japanese yen carry trade unwind"),
    ("Currency_Crisis", "rupee hits all time low dollar"),
    ("Currency_Crisis", "emerging market currency sell-off"),
    ("Currency_Crisis", "dollar index DXY surge emerging markets"),
    ("Currency_Crisis", "yuan devaluation China currency"),
    ("Currency_Crisis", "South Korean won crash"),
    ("Currency_Crisis", "Brazil real Argentina peso crisis"),

    ("Commodities",     "LME aluminium copper nickel price crash"),
    ("Commodities",     "COMEX gold silver futures price"),
    ("Commodities",     "natural gas price spike Europe India"),
    ("Commodities",     "wheat corn soybean price India impact"),
    ("Commodities",     "Baltic dry index shipping freight"),
    ("Commodities",     "coal price Australia India import"),

    ("Global_Trade",    "US tariff announcement India impact"),
    ("Global_Trade",    "WTO trade ruling India"),
    ("Global_Trade",    "India US trade deal bilateral"),
    ("Global_Trade",    "China export restriction India supply chain"),
    ("Global_Trade",    "semiconductor chip export control India"),
    ("Global_Trade",    "India export ban restriction commodity"),
    ("Global_Trade",    "anti-dumping duty India steel chemical"),

    ("Geopolitical",    "strait of hormuz oil disruption shipping"),
    ("Geopolitical",    "North Korea missile test market reaction"),
    ("Geopolitical",    "Taiwan strait China military drill market"),
    ("Geopolitical",    "OPEC plus production decision oil price"),
    ("Geopolitical",    "Russia gas pipeline Europe energy crisis"),
    ("Geopolitical",    "South China Sea tension shipping route"),

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

    ("India_Refinery_Ops", "IOC Indian Oil refinery maintenance shutdown"),
    ("India_Refinery_Ops", "BPCL refinery capacity utilisation output"),
    ("India_Refinery_Ops", "HPCL refinery throughput maintenance turnaround"),
    ("India_Refinery_Ops", "Reliance Jamnagar refinery capacity output"),
    ("India_Refinery_Ops", "India refinery crude throughput data"),
    ("India_Refinery_Ops", "India refinery planned shutdown turnaround"),
    ("India_Refinery_Ops", "CPCL NRL refinery capacity utilisation"),
    ("India_Refinery_Ops", "India petroleum product output PPAC data"),
    ("India_Refinery_Ops", "India refinery capacity expansion upgrade"),

    ("India_SPR", "India strategic petroleum reserve release"),
    ("India_SPR", "ISPRL crude oil storage reserve India"),
    ("India_SPR", "India strategic crude reserve Vizag underground"),
    ("India_SPR", "India strategic reserve Mangalore cavern"),
    ("India_SPR", "Padur strategic petroleum reserve India"),
    ("India_SPR", "India emergency petroleum reserve drawdown"),
    ("India_SPR", "India SPR expansion new storage capacity"),
    ("India_SPR", "IEA India strategic reserve coordination"),

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

    ("Fuel_Substitution", "India ethanol blending petrol percentage target"),
    ("Fuel_Substitution", "ethanol blending programme India E20"),
    ("Fuel_Substitution", "coal gasification India policy syngas"),
    ("Fuel_Substitution", "LNG import India price regasification terminal"),
    ("Fuel_Substitution", "India LNG spot cargo price import"),
    ("Fuel_Substitution", "compressed natural gas CNG price India"),
    ("Fuel_Substitution", "India biofuel policy blending mandate"),
    ("Fuel_Substitution", "India green hydrogen fuel substitute"),

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
# SECTOR + COMPANY IMPACT MAPPING
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

# --------------------------------------------------------------------------
# CORRIDOR IMPACT MAP
# --------------------------------------------------------------------------
CORRIDOR_IMPACT_MAP = [
    (["strait of hormuz", "hormuz closure", "hormuz blockade",
      "hormuz disruption", "hormuz attack", "hormuz tension"],
     {"buffer_layer": "on_water", "corridor": "hormuz", "severity": 5}),

    (["red sea attack", "houthi attack", "bab-el-mandeb", "bab el mandeb",
      "red sea shipping", "red sea disruption", "red sea tanker",
      "houthi missile", "houthi drone"],
     {"buffer_layer": "on_water", "corridor": "red_sea", "severity": 4}),

    (["suez canal", "suez closure", "suez blocked", "suez disruption",
      "suez transit", "ever given"],
     {"buffer_layer": "on_water", "corridor": "suez", "severity": 4}),

    (["cape of good hope", "cape rerouting", "good hope tanker",
      "longer route tanker", "rerouting via cape"],
     {"buffer_layer": "on_water", "corridor": "cape_of_good_hope", "severity": 2}),

    (["russia crude route", "russia ukraine shipping", "black sea oil",
      "urals crude", "russia oil export", "russia pipeline",
      "russia oil ban", "russian crude"],
     {"buffer_layer": "on_water", "corridor": "russia_route", "severity": 3}),

    (["malacca strait", "strait of malacca", "malacca shipping",
      "malacca piracy", "south china sea shipping"],
     {"buffer_layer": "on_water", "corridor": "malacca", "severity": 3}),

    (["panama canal", "panama drought", "panama shipping delay"],
     {"buffer_layer": "on_water", "corridor": "cape_of_good_hope", "severity": 2}),

    (["opec cut", "opec production cut", "opec plus", "crude oil price spike",
      "oil supply disruption", "oil embargo", "tanker attack",
      "oil sanctions", "iran oil", "iran sanctions", "venezuela oil"],
     {"buffer_layer": "on_water", "corridor": "none", "severity": 3}),

    (["brent crude", "wti crude", "crude oil", "brent price",
      "oil price surge", "oil price crash", "oil rally"],
     {"buffer_layer": "on_water", "corridor": "none", "severity": 2}),

    (["strategic petroleum reserve", "isprl", "spr release", "spr drawdown",
      "strategic crude reserve", "vizag reserve", "mangalore cavern",
      "padur reserve", "emergency reserve"],
     {"buffer_layer": "spr", "corridor": "none", "severity": 3}),

    (["refinery shutdown", "refinery maintenance", "refinery turnaround",
      "refinery capacity", "refinery throughput", "refinery output",
      "ioc refinery", "bpcl refinery", "hpcl refinery",
      "reliance refinery", "jamnagar refinery", "cpcl refinery"],
     {"buffer_layer": "refinery_stock", "corridor": "none", "severity": 3}),

    (["ethanol blending", "e20", "coal gasification", "lng import",
      "lng terminal", "cng price", "biofuel", "green hydrogen",
      "fuel substitution"],
     {"buffer_layer": "refinery_stock", "corridor": "none", "severity": 2}),

    (["petrol price", "diesel price", "lpg price", "lpg cylinder",
      "fuel price revision", "under-recovery", "omc pricing"],
     {"buffer_layer": "refinery_stock", "corridor": "india_domestic", "severity": 2}),
]

_CORRIDOR_NO_MATCH = {"buffer_layer": "none", "corridor": "none", "severity": 0}

# --------------------------------------------------------------------------
# SOURCE PRIORITY
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
    "ppac.gov.in": 1000,
    "ppac.gov": 1000,
    "eia.gov": 1000,
    "iea.org": 1000,
}

NEWS_SOURCE_PRIORITY = {
    "reuters": 90,
    "bloomberg": 90,
    "associated press": 88, "ap news": 88,
    "press trust of india": 88, "pti": 88,
    "ani": 82,
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
    "nikkei": 75,
    "south china morning post": 70, "scmp": 70,
    "korea herald": 65,
    "yonhap": 65,
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

# --------------------------------------------------------------------------
# RELEVANCE & STOP WORDS
# --------------------------------------------------------------------------
RELEVANCE_KEYWORDS = {
    "rbi", "india", "nifty", "sensex", "rupee", "sebi", "bse", "nse",
    "indian", "fed", "fomc", "opec", "crude", "iran", "oil", "inflation",
    "gdp", "repo", "rate", "growth", "market", "stock", "fiscal", "budget",
    "gst", "imf", "china", "dollar", "dxy", "treasury", "yield", "mpc",
    "ai", "nvidia", "semiconductor", "geopolit", "war", "ceasefire", "sanctions",
    "fii", "dii", "nifty50", "supply chain", "tariff", "trade",
    "ongc", "reliance", "tata", "infosys", "hdfc", "sbi",
    "kospi", "nikkei", "dax", "ftse", "nasdaq", "s&p", "dow",
    "circuit breaker", "trading halt", "flash crash", "sell-off",
    "emerging market", "vix", "risk-off", "lira", "yen", "yuan",
    "won", "real", "peso", "carry trade", "devaluation",
    "lme", "comex", "baltic", "freight", "shipping",
    "wto", "anti-dumping", "bilateral", "export ban",
    "strait", "hormuz", "pipeline", "north korea", "taiwan",
    "suez", "bab-el-mandeb", "malacca", "cape of good hope", "panama",
    "red sea", "tanker", "rerouting", "chokepoint", "houthi",
    "refinery", "throughput", "turnaround", "ioc", "bpcl", "hpcl",
    "ppac", "petroleum", "eia", "iea", "isprl", "spr",
    "vizag", "mangalore", "padur", "strategic reserve",
    "urals", "basra", "bonny light", "arab light", "jamnagar",
    "ethanol", "blending", "lng", "cng", "biofuel", "gasification",
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

# --------------------------------------------------------------------------
# REGEX DEFINITIONS & EXTRACTORS
# --------------------------------------------------------------------------
NUMERIC_VALUE_RE = re.compile(r"-?\d+(?:\.\d+)?\s*(?:%|bps|basis points)")

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

# --------------------------------------------------------------------------
# RSS FEEDS & CONSTANTS
# --------------------------------------------------------------------------
OFFICIAL_RSS_FEEDS = [
    ("RBI_Monetary", "https://www.rbi.org.in/RSS/RSSFeed.aspx?Id=1",  "RBI Press Releases"),
    ("RBI_Monetary", "https://www.rbi.org.in/RSS/RSSFeed.aspx?Id=12", "RBI Monetary Policy"),
    ("India_Policy", "https://www.sebi.gov.in/sebi_data/attachdocs/rss/sebirss.xml", "SEBI Circulars"),
    ("India_Policy", "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3", "PIB Finance"),
    ("India_Policy", "https://finmin.nic.in/rss.xml", "Ministry of Finance"),
    ("India_Macro", "https://mospi.gov.in/rss.xml", "MOSPI"),
    ("US_Macro", "https://www.federalreserve.gov/feeds/press_all.xml", "Federal Reserve"),
    ("US_Macro", "https://www.federalreserve.gov/feeds/speeches.xml",  "Fed Speeches"),
    ("US_Macro", "https://www.bls.gov/feed/bls_latest.rss", "BLS Data"),
    ("Global_CB", "https://www.imf.org/en/News/RSS", "IMF News"),
    ("Global_CB", "https://feeds.worldbank.org/worldbank/pressreleases", "World Bank"),
    ("Global_CB", "https://www.ecb.europa.eu/rss/press.html", "ECB Press"),
    ("Commodities", "https://www.opec.org/opec_web/en/press_room/rss.htm", "OPEC"),
    ("Global_Trade", "https://www.wto.org/english/news_e/news_e.rss", "WTO"),
    ("India_Policy", "https://nsearchives.nseindia.com/content/circulars/circulars.xml", "NSE Circulars"),
    ("India_Fuel_Pricing",    "https://ppac.gov.in/rss.xml",              "PPAC"),
    ("Commodities",           "https://www.eia.gov/rss/news.xml",         "EIA News"),
    ("Commodities",           "https://www.iea.org/feed/news",            "IEA News"),
]

# --------------------------------------------------------------------------
# OFAC
# --------------------------------------------------------------------------
_OFAC_SDN_URL = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.CSV"
_OFAC_SDN_URL_ALT = "https://www.treasury.gov/ofac/downloads/sdn.csv"
_OFAC_SDN_COLS = [
    "ent_num", "sdn_name", "sdn_type", "program", "title",
    "call_sign", "vess_type", "tonnage", "grt", "vess_flag",
    "vess_owner", "remarks",
]

# --------------------------------------------------------------------------
# COMMODITY
# --------------------------------------------------------------------------
_COMMODITY_TICKERS = {
    "BZ=F":  "Brent_Crude_USD_bbl",
    "CL=F":  "WTI_Crude_USD_bbl",
    "INR=X": "USD_INR",
}
MACRO_QUERIES = MACRO_QUERIES

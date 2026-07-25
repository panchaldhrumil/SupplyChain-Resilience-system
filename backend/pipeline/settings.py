import os

from dotenv import load_dotenv
load_dotenv()

_SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_OUTPUT_DIR = os.environ.get("CSV_OUTPUT_DIR") or os.path.join(_SCRIPT_DIR, "data", "macro_events")

REQUEST_DELAY                    = 0.05
ARTICLE_FETCH_DELAY              = 0.8
SIMILARITY_THRESHOLD             = 0.48
ARTICLE_TIMEOUT                  = 10
ARTICLE_RETRIES                  = 1
DEFAULT_MAX_ITEMS_PER_QUERY      = 20
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

GEMINI_API_KEY                   = os.environ.get("GEMINI_API_KEY", "")
MAX_LLM_CLASSIFICATIONS_PER_RUN  = 40

DATABASE_URL                     = os.environ.get("DATABASE_URL", "")
# Neon unpooled (direct) connection — uses less data-transfer quota.
# Set this in .env to the "Direct connection" URL from your Neon dashboard.
# Falls back to DATABASE_URL if not set.
DATABASE_URL_UNPOOLED            = os.environ.get("DATABASE_URL_UNPOOLED", "") or os.environ.get("DATABASE_URL", "")
QDRANT_URL                       = os.environ.get("QDRANT_URL", "")
QDRANT_API_KEY                   = os.environ.get("QDRANT_API_KEY", "")
QDRANT_COLLECTION                = os.environ.get("QDRANT_COLLECTION", "macro_events")

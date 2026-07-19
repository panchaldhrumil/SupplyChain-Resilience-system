import os

# --------------------------------------------------------------------------
# CONFIG / SETTINGS
# --------------------------------------------------------------------------
# Adjusted _SCRIPT_DIR to point to the backend/ root folder, 
# since settings.py is inside backend/pipeline/
_SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Default output: backend/data/macro_events/ (created automatically if missing).
# Override by setting the CSV_OUTPUT_DIR environment variable — the same var
# the FastAPI backend reads so both always point at the same directory.
DEFAULT_OUTPUT_DIR = os.environ.get(
    "CSV_OUTPUT_DIR",
    os.path.join(_SCRIPT_DIR, "data", "macro_events"),
)
REQUEST_DELAY                = 0.05
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

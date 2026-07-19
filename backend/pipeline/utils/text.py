import re
from pipeline.config import STOP_WORDS

def _title_tokens(title):
    words = re.findall(r"[a-zA-Z0-9]+", str(title).lower())
    return set(w for w in words if w not in STOP_WORDS and len(w) > 2)

import ast

with open('live_macro_pipeline.py', 'r', encoding='utf-8') as f:
    source = f.read()

import_str = '''from pipeline.settings import (
    _SCRIPT_DIR, DEFAULT_OUTPUT_DIR, REQUEST_DELAY, ARTICLE_FETCH_DELAY,
    SIMILARITY_THRESHOLD, ARTICLE_TIMEOUT, ARTICLE_RETRIES, DEFAULT_MAX_ITEMS_PER_QUERY,
    USER_AGENT, GEMINI_API_KEY, MAX_LLM_CLASSIFICATIONS_PER_RUN
)
from pipeline.config import (
    MACRO_QUERIES, IMPACT_MAP, CORRIDOR_IMPACT_MAP, _CORRIDOR_NO_MATCH,
    OFFICIAL_SOURCES, NEWS_SOURCE_PRIORITY, RELEVANCE_KEYWORDS, STOP_WORDS,
    GEOPOLITICAL_RELEVANCE_WORDS, ELECTION_NOISE_WORDS, DATA_RELEASE_CATEGORIES,
    PREVIEW_NOISE_WORDS, OUTCOME_SIGNAL_WORDS, CATEGORY_ANCHORS, NUMERIC_VALUE_RE,
    NUMERIC_PATTERNS, TAKEAWAY_MARKERS, OFFICIAL_RSS_FEEDS, _OFAC_SDN_URL,
    _OFAC_SDN_COLS, _COMMODITY_TICKERS
)
from pipeline.utils.dates import _parse_date, _in_date_range, _google_news_window
from pipeline.utils.text import _title_tokens
from pipeline.utils.similarity import _jaccard
from pipeline.utils.urls import _domain, _resolve_google_news_url, _fetch_article_text
'''

class FuncVisitor(ast.NodeVisitor):
    def __init__(self):
        self.funcs_to_remove = []
    def visit_FunctionDef(self, node):
        if node.name in ['_title_tokens', '_jaccard', '_parse_date', '_in_date_range', '_google_news_window', '_domain', '_resolve_google_news_url', '_fetch_article_text']:
            self.funcs_to_remove.append((node.lineno, node.end_lineno))
        self.generic_visit(node)

tree = ast.parse(source)
visitor = FuncVisitor()
visitor.visit(tree)

ranges_to_delete = visitor.funcs_to_remove

# We want to remove the config chunk as well. Let's find its line numbers safely.
lines = source.splitlines()

config_start = None
config_end = None

for i, line in enumerate(lines):
    if '# CONFIG' in line and lines[i-1].startswith('# ---'):
        config_start = i - 1
    if 'def fetch_commodity_prices(' in line:
        config_end = i - 5 # The line `_COMMODITY_TICKERS = { ... }` ends slightly above. 
        # Actually, let's just go up from i until we find '}'
        break

while lines[config_end].strip() != '}':
    config_end -= 1
# Include the '}' line
config_end += 1

ranges_to_delete.append((config_start + 1, config_end))

ranges_to_delete.sort(key=lambda x: x[0], reverse=True)

for start, end in ranges_to_delete:
    del lines[start-1:end]

# Insert imports
idx = 0
for i, line in enumerate(lines):
    if line.startswith('try:'):
        idx = i + 5
        break

lines.insert(idx, import_str)

with open('live_macro_pipeline.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')


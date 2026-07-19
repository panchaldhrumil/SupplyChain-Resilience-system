import re
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

def _parse_date(pub):
    try:
        return parsedate_to_datetime(str(pub)).strftime("%Y-%m-%d")
    except Exception:
        m = re.search(r"\d{1,2}\s+\w{3}\s+\d{4}", str(pub))
        return m.group(0) if m else str(pub)[:10]


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

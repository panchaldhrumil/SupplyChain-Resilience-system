"""
postgres_writer.py
==================
Converts the final DataFrame into DB rows and upserts to Postgres.

Provides:
  to_db_macro_rows — convert DataFrame to list of dicts for db_writer
"""

from datetime import date


def to_db_macro_rows(df):
    """
    Convert the final filtered DataFrame into a list of row dicts shaped
    for db_writer.upsert_macro_events().
    Rows with unparseable dates are silently dropped.
    """
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

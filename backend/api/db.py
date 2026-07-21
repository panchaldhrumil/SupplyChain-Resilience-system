import psycopg2
import pandas as pd

from pipeline.settings import DATABASE_URL


def get_conn():
    if not DATABASE_URL:
        return None
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print(f"[API DB] connection failed: {e}")
        return None


def query_df(sql, params=None):
    conn = get_conn()
    if conn is None:
        return pd.DataFrame()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if cur.description is None:
                return pd.DataFrame()
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
            return pd.DataFrame(rows, columns=cols)
    except Exception as e:
        print(f"[API DB] query_df: {e}")
        return pd.DataFrame()
    finally:
        try:
            conn.close()
        except Exception:
            pass


def query_rows(sql, params=None):
    conn = get_conn()
    if conn is None:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if cur.description is None:
                return []
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as e:
        print(f"[API DB] query_rows: {e}")
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass

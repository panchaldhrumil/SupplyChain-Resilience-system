import os
import requests
import pandas as pd
from datetime import datetime, timezone
from io import StringIO
from pipeline.settings import USER_AGENT
from pipeline.config import _OFAC_SDN_URL, _OFAC_SDN_COLS
try:
    from pipeline.config import _OFAC_SDN_URL_ALT
except ImportError:
    _OFAC_SDN_URL_ALT = "https://www.treasury.gov/ofac/downloads/sdn.csv"


def fetch_ofac_sanctions_list(output_dir, db_conn=None):
    out_path = os.path.join(output_dir, "ofac_sanctions.csv")
    print(f"\n[OFAC] Downloading SDN list from {_OFAC_SDN_URL} ...")

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
    }
    
    resp = None
    urls_to_try = [_OFAC_SDN_URL, _OFAC_SDN_URL_ALT]
    
    for url in urls_to_try:
        try:
            r = requests.get(url, headers=headers, timeout=(5, 12))
            if r.status_code == 200:
                resp = r
                break
            else:
                print(f"  [OFAC] {url} returned HTTP {r.status_code}")
        except Exception as err:
            print(f"  [OFAC] {url} connection/timeout: {err}")

    if not resp or resp.status_code != 200:
        print("  [OFAC] All OFAC download attempts failed or timed out — skipping OFAC refresh.")
        return 0, 0

    try:
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

        existing_ids: set = set()
        if db_conn:
            from pipeline.db import get_existing_sanction_ids
            existing_ids = get_existing_sanction_ids(db_conn)
        elif os.path.exists(out_path):
            try:
                df_existing = pd.read_csv(out_path, dtype=str)
                if "ent_num" in df_existing.columns:
                    existing_ids = set(df_existing["ent_num"].dropna().str.strip())
            except Exception:
                pass

        df_new["new_since_last_run"] = ~df_new["ent_num"].isin(existing_ids)
        new_count = int(df_new["new_since_last_run"].sum())

        if db_conn:
            from pipeline.db import upsert_sanctions
            rows = df_new.to_dict("records")
            upsert_sanctions(db_conn, rows)
            print(f"  [OFAC] Upserted {len(rows)} entries to Neon ({new_count} new)")

        if not os.path.exists(out_path):
            df_new.to_csv(out_path, index=False, encoding="utf-8-sig")
            print(f"  [OFAC] First run — wrote {len(df_new):,} entries to {out_path}")
        else:
            net_new = df_new[df_new["new_since_last_run"]]
            if not net_new.empty:
                net_new.to_csv(out_path, mode="a", header=False, index=False, encoding="utf-8-sig")
                print(f"  [OFAC] Appended {new_count} new entries -> {out_path}")
            else:
                print(f"  [OFAC] No new SDN entries since last run ({len(df_new):,} total).")

        if new_count:
            samples = df_new[df_new["new_since_last_run"]]["sdn_name"].dropna().head(5).tolist()
            print(f"  [OFAC] New names (sample): {', '.join(samples)}")

        return new_count, len(df_new)

    except Exception as e:
        print(f"  [OFAC] fetch_ofac_sanctions_list failed: {e}")
        return 0, 0

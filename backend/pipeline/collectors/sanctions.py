import os
import requests
import pandas as pd
from datetime import datetime, timezone
from io import StringIO
from pipeline.settings import USER_AGENT
from pipeline.config import _OFAC_SDN_URL, _OFAC_SDN_COLS

def fetch_ofac_sanctions_list(output_dir):
    """
    Download the OFAC SDN (Specially Designated Nationals) CSV from the
    public Treasury URL, parse it, and write/append to ofac_sanctions.csv
    in *output_dir*.

    On each run:
    - Compares new entries against the previous file (keyed on ent_num).
    - Flags genuinely new entries with new_since_last_run=True.
    - Appends only net-new rows so the file grows incrementally.

    Returns (new_count, total_count).  Never raises — errors are logged and
    (0, 0) is returned so the main pipeline is unaffected.
    """
    out_path = os.path.join(output_dir, "ofac_sanctions.csv")
    print(f"\n[OFAC] Downloading SDN list from {_OFAC_SDN_URL} ...")

    try:
        resp = requests.get(
            _OFAC_SDN_URL,
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"  [OFAC] HTTP {resp.status_code} — skipped.")
            return 0, 0

        # The SDN CSV has no header; assign the published column names.
        # Use StringIO so we never write temp files.
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

        # Load previous file if it exists, compare on ent_num
        existing_ids: set = set()
        if os.path.exists(out_path):
            try:
                df_existing = pd.read_csv(out_path, dtype=str)
                if "ent_num" in df_existing.columns:
                    existing_ids = set(df_existing["ent_num"].dropna().str.strip())
            except Exception as e:
                print(f"  [OFAC] Could not read existing file ({e}); treating all as new.")

        # Flag net-new entries
        df_new["new_since_last_run"] = ~df_new["ent_num"].isin(existing_ids)
        new_count = int(df_new["new_since_last_run"].sum())

        # Append only net-new rows (or write full file on first run)
        if not os.path.exists(out_path):
            df_new.to_csv(out_path, index=False, encoding="utf-8-sig")
            print(f"  [OFAC] First run - wrote {len(df_new):,} entries to {out_path}")
        else:
            net_new = df_new[df_new["new_since_last_run"]]
            if not net_new.empty:
                net_new.to_csv(out_path, mode="a", header=False, index=False,
                                encoding="utf-8-sig")
                print(f"  [OFAC] Appended {new_count} new entries "
                      f"({len(df_new):,} total in download) -> {out_path}")
            else:
                print(f"  [OFAC] No new SDN entries since last run "
                      f"({len(df_new):,} total in download).")

        # Print a brief sample of newly added names (useful for monitoring)
        if new_count:
            samples = df_new[df_new["new_since_last_run"]]["sdn_name"].dropna().head(5).tolist()
            print(f"  [OFAC] New names (sample): {', '.join(samples)}")

        return new_count, len(df_new)

    except Exception as e:
        print(f"  [OFAC] fetch_ofac_sanctions_list failed: {e}")
        return 0, 0

"""
csv_writer.py
=============
Writes the final filtered DataFrame to CSV backup files.

Provides:
  write_csv_outputs — writes master CSV + per-category CSV files
"""

import os


def write_csv_outputs(df_filtered, output_dir):
    """
    Write master macro_events_filtered.csv and per-category CSV files.
    Identical to the original output logic in live_macro_pipeline.py.
    """
    master_path = os.path.join(output_dir, "macro_events_filtered.csv")
    df_filtered.to_csv(master_path, index=False, encoding="utf-8-sig")
    print(f"\nSaved master file: {master_path}")

    for cat, cat_df in df_filtered.groupby("category"):
        cat_path = os.path.join(output_dir, f"{cat}_events.csv")
        cat_df.to_csv(cat_path, index=False, encoding="utf-8-sig")
        print(f"  {cat}: {len(cat_df)} items -> {cat_path}")

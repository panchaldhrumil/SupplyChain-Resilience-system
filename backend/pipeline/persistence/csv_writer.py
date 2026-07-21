import os


def write_csv_outputs(df_filtered, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    master_path = os.path.join(output_dir, "macro_events_filtered.csv")
    df_filtered.to_csv(master_path, index=False, encoding="utf-8-sig")
    print(f"\nSaved master CSV: {master_path}")
    for cat, cat_df in df_filtered.groupby("category"):
        cat_path = os.path.join(output_dir, f"{cat}_events.csv")
        cat_df.to_csv(cat_path, index=False, encoding="utf-8-sig")
        print(f"  {cat}: {len(cat_df)} items -> {cat_path}")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build SQLite DB (metadata.db) from an existing metadata.tsv.

- Loads metadata.tsv from disk (exactly what fetch_metadata.py wrote or what you edited).
- Ensures helper columns (file_accession, file_download_url) exist.
- Writes full-table SQLite DB with ALL columns preserved (no drops/renames).

Re-run this script any time you change metadata.tsv
"""

import argparse
import os

import pandas as pd
import sqlite3
import yaml
from pathlib import Path

COLUMN_CANDIDATES = {
    "file_accession": ["File accession", "file accession", "Accession", "accession", "accession_id"],
    "file_download_url": ["File download URL", "file download url", "download_url", "href", "file href"],
    "file_format": ["File format", "file format", "Format", "format"],
    "file_type": ["File type", "file type", "Output type", "output type"],
    "assembly": ["Assembly", "assembly", "genome assembly"],
    "assay_title": ["Assay", "assay", "Assay title", "assay title"],
    "organism": ["Biosample organism", "biosample organism", "Organism", "organism"],
    "audit_status": ["Audit status", "audit status"],
}


def first_existing(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


def ensure_helper_columns(df: pd.DataFrame) -> pd.DataFrame:
    if "file_accession" not in df.columns:
        if df.empty:
            df["file_accession"] = pd.Series(dtype=str)
        else:
            src = first_existing(df, COLUMN_CANDIDATES["file_accession"])
            if not src:
                raise SystemExit("Required column not found: file_accession (nor any known alias).")
            df["file_accession"] = df[src]
    if "file_download_url" not in df.columns:
        if df.empty:
            df["file_download_url"] = pd.Series(dtype=str)
        else:
            src = first_existing(df, COLUMN_CANDIDATES["file_download_url"])
            if not src:
                raise SystemExit("Required column not found: file_download_url (nor any known alias).")
            df["file_download_url"] = df[src]
    return df

def get_metadata_paths(cfg):
    in_tsv = Path(os.path.expanduser(cfg.get("metadata_tsv", "metadata.tsv")))
    out_db = Path(os.path.expanduser(cfg.get("metadata_db", "metadata.db")))
    return in_tsv, out_db


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()
    config = yaml.safe_load(open(args.config, "r", encoding="utf-8"))
    in_tsv, out_db = get_metadata_paths(cfg=config)

    if not in_tsv.exists():
        raise SystemExit(f"metadata.tsv not found at {in_tsv}. Run fetch step first or provide the file.")

    # Load TSV with robust settings (handles BOMs and odd headers)
    df = pd.read_csv(in_tsv, sep="\t", dtype=str, encoding="utf-8-sig", engine="python").fillna("")
    print(f"Loaded {len(df)} rows from {in_tsv}")

    # Ensure helper columns; do NOT drop/rename any originals
    df = ensure_helper_columns(df)

    # Write DB (replace)
    conn = sqlite3.connect(out_db)
    try:
        df.to_sql("metadata", conn, if_exists="replace", index=False)
    finally:
        conn.close()
    print(f"Wrote {out_db} with {len(df)} rows and {df.shape[1]} columns.")


if __name__ == "__main__":
    main()

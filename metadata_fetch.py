#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fetch the raw ENCODE metadata TSV and write it verbatim to metadata.tsv.

Reads ONLY the first non-empty, non-comment line of files.txt.
That line can be:
  - a full ENCODE /metadata/ URL, or
  - a one-line list of accessions (ENCFF... or ENCSR...), separated by whitespace/comma/semicolon.

This script does NOT touch the SQLite DB. It only writes metadata.tsv exactly as returned.
"""

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse, urlencode

import requests

from config import read_config

RE_ACC_FILE = re.compile(r"\bENCFF[0-9]{3}[A-Z0-9]{3}\b", re.IGNORECASE)
RE_ACC_EXPT = re.compile(r"\bENCSR[0-9]{3}[A-Z0-9]{3}\b", re.IGNORECASE)


def read_first_useful_line(path: Path) -> str:
    try:
        path.resolve(strict=True)
    except FileNotFoundError:
        return ""
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            return s
    return ""


def sanitize_quotes(s: str) -> str:
    u = s.strip()
    if (u.startswith('"') and u.endswith('"')) or (u.startswith("'") and u.endswith("'")):
        u = u[1:-1].strip()
    return u


def is_url(s: str) -> bool:
    return urlparse(s).scheme in ("http", "https")


def parse_accession_line(s: str):
    return [t for t in re.split(r"[\s,;]+", s.strip()) if t]


def build_metadata_url_from_accessions(tokens):
    files = [t.upper() for t in tokens if RE_ACC_FILE.fullmatch(t)]
    expts = [t.upper() for t in tokens if RE_ACC_EXPT.fullmatch(t)]
    base = "https://www.encodeproject.org/metadata/"
    if files:
        params = [("type", "File")] + [("accession", acc) for acc in files] + [("limit", "all")]
        return base + "?" + urlencode(params)
    if expts:
        params = [("type", "Experiment")] + [("accession", acc) for acc in expts] + [("limit", "all")]
        return base + "?" + urlencode(params)
    raise SystemExit("First line is neither a URL nor valid ENCFF/ENCSR accession list.")


def http_get_text(url: str) -> str:
    r = requests.get(url, headers={"Accept": "text/tsv"}, timeout=180, allow_redirects=True)
    r.raise_for_status()
    return r.text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    cfg = read_config(ap.parse_args().config)

    file_list = Path(cfg.get("file_list", "files.txt"))
    out_tsv = Path(cfg.get("metadata_tsv", "metadata.tsv"))
    if not file_list.exists():
        print(f"INFO: file_list not found {file_list}.", file=sys.stderr)
        return
    raw = read_first_useful_line(file_list)
    if not raw:
        raise SystemExit(f"{file_list} has no usable lines.")
    raw = sanitize_quotes(raw)

    if is_url(raw):
        meta_url = raw
    else:
        meta_url = build_metadata_url_from_accessions(parse_accession_line(raw))

    print("Fetching metadata from:", meta_url)
    text = http_get_text(meta_url)

    out_tsv.write_text(text, encoding="utf-8")
    print(f"Wrote raw TSV to {out_tsv}")


if __name__ == "__main__":
    main()

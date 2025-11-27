from __future__ import annotations
import re
from typing import Iterable, List, Tuple
import urllib.parse
import requests

UA = "encode-batch-tsv/2.0 (+requests)"
BASE = "https://www.encodeproject.org"

# Extract ENCFF... (files) and ENCSR... (experiments) from mixed inputs.
_RE_FILE = re.compile(r"(ENCFF[0-9]{3}[A-Z]{3})")
_RE_EXPT = re.compile(r"(ENCSR[0-9]{3}[A-Z]{3})")

def _collect_ids(values: Iterable[str]) -> tuple[list[str], list[str]]:
    files: List[str] = []
    expts: List[str] = []
    seen_f, seen_e = set(), set()
    for raw in values or []:
        s = str(raw or "")
        m_f = _RE_FILE.search(s)
        if m_f:
            acc = m_f.group(1)
            if acc not in seen_f:
                seen_f.add(acc); files.append(acc)
        m_e = _RE_EXPT.search(s)
        if m_e:
            acc = m_e.group(1)
            if acc not in seen_e:
                seen_e.add(acc); expts.append(acc)
    if not files and not expts:
        raise ValueError("No valid ENCFF or ENCSR accessions found.")
    return files, expts

def _build_query_style_url(files: list[str], expts: list[str]) -> str:
    """
    /metadata/?type=Experiment&limit=all&files.accession=ENCFF...&dataset=/experiments/ENCSR.../
    Returns a URL that should stream TSV when Accept: text/tsv is used.
    """
    params: list[tuple[str, str]] = [("type", "Experiment"), ("limit", "all")]
    for a in files:
        params.append(("files.accession", a))
    for e in expts:
        params.append(("dataset", f"/experiments/{e}/"))
    return f"{BASE}/metadata/?{urllib.parse.urlencode(params, doseq=True)}"

def _build_path_style_url(files: list[str], expts: list[str]) -> str:
    """
    /metadata/type=Experiment&limit=all&files.accession=...&dataset=%2Fexperiments%2FENCSR...%2F/metadata.tsv
    This mirrors the link placed in files.txt by the Batch Download feature.
    """
    # Build an ampersand-joined query string then URL-encode it for a path segment.
    pairs: list[tuple[str, str]] = [("type", "Experiment"), ("limit", "all")]
    pairs += [("files.accession", a) for a in files]
    pairs += [("dataset", f"/experiments/{e}/") for e in expts]
    # Important: we need a raw "a=b&c=d" string, then quote it as a single path part.
    raw_qs = urllib.parse.urlencode(pairs, doseq=True)
    return f"{BASE}/metadata/{urllib.parse.quote(raw_qs, safe='')}/metadata.tsv"

def get_metadata_tsv(selected: Iterable[str]) -> Tuple[bytes, str]:
    """
    Robustly fetches metadata.tsv for the selected ENCFF/ENCSR accessions.
    Strategy:
      1) Use query-style /metadata/?type=Experiment&files.accession=... (preferred)
      2) If ENCODE returns 400, retry with path-style /metadata/<qs>/metadata.tsv
    """
    files, expts = _collect_ids(selected)

    headers = {
        "Accept": "text/tsv; charset=utf-8",
        "User-Agent": UA,
    }

    # Try query-style first
    url = _build_query_style_url(files, expts)
    r = requests.get(url, headers=headers, timeout=180, allow_redirects=True)
    if r.status_code == 200 and r.headers.get("Content-Type", "").startswith("text/tab-separated-values"):
        return r.content

    # Fallback: path-style used by the portal's "files.txt"
    url2 = _build_path_style_url(files, expts)
    r2 = requests.get(url2, headers=headers, timeout=180, allow_redirects=True)
    try:
        r2.raise_for_status()
    except requests.HTTPError as e:
        # Surface ENCODE’s message (helpful when a bad accession slips in)
        snippet = r2.text[:600]
        raise RuntimeError(f"ENCODE metadata error ({r2.status_code}) for {url2} :: {snippet}") from e

    return r2.content

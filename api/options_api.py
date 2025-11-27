from __future__ import annotations

from typing import Dict, Any, List, Tuple, Optional, Set
from urllib.parse import urlencode

import requests

BASE = "https://www.encodeproject.org/search/"
UA = "encode-lite/options/1.2 (+requests)"


# ------------------------
# Basic helpers
# ------------------------

def _http_json(url: str, timeout: int = 60) -> Dict[str, Any]:
    r = requests.get(url, timeout=timeout, headers={"Accept": "application/json", "User-Agent": UA})
    r.raise_for_status()
    return r.json()


def _facet_terms(payload: Dict[str, Any], field_name: str) -> List[Tuple[str, int]]:
    facets = payload.get("facets") or []
    for f in facets:
        if f.get("field") == field_name:
            terms = f.get("terms") or []
            out: List[Tuple[str, int]] = []
            for t in terms:
                key = t.get("key")
                if key:
                    out.append((key, int(t.get("doc_count") or 0)))
            return out
    return []


def _payload(params: List[Tuple[str, str]]) -> Dict[str, Any]:
    url = BASE + "?" + urlencode(params)
    return _http_json(url)


# ------------------------
# Options endpoints
# ------------------------

def get_assays_and_organisms() -> Dict[str, List[str]]:
    params = [
        ("format", "json"),
        ("frame", "embedded"),
        ("type", "Experiment"),
        ("status", "released"),
        ("limit", "0"),
    ]
    p = _payload(params)
    assays = [a for a, _ in sorted(_facet_terms(p, "assay_title"), key=lambda t: (-t[1], t[0].lower()))]
    organisms = [o for o, _ in sorted(_facet_terms(p, "organism.scientific_name"), key=lambda t: (-t[1], t[0].lower()))]
    return {"assays": assays, "organisms": organisms}


def get_targets() -> List[str]:
    params_exp = [
        ("format", "json"),
        ("frame", "embedded"),
        ("type", "Experiment"),
        ("status", "released"),
        ("limit", "0"),
    ]
    pe = _payload(params_exp)
    targets = [t for t, _ in sorted(_facet_terms(pe, "target.label"), key=lambda t: (-t[1], t[0].lower()))]
    if targets:
        return targets

    params_file = [
        ("format", "json"),
        ("frame", "embedded"),
        ("type", "File"),
        ("status", "released"),
        ("limit", "0"),
    ]
    pf = _payload(params_file)
    targets = [t for t, _ in sorted(_facet_terms(pf, "dataset.target.label"), key=lambda t: (-t[1], t[0].lower()))]
    return targets


def get_cell_types() -> List[str]:
    """
    Flat list (legacy).
    """
    params = [
        ("format", "json"),
        ("frame", "embedded"),
        ("type", "Experiment"),
        ("status", "released"),
        ("limit", "0"),
    ]
    p = _payload(params)
    terms = _facet_terms(p, "biosample_ontology.term_name")
    if not terms:
        pf = _payload([
            ("format", "json"),
            ("frame", "embedded"),
            ("type", "File"),
            ("status", "released"),
            ("limit", "0"),
        ])
        terms = _facet_terms(pf, "replicates.library.biosample.biosample_ontology.term_name")
    return [k for k, _ in sorted(terms, key=lambda t: t[0].casefold())]


def get_assemblies(organism: Optional[str]) -> List[str]:
    params: List[Tuple[str, str]] = [
        ("format", "json"),
        ("frame", "embedded"),
        ("type", "File"),
        ("status", "released"),
        ("limit", "0"),
    ]
    if organism:
        params.extend([
            ("organism.scientific_name", organism),
            ("dataset.organism.scientific_name", organism),
            ("dataset.replicates.library.biosample.donor.organism.scientific_name", organism),
        ])
    p = _payload(params)
    assemblies = _facet_terms(p, "assembly")
    return [a for a, _ in sorted(assemblies, key=lambda t: (-t[1], t[0]))]


# ------------------------
# ENCODE-only cell "tree" (built from cell_slims)
# ------------------------

def _fetch_biosample_types() -> List[Dict[str, Any]]:
    url = "https://www.encodeproject.org/search/?type=BiosampleType&format=json&frame=object&limit=all"
    payload = _http_json(url, timeout=60)
    return payload.get("@graph") or []


def get_cell_tree() -> Dict[str, Any]:
    """
    Build a hierarchy from ENCODE's `cell_slims` only (no external ontologies).

    Parent-child relation between slims inferred by strict subset of member sets.
    """
    bios = _fetch_biosample_types()

    allowed_classes = {"primary cell", "in vitro differentiated cells", "cell line", "cell"}
    enc_terms: List[Dict[str, Any]] = []
    for b in bios:
        classification = (b.get("classification") or "").strip().lower()
        if classification and classification not in allowed_classes:
            continue
        name = b.get("term_name")
        if not name:
            continue
        enc_terms.append({
            "term_name": name,
            "cell_slims": [str(s) for s in (b.get("cell_slims") or [])],
        })

    # Slim buckets
    slim_members: Dict[str, Set[str]] = {}
    for t in enc_terms:
        for slim in t["cell_slims"]:
            slim_members.setdefault(slim, set()).add(t["term_name"])
    slim_members = {k: v for k, v in slim_members.items() if v}

    slims = list(slim_members.keys())
    sizes = {s: len(slim_members[s]) for s in slims}
    parents: Dict[str, Optional[str]] = {s: None for s in slims}

    # Minimal strict superset = parent
    for a in slims:
        cand = [b for b in slims if a != b and slim_members[a] < slim_members[b]]
        if not cand:
            continue
        # Keep minimal supersets
        minimal = set(cand)
        for x in cand:
            for y in cand:
                if x != y and slim_members[x] > slim_members[y]:
                    minimal.discard(x)
        if minimal:
            parent = sorted(minimal, key=lambda s: (sizes[s], s.casefold()))[0]
            parents[a] = parent

    # Build nodes
    nodes: Dict[str, Dict[str, Any]] = {}

    def ensure_node(s: str):
        if s not in nodes:
            nodes[s] = {
                "id": f"SLIM::{s}",
                "label": s,
                "children": [],
                "members": sorted(slim_members[s], key=str.casefold),
            }

    for s in slims:
        ensure_node(s)

    # Children
    for child, parent in parents.items():
        if parent and child != parent:
            nodes[parent]["children"].append(child)

    # Roots
    all_children = {c for s in slims for c in nodes[s]["children"]}
    roots = [s for s in slims if parents.get(s) is None and s not in all_children]
    if not roots and slims:
        roots = [sorted(slims, key=lambda s: (-sizes[s], s.casefold()))[0]]

    # Aggregate members
    from functools import lru_cache
    @lru_cache(maxsize=None)
    def agg(s: str) -> List[str]:
        seen = set(nodes[s]["members"])
        for c in nodes[s]["children"]:
            seen.update(agg(c))
        return sorted(seen, key=str.casefold)

    for s in slims:
        nodes[s]["aggregate_members"] = agg(s)

    def pack(s: str) -> Dict[str, Any]:
        nd = nodes[s]
        return {
            "id": nd["id"],
            "label": nd["label"],
            "members": nd["members"],
            "aggregate_members": nd["aggregate_members"],
            "children": [pack(c) for c in sorted(nd["children"], key=str.casefold)],
        }

    tree = {
        "id": "SLIM::ROOT",
        "label": "Cell types",
        "children": [pack(r) for r in sorted(roots, key=str.casefold)],
        "members": [],
        "aggregate_members": sorted({m for s in slims for m in nodes[s]["aggregate_members"]},
                                    key=str.casefold),
    }
    return {"ok": True, "tree": tree}

from itertools import product
from typing import Optional, Dict, Any, List, Set, Tuple
from urllib.parse import urlencode

import requests

BASE = "https://www.encodeproject.org/search/"
UA = "encode-helper/1.4 (+requests)"
HEADERS = {"Accept": "application/json", "User-Agent": UA}


def _http_json(url: str, timeout: float = 45) -> Dict[str, Any]:
    """
    HTTP GET with ENCODE-friendly behavior.
    - 200 returns JSON
    - 404 treated as empty search (ENCODE sometimes uses 404 for empty result with certain filters)
    - other HTTP errors re-raised
    """
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    if r.status_code == 404:
        return {"@graph": [], "total": 0, "next": None}
    r.raise_for_status()
    return r.json()


def _safe(obj: Any, *path) -> Any:
    cur = obj
    for k in path:
        if isinstance(cur, dict):
            cur = cur.get(k)
        elif isinstance(cur, list):
            try:
                idx = int(k)
            except Exception:
                return None
            if 0 <= idx < len(cur):
                cur = cur[idx]
            else:
                return None
        else:
            return None
    return cur


def _extract_display_fields(it: Dict[str, Any]) -> Dict[str, Optional[str]]:
    assembly_val = it.get("assembly") or _safe(it, "dataset", "assembly")
    organism_val = (
            _safe(it, "organism", "scientific_name")
            or _safe(it, "dataset", "organism", "scientific_name")
            or _safe(it, "replicates", 0, "library", "biosample", "organism", "scientific_name")
    )
    cell_type_val = (
            _safe(it, "biosample_ontology", "term_name")
            or _safe(it, "replicates", 0, "library", "biosample", "biosample_ontology", "term_name")
            or _safe(it, "dataset", "replicates", 0, "library", "biosample", "biosample_ontology", "term_name")
    )
    target_val = (
            _safe(it, "target", "label")
            or _safe(it, "experiment_object", "target", "label")
            or _safe(it, "dataset", "target", "label")
    )
    primary_type = (
            it.get("assay_title")
            or it.get("output_type")
            or it.get("file_format")
            or it.get("display_title")
    )
    return {
        "assembly": assembly_val,
        "organism": organism_val,
        "cell_type": cell_type_val,
        "target": target_val,
        "type": primary_type,
    }


def _items_from_graph(graph: List[Dict[str, Any]]) -> List[Dict[str, Optional[str]]]:
    items: List[Dict[str, Optional[str]]] = []
    for it in graph:
        f = _extract_display_fields(it)
        items.append({
            "accession": it.get("accession"),
            "id": it.get("@id"),
            **f,
        })
    return items


def _build_base_params(
        *,
        type_: str,
        search_term: Optional[str],
        assay_title: Optional[str],
        organism: Optional[str],
        assembly: Optional[str],
        file_format: Optional[str],
        limit: int,
        after: Optional[str],
) -> Dict[str, Any]:
    enc_params: Dict[str, Any] = {
        "type": type_ if type_ in {"File", "Experiment", "Dataset"} else "File",
        "format": "json",
        "frame": "embedded",
        "status": "released",
        "limit": max(1, min(int(limit or 25), 200)),
    }
    if search_term:
        enc_params["searchTerm"] = search_term
    if assay_title:
        enc_params["assay_title"] = assay_title
    if organism:
        enc_params["organism.scientific_name"] = organism
    if assembly:
        enc_params["assembly"] = assembly
    if file_format:
        enc_params["file_format"] = file_format
    if after:
        enc_params["after"] = after
    return enc_params


def _pairs_for_queries(
        cells: List[str],
        targets: List[str],
) -> List[Tuple[Optional[str], Optional[str]]]:
    """
    Expand to a list of (cell_term, target) pairs.
    If cells is empty -> [None]; if targets is empty -> [None].
    Result will contain at least one pair (None, None) meaning 'no filters'.
    """
    cells_e = cells if cells else [None]
    targs_e = targets if targets else [None]
    out: List[Tuple[Optional[str], Optional[str]]] = []
    for c in cells_e:
        for t in targs_e:
            out.append((c, t))
    # Deduplicate identical pairs
    unique: List[Tuple[Optional[str], Optional[str]]] = []
    seen = set()
    for cp in out:
        if cp not in seen:
            seen.add(cp)
            unique.append(cp)
    return unique


def search_encode(
        *,
        type_: str = "File",
        search_term: Optional[str] = None,
        assay_title: Optional[str] = None,
        organism: Optional[str] = None,
        assembly: Optional[str] = None,
        # legacy single-target (kept for compatibility; prefer include_targets)
        target: Optional[str] = None,
        # filters
        include_cell_terms: Optional[List[str]] = None,
        exclude_cell_terms: Optional[List[str]] = None,
        include_targets: Optional[List[str]] = None,
        file_format: Optional[str] = None,
        output_types: List[str] = [],
        limit: int = 25,
        after: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Symmetric filtering and request expansion:
      - Build one request for every combination of (cell term × target).
      - If a side is empty, it contributes a single 'None' -> no filter on that axis.
      - If both sides are empty, make a single unfiltered request (subject to assay/organism/assembly).
      - Results are de-duplicated by '@id' across all requests.
      - 'exclude_cell_terms' is applied to the merged items.
    """
    cell_terms = list(dict.fromkeys(include_cell_terms or []))
    targets = list(dict.fromkeys(include_targets or []))
    if not targets and target:
        targets = [target]  # back-compat

    exclude_set: Set[str] = set(exclude_cell_terms or [])

    base = _build_base_params(
        type_=type_,
        search_term=search_term,
        assay_title=assay_title,
        organism=organism,
        assembly=assembly,
        file_format=file_format,
        limit=limit,
        after=after,
    )

    combined: Dict[str, Dict[str, Any]] = {}
    urls: List[str] = []

    for cell_term, targ, output_type in product(cell_terms, targets, output_types):
        params = dict(base)
        params["biosample_ontology.term_name"] = cell_term
        params["target.label"] = targ
        params["output_type"] = output_type

        url = BASE + "?" + urlencode(params, doseq=True)
        urls.append(url)

        payload = _http_json(url, timeout=45)
        graph = payload.get("@graph", []) or []
        for item in _items_from_graph(graph):
            iid = item.get("id")
            if not iid:
                continue
            combined[iid] = item

    items_list = list(combined.values())
    if exclude_set:
        items_list = [it for it in items_list if (it.get("cell_type") or "") not in exclude_set]

    # Trim to display limit
    items_list = items_list[: max(1, min(int(limit or 25), 200))]

    return {
        "ok": True,
        "urls": urls,
        "url": urls[0] if urls else None,
        "total": len(items_list),
        "returned": len(items_list),
        "next": None,
        "items": items_list,
    }

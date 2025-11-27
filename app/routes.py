import json

from flask import Blueprint, jsonify, request, render_template, current_app
from jinja2 import TemplateNotFound

from api.encode_api import search_encode
from api.giggle_api import run_giggle_search
from api.options_api import (
    get_assays_and_organisms,
    get_targets,
    get_cell_types,
    get_assemblies,
    get_cell_tree,
)
from batch_tsv import get_metadata_tsv  # reuse working helper
from config import read_config
from db_writer import ingest_tsv_bytes
from metadata_build_db import get_metadata_paths

bp = Blueprint("app", __name__, template_folder="templates", static_folder="static")


@bp.get("/data")
def search():
    try:
        return render_template("data.html")
    except TemplateNotFound:
        # In case templates are not packaged
        return jsonify({"ok": True, "message": "Template missing"})


@bp.get("/search")
def api_search():
    # Basic query params
    q = request.args.get("q", "").strip() or None
    assay = request.args.get("assay") or None
    organism = request.args.get("organism") or None
    assembly = request.args.get("assembly") or None
    typ = request.args.get("type") or "File"
    target = request.args.get("target") or None  # legacy single target
    limit = request.args.get("limit", type=int) or 25
    after = request.args.get("after")

    # Load config file
    cfg = read_config(current_app.config['CONFIG_YAML'])

    # Selected cell types from tri-state picker
    include_terms: list[str] = []
    exclude_terms: list[str] = []  # post-filter
    inc_raw = request.args.get("cell_includes")
    exc_raw = request.args.get("cell_excludes")
    try:
        if inc_raw:
            include_terms = list(dict.fromkeys(json.loads(inc_raw)))
        if exc_raw:
            exclude_terms = list(dict.fromkeys(json.loads(exc_raw)))
    except Exception:
        include_terms, exclude_terms = [], []

    # Selected targets (can be empty -> means "do not filter by target")
    include_targets: list[str] = []
    t_inc_raw = request.args.get("target_includes")
    try:
        if t_inc_raw:
            include_targets = list(dict.fromkeys(json.loads(t_inc_raw)))
    except Exception:
        include_targets = []

    try:
        data = search_encode(
            type_=typ,
            search_term=q,
            assay_title=assay,
            organism=organism,
            assembly=assembly,
            target=target,  # legacy single-target still supported
            include_cell_terms=include_terms,
            exclude_cell_terms=exclude_terms,
            include_targets=include_targets,
            file_format=cfg["file_format"],
            output_types=cfg["output_types"].split(","),
            limit=limit,
            after=after,
        )
        return jsonify(data)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.get("/options")
def api_options():
    try:
        base = get_assays_and_organisms()
        targets = get_targets()
        cell_types = get_cell_types()
        tree_payload = get_cell_tree()
        return jsonify({
            "ok": True,
            **base,
            "targets": targets,
            "cell_types": cell_types,
            "cell_tree": tree_payload.get("tree"),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.get("/assemblies")
def api_assemblies():
    org = request.args.get("organism")
    try:
        assemblies = get_assemblies(org)
        return jsonify({"ok": True, "assemblies": assemblies})
    except Exception as e:
        return jsonify({"ok": False, "assemblies": [], "error": str(e)}), 400


@bp.post("/batch-tsv-save")
def api_batch_tsv_save():
    try:
        payload = request.get_json(silent=True) or {}
        ids = payload.get("ids") or []
        if not isinstance(ids, list):
            return jsonify({"ok": False, "error": "ids must be a list"}), 400

        content = get_metadata_tsv([str(x) for x in ids])

        cfg = read_config(current_app.config['CONFIG_YAML'])
        in_tsv, out_db = get_metadata_paths(cfg)
        # target directory: app/
        with open(in_tsv, "wb") as f:
            f.write(content)

        # NEW: ingest into SQLite with filters applied
        ingest_info = ingest_tsv_bytes(content, out_db)

        return jsonify({
            "ok": True,
            "saved_path": str(in_tsv),
            "db_path": ingest_info.get("db_path"),
            "db_table": ingest_info.get("table"),
            "rows_kept": ingest_info.get("total_kept"),
            "rows_inserted": ingest_info.get("inserted"),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.get("/giggle")
def giggle_page():
    return render_template(
        "giggle.html",
        error=None,
        meta=None,
        headers=None,
        rows=None,
        raw_output=None,
    )


@bp.post("/giggle")
def giggle_search():
    try:
        if "bedfile" not in request.files:
            return render_template(
                "giggle.html",
                error="No file part in the request.", meta=None, headers=None, rows=None, raw_output=None
            )

        file = request.files["bedfile"]
        if not file or not file.filename:
            return render_template(
                "giggle.html", error="No file selected.", meta=None, headers=None, rows=None, raw_output=None
            )

        cfg_path = current_app.config["CONFIG_YAML"]

        meta, headers, rows, raw_output = run_giggle_search(
            upload_storage=file,
            cfg_path=cfg_path,
        )

        if headers and rows:
            return render_template(
                "giggle.html", error=None, meta=meta, headers=headers, rows=rows, raw_output=None
            )
        else:
            return render_template(
                "giggle.html", error=None, meta=meta, headers=None, rows=None, raw_output=raw_output
            )

    except Exception as e:
        return render_template(
            "giggle.html", error=f"ERROR {e}", meta=None, headers=None, rows=None, raw_output=None
        )

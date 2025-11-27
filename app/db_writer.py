# encode_app/db_writer.py
from __future__ import annotations
import csv
import io
import re
import sqlite3
from pathlib import Path
from typing import Iterable, Tuple, List, Dict

# column names in the TSV we need for filtering
COL_FILE_FORMAT = "File format"
COL_OUTPUT_TYPE = "Output type"
COL_AUDIT_ERR = "Audit ERROR"
COL_AUDIT_NC  = "Audit NOT_COMPLIANT"

# --- filtering logic ---------------------------------------------------------
def _passes_filters(row: Dict[str, str]) -> bool:
    fmt = (row.get(COL_FILE_FORMAT) or "").strip().lower()
    out = (row.get(COL_OUTPUT_TYPE) or "")
    err = (row.get(COL_AUDIT_ERR) or "")
    nc  = (row.get(COL_AUDIT_NC)  or "")

    if fmt not in {"bam", "bigwig"}:
        return False
    if "alignment" not in out.lower():
        return False
    if str(err).strip() != "":
        return False
    if str(nc).strip() != "":
        return False
    return True

# --- sqlite helpers ----------------------------------------------------------
def _sanitize(name: str) -> str:
    s = re.sub(r"\W+", "_", (name or "").strip()).lower().strip("_")
    if not s:
        s = "col"
    if s[0].isdigit():
        s = "_" + s
    return s

def _ensure_table(conn: sqlite3.Connection, headers: List[str], table: str = "metadata") -> Tuple[str, List[str]]:
    cols = [_sanitize(h) for h in headers]
    # primary key on file_accession if present
    pk = "file_accession" if "file_accession" in cols else None
    cols_def = ", ".join([f'"{c}" TEXT' for c in cols])
    if pk:
        cols_def = f"{cols_def}, PRIMARY KEY(\"{pk}\")"
    conn.execute(f'CREATE TABLE IF NOT EXISTS {table} ({cols_def})')
    return table, cols

def _upsert_rows(conn: sqlite3.Connection, table: str, cols: List[str], rows: Iterable[List[str]]) -> int:
    placeholders = ", ".join(["?"] * len(cols))
    collist = ", ".join([f'"{c}"' for c in cols])
    sql = f'INSERT OR REPLACE INTO {table} ({collist}) VALUES ({placeholders})'
    cur = conn.executemany(sql, rows)
    return cur.rowcount or 0

# --- public API --------------------------------------------------------------
def ingest_tsv_bytes(tsv_content: bytes, db_path: Path) -> dict:
    """
    Parse TSV bytes, filter rows, and upsert into SQLite at db_path.
    Returns: {"inserted": int, "total_kept": int, "table": str, "db_path": str}
    """
    text = tsv_content.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    headers = reader.fieldnames or []
    if not headers:
        raise ValueError("TSV has no header row")

    kept_rows: List[Dict[str, str]] = []
    for row in reader:
        if _passes_filters(row):
            kept_rows.append(row)

    if not kept_rows:
        # still initialize the DB/table so schema exists
        conn = sqlite3.connect(str(db_path))
        try:
            table, cols = _ensure_table(conn, headers)
            conn.commit()
        finally:
            conn.close()
        return {"inserted": 0, "total_kept": 0, "table": table, "db_path": str(db_path)}

    # Prepare values in column order
    cols = [_sanitize(h) for h in headers]
    values: List[List[str]] = []
    for r in kept_rows:
        values.append([str(r.get(h, "")) for h in headers])

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        table, cols_sql = _ensure_table(conn, headers)
        inserted = _upsert_rows(conn, table, cols_sql, values)
        conn.commit()
    finally:
        conn.close()

    return {"inserted": inserted, "total_kept": len(kept_rows), "table": table, "db_path": str(db_path)}

import sqlite3
from pathlib import Path

from snakemake.exceptions import WorkflowError


def get_samples(metadata_db):
    pdb = Path(metadata_db)
    if not pdb.exists():
        raise WorkflowError(
            f"{metadata_db} not found. Run the metadata steps first (e.g., `python run.py --build-only`)."
        )
    con = sqlite3.connect(pdb)
    try:
        rows = con.execute("SELECT file_accession FROM metadata").fetchall()
    finally:
        con.close()
    return sorted({r[0] for r in rows})

def lookup_bigwig_url(metadata_db, file_format, sample):
    db = Path(metadata_db)
    if not db.exists():
        raise ValueError("metadata.db not found in the working directory.")

    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute(
            'SELECT "File download URL","File format" FROM metadata WHERE "File accession"=?',
            (sample,)
        ).fetchone()
        if not row:
            raise ValueError(f"No row found in metadata.db for accession: {sample}")
        url, fmt = row
        if not url:
            raise ValueError(f"No download URL in metadata.db for accession: {sample}")
        if (fmt or "").lower() != file_format.lower():
            raise ValueError(
                f"Accession {sample} has File format='{fmt}', expected '{file_format}'."
            )
        return url
    finally:
        conn.close()

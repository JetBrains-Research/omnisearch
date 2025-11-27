from __future__ import annotations

import gzip
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from config import read_config


def _safe_filename(name: str) -> str:
    name = (name or "query.bed").strip()
    safe = "".join(c for c in name if c.isalnum() or c in ("-", "_", ".", " "))
    return safe or "query.bed"


def _get_genome_size(chromosomes_sizes: str, chrom: Optional[str]) -> int:
    if not chromosomes_sizes:
        raise RuntimeError("config.yaml must define 'chromosome_sizes'.")
    chrom_sizes_path = Path(chromosomes_sizes)
    if not chrom_sizes_path.exists():
        raise RuntimeError(f"chromosome_sizes file not found: {chromosomes_sizes}")
    size = 0
    with chrom_sizes_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            parts = line.strip().split()
            if chrom == "" or chrom is None or parts[0] == chrom:
                try:
                    size += int(parts[1])
                except Exception:
                    pass
                break
    if size == 0:
        raise RuntimeError(f"Chromosome '{chrom}' not found in sizes file: {chromosomes_sizes}")
    return size


def _normalize_and_trim(upload_storage, tmpdir: Path, chromosome: str) -> Path:
    """
    Save upload to storage_dir, gunzip if needed, then trim to `chromosome`.
    Return path to trimmed .bed (uncompressed).
    """
    base = _safe_filename(getattr(upload_storage, "filename", "query.bed"))
    dest_raw = tmpdir / base
    upload_storage.save(dest_raw)

    # If gzipped, gunzip first -> .bed
    if dest_raw.suffix == ".gz":
        dest_bed = tmpdir / dest_raw.with_suffix("").name
        with gzip.open(dest_raw, "rb") as src, dest_bed.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        try:
            dest_raw.unlink()
        except Exception:
            pass
    else:
        dest_bed = dest_raw

    # Trim to chromosome
    trimmed = dest_bed.with_suffix("")  # strip .bed if present for .chrtrim.bed
    if trimmed.suffix != ".bed":
        trimmed = trimmed.with_suffix(".bed")
    trimmed = trimmed.with_name(trimmed.stem + ".chrtrim.bed")

    with (dest_bed.open("rt", encoding="utf-8", errors="ignore") as src,
          trimmed.open("wt", encoding="utf-8") as dst):
        for line in src:
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if chromosome == "" or chromosome is None or parts and parts[0] == chromosome:
                dst.write(line)

    return trimmed


def _bgzf_compress(bed_path: Path, bgzip_bin: str) -> Path:
    # bgzip -f <file>
    subprocess.run([bgzip_bin, "-f", str(bed_path)], cwd=bed_path.parent, check=True)
    gz = bed_path.with_suffix(bed_path.suffix + ".gz")
    if not gz.exists():
        raise RuntimeError("BGZF output not created by bgzip.")
    return gz


def _run_giggle(giggle_bin: str, index_dir: Path, query_bgzf: Path, chr_size: int) -> str:
    # EXACT flags as in consensus_launch.py
    cmd = [giggle_bin, "search", "-i", str(index_dir), "-q", str(query_bgzf), "-s", "-g", str(chr_size)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"Giggle exited with code {proc.returncode}")
    return proc.stdout


def _run_giggle_search(giggle_bin: str, index_dir: str, query_bgzf: str, genome_size: int) -> str:
    # EXACT flags as in consensus_launch.py
    cmd = [giggle_bin, "search", "-i", index_dir, "-q", query_bgzf, "-s", "-g", str(genome_size)]
    print("\nRUN:", " ".join(map(str, cmd)), "\n", flush=True)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"Giggle exited with code {proc.returncode}")
    return proc.stdout


# ---------- NEW: shorten filename cells (strip path and extensions) ----------

_PATH_LIKE = re.compile(r"[\\/]|\.bed(\.gz)?$", re.IGNORECASE)


def _shorten_filename_token(s: str) -> str:
    """Turn '/path/ENCFF000CCX.bed.gz' -> 'ENCFF000CCX'."""
    if not isinstance(s, str):
        return s
    # Only touch things that look like file paths or .bed/.bed.gz tokens
    if not _PATH_LIKE.search(s):
        return s
    base = s.split("/")[-1].split("\\")[-1]  # handle both separators
    # Remove common extensions
    for ext in (".bed.gz", ".bed", ".bgz", ".gz"):
        if base.lower().endswith(ext):
            base = base[: -len(ext)]
            break
    # If still has an extra extension (rare), drop the trailing one: name.txt -> name
    if "." in base:
        base = base.split(".")[0]
    return base


def _postprocess_rows(headers: list[str] | None, rows: list[list[str]] | None) -> tuple[
    list[str] | None, list[list[str]] | None]:
    if not rows:
        return headers, rows
    # Heuristic: apply shortening to any cell that looks like a path or .bed token
    new_rows: list[list[str]] = []
    for r in rows:
        new_rows.append([_shorten_filename_token(c) for c in r])
    return headers, new_rows


# ---------- parsing ----------

def _parse_output(text: str):
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None, None
    if lines[0].startswith("#"):
        headers = lines[0].lstrip("#").strip().split("\t")
        rows = [ln.split("\t") for ln in lines[1:]]
        return headers, rows
    # uniform tabs?
    tabs = [ln.count("\t") for ln in lines]
    if tabs and max(tabs) == min(tabs) and tabs[0] > 0:
        n = tabs[0] + 1
        headers = [f"col{i + 1}" for i in range(n)]
        rows = [ln.split("\t") for ln in lines]
        return headers, rows
    return None, None


# ---------- public entry point ----------

def run_giggle_search(upload_storage, cfg_path: Path):
    """
    Public entry point: mirror consensus_launch.py behavior on a single uploaded BED.
    Returns: (meta:dict, headers:list|None, rows:list|None, raw_output:str|None)
    """
    cfg = read_config(cfg_path)
    index_dir = os.path.expanduser(cfg.get("giggle_index_dir", "index"))
    giggle_bin = os.path.expanduser(cfg.get("giggle_bin", "giggle"))
    bgzip_bin = os.path.expanduser(cfg.get("bgzip_bin", "bgzip"))
    chromosomes_sizes = os.path.expanduser(cfg.get("chromosome_sizes") or "")
    chrom = cfg.get("chromosome")
    genome_size = _get_genome_size(chromosomes_sizes, chrom)

    with tempfile.TemporaryDirectory(delete=False) as tmpdir:
        trimmed_bed = _normalize_and_trim(upload_storage, Path(tmpdir), chrom)
        query_bgzf = _bgzf_compress(trimmed_bed, bgzip_bin)

        out_text = _run_giggle_search(giggle_bin, index_dir, str(query_bgzf), genome_size)
        headers, rows = _parse_output(out_text)

        # NEW: replace file paths with bare names
        headers, rows = _postprocess_rows(headers, rows)

        meta = {
            "index_dir": str(index_dir),
            "giggle_bin": giggle_bin,
            "genome_len": genome_size,
        }
        if headers and rows:
            return meta, headers, rows, None
        return meta, None, None, out_text

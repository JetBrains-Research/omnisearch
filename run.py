#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import os
import subprocess
import sys
from pathlib import Path

from config import read_config, expand_user_config

HERE = Path(__file__).resolve().parent

def run(cmd, cwd=None):
    print("\nRUN:", " ".join(map(str, cmd)), "\n", flush=True)
    proc = subprocess.run(cmd, cwd=cwd)
    if proc.returncode != 0:
        sys.exit(proc.returncode)


def main():
    ap = argparse.ArgumentParser(description="Entry point to fetch TSV, build DB, then run Snakemake")
    ap.add_argument("--cores", "-j", type=int, default=4, help="Max parallel jobs for Snakemake")
    ap.add_argument("--config", default=str(HERE / "config.yaml"), help="Path to config.yaml")
    ap.add_argument("--snakefile", default=str(HERE / "snakemake" / "Snakefile"), help="Path to Snakefile")
    ap.add_argument("--unlock", action="store_true", help="Pass --unlock to Snakemake and exit")

    # New step controls
    ap.add_argument("--fetch-only", action="store_true", help="Only fetch metadata.tsv and exit")
    ap.add_argument("--build-only", action="store_true", help="Only build metadata.db from existing metadata.tsv and exit")
    ap.add_argument("--no-snakemake", action="store_true", help="Do not run Snakemake after metadata steps")

    args = ap.parse_args()

    if args.unlock:
        run(["snakemake", "-s", args.snakefile, "--configfile", args.config, "--unlock"])
        return

    fetch_py = str(HERE / "metadata_fetch.py")
    build_py = str(HERE / "metadata_build_db.py")

    if args.fetch_only:
        run([sys.executable, fetch_py, "--config", args.config])
        return

    if args.build_only:
        run([sys.executable, build_py, "--config", args.config])
        return

    # Default: fetch → build → (optionally) snakemake
    run([sys.executable, fetch_py, "--config", args.config])
    run([sys.executable, build_py, "--config", args.config])

    if not args.no_snakemake:
        # Prepare a temporary config file with all tildes expanded
        cfg = read_config(args.config)
        expanded_cfg = expand_user_config(cfg)

        run([
            "snakemake",
            "-s", os.path.expanduser(args.snakefile),
            "--configfile", expanded_cfg,
            "-j", str(args.cores),
            "--rerun-incomplete",
            "--printshellcmds",
        ])


if __name__ == "__main__":
    main()

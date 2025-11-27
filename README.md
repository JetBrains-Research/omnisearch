# Omnisearch — ENCODE ➜ OmniPeak ➜ Giggle

Intelligent search across public ChIP/ATAC-seq datasets

A pipeline that:

1. **Fetches** ENCODE metadata TSV from a URL in `files.txt` (first non-empty line).
2. **Builds**/updates a local **`metadata.db`** from that TSV (append-only behavior).
3. **Downloads** BAM/BigWig files from ENCODE listed in `metadata.db`.
4. **Calls peaks** with **OmniPeak** (`.peak`).
5. **Builds a Giggle interval index** for fast interval queries from the `.peak` outputs.

## Installation

Use an existing conda env or Python ≥ 3.10. Java is required for OmniPeak.

```bash
python -m pip install -r requirements.txt
```

### Giggle

Please follow the installation instructions to install `giggle`: https://github.com/ryanlayer/giggle

---

## Configuration (`config.yaml`)

Please ensure you have a `config.yaml` in the project root.

> If you want **genome-wide** peaks, remove `chromosome:` or set it empty and re-run OmniPeak.

---

## Launch web app

Launch `python -m app.app` to launch a web app to select files.

## Select files to add to Giggle index

Navigate to `http://localhost:5000/data`.

## Build Giggle index

At the moment, the index is built from the command line only.

### End-to-end (fetch → db → all rules)

```bash
python run.py --cores 8
```

Optional knobs:

```bash
python run.py --cores 8 --config config.yaml --snakefile Snakefile
```

### Fetch only

```bash
python run.py --fetch-only
```

### Build DB only (from an already-downloaded TSV)

```bash
python run.py --build-only
```

### Run specific Snakemake targets

* **Download**:

  ```bash
  snakemake -s Snakefile --configfile config.yaml -j 8 <path_to_downloads>
  ```

* **OmniPeak only**:

  ```bash
  snakemake -s Snakefile --configfile config.yaml -j 8 <path_to_peaks>
  ```

* **Giggle index only** (rebuild index):

  ```bash
  rm -rf index
  snakemake -s Snakefile --configfile config.yaml -j 4 <path_to_giggle_index_marker>
  ```

* **Unlock** Snakemake working dir after a crash:

  ```bash
  python run.py --unlock
  ```

---

## Giggle: searching with index

Navigate to `http://localhost:5000/giggle`.

Additionally, you can search via the Giggle **CLI** for convenience:

```bash
# list indexed files
$GIGGLE search -i index -l

# count overlaps in a region (example: chr15)
$GIGGLE search -i index -r chr15:1-250000000 -c

# print overlapping records
$GIGGLE search -i index -r chr15:1-250000000 -v | head -n 50
```

> `-s` (significance) requires a query file: `-q query.bed`. For simple inspection, use `-c` or `-v`.

---

## Notes & tips

* If `giggle search -v` errors with a doubled absolute path, it means your **old index** recorded absolute paths. Rebuild with this pipeline’s Giggle rule to store **relative** paths.
* Giggle’s index can break if a previous run aborted mid‑write (you’ll see messages about `cache.0.dat` vs `cache.0.idx`). **Delete `index/` and rebuild**.
* **bgzip**: ensure the `bgzip` configured in `config.yaml` exists and is executable. Either the htslib version or a system one (e.g., Homebrew) is fine.

---

## Troubleshooting

* **Downloads are slow/huge**: consider reducing your metadata filter to fewer experiments.
* **OmniPeak on one chromosome**: set `chromosome:` in `config.yaml` (e.g., `chr15`) to speed up exploratory runs. Remove for full‑genome.
* **Snakemake DAG wants to run everything** when you only want Giggle: request the explicit giggle step.
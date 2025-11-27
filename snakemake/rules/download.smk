# Download files listed in metadata.db

from snakemake.io import ancient

from utils import lookup_bigwig_url

file_format = config.get("file_format","bigWig")
metadata_db = config.get("metadata_db","metadata.db")
download_dir = config.get("download_dir","downloads")


rule download:
    input:
        ancient(metadata_db),
    output:
        f"{download_dir}/{{sample}}.{file_format}"
    resources:
        mem_mb=1000
    params:
        url=lambda wc: lookup_bigwig_url(metadata_db,file_format,wc.sample)
    shell:
        """
        set -euo pipefail;
        mkdir -p "$(dirname {output})";
        curl -C - -sS -L --retry 5 --retry-delay 5 -o "{output}" "{params.url}"
        """

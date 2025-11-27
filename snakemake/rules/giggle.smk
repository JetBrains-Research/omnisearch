# Build a Giggle index from all OmniPeak outputs

from utils import get_samples

metadata_db = config.get("metadata_db","metadata.db")
giggle_bin = config.get("giggle_bin","giggle")
giggle_index_dir = config.get("giggle_index_dir","index")
omnipeak_dir = config.get("omnipeak_dir","results")
logs_dir = config.get("logs_dir","logs")

bed3gz_dir = config.get("bed3gz_dir","bed3gz")
bgzip_bin = config.get("bgzip_bin","bgzip")

SAMPLES = get_samples(metadata_db)

rule:
    input: f"{omnipeak_dir}/{{sample}}.peak"
    output: f"{bed3gz_dir}/{{sample}}.bed.gz"
    shell: f"cat {{input}} | cut -f1-3 | {bgzip_bin} > {{output}}"

rule giggle_index:
    input: expand(f"{bed3gz_dir}/{{sample}}.bed.gz",sample=SAMPLES)
    params: files=lambda wildcards, input: " -i " + " -i ".join(input)
    log: f"{logs_dir}/giggle_index.log"
    output:
        f"{giggle_index_dir}/giggle.done"
    shell:
        f"""
        set -euo pipefail;
        mkdir -p {giggle_index_dir};
        {giggle_bin} index {{params.files}} -o {giggle_index_dir} -f &> {{log}};
        touch {{output}}
        """

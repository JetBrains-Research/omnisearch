# Run OmniPeak on bigWig inputs from downloads/.

download_dir = config.get("download_dir","downloads")
file_format = config.get("file_format","bigWig")
omnipeak_dir = config.get("omnipeak_dir","results")
logs_dir = config.get("logs_dir","logs")

java = config.get("java","java")
omnipeak_jar = config["omnipeak_jar"]  # required
chrom_sizes = config["chromosome_sizes"]  # required path
chromosome = config.get("chromosome","")
extra_params = config.get("omnipeak_params","")

# allow omnipeak_params as list or string
if isinstance(extra_params,list):
    extra_params = " ".join(map(str,extra_params))


rule omnipeak:
    input:
        file=f"{download_dir}/{{sample}}.{file_format}",
        chrom_sizes=chrom_sizes
    output:
        peak=f"{omnipeak_dir}/{{sample}}.peak"
    log:
        f"{logs_dir}/omnipeak/{{sample}}.log"
    threads: 4
    resources:
        mem_mb=10000
    params:
        java=java,
        jar=omnipeak_jar,
        chr=chromosome,
        extra=extra_params
    shell:
        """
            set -euo pipefail;
            "{params.java}" --add-modules=jdk.incubator.vector -Xmx8G \
              -jar "{params.jar}" analyze \
              -t "{input.file}" \
              --cs "{input.chrom_sizes}" \
              --chromosomes "{params.chr}" \
              -p "{output.peak}" \
              -w "{omnipeak_dir}" \
              {params.extra} \
              --log "{log}" 
        """

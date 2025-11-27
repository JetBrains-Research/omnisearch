import os
import sys
import tempfile
from pathlib import Path

import yaml


def read_config(path="config.yaml") -> dict:
    cfg_path = Path(path)
    if not cfg_path.exists():
        print("ERROR: config.yaml not found in current directory.", file=sys.stderr)
        sys.exit(1)
    with cfg_path.open() as fh:
        return yaml.safe_load(fh)


def _expand_tildes(obj):
    """Recursively expand '~' in all string values of a Python structure."""
    if isinstance(obj, str):
        return os.path.expanduser(obj)
    if isinstance(obj, list):
        return [_expand_tildes(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _expand_tildes(v) for k, v in obj.items()}
    return obj


def expand_user_config(cfg) -> str:
    cfg_expand = _expand_tildes(cfg)
    tmp = tempfile.NamedTemporaryFile(
        prefix="config_expanded_",
        suffix=".yaml",
        delete=False,
        mode="w",
        encoding="utf-8")
    with tmp as out:
        yaml.safe_dump(cfg_expand, out, default_flow_style=False, sort_keys=False)
        tmp_cfg_path = tmp.name
    return tmp_cfg_path

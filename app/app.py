from __future__ import annotations

import os
from pathlib import Path

from flask import Flask

from config import read_config
from routes import bp


def create_app():
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    app = Flask(__name__)
    config_path = str(PROJECT_ROOT / "config.yaml")
    cfg = read_config(config_path)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret"),
        PROJECT_ROOT=str(PROJECT_ROOT),
        CONFIG_YAML=config_path,
        LOG_DIR=cfg.get("logs_dir", "logs"),
        MAX_WORKERS=1,  # one pipeline job at a time (you can raise this)
    )
    os.makedirs(app.config["LOG_DIR"], exist_ok=True)

    app.register_blueprint(bp)
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)

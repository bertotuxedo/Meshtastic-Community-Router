from __future__ import annotations

import os
from typing import Any

import yaml


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def normalize_root(root: str) -> str:
    return root.strip().rstrip("/")


def load_config(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)

    if not isinstance(config, dict):
        raise ValueError(
            "Configuration must contain a YAML mapping."
        )

    return config

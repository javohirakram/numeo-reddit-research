"""Load and expose the controlled vocabulary from config/taxonomy.yaml."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

TAXONOMY_PATH = Path("config/taxonomy.yaml")
SUBREDDITS_PATH = Path("config/subreddits.yaml")


@lru_cache(maxsize=1)
def load_taxonomy() -> dict:
    with TAXONOMY_PATH.open() as f:
        data = yaml.safe_load(f)
    required = ("roles", "topics", "competitors")
    for key in required:
        if key not in data or not isinstance(data[key], list):
            raise ValueError(f"taxonomy.yaml missing list field: {key}")
    return data


@lru_cache(maxsize=1)
def load_subreddits() -> list[dict]:
    with SUBREDDITS_PATH.open() as f:
        data = yaml.safe_load(f)
    subs = data.get("subreddits", [])
    if not subs:
        raise ValueError("subreddits.yaml has no `subreddits` list")
    return subs


def roles() -> list[str]:
    return load_taxonomy()["roles"]


def topics() -> list[str]:
    return load_taxonomy()["topics"]


def competitors() -> list[str]:
    return load_taxonomy()["competitors"]

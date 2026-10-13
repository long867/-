"""Versioned UN country/area directory, separate from measured coverage."""

import json
from functools import lru_cache
from pathlib import Path


@lru_cache
def country_catalog() -> list[dict[str, str]]:
    """Load Chinese names and ISO identifiers without a network dependency."""
    document = json.loads(
        Path(__file__).with_name("countries.json").read_text(encoding="utf-8")
    )
    return document["items"]

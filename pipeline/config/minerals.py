"""Resource directory metadata, independent of quotation coverage."""

import json
from functools import lru_cache
from pathlib import Path


@lru_cache
def mineral_catalog() -> list[dict[str, str]]:
    """Load the maintained resource directory without inventing price records."""
    return json.loads(
        Path(__file__).with_name("mineral_catalog.json").read_text("utf-8")
    )

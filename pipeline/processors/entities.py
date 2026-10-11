"""spaCy EntityRuler plus bilingual mineral-domain dictionaries."""

import json
import re
from functools import lru_cache
from pathlib import Path

import spacy
from spacy.language import Language


@lru_cache
def lexicon() -> dict[str, dict[str, list[str]]]:
    return json.loads(
        (Path(__file__).parents[1] / "config" / "entities.json").read_text(
            encoding="utf-8"
        )
    )


@lru_cache
def nlp() -> Language:
    """Load lightweight rule-based NER without a separate model download."""
    model = spacy.blank("xx")
    ruler = model.add_pipe("entity_ruler", config={"phrase_matcher_attr": "LOWER"})
    ruler.add_patterns(
        [
            {"label": kind.upper(), "pattern": alias, "id": name}
            for kind, entries in lexicon().items()
            for name, aliases in entries.items()
            for alias in aliases
        ]
    )
    return model


def extract_entities(text: str) -> dict[str, list[str]]:
    """Extract canonical entities; Chinese matches do not depend on whitespace."""
    result: dict[str, set[str]] = {kind: set() for kind in lexicon()}
    for entity in nlp()(text[:200000]).ents:
        result[entity.label_.lower()].add(entity.ent_id_)
    for kind, entries in lexicon().items():
        for name, aliases in entries.items():
            for alias in aliases:
                pattern = re.escape(alias)
                if alias.isascii():
                    pattern = rf"(?<![a-zA-Z]){pattern}(?![a-zA-Z])"
                if re.search(pattern, text, re.IGNORECASE):
                    result[kind].add(name)
                    break
    return {key: sorted(value) for key, value in result.items()}

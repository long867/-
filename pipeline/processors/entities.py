"""spaCy EntityRuler plus bilingual mineral-domain dictionaries."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.config import get_settings

if TYPE_CHECKING:
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
    import spacy

    model = spacy.blank("xx")
    ruler = model.add_pipe("entity_ruler", config={"phrase_matcher_attr": "LOWER"})
    ruler.add_patterns(
        [
            {"label": kind.upper(), "pattern": alias, "id": name}
            for kind, entries in lexicon().items()
            if kind != "regions"
            for name, aliases in entries.items()
            for alias in aliases
        ]
    )
    return model


@lru_cache
def entity_patterns() -> dict[str, list[tuple[str, re.Pattern[str]]]]:
    """Compile once; country names use word boundaries outside Chinese text."""
    patterns = {}
    for kind, entries in lexicon().items():
        patterns[kind] = []
        for name, aliases in entries.items():
            for alias in aliases:
                pattern = re.escape(alias)
                if kind == "regions" and not re.search(r"[\u3400-\u9fff]", alias):
                    pattern = rf"(?<!\w){pattern}(?!\w)"
                elif alias.isascii():
                    pattern = rf"(?<![a-zA-Z]){pattern}(?![a-zA-Z])"
                patterns[kind].append((name, re.compile(pattern, re.IGNORECASE)))
    return patterns


@lru_cache
def region_patterns() -> list[tuple[str, str, re.Pattern[str]]]:
    """Retain a cheap literal prefilter before expensive multilingual boundaries."""
    aliases = (alias for values in lexicon()["regions"].values() for alias in values)
    return [
        (name, alias.casefold(), pattern)
        for (name, pattern), alias in zip(
            entity_patterns()["regions"], aliases, strict=True
        )
    ]


def extract_regions(text: str) -> list[str]:
    """Prefer longer country names: Guinea must not match Papua New Guinea."""
    text = text[:200000]
    folded = text.casefold()
    spans = [
        (match.start(), match.end(), name)
        for name, literal, pattern in region_patterns()
        if literal in folded
        for match in pattern.finditer(text)
    ]
    selected: list[tuple[int, int, str]] = []
    for start, end, name in sorted(
        spans, key=lambda item: item[1] - item[0], reverse=True
    ):
        if not any(
            start < other_end and end > other_start
            for other_start, other_end, _ in selected
        ):
            selected.append((start, end, name))
    return sorted({name for _, _, name in selected})


def extract_entities(text: str) -> dict[str, list[str]]:
    """Extract canonical entities; Chinese matches do not depend on whitespace."""
    result: dict[str, set[str]] = {kind: set() for kind in lexicon()}
    if get_settings().ENTITY_MATCHER == "spacy":
        for entity in nlp()(text[:200000]).ents:
            result[entity.label_.lower()].add(entity.ent_id_)
    for kind, patterns in entity_patterns().items():
        if kind == "regions":
            result[kind].update(extract_regions(text))
        else:
            for name, pattern in patterns:
                if name not in result[kind] and pattern.search(text):
                    result[kind].add(name)
    return {key: sorted(value) for key, value in result.items()}

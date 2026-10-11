"""URL normalization, title similarity and deterministic 64-bit SimHash."""

import hashlib
import re
import unicodedata
from difflib import SequenceMatcher

from pipeline.fetchers.http import canonical_url


def normalize_url(url: str) -> str:
    """Strip tracking parameters and fragments while retaining content identifiers."""
    return canonical_url(url)


def normalize_title(title: str) -> str:
    """Normalize Unicode, case and punctuation for comparable title strings."""
    return re.sub(
        r"[\W_]+", " ", unicodedata.normalize("NFKC", title).casefold()
    ).strip()


def title_similarity(first: str, second: str) -> float:
    """Compare normalized titles with SequenceMatcher, avoiding autojunk bias."""
    return SequenceMatcher(
        None, normalize_title(first), normalize_title(second), autojunk=False
    ).ratio()


def is_duplicate_title(first: str, second: str, threshold: float = 0.85) -> bool:
    """Treat sufficiently similar titles as duplicate candidates."""
    return (
        bool(first.strip() and second.strip())
        and title_similarity(first, second) >= threshold
    )


def simhash(content: str) -> str:
    """Hash word shingles and Chinese bigrams into a stable unsigned hex string."""
    normalized = unicodedata.normalize("NFKC", content).casefold()
    words = re.findall(r"[a-z0-9]+", normalized)
    cjk = re.findall(r"[\u3400-\u9fff]+", normalized)
    tokens = [" ".join(words[i : i + 3]) for i in range(max(1, len(words) - 2))]
    tokens += [part[i : i + 2] for part in cjk for i in range(max(1, len(part) - 1))]
    weights = [0] * 64
    for token in tokens:
        if not token:
            continue
        hashed = int.from_bytes(
            hashlib.blake2b(token.encode(), digest_size=8).digest(), "big"
        )
        for bit in range(64):
            weights[bit] += 1 if hashed & (1 << bit) else -1
    value = sum(1 << bit for bit, weight in enumerate(weights) if weight > 0)
    return f"{value:016x}"


def hamming_distance(first: str, second: str) -> int:
    """Return the number of different bits in two 64-bit fingerprints."""
    return (int(first, 16) ^ int(second, 16)).bit_count()


def same_content(first: str, second: str) -> bool:
    """Require sufficient body length before treating SimHash proximity as a copy."""
    return (
        min(len(first), len(second)) >= 200
        and hamming_distance(simhash(first), simhash(second)) <= 3
    )

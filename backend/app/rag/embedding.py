"""Lazy BGE-M3 embeddings and multilingual cross-encoder reranking."""

import asyncio
import math
from functools import lru_cache
from numbers import Real
from pathlib import Path
from threading import Lock
from typing import Any

from app.core.config import get_settings

_encoder_lock = Lock()
_reranker_lock = Lock()


@lru_cache
def resolve_model_path(model_id: str) -> str:
    """Download PyTorch weights only, excluding redundant ONNX exports."""
    if Path(model_id).is_dir():
        return model_id
    from huggingface_hub import snapshot_download

    return snapshot_download(
        model_id,
        cache_dir=get_settings().MODEL_CACHE_DIR or None,
        allow_patterns=["*.json", "*.bin", "*.safetensors", "*.model", "*.pt"],
    )


@lru_cache
def embedding_model() -> Any:
    """Load one optional BGE encoder lazily per process."""
    from FlagEmbedding import BGEM3FlagModel

    settings = get_settings()
    return BGEM3FlagModel(
        resolve_model_path(settings.EMBEDDING_MODEL),
        use_fp16=False,
        devices=settings.ML_DEVICE,
        cache_dir=settings.MODEL_CACHE_DIR or None,
    )


@lru_cache
def reranking_model() -> Any:
    """Load one optional cross-encoder lazily per process."""
    from FlagEmbedding import FlagReranker

    settings = get_settings()
    return FlagReranker(
        resolve_model_path(settings.RERANKER_MODEL),
        use_fp16=False,
        devices=settings.ML_DEVICE,
        cache_dir=settings.MODEL_CACHE_DIR or None,
    )


def validate_vector(vector: list[float]) -> list[float]:
    """Reject wrong dimensions, NaNs and zero vectors before database writes."""
    if len(vector) != 1024 or not all(math.isfinite(value) for value in vector):
        raise ValueError("BGE-M3 vectors must contain 1024 finite numbers")
    if sum(value * value for value in vector) <= 0:
        raise ValueError("Zero vectors are not semantic embeddings")
    return vector


async def embed(texts: list[str], *, max_tokens: int = 512) -> list[list[float] | None]:
    """Return null embeddings in explicit keyword mode, never pseudo-vectors."""
    if not texts:
        return []
    if not get_settings().ML_ENABLED:
        return [None] * len(texts)

    def run() -> list[list[float]]:
        # The model tokenizer, including special tokens, enforces this budget.
        with _encoder_lock:
            encoded = embedding_model().encode(
                texts, batch_size=8, max_length=max_tokens
            )
            vectors = [validate_vector(row.tolist()) for row in encoded["dense_vecs"]]
        if len(vectors) != len(texts):
            raise ValueError("Encoder returned an unexpected number of vectors")
        return vectors

    return await asyncio.to_thread(run)


async def rerank(query: str, texts: list[str]) -> list[float] | None:
    """Score candidate passages using bge-reranker-v2-m3 when enabled."""
    if not get_settings().ML_ENABLED or not texts:
        return None

    def run() -> list[float]:
        with _reranker_lock:
            scores = reranking_model().compute_score(
                [[query, text] for text in texts], normalize=True
            )
        result = (
            [float(scores)] if isinstance(scores, Real) else list(map(float, scores))
        )
        if len(result) != len(texts) or not all(
            math.isfinite(value) for value in result
        ):
            raise ValueError("Reranker must return a finite score for every candidate")
        return result

    return await asyncio.to_thread(run)

"""Hourly incremental index entrypoint; original names remain compatible."""

from app.tasks.index import dispatch_index, encode_article, sync_vectors

__all__ = ["dispatch_index", "encode_article", "sync_vectors"]

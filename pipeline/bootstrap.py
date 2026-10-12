"""Enrich bounded public archives using durable, independently validated batches."""

import argparse
import asyncio
import json
from collections import Counter, deque
from pathlib import Path
from time import monotonic

from pipeline.import_backfill import validate_record
from pipeline.processors.backfill import EditorialDocument, enrich_editorial_batch
from pipeline.processors.dedup import normalize_url
from pipeline.processors.entities import extract_entities
from pipeline.schemas import RawArticle, SourceDefinition


def load_completed(path: Path) -> set[str]:
    """Reuse only complete checkpoint lines; a partial last line is not committed."""
    result = set()
    if path.exists():
        payload = path.read_bytes()
        if payload and not payload.endswith(b"\n"):
            payload = payload[: payload.rfind(b"\n") + 1]
            path.write_bytes(payload)
        for line in payload.decode("utf-8").splitlines():
            value = json.loads(line)
            result.add(normalize_url(value["article"]["url"]))
    return result


def candidates(directories: list[Path]) -> list[EditorialDocument]:
    """Prefer complete original evidence and alternate publishers for diversity."""
    documents = {}
    for directory in directories:
        for path in sorted(directory.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or "source" not in data:
                continue
            source = SourceDefinition.model_validate(data["source"])
            for value in data.get("articles", []):
                row = RawArticle.model_validate(value)
                row.url = normalize_url(row.url)
                if (
                    len(row.content) < 160
                    or not extract_entities(row.title + "\n" + row.content)["minerals"]
                ):
                    continue
                previous = documents.get(row.url)
                if previous is None or len(row.content) > len(previous.article.content):
                    documents[row.url] = EditorialDocument(row, source)
    groups = {}
    for document in sorted(
        documents.values(),
        key=lambda d: (
            d.article.published_at.isoformat() if d.article.published_at else ""
        ),
        reverse=True,
    ):
        groups.setdefault(document.source.name, deque()).append(document)
    result = []
    while any(groups.values()):
        for rows in groups.values():
            if rows:
                result.append(rows.popleft())
    return result


async def run(args: argparse.Namespace) -> None:
    """Flush every batch; failed facts stay unpublished and can be retried later."""
    args.output_dir.mkdir(parents=True, exist_ok=True)
    target = args.output_dir / "enriched.jsonl"
    completed = load_completed(target)
    for path in args.reuse_reviewed:
        with (
            path.open(encoding="utf-8") as source,
            target.open("a", encoding="utf-8") as output,
        ):
            for line in source:
                value = json.loads(line)
                url = normalize_url(value["article"]["url"])
                if url not in completed:
                    validate_record(value)
                    output.write(json.dumps(value, ensure_ascii=False) + "\n")
                    completed.add(url)
    failed_path = args.output_dir / "enrichment-failures.json"
    failures = (
        json.loads(failed_path.read_text(encoding="utf-8"))
        if failed_path.exists()
        else {}
    )
    rows = candidates(args.input_dir)
    selected = [
        d
        for d in rows
        if d.article.url not in completed
        and (not args.skip_known_failures or d.article.url not in failures)
    ][: args.limit]
    print(
        json.dumps(
            {
                "candidates": len(rows),
                "completed": len(completed),
                "pending": len(selected),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    counts = Counter()
    started = monotonic()
    for index in range(0, len(selected), args.batch_size):
        batch = selected[index : index + args.batch_size]
        remaining = batch
        successes = {}
        feedback = {}
        for _ in range(2):
            if not remaining:
                break
            try:
                values, feedback = await enrich_editorial_batch(remaining, feedback)
                successes.update(values)
                remaining = [d for d in remaining if d.article.url in feedback]
            except Exception as error:
                feedback = {d.article.url: type(error).__name__ for d in remaining}
                await asyncio.sleep(3)
        with target.open("a", encoding="utf-8") as output:
            for document in batch:
                url = document.article.url
                if url not in successes:
                    failures[url] = {
                        "source": document.source.name,
                        "error": feedback.get(url, "Missing editorial result"),
                    }
                    continue
                value = {
                    "source": document.source.model_dump(mode="json"),
                    "article": document.article.model_dump(mode="json"),
                    "enriched": successes[url],
                }
                try:
                    validate_record(value)
                except ValueError as error:
                    failures[url] = {
                        "source": document.source.name,
                        "error": str(error)[:500],
                    }
                    continue
                output.write(json.dumps(value, ensure_ascii=False) + "\n")
                completed.add(url)
                failures.pop(url, None)
                counts[document.source.name] += 1
        failed_path.write_text(
            json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    "examined": min(index + args.batch_size, len(selected)),
                    "new_reviewed": sum(counts.values()),
                    "per_source": dict(counts),
                    "failures": len(failures),
                    "elapsed_seconds": round(monotonic() - started),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        await asyncio.sleep(0.5)
    print(
        json.dumps(
            {
                "finished": True,
                "reviewed_total": len(completed),
                "new_reviewed": sum(counts.values()),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


def main() -> None:
    """Run checkpointed historical processing without touching the public database."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reuse-reviewed", type=Path, action="append", default=[])
    parser.add_argument("--limit", type=int, default=2000)
    parser.add_argument("--batch-size", type=int, choices=range(1, 9), default=4)
    parser.add_argument("--skip-known-failures", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.limit <= 10000:
        parser.error("--limit must be between 1 and 10000")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()

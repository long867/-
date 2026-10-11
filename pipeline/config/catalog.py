"""Load validated YAML catalogs without erasing operational checkpoints."""

from pathlib import Path

import yaml
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Source
from pipeline.schemas import SourceDefinition

DEFAULT_CATALOG = Path(__file__).with_name("sources.yaml")


def load_sources(path: Path = DEFAULT_CATALOG) -> list[SourceDefinition]:
    """Validate entries and reject duplicate names or canonical URLs."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    sources = [
        SourceDefinition.model_validate(row)
        for entries in document["sources"].values()
        for row in entries
    ]
    for field in ("name", "url"):
        values = [getattr(source, field) for source in sources]
        if len(set(values)) != len(values):
            raise ValueError(f"Duplicate catalog {field}")
    return sources


async def sync_sources(db: AsyncSession, sources: list[SourceDefinition]) -> None:
    """Upsert metadata; keep manual active switches and HTTP validators intact."""
    for source in sources:
        values = source.model_dump(exclude={"parser_config"})
        values["config_json"] = source.parser_config
        statement = insert(Source).values(**values)
        await db.execute(
            statement.on_conflict_do_update(
                index_elements=[Source.url],
                set_={key: value for key, value in values.items() if key != "active"},
            )
        )

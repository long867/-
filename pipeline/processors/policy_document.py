"""Recognize curated government policy documents without manufacturing mineral tags."""

import re
from urllib.parse import urlsplit

from pipeline.schemas import SourceDefinition


def verified_policy_source(source: SourceDefinition) -> bool:
    """Require an explicit document type and an authoritative government origin."""
    host = urlsplit(source.url).hostname or ""
    domains = ("gov.uk", "gov.cn", "canada.ca", "gc.ca", "industry.gov.au", "europa.eu")
    return (
        source.category == "policy"
        and source.authority_score >= 8
        and source.parser_config.get("document_kind")
        in {"strategy", "regulation", "proposal"}
        and any(host == domain or host.endswith("." + domain) for domain in domains)
    )


def general_mineral_policy(source: SourceDefinition, title: str, content: str) -> bool:
    """A general mineral law may legitimately have no named mineral entities."""
    return (
        verified_policy_source(source)
        and source.parser_config.get("mineral_scope_all") is True
        and bool(re.search(r"矿产资源|mineral resources", title + "\n" + content, re.I))
    )

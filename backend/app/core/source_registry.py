from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceDefinition:
    key: str
    publisher: str
    rss_url: str
    source_type: str = "secondary"


_TRUSTED_SOURCES: tuple[SourceDefinition, ...] = (
    SourceDefinition(
        key="reuters",
        publisher="Reuters",
        rss_url="https://feeds.reuters.com/reuters/technologyNews",
    ),
    SourceDefinition(
        key="associated-press",
        publisher="Associated Press",
        rss_url="https://apnews.com/hub/ap-top-news?output=xml",
    ),
    SourceDefinition(
        key="ars-technica",
        publisher="Ars Technica",
        rss_url="https://feeds.arstechnica.com/arstechnica/index",
    ),
    SourceDefinition(
        key="the-verge",
        publisher="The Verge",
        rss_url="https://www.theverge.com/rss/index.xml",
    ),
    SourceDefinition(
        key="wired",
        publisher="WIRED",
        rss_url="https://www.wired.com/feed/rss",
    ),
)


def get_trusted_sources() -> list[SourceDefinition]:
    return list(_TRUSTED_SOURCES)

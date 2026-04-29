from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from app.core.source_registry import SourceDefinition


@dataclass(frozen=True)
class RSSArticle:
    source_key: str
    publisher: str
    title: str
    url: str
    summary: str
    published_at: datetime
    source_type: str


def fetch_rss_xml(
    source: SourceDefinition,
    *,
    user_agent: str,
    timeout_seconds: int = 20,
) -> str:
    request = Request(
        source.rss_url,
        headers={"User-Agent": user_agent},
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8")


def parse_rss_feed(source: SourceDefinition, rss_xml: str) -> list[RSSArticle]:
    root = ElementTree.fromstring(rss_xml)
    articles: list[RSSArticle] = []

    for item in root.findall("./channel/item"):
        title = _text_or_default(item.findtext("title"), default="Untitled article")
        url = _text_or_default(item.findtext("link"), default="")
        summary = _text_or_default(item.findtext("description"), default=title)
        published_at = _parse_pub_date(item.findtext("pubDate"))

        articles.append(
            RSSArticle(
                source_key=source.key,
                publisher=source.publisher,
                title=title,
                url=url,
                summary=summary,
                published_at=published_at,
                source_type=source.source_type,
            )
        )

    return articles


def _text_or_default(value: str | None, *, default: str) -> str:
    if value is None:
        return default

    stripped = value.strip()
    return stripped or default


def _parse_pub_date(value: str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)

    parsed = parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)

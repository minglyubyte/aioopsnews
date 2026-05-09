from __future__ import annotations

import re
import zlib
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from io import BytesIO
from typing import Any, Protocol

import httpx
from pypdf import PdfReader

from app.db.repository_protocol import IncidentRepository
from app.services.autonomous_vehicle_details import (
    extract_autonomous_vehicle_facts,
    summarize_autonomous_vehicle_facts,
)

SOURCE_EVIDENCE_TEXT_MAX_CHARS = 50_000
REVIEW_EVIDENCE_CONTEXT_MAX_CHARS = 30_000
DEFAULT_SOURCE_FETCH_HEADERS = {"User-Agent": "AIRealityCheckBot/1.0"}
BROWSER_SOURCE_FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
AUTONOMOUS_REVIEW_KEYWORDS = (
    "structured autonomous vehicle facts",
    "autonomous",
    "collision",
    "accident",
    "crash",
    "narrative",
    "injury",
    "damage",
    "driver",
    "safety driver",
    "test driver",
    "human takeover",
    "manual",
    "level 4",
    "ads",
    "mode",
    "vehicle",
    "bicyclist",
    "pedestrian",
    "motorcyclist",
    "passenger car",
    "intersection",
    "street",
)


@dataclass(frozen=True)
class FetchedIncidentSource:
    source_url: str
    canonical_url: str | None
    fetch_status: str
    http_status: int | None
    evidence_text: str | None
    fetch_error: str | None = None


class IncidentSourceFetcher(Protocol):
    def fetch(self, source_url: str) -> FetchedIncidentSource: ...


class HttpIncidentSourceFetcher:
    def __init__(self, *, timeout_seconds: float = 15.0) -> None:
        self._timeout_seconds = timeout_seconds

    def fetch(self, source_url: str) -> FetchedIncidentSource:
        try:
            response = self._get(source_url, headers=DEFAULT_SOURCE_FETCH_HEADERS)
            if response.status_code == 403:
                response = self._get(
                    source_url,
                    headers=BROWSER_SOURCE_FETCH_HEADERS,
                )
        except httpx.HTTPError as exc:
            return FetchedIncidentSource(
                source_url=source_url,
                canonical_url=None,
                fetch_status="failed",
                http_status=None,
                evidence_text=None,
                fetch_error=str(exc),
            )

        evidence_text = extract_response_evidence_text(response)
        fetch_status = "fetched" if response.is_success else "failed"
        return FetchedIncidentSource(
            source_url=source_url,
            canonical_url=str(response.url),
            fetch_status=fetch_status,
            http_status=response.status_code,
            evidence_text=evidence_text if response.is_success else None,
            fetch_error=None if response.is_success else response.reason_phrase,
        )

    def _get(
        self,
        source_url: str,
        *,
        headers: dict[str, str],
    ) -> httpx.Response:
        return httpx.get(
            source_url,
            follow_redirects=True,
            timeout=self._timeout_seconds,
            headers=headers,
        )


def refresh_source_evidence(
    repository: IncidentRepository,
    *,
    incidents: list[dict[str, Any]],
    source_fetcher: IncidentSourceFetcher,
) -> None:
    for incident in incidents:
        for source in incident.get("sources", []):
            fetched = source_fetcher.fetch(source["source_url"])
            repository.update_incident_source_evidence(
                source_id=source["id"],
                canonical_url=fetched.canonical_url,
                fetch_status=fetched.fetch_status,
                http_status=fetched.http_status,
                evidence_text=fetched.evidence_text,
                fetch_error=fetched.fetch_error,
                fetched_at=_now_isoformat(),
            )


def build_review_source_context(
    sources: list[dict[str, Any]],
    *,
    max_chars: int = REVIEW_EVIDENCE_CONTEXT_MAX_CHARS,
) -> list[dict[str, Any]]:
    used_chars = 0
    review_sources: list[dict[str, Any]] = []
    for source in sorted(sources, key=_review_source_priority):
        remaining = max(max_chars - used_chars, 0)
        evidence_text = select_review_evidence_text(
            source.get("evidence_text"),
            max_chars=remaining,
        )
        used_chars += len(evidence_text or "")
        review_sources.append(
            {
                "source_url": source["source_url"],
                "canonical_url": source.get("canonical_url"),
                "fetch_status": source.get("fetch_status"),
                "http_status": source.get("http_status"),
                "evidence_text": evidence_text,
                "source_origin": source.get("source_origin"),
                "source_registry_key": source.get("source_registry_key"),
            }
        )
    return review_sources


def _review_source_priority(source: dict[str, Any]) -> tuple[int, int]:
    source_url = str(source.get("source_url") or "").lower()
    has_evidence = bool(source.get("evidence_text"))
    is_fetched = source.get("fetch_status") == "fetched"

    if source.get("is_primary") or _looks_like_incident_document_url(source_url):
        source_rank = 0
    elif _looks_like_source_index_url(source_url):
        source_rank = 2
    else:
        source_rank = 1

    fetch_rank = 0 if is_fetched and has_evidence else 1
    return (source_rank, fetch_rank)


def _looks_like_incident_document_url(source_url: str) -> bool:
    return (
        source_url.endswith(".pdf")
        or "/portal/file/" in source_url
        or source_url.endswith("-pdf/")
        or source_url.endswith("-pdf")
    )


def _looks_like_source_index_url(source_url: str) -> bool:
    return (
        "autonomous-vehicle-collision-reports" in source_url
        or "standing-general-order-crash-reporting" in source_url
    )


def select_review_evidence_text(
    evidence_text: str | None,
    *,
    max_chars: int = REVIEW_EVIDENCE_CONTEXT_MAX_CHARS,
) -> str | None:
    if evidence_text is None:
        return None
    normalized = _normalize_evidence_text(evidence_text, max_chars=None)
    if len(normalized) <= max_chars:
        return normalized
    if max_chars <= 0:
        return ""

    selected_parts: list[str] = []
    fact_summary = _structured_fact_summary(normalized)
    if fact_summary:
        selected_parts.append(fact_summary)

    selected_parts.extend(_keyword_relevant_sentences(normalized))
    selected_parts.append(normalized[: max(max_chars // 3, 1)])
    selected_parts.append(normalized[-max(max_chars // 6, 1) :])
    return _join_unique_with_budget(selected_parts, max_chars=max_chars)


def extract_evidence_text(
    html: str,
    *,
    max_chars: int = SOURCE_EVIDENCE_TEXT_MAX_CHARS,
) -> str:
    parser = _MarkdownEvidenceHTMLParser()
    parser.feed(html)
    parser.close()
    return _normalize_evidence_text(parser.markdown_text(), max_chars=max_chars)


def extract_response_evidence_text(response: httpx.Response) -> str:
    content_type = response.headers.get("content-type", "").lower()
    if "application/pdf" in content_type or str(response.url).lower().endswith(
        ".pdf"
    ):
        evidence = extract_pdf_evidence_text(response.content)
    else:
        evidence = extract_evidence_text(response.text)

    fact_summary = summarize_autonomous_vehicle_facts(
        extract_autonomous_vehicle_facts(evidence)
    )
    if fact_summary:
        evidence = (
            f"{evidence}\n\nStructured autonomous vehicle facts: {fact_summary}"
        )
    return _normalize_evidence_text(
        evidence,
        max_chars=SOURCE_EVIDENCE_TEXT_MAX_CHARS,
    )


def extract_pdf_evidence_text(content: bytes) -> str:
    parsed_text = _extract_pdf_text_with_pypdf(content)
    if parsed_text:
        return _normalize_evidence_text(
            parsed_text,
            max_chars=SOURCE_EVIDENCE_TEXT_MAX_CHARS,
        )

    decoded_parts = [content.decode("latin-1", errors="ignore")]
    decoded_parts.extend(_extract_pdf_stream_text(content))
    decoded = " ".join(decoded_parts)
    literal_strings = re.findall(r"\(([^()]{3,})\)", decoded)
    if literal_strings:
        return _normalize_evidence_text(
            " ".join(_decode_pdf_literal_string(value) for value in literal_strings),
            max_chars=SOURCE_EVIDENCE_TEXT_MAX_CHARS,
        )
    return _normalize_evidence_text(
        decoded,
        max_chars=SOURCE_EVIDENCE_TEXT_MAX_CHARS,
    )


class _MarkdownEvidenceHTMLParser(HTMLParser):
    _SKIP_TAGS = {
        "button",
        "footer",
        "form",
        "head",
        "header",
        "nav",
        "noscript",
        "script",
        "style",
        "svg",
        "template",
    }
    _CHROME_ATTR_KEYWORDS = (
        "ask-dmv",
        "breadcrumb",
        "chat",
        "cookie",
        "disclaimer",
        "footer",
        "header",
        "menu",
        "modal",
        "nav",
        "search",
        "social",
        "subscribe",
        "virtual-assistant",
    )
    _BLOCK_TAGS = {
        "article",
        "aside",
        "blockquote",
        "div",
        "main",
        "p",
        "section",
        "table",
        "tbody",
        "thead",
        "tfoot",
        "tr",
    }
    _HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._lines: list[str] = []
        self._chunks: list[str] = []
        self._prefix = ""
        self._skip_depth = 0
        self._skip_stack: list[str] = []
        self._link_stack: list[tuple[str, list[str]]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        tag = tag.lower()
        if tag in self._SKIP_TAGS or self._is_chrome_container(tag, attrs):
            self._skip_depth += 1
            self._skip_stack.append(tag)
            return
        if self._skip_depth:
            return

        if tag in self._HEADING_TAGS:
            level = int(tag[1])
            self._start_block(f"{'#' * level} ")
        elif tag == "li":
            self._start_block("- ")
        elif tag in self._BLOCK_TAGS:
            self._start_block("")
        elif tag in {"td", "th"}:
            self._append_separator(" | ")
        elif tag == "br":
            self._append_text(" ")
        elif tag == "a":
            href = self._attrs_dict(attrs).get("href") or ""
            self._link_stack.append((href, []))

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._skip_depth:
            if self._skip_stack and tag == self._skip_stack[-1]:
                self._skip_stack.pop()
                self._skip_depth -= 1
            return

        if tag == "a":
            self._close_link()
        elif tag in self._HEADING_TAGS or tag in self._BLOCK_TAGS or tag == "li":
            self._end_block()
        elif tag in {"td", "th"}:
            self._append_separator(" | ")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        self._append_text(data)

    def markdown_text(self) -> str:
        self._end_block()
        return "\n".join(self._lines)

    def _start_block(self, prefix: str) -> None:
        self._end_block()
        self._prefix = prefix

    def _end_block(self) -> None:
        if self._link_stack:
            return
        text = _normalize_evidence_text(" ".join(self._chunks), max_chars=None)
        self._chunks = []
        if not text:
            self._prefix = ""
            return
        self._lines.append(f"{self._prefix}{text}")
        self._prefix = ""

    def _append_text(self, text: str) -> None:
        if self._link_stack:
            self._link_stack[-1][1].append(text)
        else:
            self._chunks.append(text)

    def _append_separator(self, separator: str) -> None:
        if self._chunks and self._chunks[-1] != separator:
            self._chunks.append(separator)

    def _close_link(self) -> None:
        if not self._link_stack:
            return
        href, chunks = self._link_stack.pop()
        label = _normalize_evidence_text(" ".join(chunks), max_chars=None)
        if href and label:
            self._append_text(f"[{label}]({href})")
        elif label:
            self._append_text(label)
        elif href:
            self._append_text(href)

    @staticmethod
    def _attrs_dict(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {key.lower(): value for key, value in attrs if value is not None}

    @classmethod
    def _is_chrome_container(
        cls,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> bool:
        if tag not in {"aside", "div", "section"}:
            return False
        attrs_dict = cls._attrs_dict(attrs)
        chrome_text = " ".join(
            attrs_dict.get(name, "")
            for name in ("aria-label", "class", "id", "role")
        ).lower()
        return any(keyword in chrome_text for keyword in cls._CHROME_ATTR_KEYWORDS)


def _extract_pdf_text_with_pypdf(content: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(content))
        if reader.is_encrypted:
            reader.decrypt("")
    except Exception:
        return ""

    parts: list[str] = []
    parts.extend(_extract_pdf_form_field_text(reader))

    for page in reader.pages:
        try:
            page_text = page.extract_text()
        except Exception:
            page_text = None
        if page_text:
            parts.append(page_text)
    return " ".join(parts)


def _extract_pdf_form_field_text(reader: PdfReader) -> list[str]:
    try:
        fields = reader.get_fields() or {}
    except Exception:
        return []

    field_text: list[str] = []
    for name, field in fields.items():
        value = field.get("/V") or field.get("/DV")
        if value is None:
            continue
        label = field.get("/T") or name
        field_text.append(f"{label}: {value}")
    return field_text


def _extract_pdf_stream_text(content: bytes) -> list[str]:
    stream_texts: list[str] = []
    for match in re.finditer(
        rb"<<(?P<dictionary>.*?)>>\s*stream\r?\n(?P<stream>.*?)\r?\nendstream",
        content,
        flags=re.DOTALL,
    ):
        dictionary = match.group("dictionary")
        stream = match.group("stream").strip()
        if b"/FlateDecode" not in dictionary:
            continue
        try:
            stream = zlib.decompress(stream)
        except zlib.error:
            continue
        stream_texts.append(stream.decode("latin-1", errors="ignore"))
    return stream_texts


def _decode_pdf_literal_string(value: str) -> str:
    return (
        value.replace(r"\(", "(")
        .replace(r"\)", ")")
        .replace(r"\\", "\\")
        .replace(r"\n", " ")
        .replace(r"\r", " ")
        .replace(r"\t", " ")
    )


def _normalize_evidence_text(
    value: str,
    *,
    max_chars: int | None,
) -> str:
    text = value.replace("\x00", " ").replace("\r", " ").replace("\n", " ")
    collapsed = " ".join(text.split())
    return collapsed if max_chars is None else collapsed[:max_chars]


def _structured_fact_summary(text: str) -> str:
    marker = "Structured autonomous vehicle facts:"
    marker_index = text.lower().find(marker.lower())
    if marker_index < 0:
        return ""
    return text[marker_index : marker_index + 4_000]


def _keyword_relevant_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    selected: list[str] = []
    for sentence in sentences:
        lowered = sentence.lower()
        if any(keyword in lowered for keyword in AUTONOMOUS_REVIEW_KEYWORDS):
            selected.append(sentence)
    return selected


def _join_unique_with_budget(parts: list[str], *, max_chars: int) -> str:
    seen: set[str] = set()
    output: list[str] = []
    used = 0
    for part in parts:
        cleaned = _normalize_evidence_text(part, max_chars=None)
        if not cleaned or cleaned in seen:
            continue
        remaining = max_chars - used
        if remaining <= 0:
            break
        if len(cleaned) > remaining:
            cleaned = cleaned[:remaining]
        output.append(cleaned)
        seen.add(cleaned)
        used += len(cleaned)
    return " ".join(output)[:max_chars]


def _now_isoformat() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()

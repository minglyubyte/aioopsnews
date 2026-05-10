from __future__ import annotations

import csv
import html as html_lib
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from html.parser import HTMLParser
from io import StringIO
from typing import Protocol
from urllib.parse import urljoin

import httpx

from app.workflows.dual_track_ingestion import VerifiedSourceRecord

CA_DMV_COLLISION_REPORTS_URL = (
    "https://www.dmv.ca.gov/portal/vehicle-industry-services/"
    "autonomous-vehicles/autonomous-vehicle-collision-reports/"
)
CHARLOTIN_DOWNLOAD_URL = (
    "https://www.damiencharlotin.com/hallucinations/hallucinations/download.csv"
)
CHARLOTIN_HOME_URL = "https://www.damiencharlotin.com/hallucinations/"
EDRM_JUDICIAL_ORDERS_URL = "https://edrm.net/judicial-orders-2/"
NHTSA_SGO_URL = (
    "https://www.nhtsa.gov/laws-regulations/standing-general-order-crash-reporting"
)
FTC_OPERATION_AI_COMPLY_URL = (
    "https://www.ftc.gov/news-events/news/press-releases/2024/09/"
    "ftc-announces-crackdown-deceptive-ai-claims-schemes"
)
DOJ_REALPAGE_AI_ENFORCEMENT_URL = (
    "https://www.justice.gov/atr/case-document/complaint-303"
)
SEC_AI_WASHING_URL = "https://www.sec.gov/newsroom/press-releases/2024-36"
SEC_RIMAR_AI_CLAIMS_URL = "https://www.sec.gov/newsroom/press-releases/2024-167"

FTC_AI_ENFORCEMENT_URLS = (FTC_OPERATION_AI_COMPLY_URL,)
DOJ_AI_ENFORCEMENT_URLS = (DOJ_REALPAGE_AI_ENFORCEMENT_URL,)
SEC_AI_ENFORCEMENT_URLS = (SEC_AI_WASHING_URL, SEC_RIMAR_AI_CLAIMS_URL)

DEFAULT_VERIFIED_SOURCES = (
    "ca_dmv_av_collisions",
    "nhtsa_data",
    "damien_charlotin_hallucinations",
    "edrm_judicial_orders",
    "ftc_ai_enforcement",
    "doj_ai_enforcement",
    "sec_ai_enforcement",
)

LOGGER = logging.getLogger(__name__)


class _HttpResponse(Protocol):
    text: str

    def raise_for_status(self) -> None: ...


class _HttpClient(Protocol):
    def get(self, url: str) -> _HttpResponse: ...


@dataclass(frozen=True)
class _Anchor:
    text: str
    href: str


def fetch_verified_source_records(
    *,
    sources: list[str] | None = None,
    since: str | None = None,
    limit_per_source: int = 50,
    http_client: _HttpClient | None = None,
) -> list[VerifiedSourceRecord]:
    selected_sources = sources or list(DEFAULT_VERIFIED_SOURCES)
    client = http_client or httpx.Client(
        timeout=30.0,
        follow_redirects=True,
        headers={
            "User-Agent": (
                "AI-Oops verified-source crawler "
                "(local development; contact repository operator)"
            )
        },
    )
    records: list[VerifiedSourceRecord] = []
    for source in selected_sources:
        try:
            source_records = _fetch_one_source(
                source=source,
                client=client,
                limit_per_source=limit_per_source,
            )
        except Exception as exc:
            if source not in DEFAULT_VERIFIED_SOURCES:
                raise
            LOGGER.warning("Skipping verified source %s: %s", source, exc)
            continue

        records.extend(_filter_since(source_records, since))
    return _dedupe_external_ids(records)


def _fetch_one_source(
    *,
    source: str,
    client: _HttpClient,
    limit_per_source: int,
) -> list[VerifiedSourceRecord]:
    if source == "ca_dmv_av_collisions":
        response = client.get(CA_DMV_COLLISION_REPORTS_URL)
        response.raise_for_status()
        return parse_ca_dmv_collision_records(
            response.text,
            limit=limit_per_source,
        )
    if source == "damien_charlotin_hallucinations":
        response = client.get(CHARLOTIN_DOWNLOAD_URL)
        response.raise_for_status()
        return parse_charlotin_hallucination_records(
            response.text,
            limit=limit_per_source,
        )
    if source == "edrm_judicial_orders":
        response = client.get(EDRM_JUDICIAL_ORDERS_URL)
        response.raise_for_status()
        return parse_edrm_judicial_order_records(
            response.text,
            limit=limit_per_source,
        )
    if source == "nhtsa_data":
        return _fetch_nhtsa_records(
            client=client,
            limit=limit_per_source,
        )
    if source == "ftc_ai_enforcement":
        return _fetch_official_ai_enforcement_records(
            client=client,
            urls=FTC_AI_ENFORCEMENT_URLS,
            parser=parse_ftc_ai_enforcement_records,
            limit=limit_per_source,
        )
    if source == "doj_ai_enforcement":
        return _fetch_official_ai_enforcement_records(
            client=client,
            urls=DOJ_AI_ENFORCEMENT_URLS,
            parser=parse_doj_ai_enforcement_records,
            limit=limit_per_source,
        )
    if source == "sec_ai_enforcement":
        return _fetch_official_ai_enforcement_records(
            client=client,
            urls=SEC_AI_ENFORCEMENT_URLS,
            parser=parse_sec_ai_enforcement_records,
            limit=limit_per_source,
        )
    raise ValueError(f"Unsupported verified source: {source}")


def parse_ca_dmv_collision_records(
    html: str,
    *,
    limit: int,
) -> list[VerifiedSourceRecord]:
    records: list[VerifiedSourceRecord] = []
    for anchor in _extract_anchors(html, base_url=CA_DMV_COLLISION_REPORTS_URL):
        match = re.fullmatch(
            r"(?P<company>.+?) (?P<month>[A-Za-z]+) (?P<day>\d{1,2}), "
            r"(?P<year>\d{4})(?: \((?P<suffix>[^)]+)\))? \(PDF\)",
            anchor.text.strip(),
        )
        if match is None:
            continue

        incident_date = _parse_date(
            f"{match['month']} {match['day']}, {match['year']}"
        )
        company = match["company"].strip()
        suffix = _slug(match["suffix"]) if match["suffix"] else ""
        external_id = "-".join(
            part
            for part in (
                "ca-dmv",
                _slug(company),
                incident_date,
                suffix,
            )
            if part
        )
        records.append(
            VerifiedSourceRecord(
                source_registry_key="ca_dmv_av_collisions",
                external_id=external_id,
                title=f"{company} {anchor.text.strip()} collision report",
                incident_date=incident_date,
                company=company,
                summary=(
                    "California DMV published an autonomous vehicle collision "
                    f"report for {company} dated {incident_date}."
                ),
                source_url=anchor.href,
                publisher="California DMV",
                raw_payload={
                    "index_text": anchor.text.strip(),
                    "index_url": CA_DMV_COLLISION_REPORTS_URL,
                },
            )
        )
        if len(records) >= limit:
            break
    return records


def parse_charlotin_hallucination_records(
    csv_text: str,
    *,
    limit: int,
) -> list[VerifiedSourceRecord]:
    records: list[VerifiedSourceRecord] = []
    for row in csv.DictReader(StringIO(csv_text)):
        normalized = _normalize_row(row)
        case_name = _first_present(normalized, "case", "case name", "title", "name")
        raw_date = _first_present(normalized, "date")
        if not case_name or not raw_date:
            continue
        incident_date = _parse_flexible_date(raw_date)
        court = _first_present(normalized, "court jurisdiction", "court") or "court"
        party = (
            _first_present(normalized, "party using ai", "party ies", "party")
            or "party"
        )
        nature = (
            _first_present(
                normalized,
                "nature of hallucination",
                "hallucination items",
                "nature",
            )
            or ""
        )
        outcome = _first_present(
            normalized,
            "outcome sanction",
            "outcome",
            "sanction",
        )
        details = _first_present(normalized, "details") or ""
        source_url = _first_url(
            _first_present(
                normalized,
                "reports",
                "report s",
                "report",
                "source",
                "pointer",
                "url",
            ),
            details,
        )
        source_url = urljoin(CHARLOTIN_HOME_URL, source_url or CHARLOTIN_HOME_URL)
        summary_parts = [
            f"Damien Charlotin's AI hallucination tracker records {case_name}",
            f"in {court}",
            f"with {party} linked to alleged or found AI legal hallucination.",
        ]
        if outcome:
            summary_parts.append(f"Outcome: {outcome}.")
        if nature:
            summary_parts.append(f"Nature: {nature}.")
        if details:
            summary_parts.append(details)
        records.append(
            VerifiedSourceRecord(
                source_registry_key="damien_charlotin_hallucinations",
                external_id=f"damien-hallucination-{_slug(case_name)}-{incident_date}",
                title=case_name,
                incident_date=incident_date,
                company="Legal filing",
                summary=" ".join(summary_parts),
                source_url=source_url,
                publisher="Damien Charlotin AI Hallucination Cases",
                raw_payload=dict(row),
            )
        )
        if len(records) >= limit:
            break
    return records


def parse_edrm_judicial_order_records(
    html: str,
    *,
    limit: int,
) -> list[VerifiedSourceRecord]:
    rows = _extract_table_rows(html)
    if not rows:
        return []
    header = [_normalize_key(cell) for cell in rows[0]]
    records: list[VerifiedSourceRecord] = []
    for cells in rows[1:]:
        row = dict(zip(header, cells, strict=False))
        court = row.get("court", "").strip()
        judge = row.get("judge", "").strip()
        raw_date = row.get("date", "").strip()
        if _looks_like_repeated_header(row):
            continue
        if not court or not raw_date:
            continue
        incident_date = _parse_flexible_date(raw_date)
        points = row.get("points of interest", "").strip()
        source_url = _first_url(row.get("pdf", "")) or EDRM_JUDICIAL_ORDERS_URL
        title = f"EDRM judicial order: {court}"
        if judge:
            title = f"{title} - {judge}"
        records.append(
            VerifiedSourceRecord(
                source_registry_key="edrm_judicial_orders",
                external_id=f"edrm-order-{_slug(court)}-{_slug(judge)}-{incident_date}",
                title=title,
                incident_date=incident_date,
                company="Judicial order",
                summary=(
                    "EDRM's judicial orders repository lists an order concerning "
                    f"AI use in {court}. Points of interest: {points or 'not listed'}."
                ),
                source_url=source_url,
                publisher="EDRM",
                raw_payload=row,
            )
        )
        if len(records) >= limit:
            break
    return records


def parse_nhtsa_sgo_records(
    csv_text: str,
    *,
    limit: int,
) -> list[VerifiedSourceRecord]:
    records: list[VerifiedSourceRecord] = []
    for row in csv.DictReader(StringIO(csv_text)):
        normalized = _normalize_row(row)
        report_id = _first_present(
            normalized,
            "report id",
            "reportid",
            "unique incident identifier",
            "incident id",
        )
        raw_date = _first_present(
            normalized,
            "incident date",
            "incident month",
            "crash date",
            "date",
        )
        if not report_id or not raw_date:
            continue
        incident_date = _parse_flexible_date(raw_date)
        company = (
            _first_present(
                normalized,
                "reporting entity",
                "manufacturer",
                "make",
                "entity",
            )
            or "Unknown vehicle operator"
        )
        narrative = _first_present(
            normalized,
            "narrative",
            "incident narrative",
            "description",
        )
        vehicle = " ".join(
            part
            for part in (
                _first_present(normalized, "make"),
                _first_present(normalized, "model"),
            )
            if part
        )
        summary = (
            "NHTSA Standing General Order data lists an automation-related "
            f"crash report for {company}."
        )
        if vehicle:
            summary = f"{summary} Vehicle: {vehicle}."
        if narrative:
            summary = f"{summary} Narrative: {narrative}"
        records.append(
            VerifiedSourceRecord(
                source_registry_key="nhtsa_data",
                external_id=f"nhtsa-sgo-{_slug(report_id)}",
                title=f"NHTSA SGO crash report {report_id}",
                incident_date=incident_date,
                company=company,
                summary=summary,
                source_url=f"{NHTSA_SGO_URL}#report-{_slug(report_id)}",
                publisher="NHTSA",
                raw_payload=dict(row),
            )
        )
        if len(records) >= limit:
            break
    return records


def parse_ftc_ai_enforcement_records(
    html: str,
    *,
    source_url: str,
    limit: int,
) -> list[VerifiedSourceRecord]:
    article_html = _html_from_first_heading(html)
    text = _html_to_text(article_html)
    incident_date = _extract_official_date(text)
    if incident_date is None or not _is_ai_enforcement_text(text):
        return []

    records: list[VerifiedSourceRecord] = []
    for heading, section_text in _extract_heading_sections(article_html):
        if not _is_ai_enforcement_text(section_text):
            continue
        company = _clean_entity_name(heading)
        if not company or _is_non_case_heading(company):
            continue
        records.append(
            _official_ai_enforcement_record(
                source_registry_key="ftc_ai_enforcement",
                external_id=f"ftc-ai-{_slug(company)}-{incident_date}",
                title=f"FTC AI enforcement action: {company}",
                incident_date=incident_date,
                company=company,
                source_url=source_url,
                publisher="FTC",
                body_text=section_text,
            )
        )
        if len(records) >= limit:
            break
    return records


def parse_doj_ai_enforcement_records(
    html: str,
    *,
    source_url: str,
    limit: int,
) -> list[VerifiedSourceRecord]:
    text = _html_to_text(_html_from_first_heading(html))
    incident_date = _extract_official_date(text)
    title = _extract_first_heading(html) or "DOJ AI enforcement action"
    company = _extract_doj_company(title, text)
    is_known_ai_case = (
        company == "RealPage"
        and "complaint-303" in source_url
        and "Document Type Complaint" in text
    )
    if incident_date is None or not (
        _is_ai_enforcement_text(text) or is_known_ai_case
    ):
        return []

    if company is None:
        return []
    if title == "Complaint" and company == "RealPage":
        title = "DOJ antitrust complaint: RealPage algorithmic pricing"
    record_source_url = _extract_doj_attachment_url(html, source_url) or source_url
    return [
        _official_ai_enforcement_record(
            source_registry_key="doj_ai_enforcement",
            external_id=f"doj-ai-{_slug(company)}-{incident_date}",
            title=title,
            incident_date=incident_date,
            company=company,
            source_url=record_source_url,
            publisher="DOJ",
            body_text=text,
        )
    ][:limit]


def parse_sec_ai_enforcement_records(
    html: str,
    *,
    source_url: str,
    limit: int,
) -> list[VerifiedSourceRecord]:
    text = _html_to_text(_html_from_first_heading(html))
    incident_date = _extract_official_date(text)
    if incident_date is None or not _is_ai_enforcement_text(text):
        return []

    title = _extract_first_heading(html) or "SEC AI enforcement action"
    companies = _extract_sec_companies(text)
    if not companies:
        company = _extract_sec_company_from_title(title)
        companies = [company] if company else []

    records: list[VerifiedSourceRecord] = []
    for company in companies:
        records.append(
            _official_ai_enforcement_record(
                source_registry_key="sec_ai_enforcement",
                external_id=f"sec-ai-{_slug(company)}-{incident_date}",
                title=title,
                incident_date=incident_date,
                company=company,
                source_url=source_url,
                publisher="SEC",
                body_text=text,
            )
        )
        if len(records) >= limit:
            break
    return records


def _fetch_nhtsa_records(
    *,
    client: _HttpClient,
    limit: int,
) -> list[VerifiedSourceRecord]:
    landing_response = client.get(NHTSA_SGO_URL)
    landing_response.raise_for_status()
    links = _extract_anchors(landing_response.text, base_url=NHTSA_SGO_URL)
    csv_links = [
        link.href
        for link in links
        if "incident report data" in link.text.lower()
        and (link.href.lower().endswith(".csv") or "csv" in link.href.lower())
    ]
    if not csv_links and landing_response.text.lstrip().lower().startswith(
        ("report id,", '"report id"', "incident id,")
    ):
        return parse_nhtsa_sgo_records(landing_response.text, limit=limit)
    records: list[VerifiedSourceRecord] = []
    for href in csv_links:
        data_response = client.get(href)
        data_response.raise_for_status()
        records.extend(parse_nhtsa_sgo_records(data_response.text, limit=limit))
        if len(records) >= limit:
            break
    return records[:limit]


def _fetch_official_ai_enforcement_records(
    *,
    client: _HttpClient,
    urls: tuple[str, ...],
    parser,
    limit: int,
) -> list[VerifiedSourceRecord]:
    records: list[VerifiedSourceRecord] = []
    for url in urls:
        response = client.get(url)
        response.raise_for_status()
        records.extend(parser(response.text, source_url=url, limit=limit))
        if len(records) >= limit:
            break
    return records[:limit]


class _AnchorParser(HTMLParser):
    def __init__(self, *, base_url: str) -> None:
        super().__init__()
        self._base_url = base_url
        self._current_href: str | None = None
        self._current_text: list[str] = []
        self.anchors: list[_Anchor] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.lower() != "a":
            return
        attr_map = dict(attrs)
        href = attr_map.get("href")
        if href:
            self._current_href = urljoin(self._base_url, href)
            self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._current_href is None:
            return
        text = " ".join("".join(self._current_text).split())
        self.anchors.append(_Anchor(text=text, href=self._current_href))
        self._current_href = None
        self._current_text = []


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None
        self._current_href: str | None = None

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        tag = tag.lower()
        if tag == "tr":
            self._current_row = []
        elif tag in {"td", "th"} and self._current_row is not None:
            self._current_cell = []
        elif tag == "a" and self._current_cell is not None:
            href = dict(attrs).get("href")
            if href:
                self._current_href = urljoin(EDRM_JUDICIAL_ORDERS_URL, href)

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._current_cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"td", "th"} and self._current_cell is not None:
            value = " ".join("".join(self._current_cell).split())
            if self._current_href:
                value = f"{value} {self._current_href}".strip()
            self._current_row.append(value)  # type: ignore[union-attr]
            self._current_cell = None
            self._current_href = None
        elif tag == "tr" and self._current_row is not None:
            if self._current_row:
                self.rows.append(self._current_row)
            self._current_row = None


def _extract_anchors(html: str, *, base_url: str) -> list[_Anchor]:
    parser = _AnchorParser(base_url=base_url)
    parser.feed(html)
    return parser.anchors


def _extract_table_rows(html: str) -> list[list[str]]:
    parser = _TableParser()
    parser.feed(html)
    return parser.rows


def _looks_like_repeated_header(row: dict[str, str]) -> bool:
    return any(
        value.strip().lower() == key
        for key, value in row.items()
        if value.strip()
    )


def _official_ai_enforcement_record(
    *,
    source_registry_key: str,
    external_id: str,
    title: str,
    incident_date: str,
    company: str,
    source_url: str,
    publisher: str,
    body_text: str,
) -> VerifiedSourceRecord:
    summary = (
        f"{publisher} official enforcement page records AI-related allegations "
        f"or findings involving {company}. {_summarize_official_text(body_text)}"
    )
    return VerifiedSourceRecord(
        source_registry_key=source_registry_key,
        external_id=external_id,
        title=title,
        incident_date=incident_date,
        company=company,
        summary=summary,
        source_url=source_url,
        publisher=publisher,
        raw_payload={
            "source_url": source_url,
            "source_excerpt": _summarize_official_text(body_text, max_chars=900),
        },
        source_family=_infer_official_source_family(body_text),
    )


def _html_to_text(html: str) -> str:
    without_scripts = re.sub(
        r"(?is)<(script|style).*?>.*?</\1>",
        " ",
        html,
    )
    with_breaks = re.sub(
        r"(?i)</?(?:p|div|br|li|h[1-6]|time)\b[^>]*>",
        " ",
        without_scripts,
    )
    stripped = re.sub(r"<[^>]+>", " ", with_breaks)
    return " ".join(html_lib.unescape(stripped).split())


def _html_from_first_heading(html: str) -> str:
    match = re.search(r"(?is)<h1\b[^>]*>.*?</h1>", html)
    if match is None:
        return html
    return html[match.start() :]


def _extract_first_heading(html: str) -> str | None:
    match = re.search(r"(?is)<h1[^>]*>(.*?)</h1>", html)
    if match is None:
        return None
    return _html_to_text(match.group(1))


def _extract_heading_sections(html: str) -> list[tuple[str, str]]:
    pattern = re.compile(r"(?is)<h2[^>]*>(.*?)</h2>")
    matches = list(pattern.finditer(html))
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(html)
        heading = _html_to_text(match.group(1))
        body = _html_to_text(html[start:end])
        sections.append((heading, body))
    return sections


def _extract_doj_attachment_url(html: str, source_url: str) -> str | None:
    match = re.search(
        r'(?is)<a\s+[^>]*href=["\'](?P<href>[^"\']+)["\'][^>]*>\s*[^<]*\.pdf\s*</a>',
        html,
    )
    if match is None:
        return None
    return urljoin(source_url, match.group("href"))


def _extract_official_date(text: str) -> str | None:
    month_names = (
        "January|February|March|April|May|June|July|August|September|October|"
        "November|December|Jan\\.|Feb\\.|Mar\\.|Apr\\.|Jun\\.|Jul\\.|Aug\\.|"
        "Sept\\.|Sep\\.|Oct\\.|Nov\\.|Dec\\."
    )
    match = re.search(
        rf"\b(?P<month>{month_names})\s+"
        r"(?P<day>\d{1,2}),\s+(?P<year>\d{4})\b",
        text,
    )
    if match is None:
        return None
    month = match.group("month").replace(".", "")
    aliases = {
        "Jan": "January",
        "Feb": "February",
        "Mar": "March",
        "Apr": "April",
        "Jun": "June",
        "Jul": "July",
        "Aug": "August",
        "Sep": "September",
        "Sept": "September",
        "Oct": "October",
        "Nov": "November",
        "Dec": "December",
    }
    month = aliases.get(month, month)
    return _parse_flexible_date(f"{month} {match.group('day')}, {match.group('year')}")


def _is_ai_enforcement_text(text: str) -> bool:
    lowered = text.lower()
    has_ai_signal = any(
        signal in lowered
        for signal in (
            "artificial intelligence",
            " ai ",
            "ai-generated",
            "algorithmic",
            "algorithm",
        )
    )
    has_action_signal = any(
        signal in lowered
        for signal in (
            "complaint",
            "settlement",
            "lawsuit",
            "sues",
            "charges",
            "charged",
            "order",
            "enforcement",
            "alleges",
            "alleged",
            "action against",
        )
    )
    return has_ai_signal and has_action_signal


def _is_non_case_heading(value: str) -> bool:
    return value.lower() in {
        "breadcrumb",
        "related documents",
        "press release",
        "contacts",
        "media contacts",
        "our topics",
    }


def _clean_entity_name(value: str) -> str:
    return " ".join(value.strip().strip(":").split())


def _extract_doj_company(title: str, text: str) -> str | None:
    if re.search(r"\bRealPage\b", f"{title} {text}"):
        return "RealPage"
    match = re.search(
        r"\b(?:against|sues|sued|settlement with)\s+([A-Z][A-Za-z0-9&.,' -]+)",
        title,
    )
    if match:
        return _clean_entity_name(match.group(1))
    return None


def _extract_sec_companies(text: str) -> list[str]:
    companies: list[str] = []
    for company in (
        "Delphia (USA) Inc.",
        "Global Predictions Inc.",
        "Rimar Capital USA, Inc.",
    ):
        if company in text:
            companies.append(company)
    return companies


def _extract_sec_company_from_title(title: str) -> str | None:
    match = re.search(r"\bCharges\s+(.+?)\s+(?:with|for)\b", title)
    if match:
        return _clean_entity_name(match.group(1))
    return None


def _infer_official_source_family(text: str):
    lowered = text.lower()
    if any(term in lowered for term in ("privacy", "biometric", "facial recognition")):
        return "security_privacy"
    if any(term in lowered for term in ("chatbot", "customer support")):
        return "customer_support"
    return "model_governance"


def _summarize_official_text(text: str, *, max_chars: int = 500) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[: max_chars - 1].rstrip()}."


def _filter_since(
    records: list[VerifiedSourceRecord],
    since: str | None,
) -> list[VerifiedSourceRecord]:
    if since is None:
        return records
    since_date = date.fromisoformat(since)
    return [
        record
        for record in records
        if date.fromisoformat(record.incident_date) >= since_date
    ]


def _dedupe_external_ids(
    records: list[VerifiedSourceRecord],
) -> list[VerifiedSourceRecord]:
    seen: set[str] = set()
    deduped: list[VerifiedSourceRecord] = []
    for record in records:
        external_id = record.external_id
        if external_id in seen:
            source_slug = _source_slug(record.source_url)
            external_id = f"{record.external_id}-{source_slug}"
            counter = 2
            while external_id in seen:
                external_id = f"{record.external_id}-{source_slug}-{counter}"
                counter += 1
            record = VerifiedSourceRecord(
                source_registry_key=record.source_registry_key,
                external_id=external_id,
                title=record.title,
                incident_date=record.incident_date,
                company=record.company,
                summary=record.summary,
                source_url=record.source_url,
                publisher=record.publisher,
                raw_payload=record.raw_payload,
                source_family=record.source_family,
            )
        seen.add(record.external_id)
        deduped.append(record)
    return deduped


def _source_slug(url: str) -> str:
    path = url.rstrip("/").rsplit("/", maxsplit=1)[-1]
    return _slug(path or url)


def _normalize_row(row: dict[str, str | None]) -> dict[str, str]:
    return {
        _normalize_key(key): (value or "").strip()
        for key, value in row.items()
        if key is not None
    }


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", key.lower()).strip()


def _first_present(row: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        value = row.get(_normalize_key(key))
        if value:
            return value
    return None


def _first_url(*values: str | None) -> str | None:
    for value in values:
        if not value:
            continue
        match = re.search(r"https?://\S+", value)
        if match:
            return match.group(0).rstrip(".,)")
        if value.startswith("/"):
            return value
    return None


def _parse_date(value: str) -> str:
    return datetime.strptime(value, "%B %d, %Y").date().isoformat()


def _parse_flexible_date(value: str) -> str:
    stripped = value.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m", "%B %d, %Y", "%d %B %Y", "%m/%d/%Y"):
        try:
            if fmt == "%Y-%m":
                return f"{datetime.strptime(stripped, fmt).date().isoformat()[:7]}-01"
            return datetime.strptime(stripped, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: {value}")


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"

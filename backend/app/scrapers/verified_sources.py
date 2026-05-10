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
FTC_AI_INDEX_URL = "https://www.ftc.gov/industry/technology/artificial-intelligence"
FTC_PRESS_RELEASE_SOFTWARE_SEARCH_URL = (
    "https://www.ftc.gov/news-events/news/press-releases?search=software"
)
FTC_PRESS_RELEASE_AUTOMATED_SEARCH_URL = (
    "https://www.ftc.gov/news-events/news/press-releases?search=automated"
)
FTC_CASES_SOFTWARE_SEARCH_URL = (
    "https://www.ftc.gov/legal-library/browse/cases-proceedings?search=software"
)
FTC_CASES_ALGORITHM_SEARCH_URL = (
    "https://www.ftc.gov/legal-library/browse/cases-proceedings?search=algorithm"
)
FTC_AUTOMATORS_CASE_URL = (
    "https://www.ftc.gov/legal-library/browse/cases-proceedings/automators"
)
FTC_CAREER_STEP_AI_ADS_URL = (
    "https://www.ftc.gov/news-events/news/press-releases/2024/07/"
    "career-step-pay-435-million-cash-debt-cancellation-resolve-charges-it-used-"
    "deceptive-advertising"
)
FTC_CRI_GENETICS_CASE_URL = (
    "https://www.ftc.gov/legal-library/browse/cases-proceedings/"
    "cri-genetics-ftc-state-california-v"
)
FTC_NGL_AI_MODERATION_URL = (
    "https://www.ftc.gov/news-events/news/press-releases/2024/07/"
    "ftc-order-will-ban-ngl-labs-its-founders-offering-anonymous-messaging-apps-"
    "kids-under-18-halt"
)
DOJ_REALPAGE_AI_ENFORCEMENT_URL = (
    "https://www.justice.gov/atr/case-document/complaint-303"
)
DOJ_CIVIL_RIGHTS_AI_URL = "https://www.justice.gov/crt/ai"
DOJ_ELEGANT_AI_ADS_URL = (
    "https://www.justice.gov/opa/pr/civil-rights-division-obtains-settlement-"
    "company-used-ai-generated-advertisements-excluded"
)
DOJ_META_ALGORITHMIC_ADS_URL = (
    "https://www.justice.gov/crt/case/"
    "united-states-v-meta-platforms-inc-fka-facebook-inc-sdny"
)
DOJ_GREYSTAR_ALGORITHMIC_PRICING_URL = (
    "https://www.justice.gov/opa/pr/justice-department-reaches-proposed-"
    "settlement-greystar-largest-us-landlord-end-its"
)
DOJ_LIVCOR_ALGORITHMIC_PRICING_URL = (
    "https://www.justice.gov/opa/pr/justice-department-reaches-proposed-"
    "consent-decree-livcor-one-americas-largest-landlords"
)
DOJ_SIX_LANDLORDS_ALGORITHMIC_PRICING_URL = (
    "https://www.govinfo.gov/content/pkg/FR-2025-01-30/html/2025-01886.htm"
)
DOJ_SAFERENT_ALGORITHM_SCREENING_URL = (
    "https://www.justice.gov/crt/case/louis-et-al-v-saferent-et-al-d-mass"
)
DOJ_UC_BERKELEY_AUTOMATED_CAPTIONING_URL = (
    "https://www.justice.gov/crt/case/us-v-regents-university-california"
)
DOJ_CIVIL_RIGHTS_SETTLEMENTS_URL = (
    "https://www.justice.gov/crt/settlements-and-lawsuits"
)
DOJ_MICROSOFT_EMPLOYMENT_SOFTWARE_URL = (
    f"{DOJ_CIVIL_RIGHTS_SETTLEMENTS_URL}"
    "#microsoft-corporation-citizenship-status-december-2021"
)
DOJ_ASCENSION_AUTOMATED_REVERIFICATION_URL = (
    f"{DOJ_CIVIL_RIGHTS_SETTLEMENTS_URL}"
    "#ascension-health-alliance-unfair-documentary-practices-august-2021"
)
SEC_AI_WASHING_URL = "https://www.sec.gov/newsroom/press-releases/2024-36"
SEC_RIMAR_AI_CLAIMS_URL = "https://www.sec.gov/newsroom/press-releases/2024-167"
SEC_JOONKO_AI_FRAUD_URL = "https://www.sec.gov/newsroom/press-releases/2024-70"
SEC_AMERICAN_BITCOIN_ACADEMY_URL = (
    "https://www.sec.gov/newsroom/press-releases/2024-13"
)
SEC_QZ_AI_FRAUD_URL = "https://www.sec.gov/newsroom/press-releases/2024-109"
SEC_PGI_GLOBAL_AI_FRAUD_URL = "https://www.sec.gov/newsroom/press-releases/2025-69"
SEC_AI_WEALTH_FRAUD_URL = (
    "https://www.sec.gov/newsroom/press-releases/"
    "2025-144-sec-charges-three-purported-crypto-asset-trading-platforms-"
    "four-investment-clubs-scheme-targeted"
)
SEC_PROFIT_CONNECT_AI_SUPERCOMPUTER_URL = (
    "https://www.sec.gov/enforcement-litigation/litigation-releases/lr-25144"
)
SEC_PRESTO_AI_PRODUCT_URL = (
    "https://www.sec.gov/enforcement-litigation/administrative-proceedings/"
    "33-11352-s"
)
SEC_DESTINY_ROBOTICS_AI_FRAUD_URL = (
    "https://www.sec.gov/enforcement-litigation/litigation-releases/lr-26157"
)
SEC_TADRUS_ALGORITHMIC_TRADING_URL = (
    "https://www.sec.gov/enforcement-litigation/litigation-releases/lr-25798"
)
SEC_YOUPLUS_MACHINE_LEARNING_FRAUD_URL = (
    "https://www.sec.gov/enforcement-litigation/litigation-releases/lr-24854"
)
SEC_AI_PRESS_RELEASE_SEARCH_URL = (
    "https://www.sec.gov/newsroom/press-releases?"
    "combine=artificial%20intelligence&year=All&month=All"
)
SEC_LITIGATION_RELEASES_SOFTWARE_URL = (
    "https://www.sec.gov/enforcement-litigation/litigation-releases?combine=software"
)
SEC_LITIGATION_RELEASES_ALGORITHM_URL = (
    "https://www.sec.gov/enforcement-litigation/litigation-releases?combine=algorithm"
)
SEC_ADMIN_PROCEEDINGS_SOFTWARE_URL = (
    "https://www.sec.gov/enforcement-litigation/administrative-proceedings?"
    "combine=software"
)
SEC_ADMIN_PROCEEDINGS_AI_URL = (
    "https://www.sec.gov/enforcement-litigation/administrative-proceedings?"
    "combine=artificial%20intelligence"
)
SEC_NATE_AI_FRAUD_URL = (
    "https://www.sec.gov/enforcement-litigation/litigation-releases/lr-26282"
)
EEOC_ITUTORGROUP_AI_HIRING_URL = (
    "https://www.eeoc.gov/newsroom/itutorgroup-pay-365000-settle-eeoc-"
    "discriminatory-hiring-suit"
)
EEOC_NEWSROOM_AUTOMATED_SOFTWARE_URL = (
    "https://www.eeoc.gov/newsroom?search=automated%20software"
)
EEOC_NEWSROOM_SOFTWARE_URL = "https://www.eeoc.gov/newsroom?search=software"
EEOC_NEWSROOM_ALGORITHM_URL = "https://www.eeoc.gov/newsroom?search=algorithm"
FDA_EXER_LABS_AI_WARNING_URL = (
    "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-"
    "investigations/warning-letters/exer-labs-inc-699218-02102025"
)
FDA_WAVI_AI_WARNING_URL = (
    "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-"
    "investigations/warning-letters/wavi-co-658549-10202023"
)
FDA_SENIORLIFE_AI_WARNING_URL = (
    "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-"
    "investigations/warning-letters/seniorlife-technologies-inc-707021-08212025"
)
FDA_WARNING_LETTERS_URL = (
    "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-"
    "investigations/compliance-actions-and-activities/warning-letters"
)

FTC_AI_ENFORCEMENT_URLS = (
    FTC_OPERATION_AI_COMPLY_URL,
    FTC_AI_INDEX_URL,
    FTC_PRESS_RELEASE_SOFTWARE_SEARCH_URL,
    FTC_PRESS_RELEASE_AUTOMATED_SEARCH_URL,
    FTC_CASES_SOFTWARE_SEARCH_URL,
    FTC_CASES_ALGORITHM_SEARCH_URL,
    FTC_AUTOMATORS_CASE_URL,
    FTC_CAREER_STEP_AI_ADS_URL,
    FTC_CRI_GENETICS_CASE_URL,
    FTC_NGL_AI_MODERATION_URL,
)
DOJ_AI_ENFORCEMENT_URLS = (
    DOJ_REALPAGE_AI_ENFORCEMENT_URL,
    DOJ_CIVIL_RIGHTS_AI_URL,
    DOJ_ELEGANT_AI_ADS_URL,
    DOJ_META_ALGORITHMIC_ADS_URL,
    DOJ_GREYSTAR_ALGORITHMIC_PRICING_URL,
    DOJ_LIVCOR_ALGORITHMIC_PRICING_URL,
    DOJ_SIX_LANDLORDS_ALGORITHMIC_PRICING_URL,
    DOJ_SAFERENT_ALGORITHM_SCREENING_URL,
    DOJ_UC_BERKELEY_AUTOMATED_CAPTIONING_URL,
    DOJ_MICROSOFT_EMPLOYMENT_SOFTWARE_URL,
    DOJ_ASCENSION_AUTOMATED_REVERIFICATION_URL,
)
SEC_AI_ENFORCEMENT_URLS = (
    SEC_AI_WASHING_URL,
    SEC_RIMAR_AI_CLAIMS_URL,
    SEC_AI_PRESS_RELEASE_SEARCH_URL,
    SEC_LITIGATION_RELEASES_SOFTWARE_URL,
    SEC_LITIGATION_RELEASES_ALGORITHM_URL,
    SEC_ADMIN_PROCEEDINGS_SOFTWARE_URL,
    SEC_ADMIN_PROCEEDINGS_AI_URL,
    SEC_NATE_AI_FRAUD_URL,
    SEC_JOONKO_AI_FRAUD_URL,
    SEC_AMERICAN_BITCOIN_ACADEMY_URL,
    SEC_QZ_AI_FRAUD_URL,
    SEC_PGI_GLOBAL_AI_FRAUD_URL,
    SEC_AI_WEALTH_FRAUD_URL,
    SEC_PROFIT_CONNECT_AI_SUPERCOMPUTER_URL,
    SEC_PRESTO_AI_PRODUCT_URL,
    SEC_DESTINY_ROBOTICS_AI_FRAUD_URL,
    SEC_TADRUS_ALGORITHMIC_TRADING_URL,
    SEC_YOUPLUS_MACHINE_LEARNING_FRAUD_URL,
)
EEOC_AI_ENFORCEMENT_URLS = (
    EEOC_ITUTORGROUP_AI_HIRING_URL,
    EEOC_NEWSROOM_AUTOMATED_SOFTWARE_URL,
    EEOC_NEWSROOM_SOFTWARE_URL,
    EEOC_NEWSROOM_ALGORITHM_URL,
)
FDA_AI_MEDICAL_DEVICE_WARNING_URLS = (
    FDA_EXER_LABS_AI_WARNING_URL,
    FDA_WAVI_AI_WARNING_URL,
    FDA_SENIORLIFE_AI_WARNING_URL,
    FDA_WARNING_LETTERS_URL,
)

FTC_AI_ENFORCEMENT_PREFIXES = (
    "https://www.ftc.gov/news-events/news/press-releases/",
    "https://www.ftc.gov/legal-library/browse/cases-proceedings/",
    "https://www.ftc.gov/node/",
)
DOJ_AI_ENFORCEMENT_PREFIXES = (
    "https://www.justice.gov/opa/pr/",
    "https://www.justice.gov/archives/opa/pr/",
    "https://www.justice.gov/crt/case/",
    "https://www.justice.gov/atr/case-document/",
    "https://www.justice.gov/atr/case/",
)
SEC_AI_ENFORCEMENT_PREFIXES = (
    "https://www.sec.gov/newsroom/press-releases/",
    "https://www.sec.gov/enforcement-litigation/litigation-releases/",
    "https://www.sec.gov/enforcement-litigation/administrative-proceedings/",
    "https://www.sec.gov/litigation/litreleases/",
)
EEOC_AI_ENFORCEMENT_PREFIXES = ("https://www.eeoc.gov/newsroom/",)
FDA_AI_MEDICAL_DEVICE_WARNING_PREFIXES = (
    "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-"
    "investigations/warning-letters/",
)
OFFICIAL_DISCOVERY_PAGE_LIMIT = 5
OFFICIAL_LISTING_SEED_URLS = {
    FTC_AI_INDEX_URL,
    FTC_PRESS_RELEASE_SOFTWARE_SEARCH_URL,
    FTC_PRESS_RELEASE_AUTOMATED_SEARCH_URL,
    FTC_CASES_SOFTWARE_SEARCH_URL,
    FTC_CASES_ALGORITHM_SEARCH_URL,
    DOJ_CIVIL_RIGHTS_AI_URL,
    SEC_AI_PRESS_RELEASE_SEARCH_URL,
    SEC_LITIGATION_RELEASES_SOFTWARE_URL,
    SEC_LITIGATION_RELEASES_ALGORITHM_URL,
    SEC_ADMIN_PROCEEDINGS_SOFTWARE_URL,
    SEC_ADMIN_PROCEEDINGS_AI_URL,
    EEOC_NEWSROOM_AUTOMATED_SOFTWARE_URL,
    EEOC_NEWSROOM_SOFTWARE_URL,
    EEOC_NEWSROOM_ALGORITHM_URL,
    FDA_WARNING_LETTERS_URL,
}
OPERATION_AI_COMPLY_COMPANIES = {
    "Ascend Ecom",
    "DoNotPay",
    "Ecommerce Empire Builders",
    "FBA Machine",
    "Rytr",
}

DEFAULT_VERIFIED_SOURCES = (
    "ca_dmv_av_collisions",
    "nhtsa_data",
    "damien_charlotin_hallucinations",
    "edrm_judicial_orders",
    "ftc_ai_enforcement",
    "doj_ai_enforcement",
    "sec_ai_enforcement",
    "eeoc_ai_enforcement",
    "fda_ai_medical_device_warning_letters",
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
                "(research contact: leo@example.com)"
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
            allowed_prefixes=FTC_AI_ENFORCEMENT_PREFIXES,
            limit=limit_per_source,
        )
    if source == "doj_ai_enforcement":
        return _fetch_official_ai_enforcement_records(
            client=client,
            urls=DOJ_AI_ENFORCEMENT_URLS,
            parser=parse_doj_ai_enforcement_records,
            allowed_prefixes=DOJ_AI_ENFORCEMENT_PREFIXES,
            limit=limit_per_source,
        )
    if source == "sec_ai_enforcement":
        return _fetch_official_ai_enforcement_records(
            client=client,
            urls=SEC_AI_ENFORCEMENT_URLS,
            parser=parse_sec_ai_enforcement_records,
            allowed_prefixes=SEC_AI_ENFORCEMENT_PREFIXES,
            limit=limit_per_source,
        )
    if source == "eeoc_ai_enforcement":
        return _fetch_official_ai_enforcement_records(
            client=client,
            urls=EEOC_AI_ENFORCEMENT_URLS,
            parser=parse_eeoc_ai_enforcement_records,
            allowed_prefixes=EEOC_AI_ENFORCEMENT_PREFIXES,
            limit=limit_per_source,
        )
    if source == "fda_ai_medical_device_warning_letters":
        return _fetch_official_ai_enforcement_records(
            client=client,
            urls=FDA_AI_MEDICAL_DEVICE_WARNING_URLS,
            parser=parse_fda_ai_medical_device_warning_records,
            allowed_prefixes=FDA_AI_MEDICAL_DEVICE_WARNING_PREFIXES,
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
        if _first_present(normalized, "report type") == (
            "No New or Updated Incident Reports"
        ):
            continue
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
    title = _extract_first_heading(html) or "FTC AI enforcement action"
    incident_date = _extract_official_date(text)
    is_known_ai_case = _is_known_ftc_ai_enforcement_case(source_url)
    if incident_date is None or not (
        (_is_ai_enforcement_text(text) and _has_topical_signal(title, text))
        or is_known_ai_case
    ):
        return []

    records: list[VerifiedSourceRecord] = []
    if source_url == FTC_OPERATION_AI_COMPLY_URL or "Operation AI Comply" in text:
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
    if records:
        return records

    company = _extract_ftc_company(title, text)
    if company is None or _is_non_case_heading(company):
        return []
    if _is_duplicate_operation_ai_comply_update(company, source_url):
        return []
    if _is_non_incident_ftc_action(title, text, company):
        return []
    return [
        _official_ai_enforcement_record(
            source_registry_key="ftc_ai_enforcement",
            external_id=f"ftc-ai-{_slug(company)}-{incident_date}",
            title=title,
            incident_date=incident_date,
            company=company,
            source_url=source_url,
            publisher="FTC",
            body_text=text,
        )
    ][:limit]


def parse_doj_ai_enforcement_records(
    html: str,
    *,
    source_url: str,
    limit: int,
) -> list[VerifiedSourceRecord]:
    text = _html_to_text(_html_from_first_heading(html))
    incident_date = _extract_known_doj_enforcement_date(
        source_url
    ) or _extract_official_date(text)
    title = _extract_first_heading(html) or "DOJ AI enforcement action"
    if source_url == DOJ_SIX_LANDLORDS_ALGORITHMIC_PRICING_URL:
        title = (
            "DOJ RealPage landlord algorithmic pricing amended complaint and "
            "Cortland proposed final judgment"
        )
    companies = _extract_doj_companies(source_url, title, text)
    if _is_non_incident_doj_action(title, text):
        return []
    is_known_ai_case = (
        "RealPage" in companies
        and "complaint-303" in source_url
        and "Document Type Complaint" in text
    ) or _is_known_doj_ai_enforcement_case(source_url)
    if incident_date is None or not (
        (_is_ai_enforcement_text(text) and _has_topical_signal(title, text))
        or is_known_ai_case
    ):
        return []

    if not companies:
        return []
    if title == "Complaint" and companies == ["RealPage"]:
        title = "DOJ antitrust complaint: RealPage algorithmic pricing"
    record_source_url = _extract_doj_attachment_url(html, source_url) or source_url
    records: list[VerifiedSourceRecord] = []
    for company in companies:
        records.append(
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
        )
        if len(records) >= limit:
            break
    return records


def parse_sec_ai_enforcement_records(
    html: str,
    *,
    source_url: str,
    limit: int,
) -> list[VerifiedSourceRecord]:
    text = _html_to_text(_html_from_first_heading(html))
    incident_date = _extract_official_date(text) or _extract_eeoc_press_date(text)
    if incident_date is None or not _is_ai_enforcement_text(text):
        return []

    title = _extract_first_heading(html) or _extract_first_subheading(html)
    title = title or "SEC AI enforcement action"
    if not _has_topical_signal(title, text):
        return []
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


def parse_eeoc_ai_enforcement_records(
    html: str,
    *,
    source_url: str,
    limit: int,
) -> list[VerifiedSourceRecord]:
    text = _html_to_text(_html_from_first_heading(html))
    page_text = _html_to_text(html)
    incident_date = (
        _extract_official_date(text)
        or _extract_eeoc_press_date(text)
        or _extract_eeoc_press_date(page_text)
    )
    if incident_date is None or not _is_ai_enforcement_text(text):
        return []
    title = _extract_first_heading(html) or "EEOC AI enforcement action"
    if not _has_topical_signal(title, text):
        return []
    company = _extract_eeoc_company(text)
    if company is None:
        return []
    return [
        _official_ai_enforcement_record(
            source_registry_key="eeoc_ai_enforcement",
            external_id=f"eeoc-ai-{_slug(company)}-{incident_date}",
            title=title,
            incident_date=incident_date,
            company=company,
            source_url=source_url,
            publisher="EEOC",
            body_text=text,
        )
    ][:limit]


def parse_fda_ai_medical_device_warning_records(
    html: str,
    *,
    source_url: str,
    limit: int,
) -> list[VerifiedSourceRecord]:
    text = _html_to_text(_html_from_first_heading(html))
    incident_date = _extract_official_date(text)
    if incident_date is None or not _has_agency_action_signal(text):
        return []
    if not _is_fda_software_device_warning_text(text):
        return []
    company = _extract_fda_warning_company(html)
    if company is None:
        return []
    title = _extract_first_heading(html) or f"FDA AI warning letter: {company}"
    return [
        _official_ai_enforcement_record(
            source_registry_key="fda_ai_medical_device_warning_letters",
            external_id=f"fda-ai-{_slug(company)}-{incident_date}",
            title=title,
            incident_date=incident_date,
            company=company,
            source_url=source_url,
            publisher="FDA",
            body_text=text,
        )
    ][:limit]


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
    allowed_prefixes: tuple[str, ...],
    limit: int,
) -> list[VerifiedSourceRecord]:
    records: list[VerifiedSourceRecord] = []
    visited_urls: set[str] = set()
    candidate_urls: list[str] = []
    for url in urls:
        if url in visited_urls:
            continue
        visited_urls.add(url)
        try:
            response = client.get(url)
            response.raise_for_status()
        except Exception as exc:
            LOGGER.warning("Skipping official source URL %s: %s", url, exc)
            continue
        if not _is_official_listing_seed(url):
            records.extend(parser(response.text, source_url=url, limit=limit))
        if _is_official_listing_seed(url):
            candidate_urls.extend(
                _discover_official_ai_enforcement_urls(
                    response.text,
                    base_url=url,
                    allowed_prefixes=allowed_prefixes,
                )
            )
            page_urls = _discover_official_listing_page_urls(
                response.text,
                base_url=url,
            )
            for page_url in page_urls:
                if page_url in visited_urls:
                    continue
                visited_urls.add(page_url)
                try:
                    page_response = client.get(page_url)
                    page_response.raise_for_status()
                except Exception as exc:
                    LOGGER.warning(
                        "Skipping official listing page %s: %s",
                        page_url,
                        exc,
                    )
                    continue
                candidate_urls.extend(
                    _discover_official_ai_enforcement_urls(
                        page_response.text,
                        base_url=page_url,
                        allowed_prefixes=allowed_prefixes,
                    )
                )
        if len(records) >= limit:
            break

    for url in _dedupe_strings(candidate_urls):
        if len(records) >= limit:
            break
        if url in visited_urls:
            continue
        visited_urls.add(url)
        try:
            response = client.get(url)
            response.raise_for_status()
        except Exception as exc:
            LOGGER.warning("Skipping official candidate URL %s: %s", url, exc)
            continue
        records.extend(parser(response.text, source_url=url, limit=limit))
    return _dedupe_official_enforcement_companies(records)[:limit]


def _fetch_static_official_records(
    *,
    client: _HttpClient,
    urls: tuple[str, ...],
    parser,
    limit: int,
) -> list[VerifiedSourceRecord]:
    records: list[VerifiedSourceRecord] = []
    for url in urls:
        if len(records) >= limit:
            break
        response = client.get(url)
        response.raise_for_status()
        records.extend(parser(response.text, source_url=url, limit=limit))
    return _dedupe_official_enforcement_companies(records)[:limit]


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
            self._current_href = urljoin(self._base_url, re.sub(r"\s+", "", href))
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


def _discover_official_ai_enforcement_urls(
    html: str,
    *,
    base_url: str,
    allowed_prefixes: tuple[str, ...],
) -> list[str]:
    urls: list[str] = []
    for anchor in _extract_anchors(html, base_url=base_url):
        href = _strip_url_fragment(anchor.href)
        if not any(href.startswith(prefix) for prefix in allowed_prefixes):
            continue
        if _is_disallowed_official_link(anchor.text, href):
            continue
        if not _looks_like_official_enforcement_link(anchor.text, href):
            continue
        urls.append(href)
    return _dedupe_strings(urls)


def _is_official_listing_seed(url: str) -> bool:
    return url in OFFICIAL_LISTING_SEED_URLS


def _discover_official_listing_page_urls(html: str, *, base_url: str) -> list[str]:
    urls: list[str] = []
    for anchor in _extract_anchors(html, base_url=base_url):
        href = _strip_url_fragment(anchor.href)
        if href == base_url:
            continue
        if "page=" not in href:
            continue
        if href.split("?", maxsplit=1)[0] != base_url.split("?", maxsplit=1)[0]:
            continue
        urls.append(href)
    return _dedupe_strings(urls)[:OFFICIAL_DISCOVERY_PAGE_LIMIT]


def _strip_url_fragment(url: str) -> str:
    return url.split("#", maxsplit=1)[0]


def _is_disallowed_official_link(text: str, href: str) -> bool:
    lowered = f"{text} {href}".lower()
    return any(
        term in lowered
        for term in (
            "advisory",
            "agenda",
            "blog",
            "consumer alert",
            "federal-register",
            "guidance",
            "inventory",
            "joint statement",
            "petition for rulemaking",
            "policy",
            "public-statements",
            "roundtable",
            "speech",
            "staff report",
            "statement",
            "statement of interest",
            "technical assistance",
            "workshop",
        )
    )


def _looks_like_official_enforcement_link(text: str, href: str) -> bool:
    lowered = f"{text} {href}".lower()
    if any(
        path in href
        for path in (
            "/legal-library/browse/cases-proceedings/",
            "/crt/case/",
            "/atr/case-document/",
            "/enforcement-litigation/litigation-releases/",
            "/enforcement-litigation/administrative-proceedings/",
            "/litigation/litreleases/",
            "/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/",
        )
    ):
        return True
    return any(
        term in lowered
        for term in (
            "action against",
            "agreement",
            "charges",
            "charged",
            "consent decree",
            "complaint",
            "deceiving",
            "enforcement",
            "finalizes order",
            "fraud",
            "lawsuit",
            "misleading",
            "order",
            "settlement",
            "settle",
            "suit",
            "sues",
            "takes action",
            "to pay",
            "warning letter",
        )
    )


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


def _extract_first_subheading(html: str) -> str | None:
    match = re.search(r"(?is)<h[2-4][^>]*>(.*?)</h[2-4]>", html)
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
    has_ai_signal = _has_substantive_ai_signal(text)
    return has_ai_signal and _has_agency_action_signal(text)


def _has_agency_action_signal(text: str) -> bool:
    lowered = text.lower()
    return any(
        signal in lowered
        for signal in (
            "complaint",
            "consent decree",
            "compulsory process",
            "adulterated",
            "investigation",
            "settlement",
            "lawsuit",
            "misbranded",
            "sues",
            "charges",
            "charged",
            "order",
            "enforcement",
            "alleges",
            "alleged",
            "claims against",
            "action against",
            "warning letter",
            "6(b)",
        )
    )


def _has_substantive_ai_signal(text: str) -> bool:
    lowered = text.lower()
    if "does not allege" in lowered and "ai claim" in lowered:
        return False
    if any(
        signal in lowered
        for signal in (
            "artificial intelligence",
            "ai-generated",
            "ai-powered",
            "ai content",
            "ai detection",
            "ai-driven",
            "ai-infused",
            "ai lawyer",
            "ai product",
            "ai robot",
            "ai service",
            "ai tool",
            "ai tools",
            "ai writing",
            "automatically reject",
            "automated technology",
            "algorithmic",
            "algorithm-based",
            "algorithm",
            "machine-learning",
            "machine learning",
        )
    ):
        if (
            "no software" in lowered
            and "no automation" in lowered
            and "no algorithm" in lowered
        ):
            return False
        return True
    if re.search(r"\bAI\b.{0,60}\b(claim|model|platform|system|technology)", text):
        return True
    return bool(
        re.search(
            r"\b(?:software|automated|automation)\b.{0,120}\b"
            r"(?:advertis|application|caption|decision|device|email|hiring|"
            r"platform|pricing|process|product|program|provider|screen|system|"
            r"technology|tool|trading)\b",
            lowered,
        )
        or re.search(
            r"\b(?:advertis|application|caption|decision|device|email|hiring|"
            r"platform|pricing|process|product|program|provider|screen|system|"
            r"technology|tool|trading)\b.{0,120}\b"
            r"(?:software|automated|automation)\b",
            lowered,
        )
    )


def _has_topical_signal(title: str, text: str) -> bool:
    lead = text[:1400]
    return _has_substantive_ai_signal(title) or _has_substantive_ai_signal(lead)


def _is_non_case_heading(value: str) -> bool:
    return value.lower() in {
        "breadcrumb",
        "related documents",
        "press release",
        "proposed settlement requirements",
        "contacts",
        "g7 enforcement partners",
        "media contacts",
        "our topics",
    }


def _clean_entity_name(value: str) -> str:
    return " ".join(value.strip().strip(":").split())


def _extract_ftc_company(title: str, text: str) -> str | None:
    combined = f"{title} {text}"
    known_companies = (
        "accessiBe",
        "Adobe",
        "Air AI",
        "Ascend Ecom",
        "Automators",
        "Avast",
        "Career Step",
        "D-Link",
        "DoNotPay",
        "Ecommerce Empire Builders",
        "Evolv Technologies",
        "FBA Machine",
        "IntelliVision Technologies",
        "CRI Genetics",
        "NGL Labs",
        "Rite Aid",
        "Rytr",
        "Workado, LLC",
        "Workado",
    )
    for company in known_companies:
        if re.search(rf"\b{re.escape(company)}\b", combined):
            return company
    patterns = (
        r"\b(?:against|with|requires|requiring)\s+([A-Z][A-Za-z0-9&.,' -]+?)\s+"
        r"(?:for|to|that|which|over|,)",
        r"\b([A-Z][A-Za-z0-9&.,' -]+?)\s+(?:will be banned|agrees to|agreed to)",
    )
    for pattern in patterns:
        match = re.search(pattern, title)
        if match:
            return _clean_entity_name(match.group(1))
    company = _extract_generic_agency_company(title, "")
    if company and len(company) <= 120:
        return company
    return None


def _is_duplicate_operation_ai_comply_update(company: str, source_url: str) -> bool:
    if source_url == FTC_OPERATION_AI_COMPLY_URL:
        return False
    return company in OPERATION_AI_COMPLY_COMPANIES


def _is_known_ftc_ai_enforcement_case(source_url: str) -> bool:
    return source_url in {
        FTC_AUTOMATORS_CASE_URL,
        FTC_CAREER_STEP_AI_ADS_URL,
        FTC_CRI_GENETICS_CASE_URL,
        FTC_NGL_AI_MODERATION_URL,
    }


def _is_non_incident_ftc_action(title: str, text: str, company: str) -> bool:
    lowered = f"{title} {text}".lower()
    return any(
        phrase in lowered
        for phrase in (
            "competition issues",
            "g7 enforcement partners",
            "joint statement",
            "petition for rulemaking",
            "public statement",
            "staff report",
            "workshop",
        )
    )


def _extract_doj_companies(source_url: str, title: str, text: str) -> list[str]:
    if source_url == DOJ_MICROSOFT_EMPLOYMENT_SOFTWARE_URL:
        return ["Microsoft Corporation"]
    if source_url == DOJ_ASCENSION_AUTOMATED_REVERIFICATION_URL:
        return ["Ascension Health Alliance"]
    if source_url == DOJ_SIX_LANDLORDS_ALGORITHMIC_PRICING_URL:
        combined = f"{title} {text}"
        return [
            company
            for company in (
                "Greystar Real Estate Partners LLC",
                "LivCor, LLC",
                "Camden Property Trust",
                "Cushman & Wakefield Inc.",
                "Pinnacle Property Management Services LLC",
                "Willow Bridge Property Company LLC",
                "Cortland Management LLC",
            )
            if _company_name_in_text(company, combined)
        ]
    company = _extract_doj_company(title, text)
    return [company] if company else []


def _extract_doj_company(title: str, text: str) -> str | None:
    if re.search(r"\bElegant Enterprise-Wide Solutions\b", f"{title} {text}"):
        return "Elegant Enterprise-Wide Solutions Inc."
    if re.search(r"\bAscension Health Alliance\b|\bAscension\b", f"{title} {text}"):
        return "Ascension Health Alliance"
    if re.search(r"\bGreystar\b", f"{title} {text}"):
        return "Greystar Management Services LLC"
    if re.search(r"\bLivCor\b", f"{title} {text}"):
        return "LivCor, LLC"
    if re.search(r"\bMicrosoft Corporation\b|\bMicrosoft\b", f"{title} {text}"):
        return "Microsoft Corporation"
    if re.search(
        r"\bRegents of the University of California\b|\bUC Berkeley\b",
        f"{title} {text}",
    ):
        return "Regents of the University of California"
    if re.search(r"\bSafeRent\b", f"{title} {text}"):
        return "SafeRent"
    if re.search(r"\bRealPage\b", f"{title} {text}"):
        return "RealPage"
    if re.search(r"\bMeta Platforms\b|\bFacebook\b", title):
        return "Meta Platforms Inc."
    match = re.search(
        r"\b(?:against|sues|sued|settlement with)\s+([A-Z][A-Za-z0-9&.,' -]+)",
        title,
    )
    if match:
        return _clean_entity_name(match.group(1))
    return _extract_generic_agency_company(title, text)


def _extract_known_doj_enforcement_date(source_url: str) -> str | None:
    if source_url == DOJ_META_ALGORITHMIC_ADS_URL:
        return "2022-06-21"
    if source_url == DOJ_SIX_LANDLORDS_ALGORITHMIC_PRICING_URL:
        return "2025-01-07"
    if source_url == DOJ_MICROSOFT_EMPLOYMENT_SOFTWARE_URL:
        return "2021-12-07"
    if source_url == DOJ_ASCENSION_AUTOMATED_REVERIFICATION_URL:
        return "2021-08-25"
    return None


def _is_known_doj_ai_enforcement_case(source_url: str) -> bool:
    return source_url in {
        DOJ_SAFERENT_ALGORITHM_SCREENING_URL,
        DOJ_UC_BERKELEY_AUTOMATED_CAPTIONING_URL,
        DOJ_MICROSOFT_EMPLOYMENT_SOFTWARE_URL,
        DOJ_ASCENSION_AUTOMATED_REVERIFICATION_URL,
    }


def _company_name_in_text(company: str, text: str) -> bool:
    normalized_company = re.sub(r"[^a-z0-9]+", " ", company.lower()).strip()
    normalized_text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return normalized_company in normalized_text


def _is_non_incident_doj_action(title: str, text: str) -> bool:
    lowered = f"{title} {text}".lower()
    return any(
        phrase in lowered
        for phrase in (
            "intervenes in",
            "challenging colorado",
            "ai guidance",
            "ai inventory",
        )
    )


def _extract_sec_companies(text: str) -> list[str]:
    companies: list[str] = []
    for company in (
        "Delphia (USA) Inc.",
        "Global Predictions Inc.",
        "PGI Global",
        "QZ Asset Management Limited",
        "QZ Global Limited",
        "Rimar Capital USA, Inc.",
        "Joonko",
        "Nate, Inc.",
        "Rockwell Capital Management",
        "AI Wealth Inc.",
        "Profit Connect Wealth Services, Inc.",
        "Presto Automation Inc.",
        "Destiny Robotics Corp.",
        "Tadrus Capital LLC",
        "YouPlus, Inc.",
    ):
        if company in text:
            companies.append(company)
    return companies


def _extract_sec_company_from_title(title: str) -> str | None:
    if "Joonko" in title:
        return "Joonko"
    if "Nate" in title:
        return "Nate, Inc."
    match = re.search(r"\bCharges\s+(.+?)\s+(?:with|for)\b", title)
    if match:
        return _clean_entity_name(match.group(1))
    return _extract_generic_agency_company(title, "")


def _extract_eeoc_company(text: str) -> str | None:
    if "iTutorGroup" in text:
        return "iTutorGroup"
    return _extract_generic_agency_company(text, "")


def _extract_eeoc_press_date(text: str) -> str | None:
    match = re.search(r"\bPress Release\s+(\d{2}-\d{2}-\d{4})\b", text)
    if match is None:
        return None
    return _parse_flexible_date(match.group(1))


def _extract_fda_warning_company(html: str) -> str | None:
    title = _extract_first_heading(html)
    if not title:
        return None
    company = re.split(r"\s+MARCS-CMS\b", title, maxsplit=1)[0]
    return _clean_entity_name(company)


def _extract_generic_agency_company(title: str, text: str) -> str | None:
    combined = f"{title} {text}"
    patterns = (
        r"\b([A-Z][A-Za-z0-9&.,' -]+?)\s+to\s+Pay\b",
        r"\b(?:Charges|Charged|Sues|Sue|Settles with|Settlement with|"
        r"Action Against|Takes Action Against|Order Against)\s+"
        r"([A-Z][A-Za-z0-9&.,' -]+?)(?:\s+(?:with|for|over|to|that|after)\b|,|$)",
        r"\b(?:against|with)\s+([A-Z][A-Za-z0-9&.,' -]+?)"
        r"(?:\s+(?:for|over|to|that|after)\b|,|$)",
        r"\b(?:United States v\.|EEOC v\.|FTC v\.|SEC v\.)\s+"
        r"([A-Z][A-Za-z0-9&.,' -]+?)(?:\s+\(|,|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, combined)
        if not match:
            continue
        company = _clean_entity_name(match.group(1))
        if company and not _is_non_case_heading(company):
            return company
    return None


def _is_fda_software_device_warning_text(text: str) -> bool:
    lowered = text.lower()
    lead = lowered[:2200]
    if "warning letter" not in lowered:
        return False
    if "no software" in lowered:
        return False
    if "food cgmp" in lowered and not any(
        term in lowered for term in ("device", "software", "algorithm", "automation")
    ):
        return False
    has_device_context = any(
        term in lead
        for term in (
            "medical device",
            "device",
            "diagnos",
            "monitor",
            "assessment",
            "tablet computer",
            "virtual reality",
            "authorization",
            "validation",
        )
    )
    has_software_context = any(
        term in lead
        for term in (
            "artificial intelligence",
            "algorithm",
            "machine learning",
            "software",
            "automation",
            "automated",
            "computer",
        )
    )
    is_medical_device_letter = any(
        term in lead
        for term in (
            "product: medical devices",
            "center for devices and radiological health",
            "medical device",
            "the device",
            "device is",
        )
    )
    is_ai_device_like_letter = has_software_context and any(
        term in lead for term in ("authorization", "validation", "premarket")
    )
    return (is_medical_device_letter and has_device_context) or is_ai_device_like_letter


def _infer_official_source_family(text: str):
    lowered = text.lower()
    if any(
        term in lowered
        for term in (
            "medical device",
            "diagnos",
            "neurological",
            "musculoskeletal",
            "cognitive health",
        )
    ):
        return "healthcare_benefits"
    if any(term in lowered for term in ("privacy", "biometric", "facial recognition")):
        return "security_privacy"
    if any(term in lowered for term in ("job", "hiring", "recruitment")):
        return "model_governance"
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


def _dedupe_official_enforcement_companies(
    records: list[VerifiedSourceRecord],
) -> list[VerifiedSourceRecord]:
    selected_by_company: dict[tuple[str, str], VerifiedSourceRecord] = {}
    output_keys: list[tuple[str, str] | None] = []
    passthrough: list[VerifiedSourceRecord] = []
    official_keys = {
        "ftc_ai_enforcement",
        "doj_ai_enforcement",
        "sec_ai_enforcement",
    }
    for record in records:
        if record.source_registry_key not in official_keys:
            passthrough.append(record)
            output_keys.append(None)
            continue
        key = (record.source_registry_key, _slug(record.company))
        if key not in selected_by_company:
            selected_by_company[key] = record
            output_keys.append(key)
            continue
        current = selected_by_company[key]
        if record.incident_date < current.incident_date:
            selected_by_company[key] = record

    deduped: list[VerifiedSourceRecord] = []
    passthrough_index = 0
    emitted: set[tuple[str, str]] = set()
    for key in output_keys:
        if key is None:
            deduped.append(passthrough[passthrough_index])
            passthrough_index += 1
            continue
        if key in emitted:
            continue
        deduped.append(selected_by_company[key])
        emitted.add(key)
    return deduped


def _source_slug(url: str) -> str:
    path = url.rstrip("/").rsplit("/", maxsplit=1)[-1]
    return _slug(path or url)


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


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
    for fmt in (
        "%Y-%m-%d",
        "%Y-%m",
        "%b-%Y",
        "%B-%Y",
        "%B %d, %Y",
        "%d %B %Y",
        "%m/%d/%Y",
        "%m-%d-%Y",
    ):
        try:
            if fmt in {"%Y-%m", "%b-%Y", "%B-%Y"}:
                return f"{datetime.strptime(stripped, fmt).date().isoformat()[:7]}-01"
            return datetime.strptime(stripped, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: {value}")


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"

from __future__ import annotations

import argparse
import csv
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from app.core.config import get_settings
from app.services.incident_translation import (
    DeepSeekIncidentTranslationClient,
    DisabledIncidentTranslationClient,
    IncidentTranslation,
    IncidentTranslationClient,
    translate_incident_copy,
)

try:
    import psycopg
    from psycopg.rows import dict_row
except ModuleNotFoundError:  # pragma: no cover - exercised by runtime environment
    psycopg = None
    dict_row = None


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SITEMAP_PATH = REPO_ROOT / "frontend" / "public" / "sitemap.xml"
DEFAULT_SNAPSHOT_DIR = REPO_ROOT / "backend" / "data" / "publication_snapshots"
INCIDENT_URL_RE = re.compile(r"/incidents/([0-9a-fA-F-]{36})(?:/|$)")


@dataclass(frozen=True)
class PublishUpdate:
    incident_id: str
    company_involved_zh: str | None
    headline_zh: str
    reality_summary_zh: str
    legitimacy_reasoning_zh: str | None
    source_validation_summary_zh: str | None
    incident_summary_zh: str | None
    what_happened_zh: str | None
    ai_failure_point_zh: str | None
    why_it_matters_zh: str | None
    evidence_summary_zh: str | None
    translation_status: str = "completed"


@dataclass(frozen=True)
class PublishSummary:
    sitemap_incident_ids: int
    rows_found: int
    missing_in_database: int
    missing_headline_zh_before: int
    missing_reality_summary_zh_before: int
    needs_translation: int
    translated: int
    translation_errors: int
    publishable: int
    skipped_incomplete: int
    updated: int
    dry_run: bool
    snapshot_path: str | None


def extract_sitemap_incident_ids(sitemap_xml: str) -> list[str]:
    root = ElementTree.fromstring(sitemap_xml)
    incident_ids: list[str] = []
    seen: set[str] = set()
    for loc in root.iter():
        if not loc.tag.endswith("loc") or loc.text is None:
            continue
        match = INCIDENT_URL_RE.search(loc.text)
        if match is None:
            continue
        incident_id = match.group(1).lower()
        if incident_id in seen:
            continue
        seen.add(incident_id)
        incident_ids.append(incident_id)
    return incident_ids


def _clean(value: object | None) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _merged_zh(
    row: dict[str, Any],
    field_name: str,
    translation: IncidentTranslation | None,
) -> str | None:
    existing = _clean(row.get(field_name))
    if existing:
        return existing
    if translation is None:
        return None
    generated = _clean(getattr(translation, field_name, ""))
    return generated or None


def incident_needs_translation(row: dict[str, Any]) -> bool:
    return not _clean(row.get("headline_zh")) or not _clean(
        row.get("reality_summary_zh")
    )


def build_publish_update(
    row: dict[str, Any],
    translation: IncidentTranslation | None = None,
) -> PublishUpdate | None:
    headline_zh = _merged_zh(row, "headline_zh", translation)
    reality_summary_zh = _merged_zh(row, "reality_summary_zh", translation)
    if not headline_zh or not reality_summary_zh:
        return None

    return PublishUpdate(
        incident_id=str(row["id"]),
        company_involved_zh=_merged_zh(row, "company_involved_zh", translation),
        headline_zh=headline_zh,
        reality_summary_zh=reality_summary_zh,
        legitimacy_reasoning_zh=_merged_zh(
            row,
            "legitimacy_reasoning_zh",
            translation,
        ),
        source_validation_summary_zh=_merged_zh(
            row,
            "source_validation_summary_zh",
            translation,
        ),
        incident_summary_zh=_merged_zh(row, "incident_summary_zh", translation),
        what_happened_zh=_merged_zh(row, "what_happened_zh", translation),
        ai_failure_point_zh=_merged_zh(row, "ai_failure_point_zh", translation),
        why_it_matters_zh=_merged_zh(row, "why_it_matters_zh", translation),
        evidence_summary_zh=_merged_zh(row, "evidence_summary_zh", translation),
    )


def _translate_row(
    row: dict[str, Any],
    translation_client: IncidentTranslationClient,
) -> IncidentTranslation:
    return translate_incident_copy(
        headline_en=_clean(row.get("headline_en")) or _clean(row.get("headline")),
        reality_summary_en=_clean(row.get("reality_summary_en"))
        or _clean(row.get("reality_summary")),
        legitimacy_reasoning_en=_clean(row.get("legitimacy_reasoning")),
        source_validation_summary_en=_clean(row.get("source_validation_summary")),
        company_involved_en=_clean(row.get("company_involved")),
        incident_summary_en=_clean(row.get("incident_summary_en")),
        what_happened_en=_clean(row.get("what_happened_en")),
        ai_failure_point_en=_clean(row.get("ai_failure_point_en")),
        why_it_matters_en=_clean(row.get("why_it_matters_en")),
        evidence_summary_en=_clean(row.get("evidence_summary_en")),
        client=translation_client,
    )


def _fetch_target_rows(connection, incident_ids: list[str]) -> list[dict[str, Any]]:
    if not incident_ids:
        return []
    return connection.execute(
        """
        select
            id::text as id,
            headline,
            headline_en,
            headline_zh,
            reality_summary,
            reality_summary_en,
            reality_summary_zh,
            company_involved,
            company_involved_zh,
            legitimacy_reasoning,
            legitimacy_reasoning_zh,
            source_validation_summary,
            source_validation_summary_zh,
            incident_summary_en,
            incident_summary_zh,
            what_happened_en,
            what_happened_zh,
            ai_failure_point_en,
            ai_failure_point_zh,
            why_it_matters_en,
            why_it_matters_zh,
            evidence_summary_en,
            evidence_summary_zh,
            status,
            translation_status
        from incident_logs
        where id::text = any(%s)
        order by date_logged desc, id asc
        """,
        (incident_ids,),
    ).fetchall()


def _write_snapshot(rows: list[dict[str, Any]], snapshot_path: Path) -> None:
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id",
        "status",
        "translation_status",
        "headline",
        "headline_zh",
        "reality_summary",
        "reality_summary_zh",
    ]
    with snapshot_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fieldnames})


def _apply_updates(connection, updates: list[PublishUpdate]) -> int:
    for update in updates:
        connection.execute(
            """
            update incident_logs
            set
                status = 'approved',
                company_involved_zh = %s,
                headline_zh = %s,
                reality_summary_zh = %s,
                legitimacy_reasoning_zh = %s,
                source_validation_summary_zh = %s,
                incident_summary_zh = %s,
                what_happened_zh = %s,
                ai_failure_point_zh = %s,
                why_it_matters_zh = %s,
                evidence_summary_zh = %s,
                translation_status = %s,
                translated_at = current_timestamp,
                updated_at = current_timestamp
            where id = %s
            """,
            (
                update.company_involved_zh,
                update.headline_zh,
                update.reality_summary_zh,
                update.legitimacy_reasoning_zh,
                update.source_validation_summary_zh,
                update.incident_summary_zh,
                update.what_happened_zh,
                update.ai_failure_point_zh,
                update.why_it_matters_zh,
                update.evidence_summary_zh,
                update.translation_status,
                update.incident_id,
            ),
        )
    connection.commit()
    return len(updates)


def publish_sitemap_incidents(
    *,
    database_url: str,
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    translation_client: IncidentTranslationClient,
    apply: bool = False,
    snapshot_path: Path | None = None,
    limit: int | None = None,
    missing_limit: int | None = None,
    concurrency: int = 1,
) -> PublishSummary:
    if psycopg is None or dict_row is None:
        raise ModuleNotFoundError("psycopg is required to publish sitemap incidents")

    incident_ids = extract_sitemap_incident_ids(
        sitemap_path.read_text(encoding="utf-8")
    )
    if limit is not None:
        incident_ids = incident_ids[:limit]

    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        rows = _fetch_target_rows(connection, incident_ids)
        found_ids = {str(row["id"]).lower() for row in rows}
        missing_in_database = len(
            [incident_id for incident_id in incident_ids if incident_id not in found_ids]
        )
        missing_headline_before = sum(
            1 for row in rows if not _clean(row.get("headline_zh"))
        )
        missing_summary_before = sum(
            1 for row in rows if not _clean(row.get("reality_summary_zh"))
        )
        rows_needing_translation = [
            row for row in rows if incident_needs_translation(row)
        ]
        if missing_limit is not None:
            rows_needing_translation = rows_needing_translation[:missing_limit]

        resolved_snapshot_path: Path | None = None
        if apply:
            resolved_snapshot_path = snapshot_path or _default_snapshot_path()
            _write_snapshot(rows, resolved_snapshot_path)

        translations: dict[str, IncidentTranslation] = {}
        translation_errors = 0
        if apply and rows_needing_translation:
            max_workers = max(concurrency, 1)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_row = {
                    executor.submit(_translate_row, row, translation_client): row
                    for row in rows_needing_translation
                }
                for future in as_completed(future_to_row):
                    row = future_to_row[future]
                    try:
                        translations[str(row["id"])] = future.result()
                    except Exception:
                        translation_errors += 1

        updates: list[PublishUpdate] = []
        skipped_incomplete = 0
        selected_missing_ids = {str(row["id"]) for row in rows_needing_translation}
        for row in rows:
            row_id = str(row["id"])
            if missing_limit is not None and row_id not in selected_missing_ids:
                continue
            if incident_needs_translation(row) and row_id not in selected_missing_ids:
                continue
            translation = translations.get(row_id)
            update = build_publish_update(row, translation)
            if update is None:
                skipped_incomplete += 1
                continue
            updates.append(update)

        updated = _apply_updates(connection, updates) if apply else 0

    return PublishSummary(
        sitemap_incident_ids=len(incident_ids),
        rows_found=len(rows),
        missing_in_database=missing_in_database,
        missing_headline_zh_before=missing_headline_before,
        missing_reality_summary_zh_before=missing_summary_before,
        needs_translation=len(rows_needing_translation),
        translated=len(translations),
        translation_errors=translation_errors,
        publishable=len(updates),
        skipped_incomplete=skipped_incomplete,
        updated=updated,
        dry_run=not apply,
        snapshot_path=str(resolved_snapshot_path) if apply else None,
    )


def _default_snapshot_path() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return DEFAULT_SNAPSHOT_DIR / f"sitemap-incident-publication-{timestamp}.csv"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Publish sitemap incident rows after required Chinese translations exist."
        )
    )
    parser.add_argument("--sitemap-path", type=Path, default=DEFAULT_SITEMAP_PATH)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--missing-limit",
        type=int,
        default=None,
        help="Only translate and publish this many rows missing required zh fields.",
    )
    parser.add_argument("--concurrency", type=int, default=None)
    parser.add_argument("--snapshot-path", type=Path, default=None)
    args = parser.parse_args()

    settings = get_settings()
    translation_client: IncidentTranslationClient
    if settings.deepseek_api_key:
        translation_client = DeepSeekIncidentTranslationClient(
            api_key=settings.deepseek_api_key,
            model=settings.deepseek_translation_model,
            base_url=settings.primary_review_base_url,
        )
    else:
        translation_client = DisabledIncidentTranslationClient()

    summary = publish_sitemap_incidents(
        database_url=settings.database_url,
        sitemap_path=args.sitemap_path,
        translation_client=translation_client,
        apply=args.apply,
        snapshot_path=args.snapshot_path,
        limit=args.limit,
        missing_limit=args.missing_limit,
        concurrency=args.concurrency or settings.review_concurrency,
    )
    print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))
    if args.apply and summary.skipped_incomplete:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

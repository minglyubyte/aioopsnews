# Incident Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a PostgreSQL-only incident CSV importer that stores curated AI incident batches, preserves editorial legitimacy/confidence on each record, and auto-approves only `ACCEPT/high` rows.

**Architecture:** Add a new `incident_import` service parallel to the existing claim importer, extend the repository protocol with an incident upsert method, and persist normalized source links into `incident_sources`. The importer will validate the new `source_links` list format, derive `incident_logs.status` from `legitimacy_flag` plus `confidence_level`, and upsert by stable `incident_id`.

**Tech Stack:** Python 3, FastAPI backend structure, psycopg PostgreSQL repository, pytest, existing in-memory test fakes, CSV parsing with `csv.DictReader`.

---

## File Structure

- Create: `backend/app/services/incident_import.py`
- Create: `backend/app/scripts/import_incidents_csv.py`
- Create: `backend/tests/test_incident_import.py`
- Modify: `backend/app/db/repository_protocol.py`
- Modify: `backend/app/db/postgres_repository.py`
- Modify: `backend/app/models/incident.py`
- Modify: `backend/tests/fakes.py`
- Modify: `backend/tests/test_schema_bootstrap.py`
- Modify: `infra/supabase/migrations/20260429170000_initial_incident_schema.sql`

### Task 1: Lock the schema and contract first

**Files:**
- Modify: `backend/tests/test_schema_bootstrap.py`
- Modify: `backend/app/models/incident.py`
- Modify: `backend/app/db/repository_protocol.py`
- Modify: `backend/app/db/postgres_repository.py`
- Modify: `infra/supabase/migrations/20260429170000_initial_incident_schema.sql`

- [ ] **Step 1: Write the failing schema/bootstrap test**

```python
def test_postgres_schema_tracks_incident_import_editorial_fields() -> None:
    normalized = _POSTGRES_SCHEMA.lower()

    assert "incident_topic text" in normalized
    assert "legitimacy_flag text" in normalized
    assert "confidence_level text" in normalized
    assert "import_notes text" in normalized
```

Add this next to the existing schema assertions in `backend/tests/test_schema_bootstrap.py`.

- [ ] **Step 2: Write the failing model assertion**

```python
incident = IncidentRecord(
    id="incident-1",
    headline="Agent rollout causes bad customer escalations",
    date_logged=date(2026, 4, 29),
    company_involved="OpenAI",
    incident_topic="customer support",
    legitimacy_flag="ACCEPT",
    confidence_level="high",
    import_notes="Curated from 2023 batch",
    categories=["Job Automation Fails"],
    severity_score=4,
    reality_summary="A supervised launch produced repeated escalations.",
    status="approved",
)

assert incident.incident_topic == "customer support"
assert incident.legitimacy_flag == "ACCEPT"
assert incident.confidence_level == "high"
assert incident.import_notes == "Curated from 2023 batch"
```

- [ ] **Step 3: Run the targeted bootstrap test to verify it fails**

Run:

```bash
cd /Users/leo/Desktop/AI_Oops/backend && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/test_schema_bootstrap.py -q
```

Expected: `FAIL` because the schema string, migration, and incident model do not expose the new fields yet.

- [ ] **Step 4: Add the minimal model and protocol fields**

Update `backend/app/models/incident.py` to include:

```python
    incident_topic: str | None = None
    legitimacy_flag: str | None = None
    confidence_level: str | None = None
    import_notes: str | None = None
```

Extend `backend/app/db/repository_protocol.py` with:

```python
    def upsert_incident_import_row(
        self,
        *,
        incident_id: str,
        headline: str,
        date_logged: str,
        company_involved: str,
        incident_topic: str,
        matched_claim_id: str | None,
        source_links: list[str],
        legitimacy_flag: str,
        confidence_level: str,
        import_notes: str | None,
    ) -> None: ...
```

- [ ] **Step 5: Add the minimal schema columns**

In both `backend/app/db/postgres_repository.py` and `infra/supabase/migrations/20260429170000_initial_incident_schema.sql`, extend `incident_logs` with:

```sql
incident_topic text,
legitimacy_flag text,
confidence_level text,
import_notes text,
```

Also add defensive `alter table ... add column if not exists ...` statements in `_POSTGRES_SCHEMA` for the new columns, matching the current style used for `claims.notes`.

- [ ] **Step 6: Re-run the bootstrap test to verify it passes**

Run:

```bash
cd /Users/leo/Desktop/AI_Oops/backend && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/test_schema_bootstrap.py -q
```

Expected: `PASS`.

- [ ] **Step 7: Commit the contract/schema slice**

```bash
git add backend/tests/test_schema_bootstrap.py backend/app/models/incident.py backend/app/db/repository_protocol.py backend/app/db/postgres_repository.py infra/supabase/migrations/20260429170000_initial_incident_schema.sql
git commit -m "feat: add incident import schema fields"
```

### Task 2: Add parser tests before writing importer code

**Files:**
- Create: `backend/tests/test_incident_import.py`
- Create: `backend/app/services/incident_import.py`

- [ ] **Step 1: Write the failing parsing tests**

Create `backend/tests/test_incident_import.py` with:

```python
from __future__ import annotations

import pytest

from app.services.incident_import import (
    IncidentImportValidationError,
    parse_incidents_csv_text,
)

VALID_INCIDENT_CSV = "\n".join(
    [
        (
            "ref_number,incident_id,company,incident_date,incident_topic,"
            "incident_description,mapped_claim,source_links,legitimacy_flag,"
            "confidence_level,notes"
        ),
        (
            '1,inc-openai-001,OpenAI,2026-01-15,customer support,'
            '"Bot leaks private notes",claim-openai-001,'
            '"https://example.com/a | https://example.com/b | https://example.com/c",'
            "ACCEPT,high,Strong record"
        ),
        "",
    ]
)


def test_parse_incidents_csv_text_extracts_three_links_and_optional_fields() -> None:
    rows = parse_incidents_csv_text(VALID_INCIDENT_CSV)

    assert len(rows) == 1
    assert rows[0].incident_id == "inc-openai-001"
    assert rows[0].matched_claim_id == "claim-openai-001"
    assert rows[0].source_links == [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
    ]
    assert rows[0].legitimacy_flag == "ACCEPT"
    assert rows[0].confidence_level == "high"
```

- [ ] **Step 2: Add the failing validation tests**

Append:

```python
def test_parse_incidents_csv_text_rejects_less_than_three_links() -> None:
    csv_text = "\n".join(
        [
            "incident_id,company,incident_date,incident_topic,incident_description,source_links,legitimacy_flag,confidence_level",
            (
                'inc-openai-001,OpenAI,2026-01-15,customer support,'
                '"Bot leaks private notes","https://example.com/a | https://example.com/b",ACCEPT,high'
            ),
            "",
        ]
    )

    with pytest.raises(IncidentImportValidationError) as exc_info:
        parse_incidents_csv_text(csv_text)

    assert "at least 3 links" in str(exc_info.value)


def test_parse_incidents_csv_text_rejects_invalid_legitimacy_flag() -> None:
    csv_text = "\n".join(
        [
            "incident_id,company,incident_date,incident_topic,incident_description,source_links,legitimacy_flag,confidence_level",
            (
                'inc-openai-001,OpenAI,2026-01-15,customer support,'
                '"Bot leaks private notes","https://example.com/a | https://example.com/b | https://example.com/c",MAYBE,high'
            ),
            "",
        ]
    )

    with pytest.raises(IncidentImportValidationError) as exc_info:
        parse_incidents_csv_text(csv_text)

    assert "legitimacy_flag" in str(exc_info.value)
```

- [ ] **Step 3: Add the duplicate-ID test**

```python
def test_parse_incidents_csv_text_rejects_duplicate_incident_id() -> None:
    csv_text = "\n".join(
        [
            "incident_id,company,incident_date,incident_topic,incident_description,source_links,legitimacy_flag,confidence_level",
            (
                'inc-openai-001,OpenAI,2026-01-15,customer support,'
                '"First","https://example.com/a | https://example.com/b | https://example.com/c",ACCEPT,high'
            ),
            (
                'inc-openai-001,OpenAI,2026-01-16,customer support,'
                '"Second","https://example.com/d | https://example.com/e | https://example.com/f",REVIEW,medium'
            ),
            "",
        ]
    )

    with pytest.raises(IncidentImportValidationError) as exc_info:
        parse_incidents_csv_text(csv_text)

    assert "duplicate incident_id" in str(exc_info.value)
```

- [ ] **Step 4: Run the parser tests to verify they fail**

Run:

```bash
cd /Users/leo/Desktop/AI_Oops/backend && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/test_incident_import.py -q
```

Expected: `FAIL` because `app.services.incident_import` does not exist yet.

- [ ] **Step 5: Create the minimal service skeleton**

Create `backend/app/services/incident_import.py`:

```python
from __future__ import annotations


class IncidentImportValidationError(ValueError):
    pass


def parse_incidents_csv_text(csv_text: str):
    raise IncidentImportValidationError("not implemented")
```

- [ ] **Step 6: Run the parser tests again to verify they still fail for the right reason**

Run the same command as Step 4.

Expected: `FAIL` with assertions about unimplemented parsing or wrong validation behavior, not import errors.

- [ ] **Step 7: Commit the red test slice**

```bash
git add backend/tests/test_incident_import.py backend/app/services/incident_import.py
git commit -m "test: add incident import parser coverage"
```

### Task 3: Implement CSV parsing and import decisions

**Files:**
- Modify: `backend/app/services/incident_import.py`
- Modify: `backend/tests/test_incident_import.py`

- [ ] **Step 1: Implement the parsed row and summary dataclasses**

Replace the service skeleton with:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedIncidentImportRow:
    line_number: int
    ref_number: str | None
    incident_id: str
    company: str
    incident_date: str
    incident_topic: str
    incident_description: str
    matched_claim_id: str | None
    source_links: list[str]
    legitimacy_flag: str
    confidence_level: str
    notes: str | None


@dataclass(frozen=True)
class IncidentImportSummary:
    validated: int
    inserted: int
```

- [ ] **Step 2: Implement the parser and helpers**

Use the claim importer as the pattern and add:

```python
ALLOWED_LEGITIMACY_FLAGS = {"ACCEPT", "REVIEW", "REJECT"}
ALLOWED_CONFIDENCE_LEVELS = {"low", "medium", "high"}
REQUIRED_COLUMNS = {
    "incident_id",
    "company",
    "incident_date",
    "incident_topic",
    "incident_description",
    "source_links",
    "legitimacy_flag",
    "confidence_level",
}
```

Implement:

```python
def parse_incidents_csv_text(csv_text: str) -> list[ParsedIncidentImportRow]:
    ...


def _parse_link_list(value: str, *, line_number: int) -> list[str]:
    ...


def _validate_iso_date(value: str, *, line_number: int) -> None:
    ...
```

Behavior:

- trim all fields
- skip fully blank rows
- validate required columns
- dedupe URLs while preserving order
- reject rows with fewer than 3 final URLs
- reject invalid legitimacy/confidence values
- reject duplicate `incident_id` values in-file

- [ ] **Step 3: Add the import function with status derivation**

Implement:

```python
def import_incidents_csv_text(
    repository: IncidentRepository,
    csv_text: str,
    *,
    dry_run: bool,
) -> IncidentImportSummary:
    rows = parse_incidents_csv_text(csv_text)
    if dry_run:
        return IncidentImportSummary(validated=len(rows), inserted=0)

    inserted = 0
    for row in rows:
        repository.upsert_incident_import_row(
            incident_id=row.incident_id,
            headline=row.incident_description,
            date_logged=row.incident_date,
            company_involved=row.company,
            incident_topic=row.incident_topic,
            matched_claim_id=row.matched_claim_id,
            source_links=row.source_links,
            legitimacy_flag=row.legitimacy_flag,
            confidence_level=row.confidence_level,
            import_notes=row.notes,
        )
        inserted += 1

    return IncidentImportSummary(validated=len(rows), inserted=inserted)
```

Add a helper for the status rule in the same file:

```python
def derive_incident_status(legitimacy_flag: str, confidence_level: str) -> str:
    if legitimacy_flag == "ACCEPT" and confidence_level == "high":
        return "approved"
    return "pending_review"
```

- [ ] **Step 4: Add direct tests for status derivation**

Append to `backend/tests/test_incident_import.py`:

```python
from app.services.incident_import import derive_incident_status


def test_derive_incident_status_only_auto_approves_accept_high() -> None:
    assert derive_incident_status("ACCEPT", "high") == "approved"
    assert derive_incident_status("ACCEPT", "medium") == "pending_review"
    assert derive_incident_status("REVIEW", "high") == "pending_review"
    assert derive_incident_status("REJECT", "low") == "pending_review"
```

- [ ] **Step 5: Run the parser/status tests to verify they pass**

Run:

```bash
cd /Users/leo/Desktop/AI_Oops/backend && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/test_incident_import.py -q
```

Expected: parser/status tests `PASS`, but import persistence tests do not exist yet.

- [ ] **Step 6: Commit the parser implementation**

```bash
git add backend/app/services/incident_import.py backend/tests/test_incident_import.py
git commit -m "feat: implement incident import parsing"
```

### Task 4: Add repository persistence and fake-backed import tests

**Files:**
- Modify: `backend/tests/test_incident_import.py`
- Modify: `backend/tests/fakes.py`
- Modify: `backend/app/db/postgres_repository.py`

- [ ] **Step 1: Write the failing fake-backed import tests**

Append to `backend/tests/test_incident_import.py`:

```python
from app.services.incident_import import import_incidents_csv_text
from tests.fakes import InMemoryIncidentRepository


IMPORT_CSV = "\n".join(
    [
        "incident_id,company,incident_date,incident_topic,incident_description,mapped_claim,source_links,legitimacy_flag,confidence_level,notes",
        (
            'inc-openai-001,OpenAI,2026-01-15,customer support,"Bot leaks private notes",claim-openai-001,'
            '"https://example.com/a | https://example.com/b | https://example.com/c",ACCEPT,high,Initial import'
        ),
        "",
    ]
)


def test_import_incidents_csv_text_persists_incidents_and_sources() -> None:
    repository = InMemoryIncidentRepository()

    summary = import_incidents_csv_text(repository, IMPORT_CSV, dry_run=False)

    assert summary.inserted == 1
    incident = repository.incidents["inc-openai-001"]
    assert incident["status"] == "approved"
    assert incident["incident_topic"] == "customer support"
    assert incident["legitimacy_flag"] == "ACCEPT"
    assert incident["confidence_level"] == "high"
    assert incident["matched_claim_id"] == "claim-openai-001"
    assert [source["source_url"] for source in incident["sources"]] == [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
    ]
```

- [ ] **Step 2: Add the failing upsert-replaces-sources test**

```python
def test_import_incidents_csv_text_upserts_existing_incident_and_replaces_sources() -> None:
    repository = InMemoryIncidentRepository()

    first_csv = "\n".join(
        [
            "incident_id,company,incident_date,incident_topic,incident_description,source_links,legitimacy_flag,confidence_level",
            (
                'inc-openai-001,OpenAI,2026-01-15,customer support,'
                '"First","https://example.com/a | https://example.com/b | https://example.com/c",ACCEPT,high'
            ),
            "",
        ]
    )
    second_csv = "\n".join(
        [
            "incident_id,company,incident_date,incident_topic,incident_description,source_links,legitimacy_flag,confidence_level",
            (
                'inc-openai-001,OpenAI,2026-01-16,privacy,'
                '"Second","https://example.com/d | https://example.com/e | https://example.com/f",REVIEW,medium'
            ),
            "",
        ]
    )

    import_incidents_csv_text(repository, first_csv, dry_run=False)
    import_incidents_csv_text(repository, second_csv, dry_run=False)

    incident = repository.incidents["inc-openai-001"]
    assert incident["date_logged"] == "2026-01-16"
    assert incident["incident_topic"] == "privacy"
    assert incident["status"] == "pending_review"
    assert [source["source_url"] for source in incident["sources"]] == [
        "https://example.com/d",
        "https://example.com/e",
        "https://example.com/f",
    ]
```

- [ ] **Step 3: Run the import tests to verify they fail**

Run:

```bash
cd /Users/leo/Desktop/AI_Oops/backend && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/test_incident_import.py -q
```

Expected: `FAIL` because the repository protocol/fake/postgres repository do not implement incident import persistence yet.

- [ ] **Step 4: Implement fake repository support**

Add to `backend/tests/fakes.py`:

```python
    def upsert_incident_import_row(
        self,
        *,
        incident_id: str,
        headline: str,
        date_logged: str,
        company_involved: str,
        incident_topic: str,
        matched_claim_id: str | None,
        source_links: list[str],
        legitimacy_flag: str,
        confidence_level: str,
        import_notes: str | None,
    ) -> None:
        status = derive_incident_status(legitimacy_flag, confidence_level)
        self.incidents[incident_id] = {
            "id": incident_id,
            "headline": headline,
            "date_logged": date_logged,
            "company_involved": company_involved,
            "claimant_name": None,
            "incident_topic": incident_topic,
            "legitimacy_flag": legitimacy_flag,
            "confidence_level": confidence_level,
            "import_notes": import_notes,
            "categories": self.incidents.get(incident_id, {}).get("categories", []),
            "severity_score": self.incidents.get(incident_id, {}).get("severity_score", 1),
            "reality_summary": headline,
            "status": status,
            "matched_claim_id": matched_claim_id,
            "claim_match_confidence": None,
            "sources": [
                {
                    "id": f"source-{incident_id}-{index}",
                    "source_url": url,
                    "source_type": "imported",
                    "publisher": None,
                    "title": None,
                }
                for index, url in enumerate(source_links)
            ],
        }
```

Import `derive_incident_status` at the top of `backend/tests/fakes.py`.

- [ ] **Step 5: Implement PostgreSQL upsert and source replacement**

In `backend/app/db/postgres_repository.py`, add:

```python
    def upsert_incident_import_row(
        self,
        *,
        incident_id: str,
        headline: str,
        date_logged: str,
        company_involved: str,
        incident_topic: str,
        matched_claim_id: str | None,
        source_links: list[str],
        legitimacy_flag: str,
        confidence_level: str,
        import_notes: str | None,
    ) -> None:
        from app.services.incident_import import derive_incident_status

        status = derive_incident_status(legitimacy_flag, confidence_level)
        with self._connect() as connection:
            connection.execute(
                """
                insert into incident_logs (
                    id,
                    headline,
                    date_logged,
                    company_involved,
                    claimant_name,
                    incident_topic,
                    legitimacy_flag,
                    confidence_level,
                    import_notes,
                    categories,
                    severity_score,
                    reality_summary,
                    status,
                    matched_claim_id,
                    claim_match_confidence
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (id) do update
                set
                    headline = excluded.headline,
                    date_logged = excluded.date_logged,
                    company_involved = excluded.company_involved,
                    incident_topic = excluded.incident_topic,
                    legitimacy_flag = excluded.legitimacy_flag,
                    confidence_level = excluded.confidence_level,
                    import_notes = excluded.import_notes,
                    status = excluded.status,
                    matched_claim_id = excluded.matched_claim_id,
                    updated_at = current_timestamp
                """,
                (
                    incident_id,
                    headline,
                    date_logged,
                    company_involved,
                    None,
                    incident_topic,
                    legitimacy_flag,
                    confidence_level,
                    import_notes,
                    json.dumps([]),
                    1,
                    headline,
                    status,
                    matched_claim_id,
                    None,
                ),
            )
            connection.execute("delete from incident_sources where incident_id = %s", (incident_id,))
            self._execute_many(
                connection,
                """
                insert into incident_sources (
                    id,
                    incident_id,
                    source_url,
                    source_type,
                    publisher,
                    title,
                    published_at,
                    is_primary
                ) values (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        f"source-{uuid4()}",
                        incident_id,
                        url,
                        "imported",
                        None,
                        None,
                        None,
                        1 if index == 0 else 0,
                    )
                    for index, url in enumerate(source_links)
                ],
            )
            connection.commit()
```

- [ ] **Step 6: Run the import test file to verify it passes**

Run:

```bash
cd /Users/leo/Desktop/AI_Oops/backend && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/test_incident_import.py -q
```

Expected: `PASS`.

- [ ] **Step 7: Commit the persistence slice**

```bash
git add backend/tests/test_incident_import.py backend/tests/fakes.py backend/app/db/postgres_repository.py
git commit -m "feat: persist imported incidents and sources"
```

### Task 5: Add the CLI entrypoint and finish with verification

**Files:**
- Create: `backend/app/scripts/import_incidents_csv.py`
- Modify: `backend/tests/test_incident_import.py`

- [ ] **Step 1: Write the failing CLI-facing dry-run test**

Append:

```python
def test_import_incidents_csv_text_dry_run_validates_without_persisting() -> None:
    repository = InMemoryIncidentRepository()

    summary = import_incidents_csv_text(repository, IMPORT_CSV, dry_run=True)

    assert summary.validated == 1
    assert summary.inserted == 0
    assert repository.incidents == {}
```

- [ ] **Step 2: Run the test file to verify the new test fails**

Run:

```bash
cd /Users/leo/Desktop/AI_Oops/backend && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/test_incident_import.py -q
```

Expected: `FAIL` because the dry-run assertion is not covered yet or repository state still changes.

- [ ] **Step 3: Add the CLI script**

Create `backend/app/scripts/import_incidents_csv.py`:

```python
from __future__ import annotations

import argparse
from pathlib import Path

from app.core.config import get_settings
from app.db.repository_factory import build_incident_repository
from app.services.incident_import import import_incidents_csv_text


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import curated AI incident rows from a CSV file into PostgreSQL."
    )
    parser.add_argument("csv_path", type=Path)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the CSV without writing any database rows.",
    )
    args = parser.parse_args()

    settings = get_settings()
    repository = build_incident_repository(settings.database_url)
    csv_text = args.csv_path.read_text(encoding="utf-8")
    summary = import_incidents_csv_text(repository, csv_text, dry_run=args.dry_run)

    print(f"validated={summary.validated} inserted={summary.inserted}")
    print(f"dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Ensure the dry-run code path is side-effect free**

Keep this logic in `backend/app/services/incident_import.py`:

```python
    rows = parse_incidents_csv_text(csv_text)
    if dry_run:
        return IncidentImportSummary(validated=len(rows), inserted=0)
```

Do not call `repository.upsert_incident_import_row(...)` when `dry_run=True`.

- [ ] **Step 5: Run the focused import test file**

Run:

```bash
cd /Users/leo/Desktop/AI_Oops/backend && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest backend/tests/test_incident_import.py -q
```

Expected: `PASS`.

- [ ] **Step 6: Run the backend verification suite**

Run:

```bash
cd /Users/leo/Desktop/AI_Oops/backend && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q
cd /Users/leo/Desktop/AI_Oops/backend && .venv/bin/ruff format --check .
cd /Users/leo/Desktop/AI_Oops/backend && .venv/bin/ruff check .
```

Expected:

- pytest passes
- ruff format check passes
- ruff lint passes

- [ ] **Step 7: Commit the CLI and verification slice**

```bash
git add backend/app/scripts/import_incidents_csv.py backend/app/services/incident_import.py backend/tests/test_incident_import.py
git commit -m "feat: add incident csv import command"
```

## Self-Review

- Spec coverage checked:
  - CSV format and required columns: Tasks 2 and 3
  - 3-link minimum and URL validation: Tasks 2 and 3
  - schema fields for `incident_topic`, `legitimacy_flag`, `confidence_level`, `import_notes`: Task 1
  - status mapping rule: Tasks 3 and 4
  - upsert by `incident_id` with source replacement: Task 4
  - CLI support with `--dry-run`: Task 5
- Placeholder scan checked:
  - no `TODO`, `TBD`, or “similar to above” references remain
- Type consistency checked:
  - `matched_claim_id`, `incident_topic`, `legitimacy_flag`, `confidence_level`, and `import_notes` use the same names across model, parser, repository, and tests

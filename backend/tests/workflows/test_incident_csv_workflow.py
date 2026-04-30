from __future__ import annotations

from dataclasses import dataclass

from app.services.incident_review import (
    FetchedIncidentSource,
    IncidentReviewBatchSubmission,
    IncidentReviewResult,
)
from tests.support.fakes import InMemoryIncidentRepository
from tests.support.incident_csv_fixtures import INVALID_IMPORT_CSV, VALID_IMPORT_CSV


@dataclass
class FakeSourceFetcher:
    def fetch(self, source_url: str) -> FetchedIncidentSource:
        return FetchedIncidentSource(
            source_url=source_url,
            canonical_url=f"{source_url}?canonical=1",
            fetch_status="fetched",
            http_status=200,
            evidence_text=f"Evidence for {source_url}",
        )


class FakeBatchReviewClient:
    def __init__(self, *, status_by_batch_id: dict[str, str] | None = None) -> None:
        self.status_by_batch_id = status_by_batch_id or {}
        self.submissions: list[tuple[str, list[dict[str, object]]]] = []
        self.results_by_batch_id: dict[str, list[IncidentReviewResult]] = {}

    def submit_batch(
        self,
        *,
        incidents: list[dict[str, object]],
        model: str,
    ) -> IncidentReviewBatchSubmission:
        self.submissions.append((model, incidents))
        batch_id = f"batch-{len(self.submissions)}"
        self.status_by_batch_id.setdefault(batch_id, "validating")
        return IncidentReviewBatchSubmission(
            batch_id=batch_id,
            submitted=len(incidents),
            model=model,
        )

    def get_batch_status(self, *, batch_id: str) -> str:
        return self.status_by_batch_id[batch_id]

    def get_batch_results(self, *, batch_id: str) -> list[IncidentReviewResult]:
        return self.results_by_batch_id[batch_id]

    def review_incident(
        self,
        *,
        incident: dict[str, object],
        model: str,
    ) -> IncidentReviewResult:
        raise AssertionError("Escalation should not be needed in this workflow test")


class FakeTranslationClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def translate(
        self,
        *,
        headline_en: str,
        reality_summary_en: str,
    ):
        self.calls.append((headline_en, reality_summary_en))
        from app.services.incident_translation import IncidentTranslation

        return IncidentTranslation(
            headline_zh=f"ZH:{headline_en}",
            reality_summary_zh=f"ZH:{reality_summary_en}",
            status="completed",
        )


def test_run_incident_csv_workflow_imports_archives_and_submits_new_batches(
    tmp_path,
) -> None:
    from app.workflows.incident_csv_workflow import run_incident_csv_workflow

    repository = InMemoryIncidentRepository()
    inbox_dir = tmp_path / "inbox"
    archive_dir = tmp_path / "archive"
    inbox_dir.mkdir()
    (inbox_dir / "2023-a.csv").write_text(VALID_IMPORT_CSV, encoding="utf-8")
    batch_client = FakeBatchReviewClient()

    summary = run_incident_csv_workflow(
        repository=repository,
        inbox_dir=inbox_dir,
        archive_dir=archive_dir,
        source_fetcher=FakeSourceFetcher(),
        batch_client=batch_client,
        escalation_client=batch_client,
        translation_client=FakeTranslationClient(),
        primary_model="gpt-5.4-mini",
        escalation_model="gpt-5.2",
    )

    assert summary["files_found"] == 1
    assert summary["files_imported"] == 1
    assert summary["files_failed"] == 0
    assert summary["incidents_imported"] == 2
    assert summary["batches_submitted"] == 1
    assert summary["batches_reconciled"] == 0
    assert summary["batches_skipped"] == 1
    assert summary["translations_completed"] == 0
    assert summary["translations_failed"] == 0
    assert not (inbox_dir / "2023-a.csv").exists()
    assert len(list(archive_dir.glob("2023-a*.csv"))) == 1
    assert all(
        incident["status"] == "pending_llm_review"
        for incident in repository.incidents.values()
    )


def test_run_incident_csv_workflow_leaves_invalid_csv_in_inbox_and_continues(
    tmp_path,
) -> None:
    from app.workflows.incident_csv_workflow import run_incident_csv_workflow

    repository = InMemoryIncidentRepository()
    inbox_dir = tmp_path / "inbox"
    archive_dir = tmp_path / "archive"
    inbox_dir.mkdir()
    (inbox_dir / "bad.csv").write_text(INVALID_IMPORT_CSV, encoding="utf-8")
    (inbox_dir / "good.csv").write_text(VALID_IMPORT_CSV, encoding="utf-8")

    summary = run_incident_csv_workflow(
        repository=repository,
        inbox_dir=inbox_dir,
        archive_dir=archive_dir,
        source_fetcher=FakeSourceFetcher(),
        batch_client=FakeBatchReviewClient(),
        escalation_client=FakeBatchReviewClient(),
        translation_client=FakeTranslationClient(),
        primary_model="gpt-5.4-mini",
        escalation_model="gpt-5.2",
    )

    assert summary["files_found"] == 2
    assert summary["files_imported"] == 1
    assert summary["files_failed"] == 1
    assert (inbox_dir / "bad.csv").exists()
    assert not (inbox_dir / "good.csv").exists()
    assert len(list(archive_dir.glob("good*.csv"))) == 1


def test_run_incident_csv_workflow_reconciles_completed_batches_and_translates_approved_rows(  # noqa: E501
    tmp_path,
) -> None:
    from app.services.incident_import import import_incidents_csv_text
    from app.services.incident_review import submit_incident_review_batch
    from app.workflows.incident_csv_workflow import run_incident_csv_workflow

    repository = InMemoryIncidentRepository()
    import_incidents_csv_text(repository, VALID_IMPORT_CSV, dry_run=False)
    batch_client = FakeBatchReviewClient(status_by_batch_id={"batch-1": "completed"})
    submit_incident_review_batch(
        repository,
        source_fetcher=FakeSourceFetcher(),
        batch_client=batch_client,
        primary_model="gpt-5.4-mini",
    )
    incidents_by_external_id = {
        incident["external_id"]: incident
        for incident in repository.incidents.values()
    }
    batch_client.results_by_batch_id["batch-1"] = [
        IncidentReviewResult(
            incident_id=incidents_by_external_id["inc-openai-001"]["id"],
            verdict="approved",
            score=0.96,
            reasoning="Strong source support.",
            source_quality_summary="3 fetched sources agree on the event.",
            date_confirmed=True,
            company_confirmed=True,
            headline_en="OpenAI filing included fake legal citations",
            reality_summary_en="Court records confirm the filing incident.",
            needs_escalation=False,
            reviewed_model="gpt-5.4-mini",
        ),
        IncidentReviewResult(
            incident_id=incidents_by_external_id["inc-school-002"]["id"],
            verdict="pending_review",
            score=0.62,
            reasoning="Date ambiguity remains.",
            source_quality_summary="One source remains ambiguous.",
            date_confirmed=True,
            company_confirmed=True,
            headline_en="School chatbot gave inaccurate enrollment guidance",
            reality_summary_en="Reporting indicates the incident occurred.",
            needs_escalation=False,
            reviewed_model="gpt-5.4-mini",
        ),
    ]
    translation_client = FakeTranslationClient()

    summary = run_incident_csv_workflow(
        repository=repository,
        inbox_dir=tmp_path / "empty-inbox",
        archive_dir=tmp_path / "archive",
        source_fetcher=FakeSourceFetcher(),
        batch_client=batch_client,
        escalation_client=batch_client,
        translation_client=translation_client,
        primary_model="gpt-5.4-mini",
        escalation_model="gpt-5.2",
    )

    assert summary["files_found"] == 0
    assert summary["batches_submitted"] == 0
    assert summary["batches_reconciled"] == 1
    assert summary["batches_skipped"] == 0
    assert summary["approved"] == 1
    assert summary["pending_review"] == 1
    assert summary["rejected"] == 0
    assert summary["translations_completed"] == 1
    assert incidents_by_external_id["inc-openai-001"]["headline_zh"] == (
        "ZH:OpenAI filing included fake legal citations"
    )

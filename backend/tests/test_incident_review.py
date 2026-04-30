from __future__ import annotations

from dataclasses import dataclass

from app.services.incident_import import import_incidents_csv_text
from app.services.incident_review import (
    FetchedIncidentSource,
    IncidentReviewResult,
    reconcile_incident_review_batch,
    submit_incident_review_batch,
)
from app.services.incident_translation import IncidentTranslation
from tests.fakes import InMemoryIncidentRepository
from tests.test_incident_import import VALID_IMPORT_CSV


@dataclass
class FakeBatchSubmission:
    batch_id: str
    request_count: int
    model: str


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
    def __init__(self) -> None:
        self.submissions: list[tuple[str, list[dict[str, object]]]] = []
        self.results_by_batch_id: dict[str, list[IncidentReviewResult]] = {}
        self.escalation_results: dict[str, IncidentReviewResult] = {}

    def submit_batch(
        self,
        *,
        incidents: list[dict[str, object]],
        model: str,
    ) -> FakeBatchSubmission:
        self.submissions.append((model, incidents))
        return FakeBatchSubmission(
            batch_id="batch-primary-1",
            request_count=len(incidents),
            model=model,
        )

    def get_batch_results(self, *, batch_id: str) -> list[IncidentReviewResult]:
        return self.results_by_batch_id[batch_id]

    def review_incident(
        self,
        *,
        incident: dict[str, object],
        model: str,
    ) -> IncidentReviewResult:
        return self.escalation_results[incident["id"]]


class FakeTranslationClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def translate(
        self,
        *,
        headline_en: str,
        reality_summary_en: str,
    ) -> IncidentTranslation:
        self.calls.append((headline_en, reality_summary_en))
        return IncidentTranslation(
            headline_zh=f"ZH:{headline_en}",
            reality_summary_zh=f"ZH:{reality_summary_en}",
            status="completed",
        )


def test_submit_incident_review_batch_fetches_source_evidence_and_marks_batch(
) -> None:
    repository = InMemoryIncidentRepository()
    import_incidents_csv_text(repository, VALID_IMPORT_CSV, dry_run=False)
    batch_client = FakeBatchReviewClient()

    summary = submit_incident_review_batch(
        repository,
        source_fetcher=FakeSourceFetcher(),
        batch_client=batch_client,
        primary_model="gpt-5.4-mini",
    )

    assert summary.batch_id == "batch-primary-1"
    assert summary.submitted == 2
    assert batch_client.submissions[0][0] == "gpt-5.4-mini"

    first_incident = next(iter(repository.incidents.values()))
    assert first_incident["review_batch_id"] == "batch-primary-1"
    assert first_incident["review_model"] == "gpt-5.4-mini"
    assert first_incident["sources"][0]["fetch_status"] == "fetched"
    assert first_incident["sources"][0]["canonical_url"].endswith("?canonical=1")
    assert first_incident["sources"][0]["evidence_text"].startswith("Evidence for ")


def test_reconcile_incident_review_batch_escalates_uncertain_rows_and_translates_only_approved(  # noqa: E501
) -> None:
    repository = InMemoryIncidentRepository()
    import_incidents_csv_text(repository, VALID_IMPORT_CSV, dry_run=False)
    batch_client = FakeBatchReviewClient()
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
    batch_client.results_by_batch_id["batch-primary-1"] = [
        IncidentReviewResult(
            incident_id=incidents_by_external_id["inc-openai-001"]["id"],
            verdict="approved",
            score=0.96,
            reasoning="Primary review found strong source support.",
            source_quality_summary="3 fetched sources agree on the event.",
            date_confirmed=True,
            company_confirmed=True,
            headline_en="OpenAI filing included fake legal citations",
            reality_summary_en=(
                "Court records and reporting confirm the filing incident."
            ),
            needs_escalation=False,
            reviewed_model="gpt-5.4-mini",
        ),
        IncidentReviewResult(
            incident_id=incidents_by_external_id["inc-school-002"]["id"],
            verdict="pending_review",
            score=0.62,
            reasoning="Primary review found unresolved source ambiguity.",
            source_quality_summary="One source is weak and requires closer review.",
            date_confirmed=False,
            company_confirmed=True,
            headline_en="School chatbot gave inaccurate enrollment guidance",
            reality_summary_en=(
                "Local reporting suggests the issue happened but details conflict."
            ),
            needs_escalation=True,
            reviewed_model="gpt-5.4-mini",
        ),
    ]
    batch_client.escalation_results[
        incidents_by_external_id["inc-school-002"]["id"]
    ] = IncidentReviewResult(
        incident_id=incidents_by_external_id["inc-school-002"]["id"],
        verdict="pending_review",
        score=0.74,
        reasoning="Escalation review agrees the row should wait for editor approval.",
        source_quality_summary=(
            "Escalation confirmed the event but found date ambiguity."
        ),
        date_confirmed=False,
        company_confirmed=True,
        headline_en="School chatbot gave inaccurate enrollment guidance",
        reality_summary_en=(
            "Escalation confirmed the incident but left date ambiguity unresolved."
        ),
        needs_escalation=False,
        reviewed_model="gpt-5.2",
    )
    translation_client = FakeTranslationClient()

    summary = reconcile_incident_review_batch(
        repository,
        batch_id="batch-primary-1",
        batch_client=batch_client,
        escalation_client=batch_client,
        translation_client=translation_client,
        escalation_model="gpt-5.2",
    )

    assert summary.approved == 1
    assert summary.pending_review == 1
    assert summary.rejected == 0
    assert summary.escalated == 1

    approved_incident = incidents_by_external_id["inc-openai-001"]
    queued_incident = incidents_by_external_id["inc-school-002"]

    assert approved_incident["status"] == "approved"
    assert approved_incident["translation_status"] == "completed"
    assert approved_incident["headline_zh"] == (
        "ZH:OpenAI filing included fake legal citations"
    )
    assert approved_incident["legitimacy_score"] == 0.96
    assert approved_incident["review_model"] == "gpt-5.4-mini"

    assert queued_incident["status"] == "pending_review"
    assert queued_incident["translation_status"] == "not_requested"
    assert queued_incident["legitimacy_score"] == 0.74
    assert queued_incident["review_model"] == "gpt-5.2"
    assert queued_incident["source_validation_summary"] == (
        "Escalation confirmed the event but found date ambiguity."
    )
    assert translation_client.calls == [
        (
            "OpenAI filing included fake legal citations",
            "Court records and reporting confirm the filing incident.",
        )
    ]

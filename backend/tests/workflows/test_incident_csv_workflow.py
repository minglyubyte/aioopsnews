from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

from app.services.incident_deduplication import DuplicateJudgeDecision
from app.services.incident_review import FetchedIncidentSource, IncidentReviewResult
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


class FakeAsyncReviewClient:
    def __init__(
        self,
        *,
        results_by_external_id: dict[str, list[IncidentReviewResult | Exception]],
    ) -> None:
        self.results_by_external_id = {
            key: list(value) for key, value in results_by_external_id.items()
        }
        self.calls: list[tuple[str, str]] = []

    async def review_incident(
        self,
        *,
        incident: dict[str, object],
        model: str,
    ) -> IncidentReviewResult:
        external_id = str(incident["external_id"])
        self.calls.append((external_id, model))
        response = self.results_by_external_id[external_id].pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeEscalationReviewClient:
    def __init__(
        self,
        *,
        results_by_external_id: dict[
            str, IncidentReviewResult | Exception
        ] | None = None,
    ) -> None:
        self.results_by_external_id = results_by_external_id or {}
        self.calls: list[tuple[str, str]] = []

    def review_incident(
        self,
        *,
        incident: dict[str, object],
        model: str,
    ) -> IncidentReviewResult:
        external_id = str(incident["external_id"])
        self.calls.append((external_id, model))
        response = self.results_by_external_id[external_id]
        if isinstance(response, Exception):
            raise response
        return response


class FakeTranslationClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def translate(
        self,
        *,
        company_involved_en: str,
        headline_en: str,
        reality_summary_en: str,
        legitimacy_reasoning_en: str,
        source_validation_summary_en: str,
        incident_summary_en: str = "",
        what_happened_en: str = "",
        ai_failure_point_en: str = "",
        why_it_matters_en: str = "",
        evidence_summary_en: str = "",
    ):
        self.calls.append(
            {
                "company_involved_en": company_involved_en,
                "headline_en": headline_en,
                "reality_summary_en": reality_summary_en,
                "legitimacy_reasoning_en": legitimacy_reasoning_en,
                "source_validation_summary_en": source_validation_summary_en,
                "incident_summary_en": incident_summary_en,
                "what_happened_en": what_happened_en,
                "ai_failure_point_en": ai_failure_point_en,
                "why_it_matters_en": why_it_matters_en,
                "evidence_summary_en": evidence_summary_en,
            }
        )
        from app.services.incident_translation import IncidentTranslation

        return IncidentTranslation(
            company_involved_zh=f"ZH:{company_involved_en}",
            headline_zh=f"ZH:{headline_en}",
            reality_summary_zh=f"ZH:{reality_summary_en}",
            legitimacy_reasoning_zh=f"ZH:{legitimacy_reasoning_en}",
            source_validation_summary_zh=f"ZH:{source_validation_summary_en}",
            incident_summary_zh=f"ZH:{incident_summary_en}",
            what_happened_zh=f"ZH:{what_happened_en}",
            ai_failure_point_zh=f"ZH:{ai_failure_point_en}",
            why_it_matters_zh=f"ZH:{why_it_matters_en}",
            evidence_summary_zh=f"ZH:{evidence_summary_en}",
            status="completed",
        )


class FakeEmbeddingClient:
    def create_embedding(self, *, text: str, model: str) -> list[float]:
        if "OpenAI filing included fake legal citations" in text:
            return [1.0, 0.0]
        if "Federal court filing included fabricated citations" in text:
            return [0.99, 0.01]
        return [0.0, 1.0]


class FakeDuplicateJudgeClient:
    def judge_duplicate(
        self,
        *,
        incident: dict[str, object],
        candidate: dict[str, object],
        model: str,
    ) -> DuplicateJudgeDecision:
        return DuplicateJudgeDecision(
            is_duplicate=True,
            confidence=0.95,
            reasoning="Same underlying sanctions-related filing.",
            canonical_incident_id="incident-canonical",
        )


def test_run_incident_csv_workflow_imports_archives_and_reviews_pending_rows_immediately(  # noqa: E501
    tmp_path,
) -> None:
    from app.workflows.incident_csv_workflow import run_incident_csv_workflow

    repository = InMemoryIncidentRepository()
    inbox_dir = tmp_path / "inbox"
    archive_dir = tmp_path / "archive"
    inbox_dir.mkdir()
    (inbox_dir / "2023-a.csv").write_text(VALID_IMPORT_CSV, encoding="utf-8")
    review_client = FakeAsyncReviewClient(
        results_by_external_id={
            "inc-openai-001": [
                IncidentReviewResult(
                    incident_id="unused-openai",
                    verdict="approved",
                    score=0.96,
                    reasoning="Strong source support.",
                    source_quality_summary="3 fetched sources agree on the event.",
                    date_confirmed=True,
                    company_confirmed=True,
                    headline_en="OpenAI filing included fake legal citations",
                    reality_summary_en="Court records confirm the filing incident.",
                    incident_summary_en=(
                        "A court filing incident exposed fabricated citations."
                    ),
                    what_happened_en=(
                        "The filing included fabricated citations and required "
                        "correction."
                    ),
                    ai_failure_point_en=(
                        "The drafting workflow failed to verify cited cases."
                    ),
                    why_it_matters_en=(
                        "The issue affected a real legal filing."
                    ),
                    evidence_summary_en=(
                        "Court records and reporting confirm the error."
                    ),
                    categories=["Hallucinations"],
                    suggested_severity_score=2,
                    severity_confidence=0.93,
                    severity_reasoning="Limited but confirmed harm.",
                    severity_flags=[],
                    needs_escalation=False,
                    reviewed_model="gpt-5.4-mini",
                )
            ],
            "inc-school-002": [
                IncidentReviewResult(
                    incident_id="unused-school",
                    verdict="pending_review",
                    score=0.62,
                    reasoning="Date ambiguity remains.",
                    source_quality_summary="One source remains ambiguous.",
                    date_confirmed=True,
                    company_confirmed=True,
                    headline_en="School chatbot gave inaccurate enrollment guidance",
                    reality_summary_en="Reporting indicates the incident occurred.",
                    categories=["Autonomous Systems"],
                    suggested_severity_score=None,
                    severity_confidence=0.82,
                    severity_reasoning="Still unresolved.",
                    severity_flags=[],
                    needs_escalation=False,
                    reviewed_model="gpt-5.4-mini",
                )
            ],
        }
    )
    translation_client = FakeTranslationClient()

    summary = asyncio.run(
        run_incident_csv_workflow(
            repository=repository,
            inbox_dir=inbox_dir,
            archive_dir=archive_dir,
            source_fetcher=FakeSourceFetcher(),
            review_client=review_client,
            escalation_client=FakeEscalationReviewClient(),
            translation_client=translation_client,
            primary_model="gpt-5.4-mini",
            escalation_model="gpt-5.2",
            embedding_client=FakeEmbeddingClient(),
            duplicate_judge_client=FakeDuplicateJudgeClient(),
        )
    )

    assert summary["files_found"] == 1
    assert summary["files_imported"] == 1
    assert summary["files_failed"] == 0
    assert summary["incidents_imported"] == 2
    assert summary["reviews_attempted"] == 2
    assert summary["reviews_completed"] == 2
    assert summary["reviews_failed"] == 0
    assert summary["review_failures"] == []
    assert summary["approved"] == 1
    assert summary["pending_review"] == 1
    assert summary["rejected"] == 0
    assert summary["translations_completed"] == 1
    assert summary["translations_failed"] == 0
    approved_incident = next(
        incident
        for incident in repository.incidents.values()
        if incident["external_id"] == "inc-openai-001"
    )
    assert approved_incident["company_involved_zh"] == "ZH:OpenAI"
    assert approved_incident["incident_summary_zh"] == (
        "ZH:A court filing incident exposed fabricated citations."
    )
    assert translation_client.calls == [
        {
            "company_involved_en": "OpenAI",
            "headline_en": "OpenAI filing included fake legal citations",
            "reality_summary_en": "Court records confirm the filing incident.",
            "legitimacy_reasoning_en": "Strong source support.",
            "source_validation_summary_en": "3 fetched sources agree on the event.",
            "incident_summary_en": (
                "A court filing incident exposed fabricated citations."
            ),
            "what_happened_en": (
                "The filing included fabricated citations and required "
                "correction."
            ),
            "ai_failure_point_en": (
                "The drafting workflow failed to verify cited cases."
            ),
            "why_it_matters_en": "The issue affected a real legal filing.",
            "evidence_summary_en": (
                "Court records and reporting confirm the error."
            ),
        }
    ]
    assert "batches_submitted" not in summary
    assert not (inbox_dir / "2023-a.csv").exists()
    assert len(list(archive_dir.glob("2023-a*.csv"))) == 1


def test_run_incident_csv_workflow_can_import_without_reviewing(
    tmp_path,
) -> None:
    from app.workflows.incident_csv_workflow import run_incident_csv_workflow

    repository = InMemoryIncidentRepository()
    inbox_dir = tmp_path / "inbox"
    archive_dir = tmp_path / "archive"
    inbox_dir.mkdir()
    (inbox_dir / "2023-a.csv").write_text(VALID_IMPORT_CSV, encoding="utf-8")
    review_client = FakeAsyncReviewClient(results_by_external_id={})

    summary = asyncio.run(
        run_incident_csv_workflow(
            repository=repository,
            inbox_dir=inbox_dir,
            archive_dir=archive_dir,
            source_fetcher=FakeSourceFetcher(),
            review_client=review_client,
            escalation_client=FakeEscalationReviewClient(),
            translation_client=FakeTranslationClient(),
            primary_model="gpt-5.4-mini",
            escalation_model="gpt-5.2",
            embedding_client=FakeEmbeddingClient(),
            duplicate_judge_client=FakeDuplicateJudgeClient(),
            import_only=True,
        )
    )

    assert summary["files_imported"] == 1
    assert summary["incidents_imported"] == 2
    assert summary["reviews_attempted"] == 0
    assert review_client.calls == []
    assert not (inbox_dir / "2023-a.csv").exists()
    assert len(list(archive_dir.glob("2023-a*.csv"))) == 1
    assert len(repository.list_incidents_pending_llm_review()) == 2


def test_run_incident_csv_workflow_limits_reviews_per_run(
    tmp_path,
) -> None:
    from app.workflows.incident_csv_workflow import run_incident_csv_workflow

    repository = InMemoryIncidentRepository()
    inbox_dir = tmp_path / "inbox"
    archive_dir = tmp_path / "archive"
    inbox_dir.mkdir()
    (inbox_dir / "2023-a.csv").write_text(VALID_IMPORT_CSV, encoding="utf-8")
    review_client = FakeAsyncReviewClient(
        results_by_external_id={
            "inc-openai-001": [
                IncidentReviewResult(
                    incident_id="unused-openai",
                    verdict="pending_review",
                    score=0.62,
                    reasoning="Needs editor review.",
                    source_quality_summary="Sources need review.",
                    date_confirmed=True,
                    company_confirmed=True,
                    headline_en="OpenAI filing included fake legal citations",
                    reality_summary_en="Court records describe the incident.",
                    categories=["Hallucinations"],
                    suggested_severity_score=None,
                    severity_confidence=0.82,
                    severity_reasoning="Needs review.",
                    severity_flags=[],
                    needs_escalation=False,
                    reviewed_model="gpt-5.4-mini",
                )
            ],
            "inc-school-002": [
                IncidentReviewResult(
                    incident_id="unused-school",
                    verdict="pending_review",
                    score=0.62,
                    reasoning="Needs editor review.",
                    source_quality_summary="Sources need review.",
                    date_confirmed=True,
                    company_confirmed=True,
                    headline_en="School chatbot gave inaccurate enrollment guidance",
                    reality_summary_en="Reporting describes the incident.",
                    categories=["Autonomous Systems"],
                    suggested_severity_score=None,
                    severity_confidence=0.82,
                    severity_reasoning="Needs review.",
                    severity_flags=[],
                    needs_escalation=False,
                    reviewed_model="gpt-5.4-mini",
                )
            ],
        }
    )

    summary = asyncio.run(
        run_incident_csv_workflow(
            repository=repository,
            inbox_dir=inbox_dir,
            archive_dir=archive_dir,
            source_fetcher=FakeSourceFetcher(),
            review_client=review_client,
            escalation_client=FakeEscalationReviewClient(),
            translation_client=FakeTranslationClient(),
            primary_model="gpt-5.4-mini",
            escalation_model="gpt-5.2",
            embedding_client=FakeEmbeddingClient(),
            duplicate_judge_client=FakeDuplicateJudgeClient(),
            max_reviews=1,
        )
    )

    assert summary["incidents_imported"] == 2
    assert summary["reviews_attempted"] == 1
    assert len(review_client.calls) == 1
    assert review_client.calls[0][1] == "gpt-5.4-mini"
    assert len(repository.list_incidents_pending_llm_review()) == 1


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
    review_client = FakeAsyncReviewClient(
        results_by_external_id={
            "inc-openai-001": [
                IncidentReviewResult(
                    incident_id="unused-openai",
                    verdict="rejected",
                    score=0.1,
                    reasoning="Not verified.",
                    source_quality_summary="Weak evidence.",
                    date_confirmed=True,
                    company_confirmed=True,
                    headline_en="Rejected",
                    reality_summary_en="Rejected",
                    categories=["Hallucinations"],
                    suggested_severity_score=None,
                    severity_confidence=None,
                    severity_reasoning="Rejected.",
                    severity_flags=[],
                    needs_escalation=False,
                    reviewed_model="gpt-5.4-mini",
                )
            ],
            "inc-school-002": [
                IncidentReviewResult(
                    incident_id="unused-school",
                    verdict="pending_review",
                    score=0.62,
                    reasoning="Needs more review.",
                    source_quality_summary="Conflicting source details.",
                    date_confirmed=True,
                    company_confirmed=True,
                    headline_en="School chatbot gave inaccurate enrollment guidance",
                    reality_summary_en="Reporting indicates the incident occurred.",
                    categories=["Autonomous Systems"],
                    suggested_severity_score=None,
                    severity_confidence=0.82,
                    severity_reasoning="Needs review.",
                    severity_flags=[],
                    needs_escalation=False,
                    reviewed_model="gpt-5.4-mini",
                )
            ],
        }
    )

    summary = asyncio.run(
        run_incident_csv_workflow(
            repository=repository,
            inbox_dir=inbox_dir,
            archive_dir=archive_dir,
            source_fetcher=FakeSourceFetcher(),
            review_client=review_client,
            escalation_client=FakeEscalationReviewClient(),
            translation_client=FakeTranslationClient(),
            primary_model="gpt-5.4-mini",
            escalation_model="gpt-5.2",
            embedding_client=FakeEmbeddingClient(),
            duplicate_judge_client=FakeDuplicateJudgeClient(),
        )
    )

    assert summary["files_found"] == 2
    assert summary["files_imported"] == 1
    assert summary["files_failed"] == 1
    assert summary["reviews_attempted"] == 2
    assert (inbox_dir / "bad.csv").exists()
    assert not (inbox_dir / "good.csv").exists()
    assert len(list(archive_dir.glob("good*.csv"))) == 1


def test_run_incident_csv_workflow_reports_unrecoverable_review_failures(
    tmp_path,
) -> None:
    from app.workflows.incident_csv_workflow import run_incident_csv_workflow

    repository = InMemoryIncidentRepository()
    inbox_dir = tmp_path / "inbox"
    archive_dir = tmp_path / "archive"
    inbox_dir.mkdir()
    (inbox_dir / "2023-a.csv").write_text(VALID_IMPORT_CSV, encoding="utf-8")
    review_client = FakeAsyncReviewClient(
        results_by_external_id={
            "inc-openai-001": [
                IncidentReviewResult(
                    incident_id="unused-openai",
                    verdict="approved",
                    score=0.96,
                    reasoning="Strong source support.",
                    source_quality_summary="3 fetched sources agree on the event.",
                    date_confirmed=True,
                    company_confirmed=True,
                    headline_en="OpenAI filing included fake legal citations",
                    reality_summary_en="Court records confirm the filing incident.",
                    categories=["Hallucinations"],
                    suggested_severity_score=2,
                    severity_confidence=0.93,
                    severity_reasoning="Limited but confirmed harm.",
                    severity_flags=[],
                    needs_escalation=False,
                    reviewed_model="gpt-5.4-mini",
                )
            ],
            "inc-school-002": [
                RuntimeError("temporary outage"),
                RuntimeError("temporary outage"),
                RuntimeError("temporary outage"),
            ],
        }
    )

    summary = asyncio.run(
        run_incident_csv_workflow(
            repository=repository,
            inbox_dir=inbox_dir,
            archive_dir=archive_dir,
            source_fetcher=FakeSourceFetcher(),
            review_client=review_client,
            escalation_client=FakeEscalationReviewClient(),
            translation_client=FakeTranslationClient(),
            primary_model="gpt-5.4-mini",
            escalation_model="gpt-5.2",
            embedding_client=FakeEmbeddingClient(),
            duplicate_judge_client=FakeDuplicateJudgeClient(),
        )
    )

    school_incident = next(
        incident
        for incident in repository.incidents.values()
        if incident["external_id"] == "inc-school-002"
    )

    assert summary["reviews_attempted"] == 2
    assert summary["reviews_completed"] == 1
    assert summary["reviews_failed"] == 1
    assert len(summary["review_failures"]) == 1
    assert summary["review_failures"][0]["external_id"] == "inc-school-002"
    assert summary["approved"] == 1
    assert school_incident["status"] == "pending_llm_review"


def test_run_incident_csv_workflow_reports_escalation_parse_failures_without_crashing(
    tmp_path,
) -> None:
    from app.workflows.incident_csv_workflow import run_incident_csv_workflow

    repository = InMemoryIncidentRepository()
    inbox_dir = tmp_path / "inbox"
    archive_dir = tmp_path / "archive"
    inbox_dir.mkdir()
    (inbox_dir / "2023-a.csv").write_text(VALID_IMPORT_CSV, encoding="utf-8")
    review_client = FakeAsyncReviewClient(
        results_by_external_id={
            "inc-openai-001": [
                IncidentReviewResult(
                    incident_id="unused-openai",
                    verdict="approved",
                    score=0.96,
                    reasoning="Strong source support.",
                    source_quality_summary="3 fetched sources agree on the event.",
                    date_confirmed=True,
                    company_confirmed=True,
                    headline_en="OpenAI filing included fake legal citations",
                    reality_summary_en="Court records confirm the filing incident.",
                    categories=["Hallucinations"],
                    suggested_severity_score=2,
                    severity_confidence=0.93,
                    severity_reasoning="Limited but confirmed harm.",
                    severity_flags=[],
                    needs_escalation=False,
                    reviewed_model="gpt-5.4-mini",
                )
            ],
            "inc-school-002": [
                IncidentReviewResult(
                    incident_id="unused-school",
                    verdict="pending_review",
                    score=0.58,
                    reasoning="Primary review remains uncertain.",
                    source_quality_summary="Conflicting source details.",
                    date_confirmed=False,
                    company_confirmed=True,
                    headline_en="School chatbot gave inaccurate enrollment guidance",
                    reality_summary_en="Primary review found unresolved ambiguity.",
                    categories=["Autonomous Systems"],
                    suggested_severity_score=3,
                    severity_confidence=0.61,
                    severity_reasoning="Evidence conflicts.",
                    severity_flags=[],
                    needs_escalation=True,
                    reviewed_model="gpt-5.4-mini",
                )
            ],
        }
    )

    summary = asyncio.run(
        run_incident_csv_workflow(
            repository=repository,
            inbox_dir=inbox_dir,
            archive_dir=archive_dir,
            source_fetcher=FakeSourceFetcher(),
            review_client=review_client,
            escalation_client=FakeEscalationReviewClient(
                results_by_external_id={
                    "inc-school-002": json.JSONDecodeError(
                        "Expecting value",
                        "",
                        0,
                    )
                }
            ),
            translation_client=FakeTranslationClient(),
            primary_model="gpt-5.4-mini",
            escalation_model="gpt-5.2",
            embedding_client=FakeEmbeddingClient(),
            duplicate_judge_client=FakeDuplicateJudgeClient(),
        )
    )

    school_incident = next(
        incident
        for incident in repository.incidents.values()
        if incident["external_id"] == "inc-school-002"
    )

    assert summary["reviews_attempted"] == 2
    assert summary["reviews_completed"] == 1
    assert summary["reviews_failed"] == 1
    assert len(summary["review_failures"]) == 1
    assert summary["review_failures"][0]["external_id"] == "inc-school-002"
    assert "Expecting value" in summary["review_failures"][0]["error"]
    assert summary["approved"] == 1
    assert school_incident["status"] == "pending_llm_review"


def test_run_incident_csv_workflow_merges_confirmed_duplicates_without_publicizing_duplicate(  # noqa: E501
    tmp_path,
) -> None:
    from app.services.incident_import import import_incidents_csv_text
    from app.workflows.incident_csv_workflow import run_incident_csv_workflow

    repository = InMemoryIncidentRepository(
        incidents=[
            {
                "id": "incident-canonical",
                "external_id": "inc-existing-001",
                "headline": "Federal court filing included fabricated citations",
                "headline_en": "Federal court filing included fabricated citations",
                "headline_zh": None,
                "date_logged": "2023-05-03",
                "company_involved": "OpenAI",
                "incident_topic": "legal hallucination",
                "claimant_name": None,
                "categories": [],
                "severity_score": 3,
                "reality_summary": "Existing canonical incident.",
                "reality_summary_en": "Existing canonical incident.",
                "reality_summary_zh": None,
                "status": "approved",
                "review_notes": None,
                "matched_claim_id": None,
                "claim_match_confidence": None,
                "legitimacy_score": 0.94,
                "legitimacy_label": "approved",
                "legitimacy_reasoning": "Already approved.",
                "source_validation_summary": "Validated 3 distinct sources.",
                "legitimacy_flag": "ACCEPT",
                "confidence_level": "high",
                "import_notes": "Canonical note.",
                "translation_status": "completed",
                "review_batch_id": "historic-batch",
                "review_model": "gpt-5.4-mini",
                "reviewed_at": None,
                "translated_at": None,
                "duplicate_status": None,
                "duplicate_of_incident_id": None,
                "canonical_incident_id": None,
                "embedding_model": None,
                "embedding_vector": None,
                "duplicate_candidates": [],
                "sources": [
                    {
                        "id": "canonical-source-1",
                        "source_url": "https://example.com/canonical-source",
                        "canonical_url": None,
                        "source_type": "imported",
                        "publisher": None,
                        "title": None,
                        "fetch_status": None,
                        "http_status": None,
                        "evidence_text": None,
                        "fetch_error": None,
                        "is_primary": True,
                    }
                ],
            }
        ]
    )
    import_incidents_csv_text(repository, VALID_IMPORT_CSV, dry_run=False)
    review_client = FakeAsyncReviewClient(
        results_by_external_id={
            "inc-openai-001": [
                IncidentReviewResult(
                    incident_id="unused-openai",
                    verdict="approved",
                    score=0.96,
                    reasoning="Primary review found strong source support.",
                    source_quality_summary="3 fetched sources agree on the event.",
                    date_confirmed=True,
                    company_confirmed=True,
                    headline_en="OpenAI filing included fake legal citations",
                    reality_summary_en=(
                        "Court records and reporting confirm the filing "
                        "incident."
                    ),
                    categories=["Hallucinations"],
                    suggested_severity_score=2,
                    severity_confidence=0.93,
                    severity_reasoning="Limited but confirmed harm.",
                    severity_flags=[],
                    needs_escalation=False,
                    reviewed_model="gpt-5.4-mini",
                )
            ],
            "inc-school-002": [
                IncidentReviewResult(
                    incident_id="unused-school",
                    verdict="pending_review",
                    score=0.62,
                    reasoning="Primary review found unresolved source ambiguity.",
                    source_quality_summary=(
                        "One source is weak and requires closer review."
                    ),
                    date_confirmed=True,
                    company_confirmed=True,
                    headline_en="School chatbot gave inaccurate enrollment guidance",
                    reality_summary_en=(
                        "Local reporting suggests the issue happened but "
                        "details conflict."
                    ),
                    categories=["Autonomous Systems"],
                    suggested_severity_score=None,
                    severity_confidence=0.82,
                    severity_reasoning="Needs review.",
                    severity_flags=[],
                    needs_escalation=False,
                    reviewed_model="gpt-5.4-mini",
                )
            ],
        }
    )

    summary = asyncio.run(
        run_incident_csv_workflow(
            repository=repository,
            inbox_dir=tmp_path / "empty-inbox",
            archive_dir=tmp_path / "archive",
            source_fetcher=FakeSourceFetcher(),
            review_client=review_client,
            escalation_client=FakeEscalationReviewClient(),
            translation_client=FakeTranslationClient(),
            primary_model="gpt-5.4-mini",
            escalation_model="gpt-5.2",
            embedding_client=FakeEmbeddingClient(),
            duplicate_judge_client=FakeDuplicateJudgeClient(),
        )
    )

    imported_incident = next(
        incident
        for incident in repository.incidents.values()
        if incident.get("external_id") == "inc-openai-001"
    )
    assert summary["approved"] == 0
    assert imported_incident["status"] == "duplicate_confirmed"
    assert repository.get_public_incident(imported_incident["id"]) is None
    assert repository.get_public_incident("incident-canonical") is not None

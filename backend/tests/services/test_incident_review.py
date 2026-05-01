from __future__ import annotations

from dataclasses import dataclass

from app.core.incident_taxonomy import INCIDENT_CATEGORY_TAXONOMY
from app.services.incident_deduplication import DuplicateJudgeDecision
from app.services.incident_import import import_incidents_csv_text
from app.services.incident_review import (
    FetchedIncidentSource,
    IncidentReviewResult,
    _build_review_response_format,
    _extract_evidence_text,
    _parse_review_result,
    reconcile_incident_review_batch,
    submit_incident_review_batch,
)
from app.services.incident_translation import IncidentTranslation
from tests.support.fakes import InMemoryIncidentRepository
from tests.support.incident_csv_fixtures import VALID_IMPORT_CSV


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


class FakeEmbeddingClient:
    def create_embedding(self, *, text: str, model: str) -> list[float]:
        if "OpenAI filing included fake legal citations" in text:
            return [1.0, 0.0]
        if "Federal court filing included fabricated citations" in text:
            return [0.99, 0.01]
        return [0.0, 1.0]


class FakeDuplicateJudgeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def judge_duplicate(
        self,
        *,
        incident: dict[str, object],
        candidate: dict[str, object],
        model: str,
    ) -> DuplicateJudgeDecision:
        self.calls.append((incident["id"], candidate["id"]))
        if candidate["id"] == "incident-canonical":
            return DuplicateJudgeDecision(
                is_duplicate=True,
                confidence=0.95,
                reasoning="Same underlying sanctions-related filing.",
                canonical_incident_id="incident-canonical",
            )
        return DuplicateJudgeDecision(
            is_duplicate=False,
            confidence=0.12,
            reasoning="Different real-world incident.",
            canonical_incident_id=None,
        )


def test_extract_evidence_text_strips_nul_bytes() -> None:
    evidence = _extract_evidence_text("Alpha\x00Beta\nGamma")

    assert "\x00" not in evidence
    assert evidence == "Alpha Beta Gamma"


def test_parse_review_result_accepts_qualitative_severity_confidence() -> None:
    result = _parse_review_result(
        incident_id="incident-1",
        model="gpt-5.4-mini",
        content=(
            '{"verdict":"approved","score":0.94,"reasoning":"Strong evidence.",'
            '"source_quality_summary":"Two credible sources.",'
            '"date_confirmed":true,"company_confirmed":true,'
            '"headline_en":"Incident headline","reality_summary_en":"Summary.",'
            '"categories":["Hallucinations"],'
            '"suggested_severity_score":2,"severity_confidence":"low",'
            '"severity_reasoning":"Limited confidence.","severity_flags":[],'
            '"needs_escalation":false}'
        ),
    )

    assert result.categories == ["Hallucinations"]
    assert result.severity_confidence == 0.25
    assert result.needs_escalation is False


def test_build_review_response_format_requires_taxonomy_categories() -> None:
    response_format = _build_review_response_format()

    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    schema = response_format["json_schema"]["schema"]
    assert "categories" in schema["required"]
    assert "needs_escalation" in schema["required"]
    assert schema["properties"]["categories"]["minItems"] == 1
    assert schema["properties"]["needs_escalation"]["type"] == "boolean"
    assert schema["properties"]["categories"]["items"]["enum"] == list(
        INCIDENT_CATEGORY_TAXONOMY
    )
    assert schema["additionalProperties"] is False


def test_parse_review_result_marks_unknown_categories_for_escalation() -> None:
    result = _parse_review_result(
        incident_id="incident-1",
        model="gpt-5.4-mini",
        content=(
            '{"verdict":"approved","score":0.94,"reasoning":"Strong evidence.",'
            '"source_quality_summary":"Two credible sources.",'
            '"date_confirmed":true,"company_confirmed":true,'
            '"headline_en":"Incident headline","reality_summary_en":"Summary.",'
            '"categories":["Made Up Category"],'
            '"suggested_severity_score":2,"severity_confidence":0.92,'
            '"severity_reasoning":"High confidence.","severity_flags":[],'
            '"needs_escalation":false}'
        ),
    )

    assert result.categories is None
    assert result.needs_escalation is True


def test_parse_review_result_preserves_explicit_needs_escalation() -> None:
    result = _parse_review_result(
        incident_id="incident-1",
        model="gpt-5.4-mini",
        content=(
            '{"verdict":"pending_review","score":0.51,'
            '"reasoning":"Evidence remains weak.",'
            '"source_quality_summary":"Sources conflict.",'
            '"date_confirmed":false,"company_confirmed":true,'
            '"headline_en":"Incident headline","reality_summary_en":"Summary.",'
            '"categories":["Hallucinations"],'
            '"suggested_severity_score":3,"severity_confidence":0.61,'
            '"severity_reasoning":"Signals conflict.","severity_flags":[],'
            '"needs_escalation":true}'
        ),
    )

    assert result.needs_escalation is True


def test_submit_incident_review_batch_fetches_source_evidence_and_marks_batch() -> None:
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
        incident["external_id"]: incident for incident in repository.incidents.values()
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
            categories=["Hallucinations"],
            suggested_severity_score=2,
            severity_confidence=0.92,
            severity_reasoning=(
                "Legal filing incident with reputational impact but no evidence "
                "of broader downstream harm."
            ),
            severity_flags=[],
            needs_escalation=False,
            reviewed_model="gpt-5.4-mini",
        ),
        IncidentReviewResult(
            incident_id=incidents_by_external_id["inc-school-002"]["id"],
            verdict="approved",
            score=0.94,
            reasoning="Primary review found strong source support.",
            source_quality_summary="Multiple sources agree on the incident details.",
            date_confirmed=True,
            company_confirmed=True,
            headline_en="School chatbot gave inaccurate enrollment guidance",
            reality_summary_en=(
                "School staff had to intervene after students received "
                "inaccurate enrollment guidance."
            ),
            categories=["Autonomous Systems", "Missed Timelines"],
            suggested_severity_score=3,
            severity_confidence=0.89,
            severity_reasoning=(
                "The incident caused operational disruption that required "
                "staff intervention."
            ),
            severity_flags=[],
            needs_escalation=False,
            reviewed_model="gpt-5.4-mini",
        ),
    ]
    translation_client = FakeTranslationClient()

    summary = reconcile_incident_review_batch(
        repository,
        batch_id="batch-primary-1",
        batch_client=batch_client,
        escalation_client=batch_client,
        translation_client=translation_client,
        embedding_client=FakeEmbeddingClient(),
        duplicate_judge_client=FakeDuplicateJudgeClient(),
        embedding_model="text-embedding-3-small",
        duplicate_judge_model="gpt-5.2",
        escalation_model="gpt-5.2",
    )

    assert summary.approved == 1
    assert summary.pending_review == 1
    assert summary.rejected == 0
    assert summary.escalated == 0

    approved_incident = incidents_by_external_id["inc-openai-001"]
    queued_incident = incidents_by_external_id["inc-school-002"]

    assert approved_incident["status"] == "approved"
    assert approved_incident["translation_status"] == "completed"
    assert approved_incident["headline_zh"] == (
        "ZH:OpenAI filing included fake legal citations"
    )
    assert approved_incident["legitimacy_score"] == 0.96
    assert approved_incident["review_model"] == "gpt-5.4-mini"
    assert approved_incident["categories"] == ["Hallucinations"]
    assert approved_incident["severity_score"] == 2
    assert approved_incident["suggested_severity_score"] == 2
    assert approved_incident["severity_decision_source"] == "primary_llm"

    assert queued_incident["status"] == "pending_editor_review"
    assert queued_incident["categories"] == [
        "Autonomous Systems",
        "Missed Timelines",
    ]
    assert queued_incident["translation_status"] == "not_requested"
    assert queued_incident["legitimacy_score"] == 0.94
    assert queued_incident["review_model"] == "gpt-5.4-mini"
    assert queued_incident["suggested_severity_score"] == 3
    assert queued_incident["severity_confidence"] == 0.89
    assert queued_incident["severity_decision_source"] is None
    assert translation_client.calls == [
        (
            "OpenAI filing included fake legal citations",
            "Court records and reporting confirm the filing incident.",
        )
    ]


def test_reconcile_incident_review_batch_escalates_low_confidence_rows_before_editor_queue(  # noqa: E501
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
        incident["external_id"]: incident for incident in repository.incidents.values()
    }
    target_incident = incidents_by_external_id["inc-school-002"]
    batch_client.results_by_batch_id["batch-primary-1"] = [
        IncidentReviewResult(
            incident_id=target_incident["id"],
            verdict="approved",
            score=0.91,
            reasoning=(
                "Primary review found decent support but could not resolve the "
                "downstream impact level."
            ),
            source_quality_summary=(
                "Reporting confirms the incident but the scope of harm remains "
                "fuzzy."
            ),
            date_confirmed=True,
            company_confirmed=True,
            headline_en="School chatbot gave inaccurate enrollment guidance",
            reality_summary_en=(
                "Students received inaccurate enrollment guidance and staff had "
                "to correct the information manually."
            ),
            categories=["Autonomous Systems", "Made Up Category"],
            suggested_severity_score=3,
            severity_confidence=0.61,
            severity_reasoning=(
                "There was real operational impact, but source evidence does "
                "not clearly bound the scope."
            ),
            severity_flags=["unclear_real_world_impact"],
            needs_escalation=False,
            reviewed_model="gpt-5.4-mini",
        ),
    ]
    batch_client.escalation_results[target_incident["id"]] = IncidentReviewResult(
        incident_id=target_incident["id"],
        verdict="approved",
        score=0.95,
        reasoning=(
            "Escalation confirmed the incident and agreed that it requires "
            "editor review due to severity."
        ),
        source_quality_summary=(
            "Escalation confirmed the incident and clarified the source chronology."
        ),
        date_confirmed=True,
        company_confirmed=True,
        headline_en="School chatbot gave inaccurate enrollment guidance",
        reality_summary_en=(
            "Escalation confirmed the incident and the need for staff correction."
        ),
        categories=["Autonomous Systems", "Missed Timelines"],
        suggested_severity_score=3,
        severity_confidence=0.84,
        severity_reasoning=(
            "The incident caused meaningful operational harm requiring "
            "intervention, but not the kind of irreversible harm that merits "
            "Severity 4."
        ),
        severity_flags=[],
        needs_escalation=False,
        reviewed_model="gpt-5.2",
    )

    summary = reconcile_incident_review_batch(
        repository,
        batch_id="batch-primary-1",
        batch_client=batch_client,
        escalation_client=batch_client,
        translation_client=FakeTranslationClient(),
        embedding_client=FakeEmbeddingClient(),
        duplicate_judge_client=FakeDuplicateJudgeClient(),
        embedding_model="text-embedding-3-small",
        duplicate_judge_model="gpt-5.2",
        escalation_model="gpt-5.2",
    )

    assert summary.approved == 0
    assert summary.pending_review == 1
    assert summary.rejected == 0
    assert summary.escalated == 1
    assert target_incident["status"] == "pending_editor_review"
    assert target_incident["categories"] == [
        "Autonomous Systems",
        "Missed Timelines",
    ]
    assert target_incident["review_model"] == "gpt-5.2"
    assert target_incident["suggested_severity_score"] == 3
    assert target_incident["severity_decision_source"] is None


def test_reconcile_incident_review_batch_routes_second_phase_escalation_to_pending_editor_review(  # noqa: E501
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
        incident["external_id"]: incident for incident in repository.incidents.values()
    }
    target_incident = incidents_by_external_id["inc-school-002"]
    batch_client.results_by_batch_id["batch-primary-1"] = [
        IncidentReviewResult(
            incident_id=incidents_by_external_id["inc-openai-001"]["id"],
            verdict="rejected",
            score=0.1,
            reasoning="Not substantiated.",
            source_quality_summary="Weak evidence.",
            date_confirmed=True,
            company_confirmed=True,
            headline_en="Rejected",
            reality_summary_en="Rejected",
            categories=["Hallucinations"],
            suggested_severity_score=None,
            severity_confidence=None,
            severity_reasoning="Rejected",
            severity_flags=[],
            needs_escalation=False,
            reviewed_model="gpt-5.4-mini",
        ),
        IncidentReviewResult(
            incident_id=target_incident["id"],
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
        ),
    ]
    batch_client.escalation_results[target_incident["id"]] = IncidentReviewResult(
        incident_id=target_incident["id"],
        verdict="pending_review",
        score=0.69,
        reasoning="Escalation still cannot resolve the ambiguity.",
        source_quality_summary="Escalation found the event plausible but unresolved.",
        date_confirmed=False,
        company_confirmed=True,
        headline_en="School chatbot gave inaccurate enrollment guidance",
        reality_summary_en="Escalation still requires an editor to decide.",
        categories=["Autonomous Systems"],
        suggested_severity_score=3,
        severity_confidence=0.73,
        severity_reasoning="Human review still required.",
        severity_flags=[],
        needs_escalation=True,
        reviewed_model="gpt-5.2",
    )

    summary = reconcile_incident_review_batch(
        repository,
        batch_id="batch-primary-1",
        batch_client=batch_client,
        escalation_client=batch_client,
        translation_client=FakeTranslationClient(),
        embedding_client=FakeEmbeddingClient(),
        duplicate_judge_client=FakeDuplicateJudgeClient(),
        embedding_model="text-embedding-3-small",
        duplicate_judge_model="gpt-5.2",
        escalation_model="gpt-5.2",
    )

    assert summary.approved == 0
    assert summary.pending_review == 1
    assert summary.rejected == 1
    assert summary.escalated == 1
    assert target_incident["status"] == "pending_editor_review"
    assert target_incident["review_model"] == "gpt-5.2"
    assert target_incident["translation_status"] == "not_requested"


def test_reconcile_incident_review_batch_hides_confirmed_duplicates_and_skips_translation(  # noqa: E501
) -> None:
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
    batch_client = FakeBatchReviewClient()
    submit_incident_review_batch(
        repository,
        source_fetcher=FakeSourceFetcher(),
        batch_client=batch_client,
        primary_model="gpt-5.4-mini",
    )
    imported_incident = next(
        incident
        for incident in repository.incidents.values()
        if incident.get("external_id") == "inc-openai-001"
    )
    second_incident = next(
        incident
        for incident in repository.incidents.values()
        if incident.get("external_id") == "inc-school-002"
    )
    batch_client.results_by_batch_id["batch-primary-1"] = [
        IncidentReviewResult(
            incident_id=imported_incident["id"],
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
            incident_id=second_incident["id"],
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
    batch_client.escalation_results[second_incident["id"]] = IncidentReviewResult(
        incident_id=second_incident["id"],
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
        embedding_client=FakeEmbeddingClient(),
        duplicate_judge_client=FakeDuplicateJudgeClient(),
        embedding_model="text-embedding-3-small",
        duplicate_judge_model="gpt-5.2",
    )

    assert summary.approved == 0
    assert summary.pending_review == 1
    assert summary.rejected == 0
    assert imported_incident["status"] == "duplicate_confirmed"
    assert imported_incident["duplicate_of_incident_id"] == "incident-canonical"
    assert imported_incident["translation_status"] == "not_requested"
    assert repository.incidents["incident-canonical"]["sources"][-1]["source_url"] in {
        "https://example.com/court-order",
        "https://example.com/reuters-legal",
        "https://example.com/stanford-analysis",
    }
    assert translation_client.calls == []

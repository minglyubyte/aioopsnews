from __future__ import annotations

from dataclasses import dataclass

from app.services.incident_deduplication import (
    DuplicateJudgeDecision,
    OpenAIIncidentDuplicateJudgeClient,
    detect_and_merge_duplicate_incident,
)
from tests.support.fakes import InMemoryIncidentRepository


class FakeEmbeddingClient:
    def __init__(self, embeddings_by_text: dict[str, list[float]]) -> None:
        self.embeddings_by_text = embeddings_by_text

    def create_embedding(self, *, text: str, model: str) -> list[float]:
        return self.embeddings_by_text[text]


@dataclass
class FakeDuplicateJudgeClient:
    decision_by_pair: dict[tuple[str, str], DuplicateJudgeDecision]

    def judge_duplicate(
        self,
        *,
        incident: dict[str, object],
        candidate: dict[str, object],
        model: str,
    ) -> DuplicateJudgeDecision:
        return self.decision_by_pair[(incident["id"], candidate["id"])]


def test_detect_and_merge_duplicate_incident_records_top_three_embedding_candidates(
) -> None:
    repository = InMemoryIncidentRepository(
        incidents=[
            _build_incident(
                "incident-1",
                "OpenAI filing included fake legal citations",
                "2023-05-02",
                "OpenAI",
                "legal hallucination",
                status="pending_llm_review",
            ),
            _build_incident(
                "incident-2",
                "Federal court filing included fabricated citations",
                "2023-05-03",
                "OpenAI",
                "legal hallucination",
                status="approved",
            ),
            _build_incident(
                "incident-3",
                "Lawyer submitted hallucinated legal authorities",
                "2023-05-04",
                "OpenAI",
                "legal hallucination",
                status="approved",
            ),
            _build_incident(
                "incident-4",
                "False case citations appeared in a sanctions dispute",
                "2023-05-06",
                "OpenAI",
                "legal hallucination",
                status="approved",
            ),
            _build_incident(
                "incident-5",
                "Warehouse robot stalled after pathing failure",
                "2023-05-06",
                "RoboOps",
                "autonomous systems",
                status="approved",
            ),
        ]
    )
    embeddings = {
        _normalized_text(repository.incidents["incident-1"]): [1.0, 0.0],
        _normalized_text(repository.incidents["incident-2"]): [0.99, 0.01],
        _normalized_text(repository.incidents["incident-3"]): [0.97, 0.03],
        _normalized_text(repository.incidents["incident-4"]): [0.95, 0.05],
        _normalized_text(repository.incidents["incident-5"]): [0.0, 1.0],
    }
    decision_by_pair = {
        ("incident-1", "incident-2"): DuplicateJudgeDecision(
            is_duplicate=False,
            confidence=0.21,
            reasoning="Close topic but different filing details.",
            canonical_incident_id=None,
        ),
        ("incident-1", "incident-3"): DuplicateJudgeDecision(
            is_duplicate=False,
            confidence=0.18,
            reasoning="Close topic but different filing details.",
            canonical_incident_id=None,
        ),
        ("incident-1", "incident-4"): DuplicateJudgeDecision(
            is_duplicate=False,
            confidence=0.17,
            reasoning="Close topic but different filing details.",
            canonical_incident_id=None,
        ),
    }

    outcome = detect_and_merge_duplicate_incident(
        repository,
        incident_id="incident-1",
        embedding_client=FakeEmbeddingClient(embeddings),
        duplicate_judge_client=FakeDuplicateJudgeClient(decision_by_pair),
        embedding_model="text-embedding-3-small",
        duplicate_judge_model="deepseek-v4-pro",
        retrieval_limit=3,
    )

    assert outcome.is_duplicate is False
    candidate_ids = [
        candidate["candidate_incident_id"]
        for candidate in repository.duplicate_candidates["incident-1"]
    ]
    assert candidate_ids == ["incident-2", "incident-3", "incident-4"]


def test_detect_and_merge_duplicate_incident_absorbs_sources_and_notes_into_canonical(
) -> None:
    repository = InMemoryIncidentRepository(
        incidents=[
            _build_incident(
                "incident-10",
                "OpenAI filing included fake legal citations",
                "2023-05-02",
                "OpenAI",
                "legal hallucination",
                status="pending_llm_review",
                import_notes="Imported from curated batch.",
                source_urls=[
                    "https://example.com/new-source",
                    "https://example.com/shared-source",
                ],
            ),
            _build_incident(
                "incident-11",
                "Federal court filing included fabricated citations",
                "2023-05-03",
                "OpenAI",
                "legal hallucination",
                status="approved",
                import_notes="Canonical editorial note.",
                source_urls=[
                    "https://example.com/shared-source",
                    "https://example.com/canonical-source",
                ],
            ),
        ]
    )
    embeddings = {
        _normalized_text(repository.incidents["incident-10"]): [1.0, 0.0],
        _normalized_text(repository.incidents["incident-11"]): [0.99, 0.01],
    }
    decision_by_pair = {
        ("incident-10", "incident-11"): DuplicateJudgeDecision(
            is_duplicate=True,
            confidence=0.96,
            reasoning="Both records describe the same sanctions-related filing.",
            canonical_incident_id="incident-11",
        )
    }

    outcome = detect_and_merge_duplicate_incident(
        repository,
        incident_id="incident-10",
        embedding_client=FakeEmbeddingClient(embeddings),
        duplicate_judge_client=FakeDuplicateJudgeClient(decision_by_pair),
        embedding_model="text-embedding-3-small",
        duplicate_judge_model="deepseek-v4-pro",
        retrieval_limit=3,
    )

    assert outcome.is_duplicate is True
    assert outcome.canonical_incident_id == "incident-11"
    duplicate_incident = repository.incidents["incident-10"]
    canonical_incident = repository.incidents["incident-11"]

    assert duplicate_incident["status"] == "duplicate_confirmed"
    assert duplicate_incident["duplicate_status"] == "confirmed"
    assert duplicate_incident["duplicate_of_incident_id"] == "incident-11"
    assert canonical_incident["status"] == "approved"
    assert canonical_incident["headline"] == (
        "Federal court filing included fabricated citations"
    )
    assert canonical_incident["import_notes"] == (
        "Canonical editorial note.\n"
        "Merged duplicate incident-10: Imported from curated batch."
    )
    assert [source["source_url"] for source in canonical_incident["sources"]] == [
        "https://example.com/shared-source",
        "https://example.com/canonical-source",
        "https://example.com/new-source",
    ]


def test_duplicate_judge_client_accepts_qualitative_confidence(monkeypatch) -> None:
    class StubResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"is_duplicate":false,"confidence":"high",'
                                '"reasoning":"Likely distinct records."}'
                            )
                        }
                    }
                ]
            }

    monkeypatch.setattr(
        "app.services.incident_deduplication.httpx.post",
        lambda *args, **kwargs: StubResponse(),
    )
    client = OpenAIIncidentDuplicateJudgeClient(api_key="test-key")

    decision = client.judge_duplicate(
        incident=_build_incident(
            "incident-a",
            "AI enforcement action",
            "2026-01-01",
            "AgencyCo",
            "model governance",
            status="approved",
        ),
        candidate=_build_incident(
            "incident-b",
            "Different AI enforcement action",
            "2026-01-02",
            "AgencyCo",
            "model governance",
            status="approved",
        ),
        model="deepseek-test",
    )

    assert decision.is_duplicate is False
    assert decision.confidence == 0.9


def _build_incident(
    incident_id: str,
    headline: str,
    date_logged: str,
    company_involved: str,
    incident_topic: str,
    *,
    status: str,
    import_notes: str | None = None,
    source_urls: list[str] | None = None,
) -> dict[str, object]:
    urls = source_urls or [f"https://example.com/{incident_id}"]
    return {
        "id": incident_id,
        "external_id": incident_id,
        "headline": headline,
        "headline_en": headline,
        "headline_zh": None,
        "date_logged": date_logged,
        "company_involved": company_involved,
        "incident_topic": incident_topic,
        "claimant_name": None,
        "categories": [],
        "severity_score": 3,
        "reality_summary": headline,
        "reality_summary_en": headline,
        "reality_summary_zh": None,
        "status": status,
        "ingestion_run_id": None,
        "confidence_score": None,
        "review_notes": None,
        "matched_claim_id": None,
        "claim_match_confidence": None,
        "legitimacy_score": None,
        "legitimacy_label": None,
        "legitimacy_reasoning": None,
        "source_validation_summary": None,
        "legitimacy_flag": None,
        "confidence_level": None,
        "import_notes": import_notes,
        "translation_status": "not_requested",
        "review_batch_id": None,
        "review_model": None,
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
                "id": f"{incident_id}-source-{index}",
                "source_url": url,
                "canonical_url": None,
                "source_type": "imported",
                "publisher": None,
                "title": None,
                "fetch_status": None,
                "http_status": None,
                "evidence_text": None,
                "fetch_error": None,
                "is_primary": index == 0,
            }
            for index, url in enumerate(urls)
        ],
    }


def _normalized_text(incident: dict[str, object]) -> str:
    return "\n".join(
        [
            str(incident["company_involved"]),
            str(incident["incident_topic"]),
            str(incident["date_logged"]),
            str(incident["headline_en"]),
            str(incident["reality_summary_en"]),
        ]
    )

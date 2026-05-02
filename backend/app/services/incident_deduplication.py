from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.db.repository_protocol import IncidentRepository


@dataclass(frozen=True)
class DuplicateJudgeDecision:
    is_duplicate: bool
    confidence: float
    reasoning: str
    canonical_incident_id: str | None


@dataclass(frozen=True)
class DuplicateDetectionOutcome:
    is_duplicate: bool
    canonical_incident_id: str | None
    candidate_ids: list[str]


class IncidentEmbeddingClient(Protocol):
    def create_embedding(self, *, text: str, model: str) -> list[float]: ...


class IncidentDuplicateJudgeClient(Protocol):
    def judge_duplicate(
        self,
        *,
        incident: dict[str, Any],
        candidate: dict[str, Any],
        model: str,
    ) -> DuplicateJudgeDecision: ...


class OpenAIIncidentEmbeddingClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 60.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def create_embedding(self, *, text: str, model: str) -> list[float]:
        response = httpx.post(
            f"{self._base_url}/embeddings",
            headers=self._headers,
            json={"model": model, "input": text},
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        return [float(value) for value in payload["data"][0]["embedding"]]


class OpenAIIncidentDuplicateJudgeClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 60.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def judge_duplicate(
        self,
        *,
        incident: dict[str, Any],
        candidate: dict[str, Any],
        model: str,
    ) -> DuplicateJudgeDecision:
        response = httpx.post(
            f"{self._base_url}/chat/completions",
            headers=self._headers,
            json={
                "model": model,
                "response_format": {"type": "json_object"},
                "messages": _build_duplicate_judge_messages(
                    incident=incident,
                    candidate=candidate,
                ),
            },
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return DuplicateJudgeDecision(
            is_duplicate=bool(parsed["is_duplicate"]),
            confidence=float(parsed["confidence"]),
            reasoning=parsed["reasoning"],
            canonical_incident_id=parsed.get("canonical_incident_id"),
        )


CompatibleIncidentDuplicateJudgeClient = OpenAIIncidentDuplicateJudgeClient


def detect_and_merge_duplicate_incident(
    repository: IncidentRepository,
    *,
    incident_id: str,
    embedding_client: IncidentEmbeddingClient,
    duplicate_judge_client: IncidentDuplicateJudgeClient,
    embedding_model: str,
    duplicate_judge_model: str,
    retrieval_limit: int = 3,
    similarity_floor: float = 0.2,
    date_window_days: int = 30,
) -> DuplicateDetectionOutcome:
    incident = repository.get_incident(incident_id)
    if incident is None:
        raise ValueError(f"Incident {incident_id} was not found")

    incident_embedding = _ensure_incident_embedding(
        repository,
        incident=incident,
        embedding_client=embedding_client,
        embedding_model=embedding_model,
    )

    candidates = repository.list_duplicate_search_pool(
        incident_id=incident_id,
        date_logged=incident["date_logged"],
        date_window_days=date_window_days,
    )
    scored_candidates: list[tuple[float, dict[str, Any]]] = []
    for candidate in candidates:
        candidate_embedding = _ensure_incident_embedding(
            repository,
            incident=candidate,
            embedding_client=embedding_client,
            embedding_model=embedding_model,
        )
        similarity = _cosine_similarity(incident_embedding, candidate_embedding)
        if similarity < similarity_floor:
            continue
        scored_candidates.append((similarity, candidate))

    scored_candidates.sort(
        key=lambda item: (
            item[0],
            item[1]["date_logged"],
            item[1]["id"],
        ),
        reverse=True,
    )
    shortlisted = scored_candidates[:retrieval_limit]

    duplicate_candidates: list[dict[str, Any]] = []
    best_duplicate: DuplicateJudgeDecision | None = None
    best_duplicate_candidate_id: str | None = None
    for similarity, candidate in shortlisted:
        decision = duplicate_judge_client.judge_duplicate(
            incident=incident,
            candidate=candidate,
            model=duplicate_judge_model,
        )
        duplicate_candidates.append(
            {
                "candidate_incident_id": candidate["id"],
                "embedding_score": similarity,
                "llm_verdict": "duplicate" if decision.is_duplicate else "distinct",
                "confidence": decision.confidence,
                "reasoning": decision.reasoning,
                "status": "confirmed" if decision.is_duplicate else "dismissed",
            }
        )
        if decision.is_duplicate and (
            best_duplicate is None or decision.confidence > best_duplicate.confidence
        ):
            best_duplicate = decision
            best_duplicate_candidate_id = candidate["id"]

    repository.replace_duplicate_candidates(
        incident_id=incident_id,
        candidates=duplicate_candidates,
    )

    if best_duplicate is None:
        return DuplicateDetectionOutcome(
            is_duplicate=False,
            canonical_incident_id=None,
            candidate_ids=[
                candidate["candidate_incident_id"] for candidate in duplicate_candidates
            ],
        )

    canonical_incident_id = (
        best_duplicate.canonical_incident_id
        or best_duplicate_candidate_id
    )
    repository.merge_duplicate_incident(
        duplicate_incident_id=incident_id,
        canonical_incident_id=canonical_incident_id,
        duplicate_status="confirmed",
        reasoning=best_duplicate.reasoning,
        confidence=best_duplicate.confidence,
    )
    return DuplicateDetectionOutcome(
        is_duplicate=True,
        canonical_incident_id=canonical_incident_id,
        candidate_ids=[
            candidate["candidate_incident_id"] for candidate in duplicate_candidates
        ],
    )


def build_incident_embedding_text(incident: dict[str, Any]) -> str:
    return "\n".join(
        [
            str(incident["company_involved"]),
            str(incident.get("incident_topic")),
            str(incident["date_logged"]),
            str(incident.get("headline_en") or incident["headline"]),
            str(
                incident.get("reality_summary_en")
                or incident.get("reality_summary")
                or ""
            ),
        ]
    )


def _ensure_incident_embedding(
    repository: IncidentRepository,
    *,
    incident: dict[str, Any],
    embedding_client: IncidentEmbeddingClient,
    embedding_model: str,
) -> list[float]:
    existing_embedding = incident.get("embedding_vector")
    if isinstance(existing_embedding, list) and existing_embedding:
        return [float(value) for value in existing_embedding]

    embedding = embedding_client.create_embedding(
        text=build_incident_embedding_text(incident),
        model=embedding_model,
    )
    repository.update_incident_embedding(
        incident_id=incident["id"],
        embedding_model=embedding_model,
        embedding_vector=embedding,
    )
    incident["embedding_model"] = embedding_model
    incident["embedding_vector"] = embedding
    return embedding


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(
        left_value * right_value for left_value, right_value in zip(left, right)
    )
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _build_duplicate_judge_messages(
    *,
    incident: dict[str, Any],
    candidate: dict[str, Any],
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are deciding whether two AI incident records describe the same "
                "underlying real-world event. Return JSON only with keys: "
                "is_duplicate, confidence, reasoning, canonical_incident_id. "
                "Choose canonical_incident_id from one of the two provided ids."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "incident": _serialize_duplicate_judge_incident(incident),
                    "candidate": _serialize_duplicate_judge_incident(candidate),
                }
            ),
        },
    ]


def _serialize_duplicate_judge_incident(incident: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": incident["id"],
        "external_id": incident.get("external_id"),
        "company_involved": incident["company_involved"],
        "incident_topic": incident.get("incident_topic"),
        "date_logged": incident["date_logged"],
        "headline_en": incident.get("headline_en") or incident["headline"],
        "reality_summary_en": incident.get("reality_summary_en")
        or incident.get("reality_summary"),
        "import_notes": incident.get("import_notes"),
        "sources": [
            {
                "source_url": source["source_url"],
                "canonical_url": source.get("canonical_url"),
                "evidence_text": source.get("evidence_text"),
            }
            for source in incident.get("sources", [])
        ],
    }

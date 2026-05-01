from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx

from app.core.incident_taxonomy import (
    INCIDENT_CATEGORY_TAXONOMY,
    normalize_incident_categories,
)
from app.db.repository_protocol import IncidentRepository
from app.services.incident_deduplication import (
    IncidentDuplicateJudgeClient,
    IncidentEmbeddingClient,
    detect_and_merge_duplicate_incident,
)
from app.services.incident_translation import (
    IncidentTranslationClient,
    translate_incident_copy,
)

AUTO_APPROVAL_SEVERITY_THRESHOLD = 2
AUTO_APPROVAL_LEGITIMACY_THRESHOLD = 0.90
AUTO_APPROVAL_SEVERITY_CONFIDENCE_THRESHOLD = 0.85
ESCALATION_SEVERITY_CONFIDENCE_THRESHOLD = 0.75
HIGH_RISK_SEVERITY_FLAGS = {
    "safety",
    "privacy_breach",
    "legal_or_regulatory",
    "financial_harm",
    "core_system_outage",
    "unclear_real_world_impact",
}
QUALITATIVE_SEVERITY_CONFIDENCE_SCORES = {
    "very low": 0.1,
    "low": 0.25,
    "medium": 0.6,
    "moderate": 0.6,
    "high": 0.9,
    "very high": 0.98,
}


@dataclass(frozen=True)
class FetchedIncidentSource:
    source_url: str
    canonical_url: str | None
    fetch_status: str
    http_status: int | None
    evidence_text: str | None
    fetch_error: str | None = None


@dataclass(frozen=True)
class IncidentReviewBatchSubmission:
    batch_id: str
    submitted: int
    model: str


@dataclass(frozen=True)
class IncidentReviewResult:
    incident_id: str
    verdict: str
    score: float
    reasoning: str
    source_quality_summary: str
    date_confirmed: bool
    company_confirmed: bool
    headline_en: str
    reality_summary_en: str
    categories: list[str] | None = None
    suggested_severity_score: int | None = None
    severity_confidence: float | None = None
    severity_reasoning: str | None = None
    severity_flags: list[str] | None = None
    needs_escalation: bool = False
    reviewed_model: str = ""


@dataclass(frozen=True)
class IncidentReviewBatchReconciliation:
    approved: int
    pending_review: int
    rejected: int
    escalated: int


class IncidentSourceFetcher(Protocol):
    def fetch(self, source_url: str) -> FetchedIncidentSource: ...


class IncidentBatchReviewClient(Protocol):
    def get_batch_status(self, *, batch_id: str) -> str: ...

    def submit_batch(
        self,
        *,
        incidents: list[dict[str, Any]],
        model: str,
    ) -> IncidentReviewBatchSubmission: ...

    def get_batch_results(self, *, batch_id: str) -> list[IncidentReviewResult]: ...


class IncidentEscalationReviewClient(Protocol):
    def review_incident(
        self,
        *,
        incident: dict[str, Any],
        model: str,
    ) -> IncidentReviewResult: ...


class HttpIncidentSourceFetcher:
    def __init__(self, *, timeout_seconds: float = 15.0) -> None:
        self._timeout_seconds = timeout_seconds

    def fetch(self, source_url: str) -> FetchedIncidentSource:
        try:
            response = httpx.get(
                source_url,
                follow_redirects=True,
                timeout=self._timeout_seconds,
                headers={"User-Agent": "AIRealityCheckBot/1.0"},
            )
        except httpx.HTTPError as exc:
            return FetchedIncidentSource(
                source_url=source_url,
                canonical_url=None,
                fetch_status="failed",
                http_status=None,
                evidence_text=None,
                fetch_error=str(exc),
            )

        evidence_text = _extract_evidence_text(response.text)
        fetch_status = "fetched" if response.is_success else "failed"
        return FetchedIncidentSource(
            source_url=source_url,
            canonical_url=str(response.url),
            fetch_status=fetch_status,
            http_status=response.status_code,
            evidence_text=evidence_text if response.is_success else None,
            fetch_error=None if response.is_success else response.reason_phrase,
        )


class OpenAIIncidentReviewClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 60.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._headers = {"Authorization": f"Bearer {api_key}"}

    def submit_batch(
        self,
        *,
        incidents: list[dict[str, Any]],
        model: str,
    ) -> IncidentReviewBatchSubmission:
        jsonl_body = "\n".join(
            json.dumps(
                {
                    "custom_id": incident["id"],
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": model,
                        "response_format": _build_review_response_format(),
                        "messages": _build_review_messages(incident),
                    },
                }
            )
            for incident in incidents
        )
        input_file_id = self._upload_batch_file(jsonl_body)
        batch = self._post_json(
            "/batches",
            {
                "input_file_id": input_file_id,
                "endpoint": "/v1/chat/completions",
                "completion_window": "24h",
                "metadata": {
                    "purpose": "incident_review",
                    "incident_count": str(len(incidents)),
                },
            },
        )
        return IncidentReviewBatchSubmission(
            batch_id=batch["id"],
            submitted=len(incidents),
            model=model,
        )

    def get_batch_results(self, *, batch_id: str) -> list[IncidentReviewResult]:
        batch = self._get_json(f"/batches/{batch_id}")
        if batch["status"] != "completed":
            raise RuntimeError(
                f"Batch {batch_id} is not complete yet; current status is "
                f"{batch['status']}"
            )
        output_file_id = batch.get("output_file_id")
        if not output_file_id:
            raise RuntimeError(f"Batch {batch_id} completed without output_file_id")

        response = httpx.get(
            f"{self._base_url}/files/{output_file_id}/content",
            headers=self._headers,
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        results: list[IncidentReviewResult] = []
        for raw_line in response.text.splitlines():
            if not raw_line.strip():
                continue
            payload = json.loads(raw_line)
            if payload.get("error") is not None:
                continue
            body = payload["response"]["body"]
            content = body["choices"][0]["message"]["content"]
            results.append(
                _parse_review_result(
                    incident_id=payload["custom_id"],
                    model=body["model"],
                    content=content,
                )
            )
        return results

    def get_batch_status(self, *, batch_id: str) -> str:
        batch = self._get_json(f"/batches/{batch_id}")
        return str(batch["status"])

    def review_incident(
        self,
        *,
        incident: dict[str, Any],
        model: str,
    ) -> IncidentReviewResult:
        payload = self._post_json(
            "/chat/completions",
            {
                "model": model,
                "response_format": _build_review_response_format(),
                "messages": _build_review_messages(incident),
            },
        )
        return _parse_review_result(
            incident_id=incident["id"],
            model=payload["model"],
            content=payload["choices"][0]["message"]["content"],
        )

    def _upload_batch_file(self, jsonl_body: str) -> str:
        response = httpx.post(
            f"{self._base_url}/files",
            headers=self._headers,
            files={
                "purpose": (None, "batch"),
                "file": (
                    "incident-review-batch.jsonl",
                    jsonl_body,
                    "application/jsonl",
                ),
            },
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        return response.json()["id"]

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = httpx.post(
            f"{self._base_url}{path}",
            headers={**self._headers, "Content-Type": "application/json"},
            json=payload,
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def _get_json(self, path: str) -> dict[str, Any]:
        response = httpx.get(
            f"{self._base_url}{path}",
            headers=self._headers,
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        return response.json()


def submit_incident_review_batch(
    repository: IncidentRepository,
    *,
    source_fetcher: IncidentSourceFetcher,
    batch_client: IncidentBatchReviewClient,
    primary_model: str,
) -> IncidentReviewBatchSubmission:
    incidents = [
        incident
        for incident in repository.list_incidents_pending_llm_review()
        if not incident.get("review_batch_id")
    ]
    for incident in incidents:
        for source in incident.get("sources", []):
            fetched = source_fetcher.fetch(source["source_url"])
            repository.update_incident_source_evidence(
                source_id=source["id"],
                canonical_url=fetched.canonical_url,
                fetch_status=fetched.fetch_status,
                http_status=fetched.http_status,
                evidence_text=fetched.evidence_text,
                fetch_error=fetched.fetch_error,
                fetched_at=_now_isoformat(),
            )

    refreshed_incidents = [
        incident
        for incident in repository.list_incidents_pending_llm_review()
        if not incident.get("review_batch_id")
    ]
    provider_submission = batch_client.submit_batch(
        incidents=refreshed_incidents,
        model=primary_model,
    )
    submission = IncidentReviewBatchSubmission(
        batch_id=provider_submission.batch_id,
        submitted=(
            provider_submission.submitted
            if hasattr(provider_submission, "submitted")
            else provider_submission.request_count
        ),
        model=provider_submission.model,
    )
    repository.mark_incidents_review_batch(
        incident_ids=[incident["id"] for incident in refreshed_incidents],
        review_batch_id=submission.batch_id,
        review_model=primary_model,
    )
    return submission


def reconcile_incident_review_batch(
    repository: IncidentRepository,
    *,
    batch_id: str,
    batch_client: IncidentBatchReviewClient,
    escalation_client: IncidentEscalationReviewClient,
    translation_client: IncidentTranslationClient,
    embedding_client: IncidentEmbeddingClient,
    duplicate_judge_client: IncidentDuplicateJudgeClient,
    embedding_model: str,
    duplicate_judge_model: str,
    escalation_model: str,
    approval_threshold: float = AUTO_APPROVAL_LEGITIMACY_THRESHOLD,
) -> IncidentReviewBatchReconciliation:
    incidents_by_id = {
        incident["id"]: incident
        for incident in repository.list_incidents_pending_llm_review()
    }
    approved = 0
    pending_review = 0
    rejected = 0
    escalated = 0

    for result in batch_client.get_batch_results(batch_id=batch_id):
        incident = incidents_by_id.get(result.incident_id)
        if incident is None:
            continue

        normalized_result = _normalize_review_result(result, incident=incident)
        final_result = normalized_result
        if _should_escalate(normalized_result, approval_threshold=approval_threshold):
            final_result = escalation_client.review_incident(
                incident=incident,
                model=escalation_model,
            )
            final_result = _normalize_review_result(final_result, incident=incident)
            escalated += 1

        final_status = _resolve_final_status(
            final_result,
            approval_threshold=approval_threshold,
        )
        final_severity_score = (
            final_result.suggested_severity_score
            if final_status == "approved"
            and final_result.suggested_severity_score is not None
            else incident.get("severity_score")
        )
        severity_decision_source = (
            "escalation_llm"
            if final_status == "approved"
            and final_result.reviewed_model == escalation_model
            and final_result.suggested_severity_score is not None
            else "primary_llm"
            if final_status == "approved"
            and final_result.suggested_severity_score is not None
            else None
        )
        repository.apply_incident_review_result(
            incident_id=incident["id"],
            status=final_status,
            legitimacy_score=final_result.score,
            legitimacy_label=final_result.verdict,
            legitimacy_reasoning=final_result.reasoning,
            source_validation_summary=final_result.source_quality_summary,
            headline_en=final_result.headline_en,
            reality_summary_en=final_result.reality_summary_en,
            categories=final_result.categories or list(incident.get("categories", [])),
            severity_score=final_severity_score,
            suggested_severity_score=final_result.suggested_severity_score,
            severity_confidence=final_result.severity_confidence,
            severity_reasoning=final_result.severity_reasoning,
            severity_flags=final_result.severity_flags or [],
            severity_model=final_result.reviewed_model,
            severity_decision_source=severity_decision_source,
            severity_suggested_at=_now_isoformat(),
            review_model=final_result.reviewed_model,
            review_batch_id=batch_id,
            reviewed_at=_now_isoformat(),
        )
        incident.update(
            {
                "status": final_status,
                "headline_en": final_result.headline_en,
                "reality_summary_en": final_result.reality_summary_en,
                "categories": final_result.categories or list(incident.get("categories", [])),
                "legitimacy_score": final_result.score,
                "legitimacy_label": final_result.verdict,
                "legitimacy_reasoning": final_result.reasoning,
                "source_validation_summary": final_result.source_quality_summary,
                "severity_score": final_severity_score,
                "suggested_severity_score": final_result.suggested_severity_score,
                "severity_confidence": final_result.severity_confidence,
                "severity_reasoning": final_result.severity_reasoning,
                "severity_flags": final_result.severity_flags or [],
                "severity_model": final_result.reviewed_model,
                "severity_decision_source": severity_decision_source,
                "review_model": final_result.reviewed_model,
            }
        )

        if final_status == "approved":
            duplicate_outcome = detect_and_merge_duplicate_incident(
                repository,
                incident_id=incident["id"],
                embedding_client=embedding_client,
                duplicate_judge_client=duplicate_judge_client,
                embedding_model=embedding_model,
                duplicate_judge_model=duplicate_judge_model,
            )
            if duplicate_outcome.is_duplicate:
                incident["status"] = "duplicate_confirmed"
                incident["duplicate_of_incident_id"] = (
                    duplicate_outcome.canonical_incident_id
                )
                incident["translation_status"] = "not_requested"
                continue

            translation = translate_incident_copy(
                headline_en=final_result.headline_en,
                reality_summary_en=final_result.reality_summary_en,
                client=translation_client,
            )
            repository.update_incident_translation(
                incident_id=incident["id"],
                headline_zh=translation.headline_zh,
                reality_summary_zh=translation.reality_summary_zh,
                translation_status=translation.status,
                translated_at=_now_isoformat(),
            )
            incident["translation_status"] = translation.status
            incident["headline_zh"] = translation.headline_zh
            incident["reality_summary_zh"] = translation.reality_summary_zh
            approved += 1
        elif final_status == "rejected":
            rejected += 1
        else:
            pending_review += 1

    return IncidentReviewBatchReconciliation(
        approved=approved,
        pending_review=pending_review,
        rejected=rejected,
        escalated=escalated,
    )


def _should_escalate(
    result: IncidentReviewResult,
    *,
    approval_threshold: float,
) -> bool:
    if result.needs_escalation:
        return True
    if (not result.date_confirmed) or (not result.company_confirmed):
        return True
    if result.severity_confidence is not None and (
        result.severity_confidence < ESCALATION_SEVERITY_CONFIDENCE_THRESHOLD
    ):
        return True
    if result.verdict == "approved":
        return result.score < approval_threshold
    return result.verdict not in {"rejected", "pending_review"}


def _resolve_final_status(
    result: IncidentReviewResult,
    *,
    approval_threshold: float,
) -> str:
    if result.verdict == "rejected":
        return "rejected"
    if _can_auto_approve(result, approval_threshold=approval_threshold):
        return "approved"
    if _requires_editor_review(result):
        return "pending_editor_review"
    return "pending_review"


def _build_review_messages(incident: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are an editorial reviewer for an AI incident database. "
                "Return JSON only with keys: verdict, score, reasoning, "
                "source_quality_summary, date_confirmed, company_confirmed, "
                "headline_en, reality_summary_en, categories, suggested_severity_score, "
                "severity_confidence, severity_reasoning, severity_flags. "
                "Return severity_confidence as a number between 0 and 1, "
                "not a word or label. Choose one or more categories from the "
                "approved taxonomy only. "
                "Use this impact-first severity rubric: 1=minor, quickly "
                "reversible, no meaningful external harm; 2=real but limited "
                "impact, localized and reversible; 3=clear operational or "
                "business impact requiring rollback or manual intervention; "
                "4=major real-world or sensitive-domain harm involving privacy, "
                "legal, regulatory, financial, or broad safety consequences; "
                "5=catastrophic irreversible harm or major systemic safety "
                "failure. Safety-critical incidents start at 4 unless clearly "
                "minor. Serious injury or death is 5. Broad privacy breach, "
                "major legal or regulatory action, or major financial harm is "
                "at least 4. Near misses in safety-critical systems may raise "
                "severity by one level, but do not replace actual harm."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "incident_id": incident["id"],
                    "external_id": incident.get("external_id"),
                        "company": incident["company_involved"],
                        "incident_topic": incident.get("incident_topic"),
                        "approved_categories": list(INCIDENT_CATEGORY_TAXONOMY),
                        "incident_date": incident["date_logged"],
                        "headline": incident["headline"],
                        "reality_summary": incident["reality_summary"],
                    "editorial_input": {
                        "legitimacy_flag": incident.get("legitimacy_flag"),
                        "confidence_level": incident.get("confidence_level"),
                        "import_notes": incident.get("import_notes"),
                    },
                    "sources": [
                        {
                            "source_url": source["source_url"],
                            "canonical_url": source.get("canonical_url"),
                            "fetch_status": source.get("fetch_status"),
                            "http_status": source.get("http_status"),
                            "evidence_text": source.get("evidence_text"),
                        }
                        for source in incident.get("sources", [])
                    ],
                }
            ),
        },
    ]


def _build_review_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "incident_review_result",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "verdict": {
                        "type": "string",
                        "enum": ["approved", "rejected", "pending_review"],
                    },
                    "score": {"type": "number", "minimum": 0, "maximum": 1},
                    "reasoning": {"type": "string"},
                    "source_quality_summary": {"type": "string"},
                    "date_confirmed": {"type": "boolean"},
                    "company_confirmed": {"type": "boolean"},
                    "headline_en": {"type": "string"},
                    "reality_summary_en": {"type": "string"},
                    "categories": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "string",
                            "enum": list(INCIDENT_CATEGORY_TAXONOMY),
                        },
                    },
                    "suggested_severity_score": {
                        "type": ["integer", "null"],
                        "minimum": 1,
                        "maximum": 5,
                    },
                    "severity_confidence": {
                        "type": ["number", "null"],
                        "minimum": 0,
                        "maximum": 1,
                    },
                    "severity_reasoning": {"type": ["string", "null"]},
                    "severity_flags": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "verdict",
                    "score",
                    "reasoning",
                    "source_quality_summary",
                    "date_confirmed",
                    "company_confirmed",
                    "headline_en",
                    "reality_summary_en",
                    "categories",
                    "suggested_severity_score",
                    "severity_confidence",
                    "severity_reasoning",
                    "severity_flags",
                ],
            },
        },
    }


def _parse_review_result(
    *,
    incident_id: str,
    model: str,
    content: str,
) -> IncidentReviewResult:
    payload = json.loads(content)
    categories, invalid_categories = _parse_review_categories(payload.get("categories"))
    severity_confidence, invalid_severity_confidence = (
        _parse_optional_severity_confidence(payload.get("severity_confidence"))
    )
    return IncidentReviewResult(
        incident_id=incident_id,
        verdict=payload["verdict"],
        score=float(payload["score"]),
        reasoning=payload["reasoning"],
        source_quality_summary=payload["source_quality_summary"],
        date_confirmed=bool(payload["date_confirmed"]),
        company_confirmed=bool(payload["company_confirmed"]),
        headline_en=payload["headline_en"],
        reality_summary_en=payload["reality_summary_en"],
        categories=categories,
        suggested_severity_score=(
            int(payload["suggested_severity_score"])
            if payload.get("suggested_severity_score") is not None
            else None
        ),
        severity_confidence=severity_confidence,
        severity_reasoning=payload.get("severity_reasoning"),
        severity_flags=[
            str(flag) for flag in payload.get("severity_flags", []) if str(flag)
        ],
        needs_escalation=(
            bool(payload.get("needs_escalation", False))
            or invalid_categories
            or invalid_severity_confidence
        ),
        reviewed_model=model,
    )


def _parse_review_categories(value: Any) -> tuple[list[str] | None, bool]:
    if not isinstance(value, list):
        return None, True
    categories = normalize_incident_categories(
        [str(category) for category in value if isinstance(category, str)]
    )
    if len(categories) != len(value) or not categories:
        return None, True
    return categories, False


def _parse_optional_severity_confidence(value: Any) -> tuple[float | None, bool]:
    if value is None:
        return None, False
    if isinstance(value, bool):
        return None, True
    if isinstance(value, (int, float)):
        return _normalize_confidence_number(float(value))
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None, False
        normalized = raw.lower().replace("_", " ").replace("-", " ")
        if normalized in QUALITATIVE_SEVERITY_CONFIDENCE_SCORES:
            return QUALITATIVE_SEVERITY_CONFIDENCE_SCORES[normalized], False
        if raw.endswith("%"):
            try:
                return _normalize_confidence_number(float(raw[:-1]) / 100.0)
            except ValueError:
                return None, True
        try:
            return _normalize_confidence_number(float(raw))
        except ValueError:
            return None, True
    return None, True


def _normalize_confidence_number(value: float) -> tuple[float | None, bool]:
    if 0.0 <= value <= 1.0:
        return value, False
    if 1.0 < value <= 100.0:
        return value / 100.0, False
    return None, True


def _normalize_review_result(
    result: IncidentReviewResult,
    *,
    incident: dict[str, Any],
) -> IncidentReviewResult:
    fallback_severity = incident.get("suggested_severity_score")
    fallback_categories = list(incident.get("categories", []))
    return IncidentReviewResult(
        incident_id=result.incident_id,
        verdict=result.verdict,
        score=result.score,
        reasoning=result.reasoning,
        source_quality_summary=result.source_quality_summary,
        date_confirmed=result.date_confirmed,
        company_confirmed=result.company_confirmed,
        headline_en=result.headline_en,
        reality_summary_en=result.reality_summary_en,
        categories=result.categories or fallback_categories,
        suggested_severity_score=result.suggested_severity_score or fallback_severity,
        severity_confidence=result.severity_confidence,
        severity_reasoning=result.severity_reasoning,
        severity_flags=list(result.severity_flags or []),
        needs_escalation=result.needs_escalation,
        reviewed_model=result.reviewed_model,
    )


def _can_auto_approve(
    result: IncidentReviewResult,
    *,
    approval_threshold: float,
) -> bool:
    if result.verdict != "approved":
        return False
    if result.score < approval_threshold:
        return False
    if result.suggested_severity_score is None:
        return result.date_confirmed and result.company_confirmed
    if result.suggested_severity_score > AUTO_APPROVAL_SEVERITY_THRESHOLD:
        return False
    if result.severity_confidence is None:
        return False
    if result.severity_confidence < AUTO_APPROVAL_SEVERITY_CONFIDENCE_THRESHOLD:
        return False
    if (not result.date_confirmed) or (not result.company_confirmed):
        return False
    return not any(flag in HIGH_RISK_SEVERITY_FLAGS for flag in result.severity_flags or [])


def _requires_editor_review(result: IncidentReviewResult) -> bool:
    if result.suggested_severity_score is None:
        return False
    if result.suggested_severity_score is not None and result.suggested_severity_score >= 3:
        return True
    return any(flag in HIGH_RISK_SEVERITY_FLAGS for flag in result.severity_flags or [])


def _extract_evidence_text(html: str) -> str:
    text = html.replace("\x00", " ").replace("\r", " ").replace("\n", " ")
    collapsed = " ".join(text.split())
    return collapsed[:4000]


def _now_isoformat() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()

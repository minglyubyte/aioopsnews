from __future__ import annotations

from fastapi.testclient import TestClient

from app.app_factory import create_app
from tests.support.fakes import InMemoryIncidentRepository

FUTURESTACK_CLAIM = "Our copilots will eliminate tier-one support queues."


def _build_repository() -> InMemoryIncidentRepository:
    return InMemoryIncidentRepository(
        claims=[
            {
                "id": "claim-1",
                "claimant_name": "FutureStack",
                "company_involved": "FutureStack",
                "original_claim": FUTURESTACK_CLAIM,
                "claim_date": "2026-01-10",
                "claim_topic": "job automation",
                "status": "approved",
                "notes": "Imported from launch blog.",
            }
        ],
        incidents=[
            {
                "id": "incident-4",
                "headline": "May escalation shows archive filters can narrow results",
                "headline_en": (
                    "May escalation shows archive filters can narrow results"
                ),
                "headline_zh": None,
                "date_logged": "2026-05-03",
                "company_involved": "MayOps",
                "incident_topic": "model governance",
                "claimant_name": "MayOps",
                "categories": ["Model Governance"],
                "severity_score": 2,
                "reality_summary": (
                    "A separate approved May incident supports archive "
                    "filtering coverage."
                ),
                "reality_summary_en": (
                    "A separate approved May incident supports archive "
                    "filtering coverage."
                ),
                "reality_summary_zh": None,
                "status": "approved",
                "translation_status": "not_requested",
                "publication_track": "accident_watch",
                "evidence_tier": "developing",
                "source_family": "model_governance",
                "verification_summary": (
                    "Legacy-style watch item awaiting evidence classification."
                ),
                "matched_claim_id": None,
                "claim_match_confidence": None,
                "review_notes": "editor reviewed",
                "sources": [],
            },
            {
                "id": "incident-1",
                "headline": "Database-backed feed shows a reviewed privacy incident",
                "headline_en": "Database-backed feed shows a reviewed privacy incident",
                "headline_zh": "数据库支持的隐私事件已完成审核",
                "date_logged": "2026-04-30",
                "company_involved": "FutureStack",
                "company_involved_zh": "未来栈",
                "incident_topic": "privacy",
                "claimant_name": "FutureStack",
                "categories": ["Privacy/Security"],
                "severity_score": 4,
                "reality_summary": (
                    "A reviewed database record leaked internal notes into replies."
                ),
                "reality_summary_en": (
                    "A reviewed database record leaked internal notes into replies."
                ),
                "reality_summary_zh": "经审核的数据库记录将内部备注泄露到回复中。",
                "incident_summary_en": (
                    "A customer-support automation release exposed internal billing "
                    "notes in live replies."
                ),
                "incident_summary_zh": "一次客户支持自动化发布在实时回复中暴露了内部账单备注。",
                "what_happened_en": (
                    "The rollout surfaced internal account notes directly in "
                    "customer-facing assistant messages."
                ),
                "what_happened_zh": "这次发布让内部账户备注直接出现在面向客户的助手消息中。",
                "ai_failure_point_en": (
                    "The assistant failed to separate private support context from "
                    "reply-generation context."
                ),
                "ai_failure_point_zh": "该助手未能将私密支持上下文与回复生成上下文隔离开。",
                "status": "approved",
                "translation_status": "completed",
                "publication_track": "accident_watch",
                "evidence_tier": "reported_unconfirmed",
                "source_family": "customer_support",
                "verification_summary": (
                    "Reporting describes the privacy leak; no regulator notice is "
                    "linked yet."
                ),
                "matched_claim_id": "claim-1",
                "claim_match_confidence": 0.88,
                "review_notes": "editor reviewed",
                "legitimacy_reasoning": (
                    "The failure matters because internal account data appeared in "
                    "customer-facing replies."
                ),
                "legitimacy_reasoning_zh": "问题之所以重要，是因为内部账户数据出现在面向客户的回复中。",
                "source_validation_summary": (
                    "Validated with a primary report and supporting publication."
                ),
                "source_validation_summary_zh": "已通过一手报告和补充报道完成核实。",
                "sources": [
                    {
                        "id": "source-1",
                        "source_url": "https://example.com/privacy",
                        "source_type": "primary",
                        "source_origin": "search_discovery",
                        "source_registry_key": "google_search",
                        "raw_source_payload": {
                            "query": "AI support bot privacy leak"
                        },
                        "publisher": "Example News",
                        "title": (
                            "Database-backed feed shows a reviewed privacy incident"
                        ),
                    }
                ],
            },
            {
                "id": "incident-2",
                "headline": "Warehouse robot rollback follows navigation failures",
                "headline_en": "Warehouse robot rollback follows navigation failures",
                "headline_zh": None,
                "date_logged": "2026-04-24",
                "company_involved": "RoboOps",
                "incident_topic": "autonomous systems",
                "claimant_name": "RoboOps",
                "categories": ["Autonomous Systems"],
                "severity_score": 3,
                "reality_summary": (
                    "Operators paused a pilot after repeated pathing failures."
                ),
                "reality_summary_en": (
                    "Operators paused a pilot after repeated pathing failures."
                ),
                "reality_summary_zh": None,
                "status": "approved",
                "translation_status": "not_requested",
                "publication_track": "verified_accident",
                "evidence_tier": "official_documented",
                "source_family": "autonomous_vehicle",
                "verification_summary": (
                    "A fixed verified source documents the operational rollback."
                ),
                "matched_claim_id": None,
                "claim_match_confidence": None,
                "review_notes": "editor reviewed",
                "legitimacy_reasoning": (
                    "The rollback highlights the operational limits of the pilot."
                ),
                "source_validation_summary": (
                    "Validated with city coverage of the paused deployment."
                ),
                "sources": [
                    {
                        "id": "source-2",
                        "source_url": "https://example.com/robotics",
                        "source_type": "primary",
                        "source_origin": "fixed_verified_source",
                        "source_registry_key": "ca_dmv_av_collisions",
                        "raw_source_payload": {
                            "report_number": "OL-316-robotics"
                        },
                        "publisher": "City Ledger",
                        "title": "Warehouse robot rollback follows navigation failures",
                    }
                ],
            },
            {
                "id": "incident-5",
                "headline": (
                    "Prior-year incident proves year archives can narrow results"
                ),
                "headline_en": (
                    "Prior-year incident proves year archives can narrow results"
                ),
                "headline_zh": None,
                "date_logged": "2025-12-18",
                "company_involved": "ArchiveAI",
                "incident_topic": "model governance",
                "claimant_name": "ArchiveAI",
                "categories": ["Model Governance"],
                "severity_score": 2,
                "reality_summary": (
                    "An older approved incident should only appear for matching "
                    "archive years."
                ),
                "reality_summary_en": (
                    "An older approved incident should only appear for matching "
                    "archive years."
                ),
                "reality_summary_zh": None,
                "status": "approved",
                "translation_status": "not_requested",
                "publication_track": "accident_watch",
                "evidence_tier": "reported_unconfirmed",
                "source_family": "model_governance",
                "verification_summary": "Older imported item with watch-level evidence.",
                "matched_claim_id": None,
                "claim_match_confidence": None,
                "review_notes": "editor reviewed",
                "sources": [],
            },
            {
                "id": "incident-3",
                "headline": "Draft incident should not be public",
                "headline_en": "Draft incident should not be public",
                "headline_zh": None,
                "date_logged": "2026-04-20",
                "company_involved": "HiddenCo",
                "incident_topic": "missed timelines",
                "claimant_name": "HiddenCo",
                "categories": ["Missed Timelines"],
                "severity_score": 2,
                "reality_summary": "Draft only.",
                "reality_summary_en": "Draft only.",
                "reality_summary_zh": None,
                "status": "pending_review",
                "translation_status": "not_requested",
                "matched_claim_id": None,
                "claim_match_confidence": None,
                "review_notes": "awaiting editor",
                "sources": [],
            },
        ],
    )


def test_get_incidents_reads_from_repository_records() -> None:
    repository = _build_repository()
    client = TestClient(create_app(incident_repository=repository))

    response = client.get("/incidents")

    assert response.status_code == 200
    payload = response.json()
    assert [item["headline"] for item in payload["items"]] == [
        "May escalation shows archive filters can narrow results",
        "Database-backed feed shows a reviewed privacy incident",
        "Warehouse robot rollback follows navigation failures",
        "Prior-year incident proves year archives can narrow results",
    ]
    assert payload["items"][1]["headline_en"] == (
        "Database-backed feed shows a reviewed privacy incident"
    )
    assert payload["items"][1]["headline_zh"] == "数据库支持的隐私事件已完成审核"
    assert payload["items"][1]["company_involved_zh"] == "未来栈"
    assert payload["items"][1]["archive_summary"] == (
        "A reviewed database record leaked internal notes into replies."
    )
    assert payload["items"][1]["translation_status"] == "completed"
    assert payload["items"][1]["publication_track"] == "accident_watch"
    assert payload["items"][1]["evidence_tier"] == "reported_unconfirmed"
    assert payload["items"][1]["source_family"] == "customer_support"
    assert payload["items"][1]["verification_summary"] == (
        "Reporting describes the privacy leak; no regulator notice is linked yet."
    )
    assert payload["page"] == 1
    assert payload["page_size"] == 20
    assert payload["total_count"] == 4
    assert payload["total_pages"] == 1
    assert payload["has_next_page"] is False
    assert payload["has_previous_page"] is False
    assert payload["slice_summary"] == {
        "total_matches": 4,
        "newest_logged": "2026-05-03",
        "oldest_logged": "2025-12-18",
        "highest_severity": 4,
        "top_categories": [
            {"category": "Model Governance", "count": 2},
            {"category": "Autonomous Systems", "count": 1},
            {"category": "Privacy/Security", "count": 1},
        ],
        "top_companies": [
            {"company": "ArchiveAI", "company_zh": None, "count": 1},
            {"company": "FutureStack", "company_zh": "未来栈", "count": 1},
            {"company": "MayOps", "company_zh": None, "count": 1},
            {"company": "RoboOps", "company_zh": None, "count": 1},
        ],
    }
    assert "matched_claim" not in payload["items"][1]
    assert "sources" not in payload["items"][1]
    assert "reality_summary" not in payload["items"][1]
    assert "analysis" not in payload["items"][1]


def test_get_incidents_supports_filters_and_pagination() -> None:
    repository = _build_repository()
    client = TestClient(create_app(incident_repository=repository))

    filtered_response = client.get(
        "/incidents",
        params={
            "category": "Privacy/Security",
            "company": "FutureStack",
            "claimant": "FutureStack",
            "severity_min": 4,
            "severity_max": 5,
        },
    )
    paged_response = client.get("/incidents", params={"page": 2, "page_size": 1})

    assert filtered_response.status_code == 200
    assert [item["headline"] for item in filtered_response.json()["items"]] == [
        "Database-backed feed shows a reviewed privacy incident",
    ]
    assert paged_response.status_code == 200
    paged_payload = paged_response.json()
    assert [item["headline"] for item in paged_payload["items"]] == [
        "Database-backed feed shows a reviewed privacy incident",
    ]
    assert paged_payload["page"] == 2
    assert paged_payload["page_size"] == 1
    assert paged_payload["total_count"] == 4
    assert paged_payload["total_pages"] == 4
    assert paged_payload["has_next_page"] is True
    assert paged_payload["has_previous_page"] is True


def test_get_incidents_supports_publication_track_and_source_family_filters() -> None:
    repository = _build_repository()
    client = TestClient(create_app(incident_repository=repository))

    verified_response = client.get(
        "/incidents",
        params={
            "publication_track": "verified_accident",
            "source_family": "autonomous_vehicle",
        },
    )
    watch_response = client.get(
        "/incidents",
        params={
            "publication_track": "accident_watch",
            "source_family": "customer_support",
        },
    )

    assert verified_response.status_code == 200
    assert [item["headline"] for item in verified_response.json()["items"]] == [
        "Warehouse robot rollback follows navigation failures",
    ]
    assert watch_response.status_code == 200
    assert [item["headline"] for item in watch_response.json()["items"]] == [
        "Database-backed feed shows a reviewed privacy incident",
    ]


def test_get_incidents_supports_year_and_month_archives() -> None:
    repository = _build_repository()
    client = TestClient(create_app(incident_repository=repository))

    yearly_response = client.get("/incidents", params={"year": 2026})
    monthly_response = client.get("/incidents", params={"year": 2026, "month": 4})
    category_archive_response = client.get(
        "/incidents",
        params={"year": 2026, "month": 4, "category": "Privacy/Security"},
    )

    assert [item["headline"] for item in yearly_response.json()["items"]] == [
        "May escalation shows archive filters can narrow results",
        "Database-backed feed shows a reviewed privacy incident",
        "Warehouse robot rollback follows navigation failures",
    ]
    assert [item["headline"] for item in monthly_response.json()["items"]] == [
        "Database-backed feed shows a reviewed privacy incident",
        "Warehouse robot rollback follows navigation failures",
    ]
    assert [item["headline"] for item in category_archive_response.json()["items"]] == [
        "Database-backed feed shows a reviewed privacy incident",
    ]


def test_get_incidents_rejects_month_without_year_or_invalid_month() -> None:
    repository = _build_repository()
    client = TestClient(create_app(incident_repository=repository))

    assert client.get("/incidents", params={"month": 4}).status_code == 422
    assert (
        client.get("/incidents", params={"year": 2026, "month": 13}).status_code == 422
    )


def test_get_incident_detail_returns_public_record_with_analysis_and_sources() -> None:
    repository = _build_repository()
    client = TestClient(create_app(incident_repository=repository))

    detail_response = client.get("/incidents/incident-1")
    hidden_response = client.get("/incidents/incident-3")

    assert detail_response.status_code == 200
    assert detail_response.json()["headline_en"] == (
        "Database-backed feed shows a reviewed privacy incident"
    )
    assert detail_response.json()["headline_zh"] == "数据库支持的隐私事件已完成审核"
    assert detail_response.json()["company_involved_zh"] == "未来栈"
    assert detail_response.json()["publication_track"] == "accident_watch"
    assert detail_response.json()["evidence_tier"] == "reported_unconfirmed"
    assert detail_response.json()["source_family"] == "customer_support"
    assert detail_response.json()["verification_summary"] == (
        "Reporting describes the privacy leak; no regulator notice is linked yet."
    )
    assert detail_response.json()["analysis"] == {
        "incident_summary_en": (
            "A customer-support automation release exposed internal billing "
            "notes in live replies."
        ),
        "incident_summary_zh": "一次客户支持自动化发布在实时回复中暴露了内部账单备注。",
        "what_happened_en": (
            "The rollout surfaced internal account notes directly in "
            "customer-facing assistant messages."
        ),
        "what_happened_zh": "这次发布让内部账户备注直接出现在面向客户的助手消息中。",
        "ai_failure_point_en": (
            "The assistant failed to separate private support context from "
            "reply-generation context."
        ),
        "ai_failure_point_zh": "该助手未能将私密支持上下文与回复生成上下文隔离开。",
        "why_it_matters_en": (
            "The failure matters because internal account data appeared in "
            "customer-facing replies."
        ),
        "why_it_matters_zh": (
            "问题之所以重要，是因为内部账户数据出现在面向客户的回复中。"
        ),
        "evidence_summary_en": (
            "Validated with a primary report and supporting publication."
        ),
        "evidence_summary_zh": "已通过一手报告和补充报道完成核实。",
    }
    assert detail_response.json()["matched_claim"] == {
        "id": "claim-1",
        "claimant_name": "FutureStack",
        "company_involved": "FutureStack",
        "original_claim": FUTURESTACK_CLAIM,
        "claim_date": "2026-01-10",
        "claim_topic": "job automation",
        "match_confidence": 0.88,
    }
    assert detail_response.json()["sources"] == [
        {
            "id": "source-1",
            "source_url": "https://example.com/privacy",
            "source_type": "primary",
            "source_origin": "search_discovery",
            "source_registry_key": "google_search",
            "raw_source_payload": {"query": "AI support bot privacy leak"},
            "publisher": "Example News",
            "title": "Database-backed feed shows a reviewed privacy incident",
        }
    ]
    assert hidden_response.status_code == 404


def test_get_filters_reads_distinct_values_from_repository() -> None:
    repository = _build_repository()
    client = TestClient(create_app(incident_repository=repository))

    response = client.get("/filters")

    assert response.status_code == 200
    assert response.json() == {
        "categories": [
            "Autonomous Systems",
            "Model Governance",
            "Privacy/Security",
        ],
        "claimants": ["ArchiveAI", "FutureStack", "MayOps", "RoboOps"],
        "companies": ["ArchiveAI", "FutureStack", "MayOps", "RoboOps"],
        "company_labels_zh": {
            "ArchiveAI": None,
            "FutureStack": "未来栈",
            "MayOps": None,
            "RoboOps": None,
        },
        "publication_tracks": ["accident_watch", "verified_accident"],
        "source_families": [
            "autonomous_vehicle",
            "customer_support",
            "model_governance",
        ],
        "years": [2026, 2025],
        "months_by_year": {
            "2026": [5, 4],
            "2025": [12],
        },
    }

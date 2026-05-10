from __future__ import annotations

from app.scripts import publish_sitemap_incidents as script
from app.services.incident_translation import IncidentTranslation


class FailingTranslationClient:
    def translate(self, **kwargs):
        raise AssertionError("dry-run must not call the translation client")


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class FakeConnection:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def execute(self, query, params=()):
        self.queries.append(query)
        if "select" in query:
            return FakeResult(self.rows)
        raise AssertionError("dry-run must not execute update statements")


class FakePsycopg:
    def __init__(self, connection):
        self.connection = connection

    def connect(self, *args, **kwargs):
        return self.connection


def test_extract_sitemap_incident_ids_ignores_topic_urls() -> None:
    sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://aioopsnews.com/incidents/11111111-1111-4111-8111-111111111111/example</loc></url>
      <url><loc>https://aioopsnews.com/topics/category/hallucinations</loc></url>
      <url><loc>https://aioopsnews.com/incidents/22222222-2222-4222-8222-222222222222/example</loc></url>
    </urlset>
    """

    assert script.extract_sitemap_incident_ids(sitemap_xml) == [
        "11111111-1111-4111-8111-111111111111",
        "22222222-2222-4222-8222-222222222222",
    ]


def test_build_publish_update_uses_translation_and_preserves_existing_zh() -> None:
    row = {
        "id": "incident-1",
        "headline": "English headline",
        "headline_en": "English headline",
        "headline_zh": None,
        "reality_summary": "English summary",
        "reality_summary_en": "English summary",
        "reality_summary_zh": None,
        "company_involved": "OpenAI",
        "company_involved_zh": "开放人工智能",
        "legitimacy_reasoning": "Reasoning",
        "legitimacy_reasoning_zh": None,
        "source_validation_summary": "Sources",
        "source_validation_summary_zh": None,
        "incident_summary_en": "Incident summary",
        "incident_summary_zh": "已有事件摘要",
        "what_happened_en": "What happened",
        "what_happened_zh": "已有发生经过",
        "ai_failure_point_en": "Failure point",
        "ai_failure_point_zh": None,
        "why_it_matters_en": "Why it matters",
        "why_it_matters_zh": None,
        "evidence_summary_en": "Evidence",
        "evidence_summary_zh": None,
    }
    translation = IncidentTranslation(
        company_involved_zh="",
        headline_zh="中文标题",
        reality_summary_zh="中文摘要",
        incident_summary_zh="新事件摘要",
        what_happened_zh="新发生经过",
        ai_failure_point_zh="中文失效点",
        why_it_matters_zh="中文重要性",
        evidence_summary_zh="中文证据",
        legitimacy_reasoning_zh="中文理由",
        source_validation_summary_zh="中文来源",
    )

    update = script.build_publish_update(row, translation)

    assert update is not None
    assert update.headline_zh == "中文标题"
    assert update.reality_summary_zh == "中文摘要"
    assert update.company_involved_zh == "开放人工智能"
    assert update.incident_summary_zh == "已有事件摘要"
    assert update.what_happened_zh == "已有发生经过"
    assert update.ai_failure_point_zh == "中文失效点"
    assert update.translation_status == "completed"


def test_build_publish_update_rejects_incomplete_translation() -> None:
    row = {
        "id": "incident-1",
        "headline": "English headline",
        "headline_en": "English headline",
        "headline_zh": None,
        "reality_summary": "English summary",
        "reality_summary_en": "English summary",
        "reality_summary_zh": None,
    }
    translation = IncidentTranslation(
        headline_zh="",
        reality_summary_zh="中文摘要",
        legitimacy_reasoning_zh="",
        source_validation_summary_zh="",
    )

    assert script.build_publish_update(row, translation) is None


def test_publish_sitemap_incidents_dry_run_does_not_translate_or_update(
    monkeypatch,
    tmp_path,
) -> None:
    sitemap_path = tmp_path / "sitemap.xml"
    sitemap_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://aioopsnews.com/incidents/11111111-1111-4111-8111-111111111111/example</loc></url>
        </urlset>
        """,
        encoding="utf-8",
    )
    connection = FakeConnection(
        [
            {
                "id": "11111111-1111-4111-8111-111111111111",
                "headline_zh": None,
                "reality_summary_zh": None,
            }
        ]
    )
    monkeypatch.setattr(script, "psycopg", FakePsycopg(connection))
    monkeypatch.setattr(script, "dict_row", object())

    summary = script.publish_sitemap_incidents(
        database_url="postgresql://example",
        sitemap_path=sitemap_path,
        translation_client=FailingTranslationClient(),
        apply=False,
    )

    assert summary.dry_run is True
    assert summary.needs_translation == 1
    assert summary.updated == 0
    assert len(connection.queries) == 1


def test_publish_sitemap_incidents_missing_limit_only_counts_selected_missing(
    monkeypatch,
    tmp_path,
) -> None:
    sitemap_path = tmp_path / "sitemap.xml"
    sitemap_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://aioopsnews.com/incidents/11111111-1111-4111-8111-111111111111/example</loc></url>
          <url><loc>https://aioopsnews.com/incidents/22222222-2222-4222-8222-222222222222/example</loc></url>
        </urlset>
        """,
        encoding="utf-8",
    )
    connection = FakeConnection(
        [
            {
                "id": "11111111-1111-4111-8111-111111111111",
                "headline_zh": None,
                "reality_summary_zh": None,
            },
            {
                "id": "22222222-2222-4222-8222-222222222222",
                "headline_zh": None,
                "reality_summary_zh": None,
            },
        ]
    )
    monkeypatch.setattr(script, "psycopg", FakePsycopg(connection))
    monkeypatch.setattr(script, "dict_row", object())

    summary = script.publish_sitemap_incidents(
        database_url="postgresql://example",
        sitemap_path=sitemap_path,
        translation_client=FailingTranslationClient(),
        apply=False,
        missing_limit=1,
    )

    assert summary.needs_translation == 1
    assert summary.skipped_incomplete == 1


def test_publish_sitemap_incidents_missing_limit_does_not_republish_complete_rows(
    monkeypatch,
    tmp_path,
) -> None:
    sitemap_path = tmp_path / "sitemap.xml"
    sitemap_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://aioopsnews.com/incidents/11111111-1111-4111-8111-111111111111/example</loc></url>
          <url><loc>https://aioopsnews.com/incidents/22222222-2222-4222-8222-222222222222/example</loc></url>
        </urlset>
        """,
        encoding="utf-8",
    )
    connection = FakeConnection(
        [
            {
                "id": "11111111-1111-4111-8111-111111111111",
                "headline_zh": None,
                "reality_summary_zh": None,
            },
            {
                "id": "22222222-2222-4222-8222-222222222222",
                "headline_zh": "已有标题",
                "reality_summary_zh": "已有摘要",
            },
        ]
    )
    monkeypatch.setattr(script, "psycopg", FakePsycopg(connection))
    monkeypatch.setattr(script, "dict_row", object())

    summary = script.publish_sitemap_incidents(
        database_url="postgresql://example",
        sitemap_path=sitemap_path,
        translation_client=FailingTranslationClient(),
        apply=False,
        missing_limit=1,
    )

    assert summary.needs_translation == 1
    assert summary.publishable == 0
    assert summary.skipped_incomplete == 1

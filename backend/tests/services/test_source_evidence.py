from __future__ import annotations

import zlib

import httpx

from app.services.source_evidence import (
    SOURCE_EVIDENCE_TEXT_MAX_CHARS,
    FetchedIncidentSource,
    HttpIncidentSourceFetcher,
    build_review_source_context,
    extract_evidence_text,
    refresh_source_evidence,
)


def test_extract_evidence_text_strips_nul_bytes() -> None:
    evidence = extract_evidence_text("Alpha\x00Beta\nGamma")

    assert "\x00" not in evidence
    assert evidence == "Alpha Beta Gamma"


def test_extract_evidence_text_caps_html_at_source_storage_budget() -> None:
    evidence = extract_evidence_text("A" * (SOURCE_EVIDENCE_TEXT_MAX_CHARS + 10))

    assert len(evidence) == SOURCE_EVIDENCE_TEXT_MAX_CHARS


def test_extract_evidence_text_converts_html_to_markdown_like_text() -> None:
    html = """
    <!doctype html>
    <html>
      <head>
        <title>Ignored title chrome</title>
        <style>.hidden { display: none; }</style>
        <script>window.analytics = true;</script>
      </head>
      <body>
        <h1>Autonomous Vehicle Collision Reports</h1>
        <p>Latest official DMV reports.</p>
        <ul>
          <li><a href="/portal/file/waymo_041026-pdf/">Waymo April 10 PDF</a></li>
        </ul>
      </body>
    </html>
    """

    evidence = extract_evidence_text(html)

    assert "<html" not in evidence
    assert "<script" not in evidence
    assert "window.analytics" not in evidence
    assert ".hidden" not in evidence
    assert "# Autonomous Vehicle Collision Reports" in evidence
    assert "- [Waymo April 10 PDF](/portal/file/waymo_041026-pdf/)" in evidence


def test_extract_evidence_text_keeps_dmv_index_pdf_links() -> None:
    html = """
    <main>
      <h1>Autonomous Vehicle Collision Reports</h1>
      <table>
        <tr>
          <td>Waymo LLC</td>
          <td>Collision Report - April 10, 2026</td>
          <td><a href="https://www.dmv.ca.gov/portal/file/waymo_041026-pdf/">PDF</a></td>
        </tr>
      </table>
    </main>
    """

    evidence = extract_evidence_text(html)

    assert "Waymo LLC" in evidence
    assert "Collision Report - April 10, 2026" in evidence
    assert "[PDF](https://www.dmv.ca.gov/portal/file/waymo_041026-pdf/)" in evidence
    assert "<td>" not in evidence


def test_extract_evidence_text_removes_navigation_and_modal_chrome() -> None:
    html = """
    <body>
      <nav>DMV menu and search chrome</nav>
      <div class="modal ask-dmv-chat">
        General Disclaimer for the virtual assistant.
      </div>
      <main>
        <h1>Autonomous Vehicle Collision Reports</h1>
        <a href="/portal/file/waymo_041026-pdf/">Waymo April 10, 2026 (PDF)</a>
      </main>
      <footer>California DMV footer links</footer>
    </body>
    """

    evidence = extract_evidence_text(html)

    assert "DMV menu and search chrome" not in evidence
    assert "General Disclaimer" not in evidence
    assert "California DMV footer links" not in evidence
    assert "# Autonomous Vehicle Collision Reports" in evidence
    assert "[Waymo April 10, 2026 (PDF)](/portal/file/waymo_041026-pdf/)" in evidence


def test_http_source_fetcher_extracts_text_from_pdf_bytes(monkeypatch) -> None:
    def fake_get(url: str, **kwargs: object):  # type: ignore[no-untyped-def]
        del kwargs
        request = httpx.Request("GET", url)
        return httpx.Response(
            200,
            request=request,
            headers={"content-type": "application/pdf"},
            content=(
                b"%PDF-1.4\n"
                b"1 0 obj\n"
                b"(Waymo autonomous vehicle operating in autonomous mode made "
                b"contact with a bicyclist. No injuries were reported.) Tj\n"
                b"endobj\n"
            ),
        )

    monkeypatch.setattr("app.services.source_evidence.httpx.get", fake_get)

    result = HttpIncidentSourceFetcher().fetch("https://www.dmv.ca.gov/report.pdf")

    assert result.fetch_status == "fetched"
    assert result.evidence_text is not None
    assert "Waymo autonomous vehicle operating in autonomous mode" in (
        result.evidence_text
    )
    assert "bicyclist" in result.evidence_text


def test_http_source_fetcher_extracts_text_from_flate_pdf_stream(
    monkeypatch,
) -> None:
    compressed_stream = zlib.compress(
        (
            "BT (Waymo autonomous vehicle was in autonomous mode near Market "
            "Street and contacted a bicyclist. Damage was minor and no injury "
            "was reported.) Tj ET"
        ).encode("latin-1")
    )

    def fake_get(url: str, **kwargs: object):  # type: ignore[no-untyped-def]
        del kwargs
        request = httpx.Request("GET", url)
        return httpx.Response(
            200,
            request=request,
            headers={"content-type": "application/pdf"},
            content=(
                b"%PDF-1.5\n"
                b"1 0 obj\n"
                b"<< /Length "
                + str(len(compressed_stream)).encode("ascii")
                + b" /Filter /FlateDecode >>\n"
                b"stream\n"
                + compressed_stream
                + b"\nendstream\n"
                b"endobj\n"
            ),
        )

    monkeypatch.setattr("app.services.source_evidence.httpx.get", fake_get)

    result = HttpIncidentSourceFetcher().fetch("https://www.dmv.ca.gov/report.pdf")

    assert result.fetch_status == "fetched"
    assert result.evidence_text is not None
    assert "autonomous mode near Market Street" in result.evidence_text
    assert "bicyclist" in result.evidence_text
    assert "Structured autonomous vehicle facts" in result.evidence_text


def test_pdf_form_fields_are_prioritized_before_template_text(monkeypatch) -> None:
    class FakePage:
        def extract_text(self) -> str:
            return "OL 316 template instructions and blank collision form text."

    class FakeReader:
        is_encrypted = False
        pages = [FakePage()]

        def __init__(self, content: object) -> None:
            del content

        def get_fields(self) -> dict[str, dict[str, str]]:
            return {
                "narrative": {
                    "/T": "ACCIDENT DETAILS",
                    "/V": (
                        "Waymo AV was in autonomous mode at Market Street "
                        "and contacted a bicyclist."
                    ),
                }
            }

    monkeypatch.setattr("app.services.source_evidence.PdfReader", FakeReader)

    def fake_get(url: str, **kwargs: object):  # type: ignore[no-untyped-def]
        del kwargs
        request = httpx.Request("GET", url)
        return httpx.Response(
            200,
            request=request,
            headers={"content-type": "application/pdf"},
            content=b"%PDF fake",
        )

    monkeypatch.setattr("app.services.source_evidence.httpx.get", fake_get)

    result = HttpIncidentSourceFetcher().fetch("https://www.dmv.ca.gov/report.pdf")

    assert result.evidence_text is not None
    assert result.evidence_text.index("ACCIDENT DETAILS") < result.evidence_text.index(
        "OL 316 template"
    )


def test_http_incident_source_fetcher_retries_403_with_browser_headers(
    monkeypatch,
) -> None:
    calls: list[dict[str, str]] = []

    def fake_get(url: str, **kwargs: object):  # type: ignore[no-untyped-def]
        headers = dict(kwargs["headers"])  # type: ignore[index]
        calls.append(headers)
        request = httpx.Request("GET", url, headers=headers)
        if len(calls) == 1:
            return httpx.Response(
                403,
                request=request,
                text="Forbidden",
            )
        return httpx.Response(
            200,
            request=request,
            text="<html><body>NHTSA crash reporting page</body></html>",
        )

    monkeypatch.setattr("app.services.source_evidence.httpx.get", fake_get)

    result = HttpIncidentSourceFetcher().fetch(
        "https://www.nhtsa.gov/laws-regulations/standing-general-order-crash-reporting"
    )

    assert result.fetch_status == "fetched"
    assert result.http_status == 200
    assert result.evidence_text is not None
    assert "NHTSA crash reporting page" in result.evidence_text
    assert len(calls) == 2
    assert calls[0]["User-Agent"] == "AIRealityCheckBot/1.0"
    assert "Mozilla/5.0" in calls[1]["User-Agent"]
    assert calls[1]["Accept-Language"] == "en-US,en;q=0.9"


def test_http_source_fetcher_returns_failed_source_on_http_error(monkeypatch) -> None:
    def fake_get(url: str, **kwargs: object):  # type: ignore[no-untyped-def]
        del url, kwargs
        raise httpx.ConnectError("network unavailable")

    monkeypatch.setattr("app.services.source_evidence.httpx.get", fake_get)

    result = HttpIncidentSourceFetcher().fetch("https://example.test/report.pdf")

    assert result.fetch_status == "failed"
    assert result.evidence_text is None
    assert result.fetch_error == "network unavailable"


def test_refresh_source_evidence_skips_already_attempted_sources() -> None:
    class FakeRepository:
        def __init__(self) -> None:
            self.updated_source_ids: list[str] = []

        def update_incident_source_evidence(self, **kwargs: object) -> None:
            self.updated_source_ids.append(str(kwargs["source_id"]))

    class FakeFetcher:
        def __init__(self) -> None:
            self.fetched_urls: list[str] = []

        def fetch(self, source_url: str) -> FetchedIncidentSource:
            self.fetched_urls.append(source_url)
            return FetchedIncidentSource(
                source_url=source_url,
                canonical_url=f"{source_url}?canonical",
                fetch_status="fetched",
                http_status=200,
                evidence_text=f"Evidence for {source_url}",
                fetch_error=None,
            )

    repository = FakeRepository()
    fetcher = FakeFetcher()

    refresh_source_evidence(
        repository,  # type: ignore[arg-type]
        incidents=[
            {
                "sources": [
                    {
                        "id": "source-existing",
                        "source_url": "https://example.com/existing",
                        "evidence_text": "Already in DB",
                        "fetch_status": "fetched",
                    },
                    {
                        "id": "source-failed",
                        "source_url": "https://example.com/failed",
                        "evidence_text": None,
                        "fetch_status": "failed",
                    },
                    {
                        "id": "source-missing",
                        "source_url": "https://example.com/missing",
                        "evidence_text": None,
                        "fetch_status": None,
                    },
                ]
            }
        ],
        source_fetcher=fetcher,
    )

    assert fetcher.fetched_urls == ["https://example.com/missing"]
    assert repository.updated_source_ids == ["source-missing"]


def test_review_source_context_caps_prompt_evidence_and_keeps_facts() -> None:
    source = {
        "source_url": "https://www.dmv.ca.gov/report.pdf",
        "canonical_url": "https://www.dmv.ca.gov/report.pdf",
        "fetch_status": "fetched",
        "http_status": 200,
        "source_origin": "fixed_verified_source",
        "source_registry_key": "ca_dmv_av_collisions",
        "evidence_text": (
            ("navigation boilerplate " * 2000)
            + "Structured autonomous vehicle facts: collision object: bicyclist; "
            + "location: Market Street; automation state: autonomous mode. "
            + ("extra evidence " * 2000)
        ),
    }

    context = build_review_source_context([source], max_chars=1_000)

    assert len(context[0]["evidence_text"]) <= 1_000
    assert "Structured autonomous vehicle facts" in context[0]["evidence_text"]


def test_review_source_context_prioritizes_incident_pdf_over_index_page() -> None:
    index_source = {
        "source_url": (
            "https://www.dmv.ca.gov/portal/vehicle-industry-services/"
            "autonomous-vehicles/autonomous-vehicle-collision-reports/"
        ),
        "canonical_url": None,
        "fetch_status": "fetched",
        "http_status": 200,
        "source_origin": "fixed_verified_source",
        "source_registry_key": "ca_dmv_av_collisions",
        "evidence_text": (
            "DMV index page navigation and collision reports listing. " * 200
        ),
    }
    pdf_source = {
        "source_url": "https://www.dmv.ca.gov/portal/file/waymo_040626-pdf/",
        "canonical_url": None,
        "fetch_status": "fetched",
        "http_status": 200,
        "source_origin": "fixed_verified_source",
        "source_registry_key": "ca_dmv_av_collisions",
        "evidence_text": (
            "MANUFACTURERS NAME: Waymo LLC DATE OF ACCIDENT: 4/6/2026. "
            "Autonomous mode was engaged and the vehicle contacted road debris. "
            "Property damage was reported."
        ),
    }

    context = build_review_source_context(
        [index_source, pdf_source],
        max_chars=300,
    )

    assert context[0]["source_url"] == pdf_source["source_url"]
    assert "DATE OF ACCIDENT: 4/6/2026" in context[0]["evidence_text"]


def test_review_source_context_includes_nhtsa_csv_evidence_before_home_pages() -> None:
    home_source = {
        "source_url": (
            "https://www.nhtsa.gov/laws-regulations/"
            "standing-general-order-crash-reporting"
        ),
        "canonical_url": None,
        "fetch_status": None,
        "http_status": None,
        "source_origin": "fixed_verified_source",
        "source_registry_key": "nhtsa_data",
        "evidence_text": None,
    }
    csv_source = {
        "source_url": (
            "https://www.nhtsa.gov/laws-regulations/"
            "standing-general-order-crash-reporting#report-tesla-2"
        ),
        "canonical_url": (
            "https://www.nhtsa.gov/laws-regulations/"
            "standing-general-order-crash-reporting#report-tesla-2"
        ),
        "fetch_status": "fetched",
        "http_status": None,
        "source_origin": "fixed_verified_source",
        "source_registry_key": "nhtsa_data",
        "evidence_text": (
            "NHTSA SGO CSV report facts. Report ID: tesla-2. "
            "Engagement Status: Verified Engaged. Narrative: Vehicle crashed."
        ),
    }

    context = build_review_source_context([home_source, csv_source], max_chars=500)

    assert context[0]["source_url"] == csv_source["source_url"]
    assert "Report ID: tesla-2" in context[0]["evidence_text"]

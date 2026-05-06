from __future__ import annotations

from app.scrapers.verified_sources import (
    fetch_verified_source_records,
    parse_ca_dmv_collision_records,
    parse_charlotin_hallucination_records,
    parse_edrm_judicial_order_records,
    parse_nhtsa_sgo_records,
)


def test_parse_ca_dmv_collision_records_from_index_html() -> None:
    html = """
    <a href="/portal/file/waymo_041226-2-pdf/">Waymo April 12, 2026 (2) (PDF)</a>
    <a href="/portal/file/nuro_040326-pdf/">Nuro April 3, 2026 (PDF)</a>
    """

    records = parse_ca_dmv_collision_records(html, limit=2)

    assert [record.external_id for record in records] == [
        "ca-dmv-waymo-2026-04-12-2",
        "ca-dmv-nuro-2026-04-03",
    ]
    assert records[0].source_registry_key == "ca_dmv_av_collisions"
    assert records[0].incident_date == "2026-04-12"
    assert records[0].company == "Waymo"
    assert records[0].source_url == (
        "https://www.dmv.ca.gov/portal/file/waymo_041226-2-pdf/"
    )


def test_parse_charlotin_hallucination_records_from_csv() -> None:
    csv_text = "\n".join(
        [
            (
                "Case,Court / Jurisdiction,Date,Party Using AI,AI Tool,"
                "Nature of Hallucination,Outcome / Sanction,Details,Report(s)"
            ),
            (
                "Braun v. Day,N.D. Illinois (USA),30 April 2026,Lawyer,"
                "Implied,Fabricated Case Law,Show Cause Order,"
                "\"Court identified fabricated citations.\","
                "https://www.courtlistener.com/docket/68095239/braun-v-day/"
            ),
        ]
    )

    records = parse_charlotin_hallucination_records(csv_text, limit=1)

    assert len(records) == 1
    assert records[0].source_registry_key == "damien_charlotin_hallucinations"
    assert records[0].external_id == "damien-hallucination-braun-v-day-2026-04-30"
    assert records[0].incident_date == "2026-04-30"
    assert records[0].company == "Legal filing"
    assert "Braun v. Day" in records[0].summary
    assert records[0].source_url == (
        "https://www.courtlistener.com/docket/68095239/braun-v-day/"
    )


def test_parse_edrm_judicial_order_records_from_table_html() -> None:
    html = """
    <table>
      <tr>
        <th>COURT</th><th>JUDGE</th><th>DATE</th>
        <th>POINTS OF INTEREST</th><th>PDF</th>
      </tr>
      <tr>
        <td>District Court for the Northern District of California</td>
        <td>Araceli Martinez-Olguin</td>
        <td>11/22/2023</td>
        <td>Fed. R. Civ. P. 11 applies</td>
        <td><a href="https://edrm.net/order.pdf">Download</a></td>
      </tr>
    </table>
    """

    records = parse_edrm_judicial_order_records(html, limit=1)

    assert len(records) == 1
    assert records[0].source_registry_key == "edrm_judicial_orders"
    assert records[0].external_id == (
        "edrm-order-district-court-for-the-northern-district-of-california-"
        "araceli-martinez-olguin-2023-11-22"
    )
    assert records[0].incident_date == "2023-11-22"
    assert records[0].source_url == "https://edrm.net/order.pdf"


def test_parse_edrm_judicial_order_records_skips_repeated_header_rows() -> None:
    html = """
    <table>
      <tr><th>COURT</th><th>JUDGE</th><th>DATE</th><th>PDF</th></tr>
      <tr><td>COURT</td><td>JUDGE</td><td>DATE</td><td>PDF</td></tr>
      <tr>
        <td>Superior Court of Example</td>
        <td>Example Judge</td>
        <td>01/02/2026</td>
        <td><a href="https://edrm.net/example.pdf">Download</a></td>
      </tr>
    </table>
    """

    records = parse_edrm_judicial_order_records(html, limit=1)

    assert len(records) == 1
    assert records[0].external_id == (
        "edrm-order-superior-court-of-example-example-judge-2026-01-02"
    )


def test_parse_nhtsa_sgo_records_from_csv() -> None:
    csv_text = "\n".join(
        [
            (
                "Report ID,Incident Date,Reporting Entity,Make,Model,"
                "Narrative"
            ),
            (
                "12345,2026-02,Tesla,Tesla,Model Y,"
                "\"Vehicle reported a crash with automation engaged.\""
            ),
        ]
    )

    records = parse_nhtsa_sgo_records(csv_text, limit=1)

    assert len(records) == 1
    assert records[0].source_registry_key == "nhtsa_data"
    assert records[0].external_id == "nhtsa-sgo-12345"
    assert records[0].incident_date == "2026-02-01"
    assert records[0].company == "Tesla"
    assert records[0].source_url == (
        "https://www.nhtsa.gov/laws-regulations/standing-general-order-crash-reporting#report-12345"
    )


def test_fetch_verified_source_records_collects_selected_sources() -> None:
    class FakeResponse:
        def __init__(self, text: str) -> None:
            self.text = text

        def raise_for_status(self) -> None:
            return None

    class FakeHttpClient:
        def get(self, url: str) -> FakeResponse:
            assert url == (
                "https://www.dmv.ca.gov/portal/vehicle-industry-services/"
                "autonomous-vehicles/autonomous-vehicle-collision-reports/"
            )
            return FakeResponse(
                '<a href="/portal/file/waymo_041226-2-pdf/">'
                "Waymo April 12, 2026 (2) (PDF)</a>"
            )

    records = fetch_verified_source_records(
        sources=["ca_dmv_av_collisions"],
        http_client=FakeHttpClient(),
        limit_per_source=1,
    )

    assert len(records) == 1
    assert records[0].external_id == "ca-dmv-waymo-2026-04-12-2"


def test_fetch_verified_source_records_continues_when_one_source_fails() -> None:
    class FakeResponse:
        def __init__(self, text: str, *, should_fail: bool = False) -> None:
            self.text = text
            self._should_fail = should_fail

        def raise_for_status(self) -> None:
            if self._should_fail:
                raise RuntimeError("source unavailable")

    class FakeHttpClient:
        def get(self, url: str) -> FakeResponse:
            if "nhtsa.gov" in url:
                return FakeResponse("", should_fail=True)
            return FakeResponse(
                '<a href="/portal/file/waymo_041226-2-pdf/">'
                "Waymo April 12, 2026 (2) (PDF)</a>"
            )

    records = fetch_verified_source_records(
        sources=["nhtsa_data", "ca_dmv_av_collisions"],
        http_client=FakeHttpClient(),
        limit_per_source=1,
    )

    assert [record.external_id for record in records] == [
        "ca-dmv-waymo-2026-04-12-2"
    ]


def test_fetch_verified_source_records_makes_duplicate_external_ids_unique() -> None:
    class FakeResponse:
        text = """
        <a href="/portal/file/waymo_112624-pdf/">Waymo November 26, 2024 (PDF)</a>
        <a href="/portal/file/waymo_112624b-pdf/">Waymo November 26, 2024 (PDF)</a>
        """

        def raise_for_status(self) -> None:
            return None

    class FakeHttpClient:
        def get(self, url: str) -> FakeResponse:
            return FakeResponse()

    records = fetch_verified_source_records(
        sources=["ca_dmv_av_collisions"],
        http_client=FakeHttpClient(),
        limit_per_source=10,
    )

    assert [record.external_id for record in records] == [
        "ca-dmv-waymo-2024-11-26",
        "ca-dmv-waymo-2024-11-26-waymo-112624b-pdf",
    ]

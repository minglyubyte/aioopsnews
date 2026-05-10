from __future__ import annotations

from app.scrapers.verified_sources import (
    fetch_verified_source_records,
    parse_ca_dmv_collision_records,
    parse_charlotin_hallucination_records,
    parse_doj_ai_enforcement_records,
    parse_edrm_judicial_order_records,
    parse_ftc_ai_enforcement_records,
    parse_nhtsa_sgo_records,
    parse_sec_ai_enforcement_records,
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


def test_parse_ftc_ai_enforcement_records_from_operation_ai_comply_page() -> None:
    html = """
    <nav><h2>Breadcrumb</h2><time>February 13, 2026</time></nav>
    <h1>FTC Announces Crackdown on Deceptive AI Claims and Schemes</h1>
    <time>September 25, 2024</time>
    <p>The FTC is taking action against multiple companies as part of
    Operation AI Comply.</p>
    <h2>DoNotPay</h2>
    <p>The FTC is taking action against DoNotPay, a company that claimed to
    offer an AI service that was the world's first robot lawyer. According to
    the FTC complaint, DoNotPay could not deliver on these promises.</p>
    <h2>Rytr</h2>
    <p>According to the FTC's complaint, Rytr marketed an AI writing assistant
    that enabled subscribers to generate false consumer reviews. The proposed
    order would bar similar conduct.</p>
    """

    records = parse_ftc_ai_enforcement_records(
        html,
        source_url=(
            "https://www.ftc.gov/news-events/news/press-releases/2024/09/"
            "ftc-announces-crackdown-deceptive-ai-claims-schemes"
        ),
        limit=10,
    )

    assert [record.external_id for record in records] == [
        "ftc-ai-donotpay-2024-09-25",
        "ftc-ai-rytr-2024-09-25",
    ]
    assert records[0].source_registry_key == "ftc_ai_enforcement"
    assert {record.company for record in records} == {"DoNotPay", "Rytr"}
    assert records[0].incident_date == "2024-09-25"
    assert records[0].company == "DoNotPay"
    assert "FTC official enforcement page" in records[0].summary


def test_parse_doj_ai_enforcement_records_from_press_release() -> None:
    html = """
    <h1>Justice Department Sues RealPage for Algorithmic Pricing Scheme that
    Harms Millions of American Renters</h1>
    <div>Friday, August 23, 2024</div>
    <p>The Justice Department filed a civil antitrust lawsuit today against
    RealPage Inc. The complaint alleges RealPage's pricing algorithm violated
    antitrust law and harmed renters.</p>
    """

    records = parse_doj_ai_enforcement_records(
        html,
        source_url=(
            "https://www.justice.gov/opa/pr/justice-department-sues-realpage-"
            "algorithmic-pricing-scheme-harms-millions-american-renters"
        ),
        limit=10,
    )

    assert len(records) == 1
    assert records[0].source_registry_key == "doj_ai_enforcement"
    assert records[0].external_id == "doj-ai-realpage-2024-08-23"
    assert records[0].company == "RealPage"
    assert records[0].source_family == "model_governance"


def test_parse_sec_ai_enforcement_records_from_ai_washing_press_release() -> None:
    html = """
    <h1>SEC Charges Two Investment Advisers with Making False and Misleading
    Statements About Their Use of Artificial Intelligence</h1>
    <p>Washington D.C., March 18, 2024 —</p>
    <p>The Securities and Exchange Commission announced settled charges against
    two investment advisers, Delphia (USA) Inc. and Global Predictions Inc.,
    for making false and misleading statements about their purported use of
    artificial intelligence.</p>
    """

    records = parse_sec_ai_enforcement_records(
        html,
        source_url="https://www.sec.gov/newsroom/press-releases/2024-36",
        limit=10,
    )

    assert [record.external_id for record in records] == [
        "sec-ai-delphia-usa-inc-2024-03-18",
        "sec-ai-global-predictions-inc-2024-03-18",
    ]
    assert records[0].source_registry_key == "sec_ai_enforcement"
    assert records[0].company == "Delphia (USA) Inc."


def test_parse_official_ai_guidance_pages_are_skipped() -> None:
    html = """
    <h1>Artificial Intelligence Guidance</h1>
    <p>This page explains agency guidance, best practices, speeches, and policy
    resources about artificial intelligence. It does not announce a complaint,
    settlement, lawsuit, order, or charges against a named entity.</p>
    """

    assert (
        parse_ftc_ai_enforcement_records(
            html,
            source_url="https://www.ftc.gov/industry/technology/artificial-intelligence",
            limit=10,
        )
        == []
    )
    assert (
        parse_doj_ai_enforcement_records(
            html,
            source_url="https://www.justice.gov/crt/ai",
            limit=10,
        )
        == []
    )
    assert (
        parse_sec_ai_enforcement_records(
            html,
            source_url="https://www.sec.gov/artificial-intelligence",
            limit=10,
        )
        == []
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


def test_fetch_verified_source_records_collects_selected_ai_enforcement_sources() -> (
    None
):
    class FakeResponse:
        def __init__(self, text: str) -> None:
            self.text = text

        def raise_for_status(self) -> None:
            return None

    class FakeHttpClient:
        def get(self, url: str) -> FakeResponse:
            if "ftc.gov" in url:
                return FakeResponse(
                    """
                    <h1>FTC Announces Crackdown on Deceptive AI Claims and
                    Schemes</h1><time>September 25, 2024</time>
                    <h2>DoNotPay</h2>
                    <p>The FTC complaint alleges DoNotPay made deceptive AI
                    lawyer claims.</p>
                    """
                )
            if "justice.gov" in url:
                assert "/atr/case-document/complaint-303" in url
                return FakeResponse(
                    """
                    <h1>Complaint</h1><p>Date Friday, August 23, 2024</p>
                    <p>Document Type Complaint</p>
                    <a href="/atr/media/1365471/dl">424422.pdf</a>
                    <p>Related Case U.S. and Plaintiff States v. RealPage,
                    Inc.</p>
                    """
                )
            return FakeResponse(
                """
                <h1>SEC Charges Rimar Capital Entities and Owner Itai Liptz
                for Defrauding Investors by Making False and Misleading
                Statements About Use of Artificial Intelligence</h1>
                <p>Washington D.C., Oct. 10, 2024 —</p>
                <p>The SEC announced charges against Rimar Capital USA, Inc.
                and Rimar Capital, LLC for misleading AI claims.</p>
                """
            )

    records = fetch_verified_source_records(
        sources=["ftc_ai_enforcement", "doj_ai_enforcement", "sec_ai_enforcement"],
        http_client=FakeHttpClient(),
        limit_per_source=1,
    )

    assert [record.source_registry_key for record in records] == [
        "ftc_ai_enforcement",
        "doj_ai_enforcement",
        "sec_ai_enforcement",
    ]
    assert records[1].source_url == "https://www.justice.gov/atr/media/1365471/dl"


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

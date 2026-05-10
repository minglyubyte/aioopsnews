from __future__ import annotations

from app.scrapers.verified_sources import (
    fetch_verified_source_records,
    parse_ca_dmv_collision_records,
    parse_charlotin_hallucination_records,
    parse_doj_ai_enforcement_records,
    parse_edrm_judicial_order_records,
    parse_eeoc_ai_enforcement_records,
    parse_fda_ai_medical_device_warning_records,
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


def test_parse_eeoc_ai_enforcement_records_from_itutorgroup_press_release() -> None:
    html = """
    <h1>iTutorGroup to Pay $365,000 to Settle EEOC Discriminatory Hiring Suit</h1>
    <p>Press Release 09-11-2023</p>
    <p>The EEOC lawsuit alleged iTutorGroup programmed online software to
    automatically reject female applicants aged 55 or older and male applicants
    aged 60 or older.</p>
    """

    records = parse_eeoc_ai_enforcement_records(
        html,
        source_url=(
            "https://www.eeoc.gov/newsroom/itutorgroup-pay-365000-settle-eeoc-"
            "discriminatory-hiring-suit"
        ),
        limit=10,
    )

    assert len(records) == 1
    assert records[0].source_registry_key == "eeoc_ai_enforcement"
    assert records[0].external_id == "eeoc-ai-itutorgroup-2023-09-11"
    assert records[0].company == "iTutorGroup"


def test_parse_fda_ai_warning_records_from_medical_device_warning_letter() -> None:
    html = """
    <h1>Exer Labs, Inc. MARCS-CMS 699218 — February 10, 2025</h1>
    <p>WARNING LETTER</p>
    <p>FDA determined Exer Labs, Inc. markets Exer Scan using artificial
    intelligence-based algorithms to screen, diagnose, and treat
    musculoskeletal and neurological disorders. The product is adulterated and
    misbranded because the firm lacks required premarket authorization.</p>
    """

    records = parse_fda_ai_medical_device_warning_records(
        html,
        source_url=(
            "https://www.fda.gov/inspections-compliance-enforcement-and-"
            "criminal-investigations/warning-letters/exer-labs-inc-699218-"
            "02102025"
        ),
        limit=10,
    )

    assert len(records) == 1
    assert records[0].source_registry_key == "fda_ai_medical_device_warning_letters"
    assert records[0].external_id == "fda-ai-exer-labs-inc-2025-02-10"
    assert records[0].company == "Exer Labs, Inc."
    assert records[0].source_family == "healthcare_benefits"


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
    assert (
        parse_eeoc_ai_enforcement_records(
            html,
            source_url="https://www.eeoc.gov/ai",
            limit=10,
        )
        == []
    )
    assert (
        parse_fda_ai_medical_device_warning_records(
            html,
            source_url="https://www.fda.gov/medical-devices/artificial-intelligence",
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


def test_fetch_verified_source_records_collects_eeoc_and_fda_ai_sources() -> None:
    class FakeResponse:
        def __init__(self, text: str) -> None:
            self.text = text

        def raise_for_status(self) -> None:
            return None

    class FakeHttpClient:
        def get(self, url: str) -> FakeResponse:
            if "eeoc.gov" in url:
                return FakeResponse(
                    """
                    <h1>iTutorGroup to Pay $365,000 to Settle EEOC
                    Discriminatory Hiring Suit</h1>
                    <p>Press Release 09-11-2023</p>
                    <p>The EEOC lawsuit alleged iTutorGroup programmed online
                    software to automatically reject older applicants.</p>
                    """
                )
            if "exer-labs" in url:
                return FakeResponse(
                    """
                    <h1>Exer Labs, Inc. MARCS-CMS 699218 — February 10, 2025</h1>
                    <p>WARNING LETTER</p>
                    <p>FDA says Exer Labs, Inc. marketed Exer Scan using
                    artificial intelligence-based algorithms to screen and
                    diagnose disorders, making the product adulterated and
                    misbranded without required authorization.</p>
                    """
                )
            if "wavi-co" in url:
                return FakeResponse(
                    """
                    <h1>WAVi Co. MARCS-CMS 658549 — October 20, 2023</h1>
                    <p>WARNING LETTER</p>
                    <p>The warning letter says WAVi Desktop research software
                    has Artificial Intelligence codes and capabilities and was
                    distributed without required validation and authorization.</p>
                    """
                )
            if "seniorlife-technologies" in url:
                return FakeResponse(
                    """
                    <h1>SeniorLife Technologies, Inc. MARCS-CMS 707021 —
                    August 21, 2025</h1>
                    <p>WARNING LETTER</p>
                    <p>FDA says SeniorLife.AI uses artificial
                    intelligence-based algorithms to screen and pre-diagnose
                    mobility and cognitive health conditions without required
                    premarket authorization.</p>
                    """
                )
            raise AssertionError(f"unexpected URL: {url}")

    records = fetch_verified_source_records(
        sources=["eeoc_ai_enforcement", "fda_ai_medical_device_warning_letters"],
        http_client=FakeHttpClient(),
        limit_per_source=10,
    )

    assert [record.external_id for record in records] == [
        "eeoc-ai-itutorgroup-2023-09-11",
        "fda-ai-exer-labs-inc-2025-02-10",
        "fda-ai-wavi-co-2023-10-20",
        "fda-ai-seniorlife-technologies-inc-2025-08-21",
    ]


def test_fetch_ftc_ai_enforcement_discovers_index_pages_and_filters_non_cases() -> (
    None
):
    class FakeResponse:
        def __init__(self, text: str) -> None:
            self.text = text

        def raise_for_status(self) -> None:
            return None

    class FakeHttpClient:
        def get(self, url: str) -> FakeResponse:
            if url == (
                "https://www.ftc.gov/news-events/news/press-releases/2024/09/"
                "ftc-announces-crackdown-deceptive-ai-claims-schemes"
            ):
                return FakeResponse(
                    """
                    <h1>FTC Announces Crackdown on Deceptive AI Claims and
                    Schemes</h1><time>September 25, 2024</time>
                    <h2>DoNotPay</h2>
                    <p>The FTC complaint alleges DoNotPay made deceptive AI
                    lawyer claims.</p>
                    """
                )
            if url == "https://www.ftc.gov/industry/technology/artificial-intelligence":
                return FakeResponse(
                    """
                    <a href="/news-events/news/press-releases/2025/04/ftc-order-requires-workado-back-artificial-intelligence-detection-claims">
                    FTC Order Requires Workado to Back Up Artificial
                    Intelligence Detection Claims</a>
                    <a href="/legal-library/browse/federal-register-notices/ai-rulemaking">
                    Petition for Rulemaking of Andrew Gonzalez</a>
                    <a href="/legal-library/browse/cases-proceedings/cleo-ai-inc-ftc-v">
                    Cleo AI</a>
                    <a href="/news-events/news/press-releases/2025/02/ftc-finalizes-order-donotpay-prohibits-deceptive-ai-lawyer-claims-imposes-monetary-relief-requires">
                    FTC Finalizes Order with DoNotPay That Prohibits Deceptive
                    AI Lawyer Claims</a>
                    <a href="?page=1">Next</a>
                    """
                )
            if url == (
                "https://www.ftc.gov/industry/technology/artificial-intelligence?page=1"
            ):
                return FakeResponse(
                    """
                    <a href="/news-events/news/press-releases/2024/11/ftc-takes-action-against-evolv-technologies-deceiving-users-about-its-ai-powered-security-screening">
                    FTC Takes Action Against Evolv Technologies for Deceiving
                    Users About its AI-Powered Security Screening Systems</a>
                    """
                )
            if "workado" in url:
                return FakeResponse(
                    """
                    <h1>FTC Order Requires Workado to Back Up Artificial
                    Intelligence Detection Claims</h1>
                    <time>April 28, 2025</time>
                    <p>The FTC issued a proposed order requiring Workado, LLC
                    to stop advertising the accuracy of its artificial
                    intelligence content detection products unless it has
                    competent and reliable evidence. The complaint alleges the
                    AI Content Detector was no better than a coin toss.</p>
                    """
                )
            if "evolv" in url:
                return FakeResponse(
                    """
                    <h1>FTC Takes Action Against Evolv Technologies for
                    Deceiving Users About its AI-Powered Security Screening
                    Systems</h1>
                    <time>November 26, 2024</time>
                    <p>The FTC complaint alleged Evolv Technologies made false
                    claims that its AI-powered security screening system could
                    detect weapons and ignore harmless personal items.</p>
                    """
                )
            if "cleo-ai" in url:
                return FakeResponse(
                    """
                    <h1>Cleo AI, Inc., FTC v.</h1>
                    <time>May 2, 2025</time>
                    <p>Cleo AI agreed to settle allegations that it deceived
                    consumers about cash advance subscriptions and cancellation.
                    The complaint does not allege deceptive AI claims.</p>
                    """
                )
            if "donotpay-prohibits" in url:
                return FakeResponse(
                    """
                    <h1>FTC Finalizes Order with DoNotPay That Prohibits
                    Deceptive 'AI Lawyer' Claims</h1>
                    <time>February 11, 2025</time>
                    <p>DoNotPay promoted its subscription service as the
                    world's first robot lawyer. The final order resolves the
                    same Operation AI Comply matter announced in 2024.</p>
                    """
                )
            if "automators" in url:
                return FakeResponse(
                    """
                    <h1>Automators</h1>
                    <p>February 27, 2024</p>
                    <p>The FTC case summary says Automators claimed to use
                    artificial intelligence to ensure success and profitability
                    for consumers investing in e-commerce storefronts.</p>
                    """
                )
            if "career-step" in url:
                return FakeResponse(
                    """
                    <h1>Career Step, LLC, FTC v.</h1>
                    <p>July 30, 2024</p>
                    <p>The FTC complaint alleges Career Step used AI technology
                    to persuade consumers to enroll while making deceptive job
                    placement and partnership claims.</p>
                    """
                )
            if "cri-genetics" in url:
                return FakeResponse(
                    """
                    <h1>CRI Genetics, FTC and State of California v.</h1>
                    <p>November 21, 2023</p>
                    <p>The complaint alleges CRI Genetics deceived consumers
                    about DNA reports and falsely claimed a patented algorithm
                    for genetic matching.</p>
                    """
                )
            if "ngl-labs" in url:
                return FakeResponse(
                    """
                    <h1>FTC Order Will Ban NGL Labs and its Founders from
                    Offering Anonymous Messaging Apps to Kids Under 18 and
                    Halt Deceptive Claims Around AI Content Moderation</h1>
                    <p>July 9, 2024</p>
                    <p>The FTC complaint alleges NGL Labs falsely claimed that
                    its AI content moderation program filtered out cyberbullying
                    and other harmful messages.</p>
                    """
                )
            raise AssertionError(f"unexpected URL: {url}")

    records = fetch_verified_source_records(
        sources=["ftc_ai_enforcement"],
        http_client=FakeHttpClient(),
        limit_per_source=10,
    )

    assert [record.external_id for record in records] == [
        "ftc-ai-donotpay-2024-09-25",
        "ftc-ai-automators-2024-02-27",
        "ftc-ai-career-step-2024-07-30",
        "ftc-ai-cri-genetics-2023-11-21",
        "ftc-ai-ngl-labs-2024-07-09",
        "ftc-ai-workado-llc-2025-04-28",
        "ftc-ai-evolv-technologies-2024-11-26",
    ]


def test_fetch_doj_ai_enforcement_discovers_civil_rights_cases_and_skips_policy() -> (
    None
):
    class FakeResponse:
        def __init__(self, text: str) -> None:
            self.text = text

        def raise_for_status(self) -> None:
            return None

    class FakeHttpClient:
        def get(self, url: str) -> FakeResponse:
            if "complaint-303" in url:
                return FakeResponse(
                    """
                    <h1>Complaint</h1><p>Date Friday, August 23, 2024</p>
                    <p>Document Type Complaint</p>
                    <a href="/atr/media/1365471/dl">424422.pdf</a>
                    <p>Related Case U.S. and Plaintiff States v. RealPage,
                    Inc.</p>
                    """
                )
            if url == "https://www.justice.gov/crt/ai":
                return FakeResponse(
                    """
                    <h1>Artificial Intelligence and Civil Rights</h1>
                    <h2>Cases and matters</h2>
                    <a href="/opa/pr/civil-rights-division-obtains-settlement-company-used-ai-generated-advertisements-excluded">
                    Civil Rights Division Obtains Settlement with a Company
                    that Used AI-Generated Advertisements that Excluded U.S.
                    Workers from Jobs</a>
                    <a href="/opa/pr/justice-department-intervenes-xai-lawsuit-challenging-colorados-algorithmic-discrimination">
                    Justice Department Intervenes in xAI lawsuit Challenging
                    Colorado's Algorithmic Discrimination Law</a>
                    """
                )
            if "elegant" in url or "ai-generated-advertisements" in url:
                return FakeResponse(
                    """
                    <h1>Civil Rights Division Obtains Settlement with a Company
                    that Used AI-Generated Advertisements that Excluded U.S.
                    Workers from Jobs</h1>
                    <p>Wednesday, February 25, 2026</p>
                    <p>The Civil Rights Division secured a settlement agreement
                    with Elegant Enterprise-Wide Solutions Inc. The settlement
                    addresses allegations that job advertisements generated by
                    an artificial intelligence tool included unlawful
                    citizenship status restrictions.</p>
                    """
                )
            if "meta-platforms" in url:
                return FakeResponse(
                    """
                    <h1>Justice Department Secures Groundbreaking Settlement
                    Agreement with Meta Platforms, Formerly Known as Facebook,
                    to Resolve Allegations of Discriminatory Advertising</h1>
                    <p>Tuesday, June 21, 2022</p>
                    <p>The complaint alleges Meta Platforms Inc. used algorithms
                    in determining which Facebook users receive housing ads,
                    and those algorithms relied on protected characteristics.</p>
                    """
                )
            if "greystar" in url:
                return FakeResponse(
                    """
                    <h1>Justice Department Reaches Proposed Settlement with
                    Greystar, the Largest U.S. Landlord, to End Its
                    Participation in Algorithmic Pricing Scheme</h1>
                    <p>Friday, August 8, 2025</p>
                    <p>The proposed settlement resolves claims against Greystar
                    Management Services LLC for using RealPage algorithms and
                    competitively sensitive data to generate pricing
                    recommendations.</p>
                    """
                )
            if "livcor" in url:
                return FakeResponse(
                    """
                    <h1>Justice Department Reaches Proposed Consent Decree
                    with LivCor, One of America's Largest Landlords, to Resolve
                    Information Sharing and Algorithmic Coordination Claims</h1>
                    <p>Tuesday, December 23, 2025</p>
                    <p>The proposed consent decree resolves claims against
                    LivCor, LLC for participating in common pricing algorithms
                    using competitively sensitive information.</p>
                    """
                )
            if "six-large-landlords" in url or "2025-01886" in url:
                return FakeResponse(
                    """
                    <h1>Justice Department Sues Six Large Landlords for
                    Algorithmic Pricing Scheme that Harms Millions of American
                    Renters</h1>
                    <p>Tuesday, January 7, 2025</p>
                    <p>The amended complaint alleges Greystar Real Estate
                    Partners LLC, LivCor LLC, Camden Property Trust, Cushman &
                    Wakefield Inc and Pinnacle Property Management Services LLC,
                    Willow Bridge Property Company LLC, and Cortland Management
                    LLC participated in an algorithmic pricing scheme.</p>
                    """
                )
            if "louis-et-al-v-saferent" in url:
                return FakeResponse(
                    """
                    <h1>Louis et al. v. SafeRent et al. (D. Mass.)</h1>
                    <p>January 9, 2023</p>
                    <p>The United States filed a Statement of Interest in a
                    Fair Housing Act case alleging that SafeRent provides
                    algorithm-based tenant screening software that
                    discriminates against Black and Hispanic rental
                    applicants.</p>
                    """
                )
            if "us-v-regents-university-california" in url:
                return FakeResponse(
                    """
                    <h1>U.S. v. Regents of the University of California</h1>
                    <p>November 21, 2022</p>
                    <p>The complaint alleges UC Berkeley relied on inaccurate
                    automated captions and inaccessible online content. The
                    consent decree says UC Berkeley will not rely solely on
                    YouTube's automated AI-based technology and will provide
                    accurate captions.</p>
                    """
                )
            if (
                "settles-microsoft" in url
                or "microsoft-corporation-citizenship-status-december-2021" in url
            ):
                return FakeResponse(
                    """
                    <h1>Justice Department Settles with Microsoft to Resolve
                    Immigration-Related Discrimination Claims</h1>
                    <p>Tuesday, December 7, 2021</p>
                    <p>The Civil Rights Division signed a settlement with
                    Microsoft Corporation after finding that employment
                    eligibility verification software and automated email
                    processes contributed to discriminatory document requests
                    during hiring and reverification.</p>
                    """
                )
            if (
                "large-health-care-organization" in url
                or "ascension-health-alliance-unfair-documentary-practices-august-2021"
                in url
            ):
                return FakeResponse(
                    """
                    <h1>Justice Department Settles with Large Health Care
                    Organization to Resolve Software-Based Immigration-Related
                    Discrimination Claims</h1>
                    <p>Wednesday, August 25, 2021</p>
                    <p>The department determined Ascension Health Alliance
                    improperly programmed employment eligibility verification
                    software to send automated emails requesting proof of
                    continued work authorization from non-U.S. citizen
                    employees.</p>
                    """
                )
            if "xai-lawsuit" in url:
                return FakeResponse(
                    """
                    <h1>Justice Department Intervenes in xAI lawsuit
                    Challenging Colorado's Algorithmic Discrimination Law</h1>
                    <p>Friday, April 24, 2026</p>
                    <p>The Justice Department moved to intervene in a lawsuit
                    filed by artificial intelligence company xAI challenging a
                    state law. This page is not an enforcement action against
                    xAI.</p>
                    """
                )
            raise AssertionError(f"unexpected URL: {url}")

    records = fetch_verified_source_records(
        sources=["doj_ai_enforcement"],
        http_client=FakeHttpClient(),
        limit_per_source=20,
    )

    assert [record.external_id for record in records] == [
        "doj-ai-realpage-2024-08-23",
        "doj-ai-elegant-enterprise-wide-solutions-inc-2026-02-25",
        "doj-ai-meta-platforms-inc-2022-06-21",
        "doj-ai-greystar-management-services-llc-2025-08-08",
        "doj-ai-livcor-llc-2025-01-07",
        "doj-ai-greystar-real-estate-partners-llc-2025-01-07",
        "doj-ai-camden-property-trust-2025-01-07",
        "doj-ai-cushman-wakefield-inc-2025-01-07",
        "doj-ai-pinnacle-property-management-services-llc-2025-01-07",
        "doj-ai-willow-bridge-property-company-llc-2025-01-07",
        "doj-ai-cortland-management-llc-2025-01-07",
        "doj-ai-saferent-2023-01-09",
        "doj-ai-regents-of-the-university-of-california-2022-11-21",
        "doj-ai-microsoft-corporation-2021-12-07",
        "doj-ai-ascension-health-alliance-2021-08-25",
    ]


def test_fetch_sec_ai_enforcement_discovers_fraud_releases_and_skips_alerts() -> None:
    class FakeResponse:
        def __init__(self, text: str) -> None:
            self.text = text

        def raise_for_status(self) -> None:
            return None

    class FakeHttpClient:
        def get(self, url: str) -> FakeResponse:
            if url == "https://www.sec.gov/newsroom/press-releases/2024-36":
                return FakeResponse(
                    """
                    <h1>SEC Charges Two Investment Advisers with Making False
                    and Misleading Statements About Their Use of Artificial
                    Intelligence</h1>
                    <p>Washington D.C., March 18, 2024 —</p>
                    <p>The SEC announced settled charges against Delphia (USA)
                    Inc. and Global Predictions Inc. for misleading AI claims.</p>
                    """
                )
            if url == "https://www.sec.gov/newsroom/press-releases/2024-167":
                return FakeResponse(
                    """
                    <h1>SEC Charges Rimar Capital Entities and Owner Itai
                    Liptz for Defrauding Investors by Making False and
                    Misleading Statements About Use of Artificial Intelligence</h1>
                    <p>Washington D.C., Oct. 10, 2024 —</p>
                    <p>The SEC announced charges against Rimar Capital USA, Inc.
                    and Rimar Capital, LLC for misleading AI claims.</p>
                    """
                )
            if url == (
                "https://www.sec.gov/newsroom/press-releases?"
                "combine=artificial%20intelligence&year=All&month=All"
            ):
                return FakeResponse(
                    """
                    <a href="/newsroom/press-releases/2024-70">SEC Charges
                    Founder of AI Hiring Startup Joonko with Fraud</a>
                    <a href="/enforcement-litigation/litigation-releases/lr-26282">
                    SEC Charges Founder and Former CEO of Artificial
                    Intelligence Startup with Misleading Investors</a>
                    <a href="/investor/alerts/ai-investment-fraud">Investor
                    Alert: Artificial Intelligence and Investment Fraud</a>
                    """
                )
            if url == "https://www.sec.gov/newsroom/press-releases/2024-70":
                return FakeResponse(
                    """
                    <h1>SEC Charges Founder of AI Hiring Startup Joonko with
                    Fraud</h1><p>Washington D.C., June 11, 2024 —</p>
                    <p>The SEC charged Ilit Raz, CEO and founder of artificial
                    intelligence recruitment startup Joonko, with defrauding
                    investors by making false statements about customers and
                    revenue.</p>
                    """
                )
            if url == "https://www.sec.gov/newsroom/press-releases/2024-13":
                return FakeResponse(
                    """
                    <h1>SEC Charges Founder of American Bitcoin Academy Online
                    Crypto Course with Fraud Targeting Students</h1>
                    <p>Washington D.C., Feb. 2, 2024 —</p>
                    <p>The SEC charged Brian Sewell and Rockwell Capital
                    Management over claims that a hedge fund would use
                    artificial intelligence and machine learning technology.</p>
                    """
                )
            if url == "https://www.sec.gov/newsroom/press-releases/2025-69":
                return FakeResponse(
                    """
                    <h1>SEC Charges PGI Global Founder with $198 Million
                    Crypto Asset and Foreign Exchange Fraud Scheme</h1>
                    <p>Washington D.C., April 22, 2025 —</p>
                    <p>The SEC charged Ramil Palafox, whose company PGI Global
                    claimed guaranteed returns from an AI-powered auto-trading
                    platform.</p>
                    """
                )
            if url == "https://www.sec.gov/newsroom/press-releases/2024-109":
                return FakeResponse(
                    """
                    <h1>SEC Charges China-based QZ Asset Management Ltd. and
                    its CEO in Pre-IPO Fraud Scheme</h1>
                    <p>Washington D.C., Aug. 27, 2024 —</p>
                    <p>The complaint alleges QZ Asset Management Limited and
                    QZ Global Limited falsely claimed proprietary AI-based
                    technology would help generate extraordinary returns.</p>
                    """
                )
            if url == "https://www.sec.gov/newsroom/press-releases/2025-144-sec-charges-three-purported-crypto-asset-trading-platforms-four-investment-clubs-scheme-targeted":
                return FakeResponse(
                    """
                    <h1>SEC Charges Three Purported Crypto Asset Trading
                    Platforms and Four Investment Clubs with Scheme That
                    Targeted Retail Investors on Social Media</h1>
                    <p>Washington D.C., Dec. 22, 2025 —</p>
                    <p>The complaint alleges investment clubs including AI
                    Wealth Inc. promised profits from AI-generated investment
                    tips and then lured investors to fake trading platforms.</p>
                    """
                )
            if url == "https://www.sec.gov/enforcement-litigation/litigation-releases/lr-26282":
                return FakeResponse(
                    """
                    <h1>Alberto Saniger Mantinan, a/k/a Albert Saniger</h1>
                    <h3>SEC Charges Founder and Former CEO of Artificial
                    Intelligence Startup with Misleading Investors</h3>
                    <p>Litigation Release No. 26282 / April 11, 2025</p>
                    <p>The SEC charged Albert Saniger, the founder and former
                    CEO of Nate, Inc., with fraudulently soliciting investments
                    by making false and misleading statements about Nate's use
                    of artificial intelligence.</p>
                    """
                )
            if url == "https://www.sec.gov/enforcement-litigation/litigation-releases/lr-25144":
                return FakeResponse(
                    """
                    <h1>Profit Connect Wealth Services, Inc., Joy I. Kovar,
                    and Brent C. Kovar</h1>
                    <h3>SEC Shuts Down Fraudulent Mother-Son Offering
                    Involving Purported Supercomputer</h3>
                    <p>Litigation Release No. 25144 / July 20, 2021</p>
                    <p>The SEC complaint alleges Profit Connect Wealth
                    Services, Inc. raised investor funds for trading based on
                    recommendations made by an artificial intelligence
                    supercomputer.</p>
                    """
                )
            if url == "https://www.sec.gov/enforcement-litigation/administrative-proceedings/33-11352-s":
                return FakeResponse(
                    """
                    <h1>SEC Charges Restaurant-Technology Company Presto
                    Automation for Misleading Statements About AI Product</h1>
                    <p>Jan. 14, 2025</p>
                    <p>The order finds Presto Automation Inc. made materially
                    false and misleading statements about Presto Voice, its
                    flagship artificial intelligence product for drive-thru
                    order taking.</p>
                    """
                )
            if url == "https://www.sec.gov/enforcement-litigation/litigation-releases/lr-26157":
                return FakeResponse(
                    """
                    <h1>Destiny Robotics Corp., et al.</h1>
                    <p>Litigation Release No. 26157 / October 15, 2024</p>
                    <p>The complaint alleges Destiny Robotics Corp. raised
                    investor funds by claiming to develop the world's first
                    humanoid AI robot at-home assistant and companion.</p>
                    """
                )
            if url == "https://www.sec.gov/enforcement-litigation/litigation-releases/lr-25798":
                return FakeResponse(
                    """
                    <h1>Mina Tadrus; Tadrus Capital LLC</h1>
                    <p>Litigation Release No. 25798 / August 2, 2023</p>
                    <p>The complaint alleges Tadrus Capital LLC falsely told
                    investors their funds would be pooled and invested using
                    algorithmic trading that would guarantee steady monthly
                    returns.</p>
                    """
                )
            if url == "https://www.sec.gov/enforcement-litigation/litigation-releases/lr-24854":
                return FakeResponse(
                    """
                    <h1>YouPlus, Inc., et al.</h1>
                    <p>Litigation Release No. 24854 / July 20, 2020</p>
                    <p>The complaint alleges YouPlus, Inc., a startup that
                    purported to have developed a machine-learning tool to
                    analyze online videos, defrauded investors with false
                    revenue and customer claims.</p>
                    """
                )
            raise AssertionError(f"unexpected URL: {url}")

    records = fetch_verified_source_records(
        sources=["sec_ai_enforcement"],
        http_client=FakeHttpClient(),
        limit_per_source=20,
    )

    assert [record.external_id for record in records] == [
        "sec-ai-delphia-usa-inc-2024-03-18",
        "sec-ai-global-predictions-inc-2024-03-18",
        "sec-ai-rimar-capital-usa-inc-2024-10-10",
        "sec-ai-nate-inc-2025-04-11",
        "sec-ai-joonko-2024-06-11",
        "sec-ai-rockwell-capital-management-2024-02-02",
        "sec-ai-qz-asset-management-limited-2024-08-27",
        "sec-ai-qz-global-limited-2024-08-27",
        "sec-ai-pgi-global-2025-04-22",
        "sec-ai-ai-wealth-inc-2025-12-22",
        "sec-ai-profit-connect-wealth-services-inc-2021-07-20",
        "sec-ai-presto-automation-inc-2025-01-14",
        "sec-ai-destiny-robotics-corp-2024-10-15",
        "sec-ai-tadrus-capital-llc-2023-08-02",
        "sec-ai-youplus-inc-2020-07-20",
    ]


def test_fetch_eeoc_ai_enforcement_discovers_newsroom_actions() -> None:
    class FakeResponse:
        def __init__(self, text: str) -> None:
            self.text = text

        def raise_for_status(self) -> None:
            return None

    class FakeHttpClient:
        def get(self, url: str) -> FakeResponse:
            if url == (
                "https://www.eeoc.gov/newsroom/itutorgroup-pay-365000-settle-"
                "eeoc-discriminatory-hiring-suit"
            ):
                return FakeResponse(
                    """
                    <h1>iTutorGroup to Pay $365,000 to Settle EEOC
                    Discriminatory Hiring Suit</h1>
                    <p>Press Release 09-11-2023</p>
                    <p>The EEOC lawsuit alleged iTutorGroup programmed online
                    software to automatically reject older applicants.</p>
                    """
                )
            if url == "https://www.eeoc.gov/newsroom?search=automated%20software":
                return FakeResponse(
                    """
                    <a href="/newsroom/examplecorp-pay-250000-settle-eeoc-
                    automated-hiring-suit">
                    ExampleCorp to Pay $250,000 to Settle EEOC Automated
                    Hiring Software Suit</a>
                    <a href="/newsroom/eeoc-issues-ai-technical-assistance">
                    EEOC Issues AI Technical Assistance Document</a>
                    """
                )
            if "examplecorp-pay" in url:
                return FakeResponse(
                    """
                    <h1>ExampleCorp to Pay $250,000 to Settle EEOC Automated
                    Hiring Software Suit</h1>
                    <p>Press Release 03-14-2025</p>
                    <p>The EEOC announced a settlement with ExampleCorp after
                    alleging its automated hiring software rejected applicants
                    based on a protected characteristic.</p>
                    """
                )
            raise AssertionError(f"unexpected URL: {url}")

    records = fetch_verified_source_records(
        sources=["eeoc_ai_enforcement"],
        http_client=FakeHttpClient(),
        limit_per_source=10,
    )

    assert [record.external_id for record in records] == [
        "eeoc-ai-itutorgroup-2023-09-11",
        "eeoc-ai-examplecorp-2025-03-14",
    ]


def test_fetch_fda_warning_letters_discovers_software_device_letters() -> None:
    class FakeResponse:
        def __init__(self, text: str) -> None:
            self.text = text

        def raise_for_status(self) -> None:
            return None

    class FakeHttpClient:
        def get(self, url: str) -> FakeResponse:
            if url == (
                "https://www.fda.gov/inspections-compliance-enforcement-and-"
                "criminal-investigations/warning-letters/exer-labs-inc-699218-"
                "02102025"
            ):
                return FakeResponse(
                    """
                    <h1>Exer Labs, Inc. MARCS-CMS 699218 — February 10, 2025</h1>
                    <p>WARNING LETTER</p>
                    <p>The firm manufactures Exer Scan. The product uses
                    artificial intelligence algorithms for musculoskeletal
                    assessment and is a medical device. The device is
                    adulterated and misbranded.</p>
                    """
                )
            if url == (
                "https://www.fda.gov/inspections-compliance-enforcement-and-"
                "criminal-investigations/compliance-actions-and-activities/"
                "warning-letters"
            ):
                return FakeResponse(
                    """
                    <table>
                      <tr><td>05/09/2025</td><td>
                        <a href="/inspections-compliance-enforcement-and-
                        criminal-investigations/warning-letters/neurosync-inc-
                        705489-05092025">
                        NeuroSync, Inc.</a></td><td>Medical Devices</td></tr>
                      <tr><td>04/14/2026</td><td>
                        <a href="/inspections-compliance-enforcement-and-
                        criminal-investigations/warning-letters/plain-food-
                        company-711111-04142026">
                        Plain Food Company</a></td><td>Food CGMP</td></tr>
                    </table>
                    """
                )
            if "neurosync" in url:
                return FakeResponse(
                    """
                    <h1>NeuroSync, Inc. MARCS-CMS 705489 — May 09, 2025</h1>
                    <p>WARNING LETTER</p>
                    <p>The FDA determined the firm manufactures EYE-SYNC, a
                    virtual reality headset and tablet computer that uses
                    software to perform eye assessments. The device is
                    adulterated and misbranded.</p>
                    """
                )
            if "plain-food-company" in url:
                return FakeResponse(
                    """
                    <h1>Plain Food Company MARCS-CMS 711111 — April 14, 2026</h1>
                    <p>WARNING LETTER</p>
                    <p>The FDA cited ordinary food CGMP violations with no
                    software, automation, algorithm, or device issue.</p>
                    """
                )
            raise AssertionError(f"unexpected URL: {url}")

    records = fetch_verified_source_records(
        sources=["fda_ai_medical_device_warning_letters"],
        http_client=FakeHttpClient(),
        limit_per_source=10,
    )

    assert [record.external_id for record in records] == [
        "fda-ai-exer-labs-inc-2025-02-10",
        "fda-ai-neurosync-inc-2025-05-09",
    ]


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

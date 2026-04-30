from __future__ import annotations

VALID_IMPORT_CSV = "\n".join(
    [
        (
            "ref_number,incident_id,company,incident_date,incident_topic,"
            "incident_description,mapped_claim,source_links,legitimacy_flag,"
            "confidence_level,notes"
        ),
        (
            "1,inc-openai-001,OpenAI,2023-05-01,legal hallucination,"
            '"ChatGPT-generated fake legal citations were filed in federal court.",,'
            '"https://example.com/court-order | https://example.com/reuters-legal | '
            'https://example.com/stanford-analysis",ACCEPT,high,Strong primary support'
        ),
        (
            "2,inc-school-002,Example School District,"
            '2023-09-14,education failure,'
            '"A school chatbot gave families inaccurate enrollment guidance.",'
            "claim-missing-1,"
            '"https://example.com/district-statement | '
            "https://example.com/local-news | "
            'https://example.com/state-analysis | https://example.com/local-news",'
            "REVIEW,medium,Claim mapping should be ignored when missing"
        ),
        "",
    ]
)

INVALID_IMPORT_CSV = "\n".join(
    [
        (
            "ref_number,incident_id,company,incident_date,incident_topic,"
            "incident_description,mapped_claim,source_links,legitimacy_flag,"
            "confidence_level,notes"
        ),
        (
            "1,inc-bad-001,OpenAI,2023-05-01,legal hallucination,"
            '"This row only has two distinct sources.",,'
            '"https://example.com/court-order | https://example.com/court-order | '
            'https://example.com/reuters-legal",ACCEPT,high,'
        ),
        "",
    ]
)

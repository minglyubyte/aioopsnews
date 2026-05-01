from __future__ import annotations

CATEGORY_AUTONOMOUS_SYSTEMS = "Autonomous Systems"
CATEGORY_HALLUCINATIONS = "Hallucinations"
CATEGORY_JOB_AUTOMATION_FAILS = "Job Automation Fails"
CATEGORY_MISSED_TIMELINES = "Missed Timelines"
CATEGORY_MODEL_GOVERNANCE = "Model Governance"
CATEGORY_PRIVACY_SECURITY = "Privacy/Security"

INCIDENT_CATEGORY_TAXONOMY = (
    CATEGORY_AUTONOMOUS_SYSTEMS,
    CATEGORY_HALLUCINATIONS,
    CATEGORY_JOB_AUTOMATION_FAILS,
    CATEGORY_MISSED_TIMELINES,
    CATEGORY_MODEL_GOVERNANCE,
    CATEGORY_PRIVACY_SECURITY,
)

INCIDENT_CATEGORY_SET = frozenset(INCIDENT_CATEGORY_TAXONOMY)


def normalize_incident_categories(categories: list[str]) -> list[str]:
    normalized_categories: list[str] = []
    seen_categories: set[str] = set()
    for category in categories:
        if category not in INCIDENT_CATEGORY_SET or category in seen_categories:
            continue
        normalized_categories.append(category)
        seen_categories.add(category)
    return normalized_categories

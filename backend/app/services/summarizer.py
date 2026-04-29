from __future__ import annotations


def summarize_incident(*, headline: str, source_summary: str) -> str:
    cleaned_headline = headline.strip().rstrip(".")
    cleaned_summary = " ".join(source_summary.strip().split()).rstrip(".")

    return f"{cleaned_headline}. {cleaned_summary}."

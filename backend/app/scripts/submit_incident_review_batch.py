from __future__ import annotations


def main() -> int:
    print(
        "submit_incident_review_batch is deprecated. "
        "Run python -m app.scripts.run_incident_csv_workflow instead."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from app.scripts import submit_incident_review_batch as submit_script


def test_submit_script_reports_deprecation(capsys) -> None:
    exit_code = submit_script.main()

    assert exit_code == 1
    assert "run_incident_csv_workflow" in capsys.readouterr().out

from __future__ import annotations

from app.scripts import reconcile_incident_review_batch as reconcile_script


def test_reconcile_script_reports_deprecation(capsys) -> None:
    exit_code = reconcile_script.main()

    assert exit_code == 1
    assert "run_incident_csv_workflow" in capsys.readouterr().out

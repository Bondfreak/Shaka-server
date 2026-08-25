from pathlib import Path


def test_diagnostic_projection_contract_name_is_pinned() -> None:
    app = (Path(__file__).resolve().parents[1] / "src/shaka_server/app.py").read_text(encoding="utf-8")
    assert "verified_diagnostic_anchors_with_explicit_candidate_investigation" in app
    assert "scenario_template_not_root_cause_determination" in app

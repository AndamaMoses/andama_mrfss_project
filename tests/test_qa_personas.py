"""Smoke test for the persona QA harness (P2 golden path)."""
from qa.harness import build_scratch_app
from qa.runner import ScenarioRunner
from qa.specs import load_scenario, persona_by_id


def test_p2_golden_path_passes_on_scratch_database(tmp_path):
    app = build_scratch_app(
        tmp_path / "drugshop.db",
        tmp_path / "uploads",
        plan="pro",
        profile="pharmacy_day",
    )

    result = ScenarioRunner(
        app,
        persona_by_id("P2"),
        load_scenario("P2", "P2-J1"),
    ).run()

    assert result.result == "pass", result.findings
    assert all(step.ok for step in result.steps)
    assert result.ux_actions <= result.budget_actions

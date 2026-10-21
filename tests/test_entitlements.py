"""Entitlement service and CLI tests (Phase 1).

The shared ``app_under_test`` fixture seeds the Pro bundle, matching the
grandfathered production installation, so these tests start from a known plan.
"""
import pytest

from drugshop.apps import registry, service
from drugshop.db import execute


def test_fixture_seeds_pro(app_under_test):
    plan = service.current_plan()
    assert plan["bundle"] == "pro"
    assert plan["label"] == "Pro"
    assert plan["bootstrap"] is False
    assert plan["expires_at"] is None
    assert set(plan["apps"]) == set(registry.bundle_apps("pro"))


def test_always_on_dashboard_is_entitled(app_under_test):
    service.set_bundle("core")
    assert service.is_entitled("dashboard") is True


def test_set_bundle_core_revokes_pro_apps(app_under_test):
    result = service.set_bundle("core", actor="tester")

    assert result["added"] == []
    assert result["changed"] == []
    assert result["removed"] == ["finance", "patients"]
    assert service.is_entitled("pos")
    assert service.is_entitled("inventory")
    assert not service.is_entitled("patients")
    assert not service.is_entitled("finance")
    assert service.current_plan()["bundle"] == "core"


def test_reactivating_pro_restores_access_without_data_loss(app_under_test):
    service.set_bundle("core")
    service.set_bundle("pro")

    assert service.is_entitled("patients")
    assert service.is_entitled("finance")
    assert service.current_plan()["bundle"] == "pro"
    # Revoked rows are kept, not deleted, so the install keeps its history.
    rows = {r["app_id"]: r for r in service.entitlement_rows()}
    assert rows["patients"]["status"] == "active"
    assert rows["patients"]["source"] == "cli"


def test_add_alerts_requires_pro(app_under_test):
    service.set_bundle("core")
    with pytest.raises(ValueError, match="requires"):
        service.add_app("alerts")


def test_add_and_remove_alerts(app_under_test):
    service.add_app("alerts", actor="tester")
    assert service.is_entitled("alerts")
    assert service.current_plan()["bundle"] == "growth"

    service.remove_app("alerts", actor="tester")
    assert not service.is_entitled("alerts")
    assert service.current_plan()["bundle"] == "pro"


def test_remove_patients_blocked_while_alerts_active(app_under_test):
    service.add_app("alerts")
    with pytest.raises(ValueError, match="alerts"):
        service.remove_app("patients")


def test_always_on_app_cannot_be_added_or_removed(app_under_test):
    with pytest.raises(ValueError, match="always"):
        service.add_app("dashboard")
    with pytest.raises(ValueError, match="always"):
        service.remove_app("dashboard")


def test_empty_table_is_fail_open(app_under_test):
    execute("DELETE FROM app_entitlements")

    assert service.entitled_app_ids() == set(registry.APPS)
    assert service.is_entitled("patients")
    assert service.current_plan()["bootstrap"] is True
    # Single-app writes must not turn a fail-open install into a one-app plan.
    with pytest.raises(ValueError, match="not initialized"):
        service.add_app("alerts")
    with pytest.raises(ValueError, match="not initialized"):
        service.remove_app("patients")


def test_unknown_bundle_and_app_are_rejected(app_under_test):
    with pytest.raises(ValueError, match="unknown bundle"):
        service.set_bundle("platinum")
    with pytest.raises(ValueError, match="unknown app"):
        service.add_app("payroll")
    with pytest.raises(ValueError, match="unknown app"):
        service.remove_app("payroll")


def test_expiry_is_stored_and_reported(app_under_test):
    service.set_bundle("pro", expires_at="2027-10-21")
    assert service.current_plan()["expires_at"] == "2027-10-21"

    with pytest.raises(ValueError, match="ISO date"):
        service.set_bundle("pro", expires_at="21/10/2027")


def test_events_record_changes(app_under_test):
    service.set_bundle("core", actor="andama", notes="demo downgrade")

    recent = service.events(10)
    assert recent
    actions = {event["action"] for event in recent}
    assert "remove" in actions
    assert any(event["actor"] == "andama" for event in recent)
    assert any("demo downgrade" in event["detail"] for event in recent)


def test_ensure_entitlements_is_idempotent(app_under_test):
    before = service.entitlement_rows()
    result = service.ensure_entitlements("core")

    assert result["seeded"] is False
    assert result["count"] == len(before)
    assert service.current_plan()["bundle"] == "pro"


def test_ensure_entitlements_falls_back_to_pro(app_under_test):
    execute("DELETE FROM app_entitlements")
    result = service.ensure_entitlements("platinum")

    assert result["seeded"] is True
    assert result["bundle"] == "pro"
    assert service.current_plan()["bundle"] == "pro"


def test_ensure_entitlements_seeds_the_legacy_bundle(app_under_test):
    execute("DELETE FROM app_entitlements")
    result = service.ensure_entitlements("legacy")

    assert result["seeded"] is True
    assert result["bundle"] == "legacy"
    assert result["label"] == "Legacy (grandfathered)"
    assert set(service.entitled_app_ids()) == set(registry.gated_app_ids())

    plan = service.current_plan()
    assert plan["bundle"] == "legacy"
    assert plan["label"] == "Legacy (grandfathered)"
    assert service.is_entitled("alerts")
    assert service.is_entitled("tender")


def test_tender_bundle_is_standalone(app_under_test):
    service.set_bundle("tender")

    plan = service.current_plan()
    assert plan["bundle"] == "tender"
    assert service.is_entitled("tender")
    assert not service.is_entitled("pos")
    assert not service.is_entitled("inventory")


def test_cli_plan_show(app_under_test):
    runner = app_under_test.test_cli_runner()
    result = runner.invoke(args=["plan", "show"])

    assert result.exit_code == 0, result.output
    assert "Plan:" in result.output
    assert "Pro" in result.output
    assert "pos" in result.output
    assert "always on" in result.output


def test_cli_plan_set_add_remove(app_under_test):
    runner = app_under_test.test_cli_runner()

    result = runner.invoke(args=["plan", "set", "core", "--actor", "cli-test"])
    assert result.exit_code == 0, result.output
    assert not service.is_entitled("finance")

    result = runner.invoke(args=["plan", "add", "alerts"])
    assert result.exit_code != 0
    assert "requires" in result.output

    assert runner.invoke(args=["plan", "set", "pro"]).exit_code == 0
    assert runner.invoke(args=["plan", "add", "alerts", "--actor", "cli-test"]).exit_code == 0
    assert service.is_entitled("alerts")
    assert runner.invoke(args=["plan", "remove", "alerts"]).exit_code == 0
    assert not service.is_entitled("alerts")


def test_cli_invalid_bundle_fails_cleanly(app_under_test):
    runner = app_under_test.test_cli_runner()
    result = runner.invoke(args=["plan", "set", "platinum"])

    assert result.exit_code != 0
    assert "unknown bundle" in result.output

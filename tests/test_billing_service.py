"""Phase 2 subscription service tests."""
import pytest

from drugshop.apps import service as apps_service
from drugshop.billing import service
from drugshop.billing.catalog import PRICE_BOOK_VERSION
from drugshop.db import q_one


def _activate(**overrides):
    kwargs = {
        "bundle": "pro",
        "customer_name": "Example Pharmacy",
        "contact_name": "Dr. A",
        "contact_phone": "+256700000000",
        "start": "2026-11-05",
        "period_end": "2027-11-05",
        "actor": "Andama",
        "notes": "signed Pro, one year",
    }
    kwargs.update(overrides)
    return service.activate(**kwargs)


def _event_count():
    return q_one("SELECT COUNT(*) AS n FROM billing_events")["n"]


def test_activation_writes_subscription_and_entitlements(app_under_test):
    result = _activate()

    assert result["ok"] is True
    assert result["note"] == "activated"
    subscription = result["subscription"]
    assert subscription["bundle"] == "pro"
    assert subscription["status"] == "active"
    assert subscription["customer_name"] == "Example Pharmacy"
    assert subscription["contact_name"] == "Dr. A"
    assert subscription["contact_phone"] == "+256700000000"
    assert subscription["currency"] == "UGX"
    assert subscription["setup_fee"] == 600_000
    assert subscription["monthly_fee"] == 180_000
    assert subscription["started_on"] == "2026-11-05"
    assert subscription["current_period_start"] == "2026-11-05"
    assert subscription["current_period_end"] == "2027-11-05"
    assert subscription["price_book_version"] == PRICE_BOOK_VERSION

    plan = apps_service.current_plan()
    assert plan["bundle"] == "pro"
    assert plan["expires_at"] == "2027-11-05"
    assert {"pos", "inventory", "patients", "finance"} <= set(plan["apps"])
    assert service.reconciliation()["agrees"] is True

    event = service.subscription_events(1)[0]
    assert event["action"] == "activate"
    assert event["actor"] == "Andama"
    assert "bundle=pro" in event["detail"]
    assert "customer=Example Pharmacy" in event["detail"]
    assert "signed Pro, one year" in event["detail"]


def test_repeating_same_activation_is_noop(app_under_test):
    _activate()
    events_before = _event_count()

    result = _activate()

    assert result["note"] == "already active"
    assert _event_count() == events_before
    assert service.current_subscription()["status"] == "active"


def test_activation_change_updates_the_single_row(app_under_test):
    _activate()

    result = _activate(
        bundle="growth",
        period_end="2027-05-05",
        setup_fee=750_000,
        monthly_fee=230_000,
        override_reason="founder approved Growth upgrade",
    )

    assert result["note"] == "changed"
    subscription = result["subscription"]
    assert subscription["bundle"] == "growth"
    assert subscription["setup_fee"] == 750_000
    assert subscription["monthly_fee"] == 230_000
    assert q_one("SELECT COUNT(*) AS n FROM billing_subscriptions")["n"] == 1
    assert apps_service.current_plan()["bundle"] == "growth"
    event = service.subscription_events(1)[0]
    assert event["action"] == "change"
    assert "founder approved Growth upgrade" in event["detail"]


def test_failed_entitlement_step_leaves_pending_then_retry_works(
    app_under_test, monkeypatch
):
    def fail(*args, **kwargs):
        raise ValueError("simulated entitlement failure")

    monkeypatch.setattr(apps_service, "set_bundle", fail)
    with pytest.raises(service.BillingError, match="remains pending"):
        _activate()

    pending = service.current_subscription()
    assert pending["status"] == "pending"
    assert service.reconciliation()["agrees"] is False
    event = service.subscription_events(1)[0]
    assert event["action"] == "activate_failed"
    assert "simulated entitlement failure" in event["detail"]

    monkeypatch.undo()
    result = _activate()

    assert result["note"] == "activated"
    assert service.current_subscription()["status"] == "active"


def test_legacy_rules_and_grandfathered_record(app_under_test):
    with pytest.raises(service.BillingError, match="requires --grandfathered"):
        service.activate("legacy", customer_name="Onzima")

    with pytest.raises(service.BillingError, match="only valid for legacy"):
        service.activate(
            "pro",
            customer_name="Example",
            start="2026-11-05",
            period_end="2027-11-05",
            grandfathered=True,
        )

    with pytest.raises(service.BillingError, match="do not use --period-end"):
        service.activate(
            "legacy",
            customer_name="Onzima",
            grandfathered=True,
            period_end="2027-11-05",
        )

    result = service.activate(
        "legacy",
        customer_name="Onzima",
        grandfathered=True,
        actor="Andama",
        notes="existing shop",
    )
    subscription = result["subscription"]
    assert result["note"] == "activated"
    assert subscription["status"] == "grandfathered"
    assert subscription["setup_fee"] == 0
    assert subscription["monthly_fee"] == 0
    assert subscription["current_period_start"] is None
    assert subscription["current_period_end"] is None
    assert subscription["price_book_version"] == "legacy"
    assert apps_service.current_plan()["bundle"] == "legacy"
    assert service.reconciliation()["agrees"] is True

    events_before = _event_count()
    again = service.activate(
        "legacy",
        customer_name="Onzima",
        grandfathered=True,
        actor="Andama",
        notes="existing shop",
    )
    assert again["note"] == "already grandfathered"
    assert _event_count() == events_before

    with pytest.raises(service.BillingError, match="do not renew"):
        service.renew("2027-11-05")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"bundle": "platinum"}, "unknown bundle"),
        ({"start": "not-a-date"}, "start must be an ISO date"),
        ({"period_end": "2027-13-01"}, "period-end must be an ISO date"),
        ({"period_end": "2026-11-04"}, "period-end must be after start"),
        ({"period_end": None}, "--period-end is required"),
        ({"setup_fee": -1}, "setup fee cannot be negative"),
        ({"monthly_fee": -1}, "monthly fee cannot be negative"),
        ({"setup_fee": 100.5}, "setup fee must be a whole number"),
        ({"currency": "USD"}, "must use UGX"),
        ({"customer_name": "   "}, "customer is required"),
    ],
)
def test_activation_validation_errors(app_under_test, overrides, message):
    with pytest.raises(service.BillingError, match=message):
        _activate(**overrides)


def test_setup_discount_cap_is_enforced(app_under_test):
    with pytest.raises(service.BillingError, match="below the allowed minimum"):
        _activate(setup_fee=499_999)

    result = _activate(
        setup_fee=500_000,
        override_reason="founder approved 100000 setup discount",
    )
    assert result["subscription"]["setup_fee"] == 500_000
    assert "founder approved 100000" in service.subscription_events(1)[0]["detail"]


def test_fee_override_requires_reason(app_under_test):
    with pytest.raises(service.BillingError, match="requires --override-reason"):
        _activate(setup_fee=500_000)

    with pytest.raises(service.BillingError, match="requires --override-reason"):
        _activate(monthly_fee=200_000)


def test_monthly_fee_cannot_be_discounted(app_under_test):
    with pytest.raises(service.BillingError, match="cannot be below"):
        _activate(monthly_fee=179_999, override_reason="discount requested")

    result = _activate(
        monthly_fee=200_000,
        override_reason="includes extra onsite support",
    )
    assert result["subscription"]["monthly_fee"] == 200_000


def test_status_transitions_and_event_notes(app_under_test):
    _activate()

    past_due = service.set_status(
        "past_due", actor="Andama", notes="November invoice unpaid"
    )
    assert past_due["subscription"]["status"] == "past_due"
    assert apps_service.current_plan()["bundle"] == "pro"
    event = service.subscription_events(1)[0]
    assert event["action"] == "status"
    assert event["actor"] == "Andama"
    assert "from active to past_due" in event["detail"]
    assert "November invoice unpaid" in event["detail"]

    assert service.set_status("active", actor="Andama")["subscription"]["status"] == "active"
    assert (
        service.set_status("cancelled", actor="Andama")["subscription"]["status"]
        == "cancelled"
    )

    with pytest.raises(service.BillingError, match="reactivated"):
        service.set_status("active")
    with pytest.raises(service.BillingError, match="unknown status"):
        service.set_status("bogus")
    with pytest.raises(service.BillingError, match="use `revenue activate legacy"):
        service.set_status("grandfathered")


def test_status_same_value_is_noop(app_under_test):
    _activate()
    events_before = _event_count()

    result = service.set_status("active", actor="Andama")

    assert result["note"] == "unchanged"
    assert _event_count() == events_before


def test_pending_status_cannot_be_forced_active(app_under_test, monkeypatch):
    def fail(*args, **kwargs):
        raise ValueError("simulated entitlement failure")

    monkeypatch.setattr(apps_service, "set_bundle", fail)
    with pytest.raises(service.BillingError):
        _activate()

    with pytest.raises(service.BillingError, match="through activation"):
        service.set_status("active")


def test_renew_extends_period_and_entitlements(app_under_test):
    _activate()

    result = service.renew("2028-11-05", actor="Andama", notes="annual renewal")

    subscription = result["subscription"]
    assert subscription["status"] == "active"
    assert subscription["current_period_start"] == "2027-11-05"
    assert subscription["current_period_end"] == "2028-11-05"
    assert apps_service.current_plan()["expires_at"] == "2028-11-05"
    assert service.reconciliation()["agrees"] is True
    event = service.subscription_events(1)[0]
    assert event["action"] == "renew"
    assert "2026-11-05..2027-11-05" in event["detail"]
    assert "2027-11-05..2028-11-05" in event["detail"]
    assert "annual renewal" in event["detail"]

    with pytest.raises(service.BillingError, match="must be after 2028-11-05"):
        service.renew("2028-11-05")
    with pytest.raises(service.BillingError, match="must be after"):
        service.renew("2028-01-01")


def test_renew_reactivates_past_due(app_under_test):
    _activate()
    service.set_status("past_due")

    result = service.renew("2028-11-05", actor="Andama")

    assert result["subscription"]["status"] == "active"


def test_renew_cancelled_is_refused(app_under_test):
    _activate()
    service.set_status("cancelled")

    with pytest.raises(service.BillingError, match="reactivated before renewal"):
        service.renew("2028-11-05")


def test_reconciliation_detects_entitlement_drift(app_under_test):
    _activate()
    apps_service.set_bundle("core")

    check = service.reconciliation()

    assert check["agrees"] is False
    assert check["plan"]["bundle"] == "core"
    assert check["subscription"]["bundle"] == "pro"


def test_actions_require_an_existing_subscription(app_under_test):
    assert service.current_subscription() is None
    with pytest.raises(service.BillingError, match="no subscription recorded"):
        service.renew("2027-11-05")
    with pytest.raises(service.BillingError, match="no subscription recorded"):
        service.set_status("active")


def test_events_have_actor_and_reason_for_every_change(app_under_test):
    _activate(
        setup_fee=500_000,
        override_reason="founder approved setup discount",
    )
    service.set_status("past_due", actor="Andama", notes="invoice unpaid")
    service.renew("2028-11-05", actor="Andama", notes="paid and renewed")

    events = service.subscription_events(10)
    actions = {event["action"] for event in events}
    assert {"activate", "status", "renew"} <= actions
    for event in events:
        assert event["actor"] == "Andama"
        assert event["detail"]
    by_action = {event["action"]: event for event in events}
    assert "founder approved setup discount" in by_action["activate"]["detail"]
    assert "invoice unpaid" in by_action["status"]["detail"]
    assert "paid and renewed" in by_action["renew"]["detail"]

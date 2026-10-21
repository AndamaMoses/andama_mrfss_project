"""Registry unit tests for the app catalog (Phase 1)."""
from drugshop.apps import registry


def test_bundles_reference_known_apps():
    for bundle_id, bundle in registry.BUNDLES.items():
        assert bundle["apps"], bundle_id
        assert bundle["label"]
        for app_id in bundle["apps"]:
            assert app_id in registry.APPS, (bundle_id, app_id)


def test_core_pro_and_growth_membership():
    assert set(registry.bundle_apps("core")) == {"pos", "inventory"}
    assert set(registry.bundle_apps("pro")) == {
        "pos", "inventory", "patients", "finance",
    }
    assert set(registry.bundle_apps("growth")) == {
        "pos", "inventory", "patients", "finance", "alerts",
    }
    assert registry.bundle_apps("tender") == ["tender"]


def test_every_bundle_satisfies_its_app_dependencies():
    for bundle_id in registry.BUNDLES:
        active = set(registry.bundle_apps(bundle_id))
        for app_id in active:
            missing = set(registry.requires_of(app_id)) - active
            assert not missing, (bundle_id, app_id, missing)


def test_always_on_apps_are_not_sold_in_bundles():
    for bundle in registry.BUNDLES.values():
        for app_id in bundle["apps"]:
            assert registry.APPS[app_id]["always_on"] is False


def test_legacy_bundle_contains_every_current_gated_app():
    assert set(registry.bundle_apps("legacy")) == set(registry.gated_app_ids())


def test_app_order_is_stable_and_unique():
    ids = registry.app_ids()
    assert len(ids) == len(set(ids))
    orders = [registry.APPS[app_id]["order"] for app_id in ids]
    assert orders == sorted(orders)


def test_detect_bundle():
    assert registry.detect_bundle(set()) == "none"
    assert registry.detect_bundle({"tender"}) == "tender"
    assert registry.detect_bundle(set(registry.bundle_apps("core"))) == "core"
    assert registry.detect_bundle(set(registry.bundle_apps("pro"))) == "pro"
    assert registry.detect_bundle(set(registry.bundle_apps("growth"))) == "growth"
    assert registry.detect_bundle(set(registry.gated_app_ids())) == "legacy"
    assert registry.detect_bundle({"pos"}) == "custom"
    assert registry.detect_bundle({"tender", "pos", "inventory"}) == "core"


def test_unknown_bundle_is_safe():
    assert registry.bundle_apps("platinum") == []
    assert registry.bundle_label("platinum") == "Custom"
    assert registry.requires_of("platinum") == []


def test_blueprint_maps_do_not_overlap_and_reference_known_apps():
    assert not (set(registry.BLUEPRINT_APPS) & set(registry.ALWAYS_ON_BLUEPRINTS))
    for app_id in registry.BLUEPRINT_APPS.values():
        assert app_id in registry.APPS
    for app_id in registry.ENDPOINT_APPS.values():
        assert app_id in registry.APPS


def test_gated_apps_exclude_always_on():
    assert "dashboard" not in registry.gated_app_ids()
    assert set(registry.bundle_apps("pro")) <= set(registry.gated_app_ids())

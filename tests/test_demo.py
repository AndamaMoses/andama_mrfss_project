"""Synthetic demo data used by the public Render preview."""
from drugshop.db import execute, q_one


def test_demo_seed_populates_a_fresh_database(app_under_test):
    from drugshop.demo import seed_demo

    result = seed_demo()
    assert result == {"seeded": True, "products": 10, "sales": 9, "patients": 3}
    assert q_one("SELECT COUNT(*) c FROM products")["c"] == 10
    assert q_one("SELECT COUNT(*) c FROM sales")["c"] == 9
    assert q_one("SELECT COUNT(*) c FROM sale_batches")["c"] == 9
    assert q_one("SELECT COUNT(*) c FROM patients")["c"] == 3
    assert q_one("SELECT COUNT(*) c FROM customers")["c"] == 2
    assert q_one("SELECT COUNT(*) c FROM expenses")["c"] == 2
    assert q_one("SELECT COUNT(*) c FROM batches WHERE qty_remaining<0")["c"] == 0
    assert q_one("SELECT COUNT(*) c FROM sales WHERE payment_method='CREDIT'")["c"] == 2


def test_demo_data_appears_on_the_dashboard(admin_client):
    from drugshop.demo import seed_demo

    seed_demo()
    body = admin_client.get("/api/dashboard").get_json()
    assert body["sales_today"]["count"] == 6
    assert body["sales_today"]["total"] == 6200
    assert body["credit_owed_total"] == 1300
    assert body["low_stock_count"] == 2
    assert body["expiry_counts"]["expired"] == 1
    assert body["expiry_counts"]["critical_30"] == 3
    assert body["refill"]["due_count"] == 2


def test_demo_seed_is_idempotent(app_under_test):
    from drugshop.demo import seed_demo

    seed_demo()
    again = seed_demo()
    assert again == {"seeded": False, "reason": "products already exist"}
    assert q_one("SELECT COUNT(*) c FROM products")["c"] == 10
    assert q_one("SELECT COUNT(*) c FROM sales")["c"] == 9


def test_demo_seed_refuses_to_touch_an_existing_catalogue(app_under_test):
    from drugshop.demo import seed_demo

    execute("INSERT INTO products(name) VALUES('Real medicine')")
    result = seed_demo()
    assert result["seeded"] is False
    assert q_one("SELECT COUNT(*) c FROM products")["c"] == 1

def seed(client):
    assert client.post("/api/seed").status_code == 200


def test_dashboard_aggregates(admin_client):
    seed(admin_client)
    d = admin_client.get("/api/dashboard").get_json()
    assert d["sales_today"]["total"] == 9000
    assert d["sales_today"]["count"] == 2
    assert d["low_stock_count"] >= 1
    assert d["expiry_counts"]["expired"] >= 1
    assert d["expiry_counts"]["critical_30"] >= 2
    assert d["refill"]["due_count"] >= 2


def test_my_sales_filtered_by_staff(admin_client):
    seed(admin_client)
    assert admin_client.get("/api/my-sales").get_json()["count"] == 0
    prods = admin_client.get("/api/products").get_json()
    admin_client.post("/api/sales", json={
        "product_id": prods[0]["id"], "qty": 1, "payment_method": "CASH",
        "served_by": "Charles Onzima",
    })
    assert admin_client.get("/api/my-sales").get_json()["count"] == 1


def test_staff_activity_admin_only(admin_client, staff_client):
    seed(admin_client)
    assert staff_client.get("/api/staff-activity").status_code == 403
    r = admin_client.get("/api/staff-activity")
    assert r.status_code == 200
    assert "sales_by_staff" in r.get_json()


def test_dashboard_credit_owed_matches_ledger(admin_client):
    seed(admin_client)
    prods = admin_client.get("/api/products").get_json()
    r = admin_client.post("/api/sales/cart", json={
        "items": [{"product_id": prods[0]["id"], "qty": 1}],
        "payment_method": "CREDIT", "customer_name": "Dash Credit",
    })
    assert r.status_code == 201
    ref = r.get_json()["receipt_ref"]
    sale = next(s for s in admin_client.get("/api/sales").get_json() if s["receipt_ref"] == ref)
    assert admin_client.post(f"/api/credit/{sale['id']}/pay", json={
        "amount": sale["total"] / 3,
    }).status_code == 201

    ledger = admin_client.get("/api/credit").get_json()
    dash = admin_client.get("/api/dashboard").get_json()
    assert dash["credit_owed_total"] == ledger["total_owed"]

    assert admin_client.post(f"/api/credit/{sale['id']}/pay", json={
        "amount": ledger["total_owed"],
    }).status_code == 201
    assert admin_client.get("/api/dashboard").get_json()["credit_owed_total"] == 0


def test_low_stock_alert_payload(admin_client):
    seed(admin_client)
    a = admin_client.get("/api/alerts/low-stock").get_json()
    assert a["count"] >= 1
    item = a["items"][0]
    assert "LOW STOCK" in item["sms_text"]
    assert item["suggested_order"] >= 0


def test_sms_simulated_and_logged(admin_client):
    r = admin_client.post("/api/alerts/send-sms", json={
        "to": "0776102744", "message": "Hello test", "channel": "SMS",
    })
    assert r.status_code == 201
    assert r.get_json()["status"] == "SIMULATED"
    log = admin_client.get("/api/alerts/log").get_json()
    assert log[0]["to_phone"] == "256776102744"
    assert log[0]["status"] == "SIMULATED"


def test_whatsapp_channel_link(admin_client):
    r = admin_client.post("/api/alerts/send-sms", json={
        "to": "0776102744", "message": "hi", "channel": "WHATSAPP",
    })
    assert r.status_code == 201
    assert r.get_json()["status"] == "WHATSAPP_LINK"


def test_sms_requires_to_and_message(admin_client):
    assert admin_client.post("/api/alerts/send-sms", json={}).status_code == 400


def test_sms_rejects_non_string_to_and_message(admin_client):
    assert admin_client.post("/api/alerts/send-sms", json={
        "to": 776102744, "message": "hi",
    }).status_code == 400
    assert admin_client.post("/api/alerts/send-sms", json={
        "to": "0776102744", "message": 123,
    }).status_code == 400
    assert admin_client.get("/api/alerts/log").get_json() == []


def test_sms_uses_manager_phone_when_to_omitted(admin_client):
    assert admin_client.post("/api/settings", json={"manager_phone": "0771234567"}).status_code == 200
    r = admin_client.post("/api/alerts/send-sms", json={"message": "Alert"})
    assert r.status_code == 201
    log = admin_client.get("/api/alerts/log").get_json()
    assert log[0]["to_phone"] == "256771234567"


def test_sms_failed_status_502(admin_client, monkeypatch):
    import drugshop.notifications.routes as nroutes
    monkeypatch.setattr(nroutes, "send_sms_via_gateway", lambda to, msg: ("FAILED", "boom"))
    r = admin_client.post("/api/alerts/send-sms", json={"to": "0776102744", "message": "x"})
    assert r.status_code == 502
    assert r.get_json()["status"] == "FAILED"


def test_settings_roundtrip(admin_client):
    r = admin_client.post("/api/settings", json={"shop_name": "Test Shop", "manager_phone": "0771234567"})
    assert r.status_code == 200
    s = admin_client.get("/api/settings").get_json()
    assert s["shop_name"] == "Test Shop"
    assert s["manager_phone"] == "0771234567"
    assert s["shop_branch"] == "Kireka"


def test_seed_is_idempotent(admin_client):
    assert admin_client.post("/api/seed").get_json()["note"] == "demo data loaded"
    r2 = admin_client.post("/api/seed")
    assert r2.status_code == 200
    assert r2.get_json()["note"] == "already seeded"


def test_seed_requires_admin(app_under_test, staff_client, admin_client):
    anonymous = app_under_test.test_client()
    assert anonymous.post("/api/seed").status_code == 401
    assert staff_client.post("/api/seed").status_code == 403
    assert admin_client.post("/api/seed").status_code == 200


def test_settings_write_requires_admin(staff_client, admin_client):
    assert staff_client.get("/api/settings").status_code == 200
    assert staff_client.post("/api/settings", json={"shop_name": "Hacked"}).status_code == 403
    assert admin_client.get("/api/settings").get_json()["shop_name"] == "Onzima Charles Drug Shop"
    assert admin_client.post("/api/settings", json={"shop_name": "Test Shop"}).status_code == 200
    assert admin_client.get("/api/settings").get_json()["shop_name"] == "Test Shop"


def test_seed_after_wipe_uses_new_batch_ids(admin_client):
    from drugshop.db import get_db

    seed(admin_client)
    db = get_db()
    for table in ("credit_payments", "sale_batches", "sales", "patients", "batches", "products"):
        db.execute(f"DELETE FROM {table}")
    db.commit()
    db.close()

    r = admin_client.post("/api/seed")
    assert r.status_code == 200
    assert r.get_json()["note"] == "demo data loaded"
    prods = {p["name"]: p for p in admin_client.get("/api/products").get_json()}
    assert prods["Amoxicillin 500mg"]["stock_on_hand"] == 86
    assert prods["Paracetamol 500mg"]["stock_on_hand"] == 190


def test_settings_rejects_non_object_body(admin_client):
    r = admin_client.post("/api/settings", json=[1])
    assert r.status_code == 400
    assert admin_client.get("/api/settings").get_json()["shop_name"] == "Onzima Charles Drug Shop"


def test_users_admin_management(admin_client, staff_client):
    assert staff_client.get("/api/users").status_code == 403
    r = admin_client.post("/api/users", json={
        "username": "newstaff", "password": "pass1234",
        "role": "attendant", "display_name": "New Staff",
    })
    assert r.status_code == 201
    rows = admin_client.get("/api/users").get_json()
    uid = next(u["id"] for u in rows if u["username"] == "newstaff")
    assert admin_client.delete(f"/api/users/{uid}").status_code == 200


def test_admin_cannot_delete_self(admin_client):
    me = admin_client.get("/api/me").get_json()
    r = admin_client.delete(f"/api/users/{me['id']}")
    assert r.status_code == 400


def test_export_sales_csv(admin_client):
    seed(admin_client)
    r = admin_client.get("/api/export/sales")
    assert r.status_code == 200
    assert r.mimetype == "text/csv"
    assert b"receipt" in r.data


def test_export_unknown_404(admin_client):
    assert admin_client.get("/api/export/banana").status_code == 404


def test_export_stock_and_patients_csv(admin_client):
    seed(admin_client)
    r = admin_client.get("/api/export/stock")
    assert r.status_code == 200
    assert b"on_hand" in r.data
    r2 = admin_client.get("/api/export/patients")
    assert r2.status_code == 200
    assert b"cycle_days" in r2.data


def test_backup_download(admin_client):
    from drugshop.db import db_path

    seed(admin_client)
    r = admin_client.get("/api/backup")
    assert r.status_code == 200
    assert r.headers["Content-Disposition"].startswith("attachment")
    with open(db_path(), "rb") as fh:
        assert r.data == fh.read()

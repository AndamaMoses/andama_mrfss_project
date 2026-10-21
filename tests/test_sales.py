from datetime import date, timedelta


def seed(client):
    assert client.post("/api/seed").status_code == 200


def get_product(client, name):
    return next(p for p in client.get("/api/products").get_json() if p["name"] == name)


def test_fefo_consumes_earliest_expiry_batches_first(admin_client):
    """Selling across batches must consume earliest-expiry stock first."""
    early_exp = (date.today() + timedelta(days=90)).isoformat()
    late_exp = (date.today() + timedelta(days=400)).isoformat()
    pid = admin_client.post("/api/products", json={
        "name": "FEFO Drug", "price_buy": 50, "price_sell": 100,
    }).get_json()["id"]
    admin_client.post("/api/batches", json={
        "product_id": pid, "qty_received": 10, "expiry_date": late_exp, "batch_no": "LATE",
    })
    early_id = admin_client.post("/api/batches", json={
        "product_id": pid, "qty_received": 5, "expiry_date": early_exp, "batch_no": "EARLY",
    }).get_json()["id"]

    r = admin_client.post("/api/sales", json={
        "product_id": pid, "qty": 8, "payment_method": "CASH",
    })
    assert r.status_code == 201
    sale = next(s for s in admin_client.get("/api/sales").get_json() if s["id"] == r.get_json()["id"])
    assert sale["batch_id"] == early_id

    remaining = {
        b["batch_no"]: b["qty_remaining"]
        for b in admin_client.get("/api/batches").get_json() if b["product_id"] == pid
    }
    assert remaining == {"EARLY": 0, "LATE": 7}


def test_void_cross_batch_sale_restores_every_batch(admin_client):
    """Voiding a sale that spanned batches must restore each batch's share."""
    early_exp = (date.today() + timedelta(days=90)).isoformat()
    late_exp = (date.today() + timedelta(days=400)).isoformat()
    pid = admin_client.post("/api/products", json={
        "name": "Void Drug", "price_buy": 50, "price_sell": 100,
    }).get_json()["id"]
    admin_client.post("/api/batches", json={
        "product_id": pid, "qty_received": 10, "expiry_date": late_exp, "batch_no": "LATE",
    })
    admin_client.post("/api/batches", json={
        "product_id": pid, "qty_received": 5, "expiry_date": early_exp, "batch_no": "EARLY",
    })
    sid = admin_client.post("/api/sales", json={
        "product_id": pid, "qty": 8, "payment_method": "CASH",
    }).get_json()["id"]

    r = admin_client.delete(f"/api/sales/{sid}")
    assert r.status_code == 200
    assert r.get_json()["restored"] == 8
    remaining = {
        b["batch_no"]: b["qty_remaining"]
        for b in admin_client.get("/api/batches").get_json() if b["product_id"] == pid
    }
    assert remaining == {"EARLY": 5, "LATE": 10}


def test_single_sale_creates_receipt_and_decrements_stock(admin_client):
    seed(admin_client)
    para = get_product(admin_client, "Paracetamol 500mg")
    before = para["stock_on_hand"]
    r = admin_client.post("/api/sales", json={
        "product_id": para["id"], "qty": 5, "payment_method": "CASH", "served_by": "Tester",
    })
    assert r.status_code == 201
    j = r.get_json()
    assert j["receipt_ref"].startswith("R-")
    assert j["total"] == 5 * 200
    after = get_product(admin_client, "Paracetamol 500mg")["stock_on_hand"]
    assert after == before - 5


def test_sale_insufficient_stock_400(admin_client):
    seed(admin_client)
    para = get_product(admin_client, "Paracetamol 500mg")
    r = admin_client.post("/api/sales", json={"product_id": para["id"], "qty": 99999, "payment_method": "CASH"})
    assert r.status_code == 400
    assert "Insufficient" in r.get_json()["error"]


def test_sale_non_positive_qty_rejected(admin_client):
    seed(admin_client)
    para = get_product(admin_client, "Paracetamol 500mg")
    for qty in (0, -2):
        r = admin_client.post("/api/sales", json={
            "product_id": para["id"], "qty": qty, "payment_method": "CASH",
        })
        assert r.status_code == 400
        assert "positive" in r.get_json()["error"]
    assert get_product(admin_client, "Paracetamol 500mg")["stock_on_hand"] == para["stock_on_hand"]


def test_cart_insufficient_stock_rolls_back_all_lines(admin_client):
    """A failed line must undo the stock and sale rows written for earlier lines."""
    seed(admin_client)
    para = get_product(admin_client, "Paracetamol 500mg")
    before = para["stock_on_hand"]
    r = admin_client.post("/api/sales/cart", json={
        "items": [
            {"product_id": para["id"], "qty": 1},
            {"product_id": para["id"], "qty": 99999},
        ],
        "payment_method": "CASH",
    })
    assert r.status_code == 400
    assert "Insufficient" in r.get_json()["error"]
    assert get_product(admin_client, "Paracetamol 500mg")["stock_on_hand"] == before
    assert len(admin_client.get("/api/sales").get_json()) == 2


def test_receipt_refs_increment_within_day(admin_client):
    seed(admin_client)
    para = get_product(admin_client, "Paracetamol 500mg")
    refs = [
        admin_client.post("/api/sales", json={
            "product_id": para["id"], "qty": 1, "payment_method": "CASH",
        }).get_json()["receipt_ref"]
        for _ in range(2)
    ]
    assert refs[0] != refs[1]
    assert int(refs[1].rsplit("-", 1)[1]) == int(refs[0].rsplit("-", 1)[1]) + 1


def test_sale_registers_customer_with_phone(admin_client):
    from drugshop.db import q_one

    seed(admin_client)
    para = get_product(admin_client, "Paracetamol 500mg")
    r = admin_client.post("/api/sales", json={
        "product_id": para["id"], "qty": 1, "payment_method": "CASH",
        "customer_name": "Auto Buyer", "customer_phone": "0772 123 456",
    })
    assert r.status_code == 201
    row = q_one("SELECT * FROM customers WHERE phone_digits=?", ("256772123456",))
    assert row is not None
    assert row["name"] == "Auto Buyer"


def test_bad_payment_method_rejected(admin_client):
    seed(admin_client)
    para = get_product(admin_client, "Paracetamol 500mg")
    r = admin_client.post("/api/sales", json={"product_id": para["id"], "qty": 1, "payment_method": "BITCOIN"})
    assert r.status_code == 400


def test_cart_sale_one_receipt_multiple_lines(admin_client):
    seed(admin_client)
    prods = admin_client.get("/api/products").get_json()
    items = [
        {"product_id": prods[0]["id"], "qty": 2},
        {"product_id": prods[1]["id"], "qty": 1},
    ]
    r = admin_client.post("/api/sales/cart", json={
        "items": items, "payment_method": "MTN_MOMO",
        "customer_name": "Buyer One", "customer_phone": "0772000111",
    })
    assert r.status_code == 201
    j = r.get_json()
    assert j["lines"] == 2
    receipt = admin_client.get(f"/api/receipts/{j['receipt_ref']}").get_json()
    assert len(receipt["lines"]) == 2
    assert receipt["total"] == j["total"]
    assert receipt["payment_method"] == "MTN_MOMO"


def test_cart_empty_rejected(admin_client):
    r = admin_client.post("/api/sales/cart", json={"items": []})
    assert r.status_code == 400


def test_void_sale_restores_stock_admin_only(admin_client, staff_client):
    seed(admin_client)
    para = get_product(admin_client, "Paracetamol 500mg")
    sid = admin_client.post("/api/sales", json={
        "product_id": para["id"], "qty": 5, "payment_method": "CASH",
    }).get_json()["id"]
    before = get_product(admin_client, "Paracetamol 500mg")["stock_on_hand"]
    assert staff_client.delete(f"/api/sales/{sid}").status_code == 403
    assert admin_client.delete(f"/api/sales/{sid}").status_code == 200
    after = get_product(admin_client, "Paracetamol 500mg")["stock_on_hand"]
    assert after == before + 5


def test_day_report_summary(admin_client):
    seed(admin_client)
    d = admin_client.get("/api/sales/day-report").get_json()
    assert d["summary"]["total"] == 9000
    assert d["summary"]["by_method"]["CASH"] == 2000
    assert d["summary"]["by_method"]["MTN_MOMO"] == 7000
    assert d["summary"]["count"] == 2


def test_receipt_by_ref_not_found(admin_client):
    assert admin_client.get("/api/receipts/R-00000000-9999").status_code == 404


def test_sales_list_for_day(admin_client):
    seed(admin_client)
    para = get_product(admin_client, "Paracetamol 500mg")
    ref = admin_client.post("/api/sales", json={
        "product_id": para["id"], "qty": 2, "payment_method": "CASH",
    }).get_json()["receipt_ref"]
    rows = admin_client.get("/api/sales").get_json()
    assert any(r["receipt_ref"] == ref for r in rows)


def test_receipt_by_sale_id(admin_client):
    seed(admin_client)
    para = get_product(admin_client, "Paracetamol 500mg")
    sid = admin_client.post("/api/sales", json={
        "product_id": para["id"], "qty": 1, "payment_method": "CASH",
    }).get_json()["id"]
    r = admin_client.get(f"/api/sales/{sid}/receipt")
    assert r.status_code == 200
    j = r.get_json()
    assert j["receipt_no"] == f"R-{sid:06d}"
    assert j["sale"]["id"] == sid
    assert j["sale"]["product_name"] == "Paracetamol 500mg"


def test_cart_credit_requires_customer_name(admin_client):
    seed(admin_client)
    prods = admin_client.get("/api/products").get_json()
    r = admin_client.post("/api/sales/cart", json={
        "items": [{"product_id": prods[0]["id"], "qty": 1}], "payment_method": "CREDIT",
    })
    assert r.status_code == 400
    assert "customer name" in r.get_json()["error"]

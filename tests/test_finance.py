from datetime import date


def seed(client):
    assert client.post("/api/seed").status_code == 200


def make_credit_sale(client):
    prods = client.get("/api/products").get_json()
    r = client.post("/api/sales/cart", json={
        "items": [{"product_id": prods[0]["id"], "qty": 2}],
        "payment_method": "CREDIT",
        "customer_name": "Credit Guy", "customer_phone": "0788111222",
    })
    assert r.status_code == 201
    sales = client.get("/api/sales").get_json()
    return next(s for s in sales if s["payment_method"] == "CREDIT")


def test_credit_sale_requires_customer_name(admin_client):
    seed(admin_client)
    prods = admin_client.get("/api/products").get_json()
    r = admin_client.post("/api/sales/cart", json={
        "items": [{"product_id": prods[0]["id"], "qty": 1}], "payment_method": "CREDIT",
    })
    assert r.status_code == 400


def test_credit_ledger_partial_pay_and_overpay_guard(admin_client):
    seed(admin_client)
    sale = make_credit_sale(admin_client)
    cred = admin_client.get("/api/credit").get_json()
    assert cred["count"] == 1
    assert cred["total_owed"] == sale["total"]

    pay = admin_client.post(f"/api/credit/{sale['id']}/pay", json={"amount": 100})
    assert pay.status_code == 201
    assert pay.get_json()["balance"] == sale["total"] - 100

    over = admin_client.post(f"/api/credit/{sale['id']}/pay", json={"amount": sale["total"]})
    assert over.status_code == 400
    assert "overpayment" in over.get_json()["error"].lower()


def test_credit_pay_validation(admin_client):
    seed(admin_client)
    sale = make_credit_sale(admin_client)
    assert admin_client.post(f"/api/credit/{sale['id']}/pay", json={"amount": -5}).status_code == 400
    assert admin_client.post(f"/api/credit/{sale['id']}/pay", json={"amount": "abc"}).status_code == 400
    assert admin_client.post("/api/credit/99999/pay", json={"amount": 100}).status_code == 404


def test_credit_pay_rejects_non_finite_amount(admin_client):
    seed(admin_client)
    sale = make_credit_sale(admin_client)
    for amount in ("nan", "inf", "-inf", float("nan")):
        r = admin_client.post(f"/api/credit/{sale['id']}/pay", json={"amount": amount})
        assert r.status_code == 400
    cred = admin_client.get("/api/credit").get_json()
    assert cred["total_owed"] == sale["total"]


def test_customer_auto_registered_with_stats(admin_client):
    seed(admin_client)
    make_credit_sale(admin_client)
    rows = admin_client.get("/api/customers?q=Credit").get_json()
    assert rows
    guy = rows[0]
    assert guy["name"] == "Credit Guy"
    assert guy["visits"] == 1
    assert guy["owed"] > 0
    assert guy["wa_link"] == "https://wa.me/256788111222"


def test_customer_manual_create(admin_client):
    r = admin_client.post("/api/customers", json={"name": "Walk In", "phone": "0700000000", "notes": "vip"})
    assert r.status_code == 201
    rows = admin_client.get("/api/customers?q=Walk").get_json()
    assert rows
    assert rows[0]["name"] == "Walk In"
    assert rows[0]["notes"] == "vip"


def test_customer_owed_ignores_phoneless_credit_sales_for_others(admin_client):
    seed(admin_client)
    assert admin_client.post("/api/customers", json={"name": "No Phone Client"}).status_code == 201
    prods = admin_client.get("/api/products").get_json()
    other = admin_client.post("/api/sales/cart", json={
        "items": [{"product_id": prods[0]["id"], "qty": 1}],
        "payment_method": "CREDIT", "customer_name": "Other Credit Buyer",
    })
    assert other.status_code == 201

    rows = admin_client.get("/api/customers?q=No Phone").get_json()
    assert rows and rows[0]["name"] == "No Phone Client"
    assert rows[0]["owed"] == 0

    own = admin_client.post("/api/sales/cart", json={
        "items": [{"product_id": prods[1]["id"], "qty": 1}],
        "payment_method": "CREDIT", "customer_name": "No Phone Client",
    })
    assert own.status_code == 201
    rows = admin_client.get("/api/customers?q=No Phone").get_json()
    assert rows[0]["owed"] == own.get_json()["total"]


def test_customer_create_requires_name_or_phone(admin_client):
    assert admin_client.post("/api/customers", json={}).status_code == 400


def test_reconciliation_calculate_save_states(admin_client):
    seed(admin_client)
    calc = admin_client.get("/api/reconciliation/calculate").get_json()
    assert calc["expected_cash"] == 2000
    assert calc["expected_mtn"] == 7000
    assert calc["expected_airtel"] == 0

    r = admin_client.post("/api/reconciliation", json={
        "rec_date": calc["date"], "counted_cash": 2000, "counted_mtn": 7000, "counted_airtel": 0,
    })
    assert r.get_json()["status"] == "BALANCED"

    r2 = admin_client.post("/api/reconciliation", json={
        "rec_date": calc["date"], "counted_cash": 1900, "counted_mtn": 7000, "counted_airtel": 0,
    })
    assert r2.get_json()["status"] == "SHORTAGE"
    assert round(r2.get_json()["difference"], 2) == -100.0

    rows = admin_client.get("/api/reconciliation").get_json()
    saved = next(x for x in rows if x["rec_date"] == calc["date"])
    assert saved["status"] == "SHORTAGE"
    assert admin_client.delete(f"/api/reconciliation/{calc['date']}").status_code == 200


def test_reconciliation_rejects_non_numeric_counted_amounts(admin_client):
    r = admin_client.post("/api/reconciliation", json={"counted_cash": "abc"})
    assert r.status_code == 400
    r = admin_client.post("/api/reconciliation", json={"counted_mtn": None})
    assert r.status_code == 400


def test_reconciliation_rejects_non_finite_counted_amounts(admin_client):
    for value in ("nan", "inf", float("nan")):
        r = admin_client.post("/api/reconciliation", json={"counted_cash": value})
        assert r.status_code == 400
    assert admin_client.get("/api/reconciliation").get_json() == []


def test_expenses_and_profit_formula(admin_client):
    seed(admin_client)
    today = date.today().isoformat()
    r = admin_client.post("/api/expenses", json={
        "description": "Rent", "category": "Rent", "amount": 1000, "exp_date": today,
    })
    assert r.status_code == 201
    p = admin_client.get("/api/profit").get_json()
    assert p["revenue_cash_momo"] == 9000
    assert p["cogs_approx"] == 5200
    assert p["expenses"] == 1000
    assert p["profit_approx"] == 2800


def test_expense_validation(admin_client):
    r = admin_client.post("/api/expenses", json={"description": "", "amount": -5})
    assert r.status_code == 400
    for amount in ("nan", "inf", float("nan")):
        r = admin_client.post("/api/expenses", json={"description": "Bad", "amount": amount})
        assert r.status_code == 400
    assert admin_client.get("/api/expenses").get_json() == []


def test_expense_and_rec_delete_admin_only(admin_client, staff_client):
    today = date.today().isoformat()
    r = admin_client.post("/api/expenses", json={"description": "X", "amount": 100, "exp_date": today})
    eid = r.get_json()["id"]
    assert staff_client.delete(f"/api/expenses/{eid}").status_code == 403
    assert staff_client.delete(f"/api/reconciliation/{today}").status_code == 403
    assert admin_client.delete(f"/api/expenses/{eid}").status_code == 200

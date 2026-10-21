import io
from pathlib import Path


def seed(client):
    r = client.post("/api/seed")
    assert r.status_code == 200


def test_seed_is_idempotent(admin_client):
    seed(admin_client)
    r = admin_client.post("/api/seed")
    assert r.get_json()["note"] == "already seeded"


def test_products_and_stock_levels(admin_client):
    seed(admin_client)
    prods = admin_client.get("/api/products").get_json()
    names = {p["name"] for p in prods}
    assert "Paracetamol 500mg" in names
    amlo = next(p for p in prods if p["name"] == "Amlodipine 5mg")
    assert amlo["stock_on_hand"] == 5
    assert amlo["low_stock"] is True


def test_add_update_delete_product(admin_client):
    r = admin_client.post("/api/products", json={
        "name": "Test Drug", "category": "General", "unit": "tabs",
        "reorder_level": 5, "price_buy": 100, "price_sell": 200,
    })
    assert r.status_code == 201
    pid = r.get_json()["id"]
    r = admin_client.put(f"/api/products/{pid}", json={
        "name": "Test Drug 2", "category": "General", "unit": "tabs",
        "reorder_level": 5, "price_buy": 100, "price_sell": 250,
    })
    assert r.status_code == 200
    assert admin_client.delete(f"/api/products/{pid}").status_code == 200


def test_duplicate_product_rejected(admin_client):
    body = {"name": "Dup Drug", "price_buy": 1, "price_sell": 2}
    assert admin_client.post("/api/products", json=body).status_code == 201
    assert admin_client.post("/api/products", json=body).status_code == 400


def test_staff_cannot_add_product(staff_client):
    r = staff_client.post("/api/products", json={"name": "Nope"})
    assert r.status_code == 403


def test_batch_intake_and_expiry_report(admin_client):
    seed(admin_client)
    exp = admin_client.get("/api/expiry").get_json()
    assert any(b["product_name"].startswith("Omeprazole") for b in exp["expired"])
    assert any(b["product_name"].startswith("Paracetamol") for b in exp["critical_30"])
    assert any(b["product_name"].startswith("Artemether") for b in exp["critical_30"])


def test_add_batch_validations(admin_client):
    seed(admin_client)
    pid = admin_client.get("/api/products").get_json()[0]["id"]
    r = admin_client.post("/api/batches", json={"product_id": pid, "qty_received": 10})
    assert r.status_code == 400
    r = admin_client.post("/api/batches", json={
        "product_id": pid, "qty_received": 10, "expiry_date": "2027-06-30", "batch_no": "T-1",
    })
    assert r.status_code == 201


def test_delete_product_blocked_when_batches_or_sales_exist(admin_client):
    seed(admin_client)
    prods = admin_client.get("/api/products").get_json()
    pid = prods[0]["id"]
    assert admin_client.delete(f"/api/products/{pid}").status_code == 400


def test_invoice_create_post_to_stock(admin_client):
    seed(admin_client)
    prod = admin_client.get("/api/products").get_json()[0]
    inv = admin_client.post("/api/invoices", json={"invoice_no": "INV-900", "supplier": "TestSup"}).get_json()
    r = admin_client.post(f"/api/invoices/{inv['id']}/post", json={"items": [{
        "product_id": prod["id"], "qty_received": 7, "expiry_date": "2027-01-01", "batch_no": "B-1",
    }]})
    assert r.status_code == 200
    assert r.get_json()["posted"] == 1
    invs = admin_client.get("/api/invoices").get_json()
    assert invs[0]["status"] == "POSTED"


def test_invoice_photo_upload_multipart(admin_client):
    data = {
        "invoice_no": "INV-77", "supplier": "Sup", "inv_date": "2026-10-01", "ocr_text": "ocr text",
        "photo": (io.BytesIO(b"fake-image-bytes"), "invoice.jpg"),
    }
    r = admin_client.post("/api/invoices", data=data, content_type="multipart/form-data")
    assert r.status_code == 201
    assert r.get_json()["image"].endswith("invoice.jpg")


def test_invoice_upload_filename_is_sanitized(admin_client):
    data = {"photo": (io.BytesIO(b"x"), "../../evil.jpg")}
    r = admin_client.post("/api/invoices", data=data, content_type="multipart/form-data")
    assert r.status_code == 201
    image = r.get_json()["image"]
    assert image.endswith("_evil.jpg")
    assert "/" not in image and "\\" not in image


def test_invoice_delete_removes_file_and_row(admin_client):
    from drugshop.db import upload_dir

    r = admin_client.post(
        "/api/invoices",
        data={"photo": (io.BytesIO(b"x"), "invoice.jpg")},
        content_type="multipart/form-data",
    )
    body = r.get_json()
    path = Path(upload_dir()) / body["image"]
    assert path.exists()
    assert admin_client.delete(f"/api/invoices/{body['id']}").status_code == 200
    assert not path.exists()
    assert all(i["id"] != body["id"] for i in admin_client.get("/api/invoices").get_json())


def test_invoice_delete_removes_legacy_unsafe_filename(admin_client):
    from drugshop.db import execute, upload_dir

    name = "20260101_120000_my#invoice.jpg"
    path = Path(upload_dir()) / name
    path.write_bytes(b"x")
    iid = execute("INSERT INTO invoices(invoice_no,image_name) VALUES(?,?)", ("LEGACY", name))
    assert admin_client.delete(f"/api/invoices/{iid}").status_code == 200
    assert not path.exists()


def test_invoice_post_rejects_malformed_items(admin_client):
    seed(admin_client)
    inv = admin_client.post("/api/invoices", json={"invoice_no": "INV-BAD"}).get_json()
    before = len(admin_client.get("/api/batches").get_json())
    r = admin_client.post(f"/api/invoices/{inv['id']}/post", json={"items": [{"product_id": 1}]})
    assert r.status_code == 400
    assert len(admin_client.get("/api/batches").get_json()) == before
    invs = admin_client.get("/api/invoices").get_json()
    assert next(i for i in invs if i["id"] == inv["id"])["status"] == "PENDING"


def test_uploads_route_serves_saved_file(admin_client):
    from drugshop.db import upload_dir

    path = Path(upload_dir()) / "probe.txt"
    path.write_text("hello", encoding="utf-8")
    r = admin_client.get("/uploads/probe.txt")
    assert r.status_code == 200
    assert r.data == b"hello"


def test_staff_cannot_modify_inventory(admin_client, staff_client):
    seed(admin_client)
    pid = admin_client.get("/api/products").get_json()[0]["id"]
    bid = admin_client.get("/api/batches").get_json()[0]["id"]
    inv = admin_client.post("/api/invoices", json={}).get_json()
    assert staff_client.put(f"/api/products/{pid}", json={"name": "X"}).status_code == 403
    assert staff_client.delete(f"/api/batches/{bid}").status_code == 403
    assert staff_client.delete(f"/api/invoices/{inv['id']}").status_code == 403


def test_delete_batch_blocked_when_sales_exist(admin_client):
    pid = admin_client.post("/api/products", json={
        "name": "Batch Del Drug", "price_buy": 1, "price_sell": 2,
    }).get_json()["id"]
    bid = admin_client.post("/api/batches", json={
        "product_id": pid, "qty_received": 3, "expiry_date": "2027-01-01",
    }).get_json()["id"]
    assert admin_client.post("/api/sales", json={
        "product_id": pid, "qty": 1, "payment_method": "CASH",
    }).status_code == 201
    assert admin_client.delete(f"/api/batches/{bid}").status_code == 400

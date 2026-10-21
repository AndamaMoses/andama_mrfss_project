from datetime import date, timedelta


def seed(client):
    assert client.post("/api/seed").status_code == 200


def test_reminders_from_seed(admin_client):
    seed(admin_client)
    rem = admin_client.get("/api/reminders").get_json()
    due_names = {p["name"] for p in rem["due"]}
    assert "Amina Namono" in due_names
    assert "Nakato Grace" in due_names
    amina = next(p for p in rem["due"] if p["name"] == "Amina Namono")
    assert amina["state"] == "OVERDUE"
    nakato = next(p for p in rem["due"] if p["name"] == "Nakato Grace")
    assert nakato["state"] == "DUE_SOON"
    assert amina["whatsapp_link"].startswith("https://wa.me/256")


def test_patient_create_and_reminder_state(admin_client):
    seed(admin_client)
    last = (date.today() - timedelta(days=35)).isoformat()
    r = admin_client.post("/api/patients", json={
        "name": "Test Patient", "phone": "0700111222",
        "last_refill_date": last, "cycle_days": 30,
    })
    assert r.status_code == 201
    rem = admin_client.get("/api/reminders").get_json()
    tp = next(p for p in rem["due"] if p["name"] == "Test Patient")
    assert tp["state"] == "OVERDUE"


def test_patient_requires_fields(admin_client):
    r = admin_client.post("/api/patients", json={"name": "No Phone"})
    assert r.status_code == 400


def test_refill_marks_today(admin_client):
    seed(admin_client)
    pats = admin_client.get("/api/patients").get_json()
    pid = pats[0]["id"]
    r = admin_client.post(f"/api/patients/{pid}", json={})
    assert r.status_code == 200
    assert r.get_json()["last_refill_date"] == date.today().isoformat()
    rem = admin_client.get("/api/reminders").get_json()
    assert all(p["id"] != pid for p in rem["due"])


def test_patient_delete_admin_only(admin_client, staff_client):
    seed(admin_client)
    pid = admin_client.get("/api/patients").get_json()[0]["id"]
    assert staff_client.delete(f"/api/patients/{pid}").status_code == 403
    assert admin_client.delete(f"/api/patients/{pid}").status_code == 200


def test_patient_update(admin_client):
    seed(admin_client)
    pid = admin_client.get("/api/patients").get_json()[0]["id"]
    r = admin_client.put(f"/api/patients/{pid}", json={
        "name": "Renamed", "phone": "0700999888", "last_refill_date": date.today().isoformat(),
        "cycle_days": 14, "notes": "updated",
    })
    assert r.status_code == 200
    row = next(p for p in admin_client.get("/api/patients").get_json() if p["id"] == pid)
    assert row["name"] == "Renamed"
    assert row["cycle_days"] == 14
    assert row["notes"] == "updated"


def test_patient_invalid_cycle_days_rejected(admin_client):
    payload = {
        "name": "Bad Cycle", "phone": "0700000000",
        "last_refill_date": date.today().isoformat(), "cycle_days": "abc",
    }
    r = admin_client.post("/api/patients", json=payload)
    assert r.status_code == 400
    assert "number" in r.get_json()["error"]
    assert all(p["name"] != "Bad Cycle" for p in admin_client.get("/api/patients").get_json())

    r = admin_client.post("/api/patients", json={**payload, "cycle_days": None})
    assert r.status_code == 201
    row = next(p for p in admin_client.get("/api/patients").get_json() if p["name"] == "Bad Cycle")
    assert row["cycle_days"] == 30

    r = admin_client.put(f"/api/patients/{row['id']}", json={**payload, "cycle_days": []})
    assert r.status_code == 400


def test_reminder_day25_boundaries(admin_client):
    """Pin the cycle-30 states: overdue, Day-25 due-soon, 10-day upcoming, OK."""
    cases = {
        31: "OVERDUE",
        30: "DUE_SOON",
        25: "DUE_SOON",
        24: "UPCOMING",
        20: "UPCOMING",
        19: "OK",
    }
    for offset in cases:
        r = admin_client.post("/api/patients", json={
            "name": f"Boundary {offset}", "phone": "0772 123 456",
            "last_refill_date": (date.today() - timedelta(days=offset)).isoformat(),
            "cycle_days": 30,
        })
        assert r.status_code == 201
    rem = admin_client.get("/api/reminders").get_json()
    states = {p["name"]: p["state"] for bucket in ("due", "upcoming", "ok") for p in rem[bucket]}
    for offset, expected in cases.items():
        assert states[f"Boundary {offset}"] == expected
    link = next(
        p["whatsapp_link"] for bucket in ("due", "upcoming", "ok")
        for p in rem[bucket] if p["name"] == "Boundary 25"
    )
    assert link.startswith("https://wa.me/256772123456?text=")


def test_reminders_skip_unparseable_last_refill(admin_client):
    admin_client.post("/api/patients", json={
        "name": "Bad Date", "phone": "0700000000", "last_refill_date": "not-a-date",
    })
    rem = admin_client.get("/api/reminders").get_json()
    names = {p["name"] for bucket in ("due", "upcoming", "ok") for p in rem[bucket]}
    assert "Bad Date" not in names

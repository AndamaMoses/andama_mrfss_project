import pytest


def test_me_returns_anonymous_when_logged_out(client):
    r = client.get("/api/me")
    assert r.status_code == 200
    assert r.get_json()["user"] is None


def test_protected_endpoint_requires_login(client):
    r = client.get("/api/products")
    assert r.status_code == 401


@pytest.mark.parametrize(
    "password",
    ["nope-not-a-password", "admin", "password", "Admin123", "andama123"],
)
def test_login_wrong_password_401(client, password):
    r = client.post("/api/login", json={"username": "admin", "password": password})
    assert r.status_code == 401
    assert "admin123" not in r.get_json()["error"]


def test_login_staff_rejects_legacy_admin_password(client):
    r = client.post("/api/login", json={"username": "grace", "password": "admin123"})
    assert r.status_code == 401


def test_login_errors_do_not_reveal_account_existence(client):
    wrong = client.post("/api/login", json={"username": "admin", "password": "wrong"})
    unknown = client.post("/api/login", json={"username": "nobody", "password": "wrong"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.get_json()["error"] == unknown.get_json()["error"] == "Invalid username or password."


def test_login_missing_password_400(client):
    r = client.post("/api/login", json={"username": "admin", "password": ""})
    assert r.status_code == 400


def test_login_non_object_json_400(client):
    r = client.post("/api/login", json=[1])
    assert r.status_code == 400


def test_login_admin_ok(client):
    r = client.post("/api/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    j = r.get_json()
    assert j["username"] == "admin"
    assert j["role"] == "admin"
    assert j["display_name"] == "Charles Onzima"


def test_login_staff_ok(client):
    r = client.post("/api/login", json={"username": "grace", "password": "grace123"})
    assert r.status_code == 200
    assert r.get_json()["role"] == "attendant"


def test_login_accepts_full_profile_name(client):
    r = client.post("/api/login", json={"username": "Charles Onzima", "password": "admin123"})
    assert r.status_code == 200
    assert r.get_json()["username"] == "admin"


def test_login_accepts_first_name(client):
    r = client.post("/api/login", json={"username": "Sarah", "password": "grace123"})
    assert r.status_code == 200
    assert r.get_json()["username"] == "grace"


def test_login_name_matching_is_case_insensitive(client):
    r = client.post("/api/login", json={"username": "  sArAh  ", "password": "grace123"})
    assert r.status_code == 200
    assert r.get_json()["username"] == "grace"


def test_login_first_name_with_wrong_password_401(client):
    r = client.post("/api/login", json={"username": "Sarah", "password": "admin123"})
    assert r.status_code == 401


def test_logout_clears_session(admin_client):
    assert admin_client.post("/api/logout").status_code == 200
    assert admin_client.get("/api/products").status_code == 401


def test_personas_lists_default_users(client):
    rows = client.get("/api/personas").get_json()
    usernames = {u["username"] for u in rows}
    assert {"admin", "grace"} <= usernames


def test_change_password_then_login_with_new(admin_client):
    r = admin_client.post("/api/change-password", json={"old": "admin123", "new": "newpass123"})
    assert r.status_code == 200
    admin_client.post("/api/logout")
    r = admin_client.post("/api/login", json={"username": "admin", "password": "newpass123"})
    assert r.status_code == 200


def test_change_password_requires_correct_old(admin_client):
    r = admin_client.post("/api/change-password", json={"old": "wrong", "new": "newpass123"})
    assert r.status_code == 400


def test_restart_does_not_reset_changed_password(admin_client):
    r = admin_client.post("/api/change-password", json={"old": "admin123", "new": "changed123"})
    assert r.status_code == 200

    from drugshop.auth.service import ensure_admin

    ensure_admin()

    admin_client.post("/api/logout")
    assert admin_client.post(
        "/api/login", json={"username": "admin", "password": "admin123"}
    ).status_code == 401
    assert admin_client.post(
        "/api/login", json={"username": "admin", "password": "changed123"}
    ).status_code == 200


def test_session_cookie_is_httponly_and_lax(client):
    r = client.post("/api/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    cookie = r.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie


def test_login_unknown_username_401(client):
    r = client.post("/api/login", json={"username": "nobody", "password": "whatever"})
    assert r.status_code == 401


def test_me_update_profile(admin_client):
    r = admin_client.put("/api/me", json={"display_name": "Charles O.", "phone": "0700111222"})
    assert r.status_code == 200
    me = admin_client.get("/api/me").get_json()
    assert me["display_name"] == "Charles O."
    assert me["phone"] == "0700111222"


def test_me_update_anonymous_401(client):
    assert client.put("/api/me", json={"display_name": "x"}).status_code == 401


def test_users_list_requires_admin(staff_client):
    assert staff_client.get("/api/users").status_code == 403


def test_users_create_and_delete(admin_client):
    r = admin_client.post("/api/users", json={"username": "peter", "password": "peter123", "role": "attendant"})
    assert r.status_code == 201
    uid = r.get_json()["id"]

    rows = admin_client.get("/api/users").get_json()
    peter = next(u for u in rows if u["username"] == "peter")
    assert "pass_hash" not in peter

    assert admin_client.delete(f"/api/users/{uid}").status_code == 200
    rows = admin_client.get("/api/users").get_json()
    assert all(u["username"] != "peter" for u in rows)


def test_users_create_requires_admin(staff_client):
    r = staff_client.post("/api/users", json={"username": "x", "password": "secret1"})
    assert r.status_code == 403


def test_admin_resets_staff_password(admin_client):
    rows = admin_client.get("/api/users").get_json()
    grace = next(u for u in rows if u["username"] == "grace")
    r = admin_client.post(f"/api/users/{grace['id']}/reset-password",
                          json={"password": "newgrace1"})
    assert r.status_code == 200

    fresh = admin_client.application.test_client()
    assert fresh.post("/api/login", json={"username": "grace", "password": "grace123"}).status_code == 401
    assert fresh.post("/api/login", json={"username": "grace", "password": "newgrace1"}).status_code == 200


def test_admin_can_delete_staff_with_login_history(admin_client):
    rows = admin_client.get("/api/users").get_json()
    grace = next(u for u in rows if u["username"] == "grace")
    staff = admin_client.application.test_client()
    assert staff.post("/api/login", json={"username": "grace", "password": "grace123"}).status_code == 200

    r = admin_client.delete(f"/api/users/{grace['id']}")
    assert r.status_code == 200
    remaining = {u["username"] for u in admin_client.get("/api/users").get_json()}
    assert "grace" not in remaining


def test_reset_password_requires_admin(staff_client):
    me = staff_client.get("/api/me").get_json()
    r = staff_client.post(f"/api/users/{me['id']}/reset-password", json={"password": "newpass1"})
    assert r.status_code == 403


def test_reset_password_too_short_400(admin_client):
    rows = admin_client.get("/api/users").get_json()
    grace = next(u for u in rows if u["username"] == "grace")
    r = admin_client.post(f"/api/users/{grace['id']}/reset-password", json={"password": "short"})
    assert r.status_code == 400


def test_reset_password_unknown_user_404(admin_client):
    r = admin_client.post("/api/users/9999/reset-password", json={"password": "newpass1"})
    assert r.status_code == 404


def test_reset_password_cli_recovers_lockout(app_under_test):
    runner = app_under_test.test_cli_runner()
    result = runner.invoke(args=["reset-password", "grace", "--password", "cligrace1"])
    assert result.exit_code == 0

    client = app_under_test.test_client()
    assert client.post("/api/login", json={"username": "grace", "password": "cligrace1"}).status_code == 200


def test_reset_password_cli_unknown_user(app_under_test):
    runner = app_under_test.test_cli_runner()
    result = runner.invoke(args=["reset-password", "nobody", "--password", "cligrace1"])
    assert result.exit_code == 1


def test_change_password_too_short_400(admin_client):
    r = admin_client.post("/api/change-password", json={"old": "admin123", "new": "short"})
    assert r.status_code == 400
    assert "6+" in r.get_json()["error"]


def test_users_duplicate_username_400(admin_client):
    body = {"username": "peter", "password": "peter123", "role": "attendant"}
    assert admin_client.post("/api/users", json=body).status_code == 201
    assert admin_client.post("/api/users", json=body).status_code == 400


def test_cannot_delete_own_account_400(admin_client):
    me = admin_client.get("/api/me").get_json()
    assert admin_client.delete(f"/api/users/{me['id']}").status_code == 400


def test_delete_unknown_user_404(admin_client):
    assert admin_client.delete("/api/users/9999").status_code == 404


def test_admin_required_rejects_staff(staff_client):
    r = staff_client.get("/api/staff-activity")
    assert r.status_code == 403
    assert r.get_json()["error"] == "admin only"


def test_admin_required_stale_session_is_forbidden(staff_client):
    with staff_client.session_transaction() as sess:
        sess["uid"] = 9999
    r = staff_client.get("/api/staff-activity")
    assert r.status_code == 403
    assert r.get_json()["error"] == "admin only"


def test_me_falls_back_to_username_when_display_name_blank(admin_client):
    from drugshop import db as dbm

    dbm.execute("UPDATE users SET display_name='' WHERE username='admin'")
    me = admin_client.get("/api/me").get_json()
    assert me["display_name"] == "admin"

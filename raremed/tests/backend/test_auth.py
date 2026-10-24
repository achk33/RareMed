from tests.backend.conftest import register_user, set_role


def test_register_login_me_and_logout(sqlite_client):
    created = register_user(sqlite_client, email="one@example.com")
    assert created.json()["user"]["email"] == "one@example.com"
    assert created.json()["user"]["role"] == "user"
    assert "raremed_session" in created.cookies

    me = sqlite_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "one@example.com"

    sqlite_client.cookies.clear()
    denied = sqlite_client.get("/api/v1/auth/me")
    assert denied.status_code == 401
    assert denied.json()["error"]["code"] == "unauthenticated"

    login = sqlite_client.post(
        "/api/v1/auth/login",
        json={"email": "one@example.com", "password": "correcthorse1"},
    )
    assert login.status_code == 200
    assert sqlite_client.get("/api/v1/auth/me").status_code == 200

    logout = sqlite_client.post("/api/v1/auth/logout")
    assert logout.status_code == 204
    sqlite_client.cookies.clear()
    assert sqlite_client.get("/api/v1/auth/me").status_code == 401


def test_duplicate_email_and_bad_password_are_rejected(sqlite_client):
    register_user(sqlite_client, email="dup@example.com")
    again = sqlite_client.post(
        "/api/v1/auth/register",
        json={"email": "dup@example.com", "password": "correcthorse1", "display_name": "Dup"},
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "email_taken"

    sqlite_client.cookies.clear()
    wrong = sqlite_client.post(
        "/api/v1/auth/login",
        json={"email": "dup@example.com", "password": "wrong-password"},
    )
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "invalid_credentials"
    assert "wrong-password" not in wrong.text


def test_session_token_is_http_only(sqlite_client):
    response = register_user(sqlite_client)
    cookie = response.headers.get("set-cookie", "")
    assert "raremed_session=" in cookie
    assert "HttpOnly" in cookie


def test_admin_user_list_is_enforced_by_the_api(sqlite_bundle):
    client = sqlite_bundle["client"]
    register_user(client, email="admin@example.com")
    set_role(sqlite_bundle["factory"], "admin@example.com", "admin")
    client.cookies.clear()
    register_user(client, email="plain@example.com")
    forbidden = client.get("/api/v1/admin/users")
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "forbidden"

    client.cookies.clear()
    logged_in = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "correcthorse1"},
    )
    assert logged_in.status_code == 200
    listing = client.get("/api/v1/admin/users")
    assert listing.status_code == 200
    emails = {item["email"] for item in listing.json()}
    assert emails == {"admin@example.com", "plain@example.com"}

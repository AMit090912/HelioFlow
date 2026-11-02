"""Auth API behaviour (§4) including plan Review Focus 1, 2, 3 and 5."""

from fastapi.testclient import TestClient

CSRF = {"X-HF-CSRF": "1"}


def signup(client: TestClient, **body):
    payload = {"full_name": "Prashant Wankhede", "password": "sunrise-roof-42", **body}
    return client.post("/api/auth/signup", json=payload, headers=CSRF)


def login(client: TestClient, identifier: str, password: str = "sunrise-roof-42"):
    return client.post(
        "/api/auth/login", json={"identifier": identifier, "password": password}, headers=CSRF
    )


def test_signup_sets_secure_session_cookie(client: TestClient):
    res = signup(client, email="prashant@example.com")
    assert res.status_code == 201
    body = res.json()
    assert body["role"] == "homeowner"
    assert body["email"] == "prashant@example.com"
    cookie = res.headers["set-cookie"].lower()
    assert "hf_session=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


def test_signup_cannot_choose_role(client: TestClient):
    res = signup(client, email="sneaky@example.com", role="admin")
    assert res.status_code == 201
    assert res.json()["role"] == "homeowner"


def test_email_case_and_spaces_are_one_account(client: TestClient):
    assert signup(client, email=" Prashant@Example.com ").status_code == 201
    client.cookies.clear()
    assert login(client, "prashant@example.com").status_code == 200
    dup = signup(client, email="PRASHANT@example.com")
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "ACCOUNT_EXISTS"


def test_phone_formats_normalised(client: TestClient):
    res = signup(client, phone="+91 98765 43210")
    assert res.status_code == 201
    assert res.json()["phone_masked"] == "••••••3210"
    client.cookies.clear()
    assert login(client, "098765-43210").status_code == 200


def test_signup_validation_codes(client: TestClient):
    assert signup(client).json()["error"]["code"] == "IDENTIFIER_REQUIRED"
    assert signup(client, phone="12345").json()["error"]["code"] == "PHONE_INVALID"
    assert signup(client, email="not-an-email").json()["error"]["code"] == "EMAIL_INVALID"
    weak = signup(client, email="weak@example.com", password="password123")
    assert weak.status_code == 422
    assert weak.json()["error"]["code"] == "PASSWORD_TOO_COMMON"


def test_validation_error_does_not_echo_password(client: TestClient):
    res = signup(client, email="x@example.com", password="Zq9#kW")
    assert res.status_code == 422
    assert "Zq9#kW" not in res.text


def test_bad_credentials_are_indistinguishable(client: TestClient):
    signup(client, email="prashant@example.com")
    client.cookies.clear()
    wrong_pw = login(client, "prashant@example.com", "not-the-password")
    unknown = login(client, "nobody@example.com", "not-the-password")
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json() == unknown.json()
    assert wrong_pw.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_rate_limited_after_five_failures(client: TestClient):
    signup(client, email="target@example.com")
    client.cookies.clear()
    for _ in range(5):
        assert login(client, "target@example.com", "wrong-password-x").status_code == 401
    res = login(client, "target@example.com", "wrong-password-x")
    assert res.status_code == 429
    assert res.json()["error"]["code"] == "RATE_LIMITED"


def test_lockout_is_per_client_not_per_account(client: TestClient, monkeypatch):
    """Review finding 2: an attacker failing logins must not lock the real user out."""
    from app.core.config import get_settings

    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    get_settings.cache_clear()
    try:
        signup(client, email="victim@example.com")
        client.cookies.clear()
        attacker = {**CSRF, "X-Forwarded-For": "198.51.100.7"}
        body = {"identifier": "victim@example.com", "password": "wrong-password-x"}
        for _ in range(6):
            client.post("/api/auth/login", json=body, headers=attacker)
        victim = {**CSRF, "X-Forwarded-For": "203.0.113.20"}
        ok = client.post(
            "/api/auth/login",
            json={"identifier": "victim@example.com", "password": "sunrise-roof-42"},
            headers=victim,
        )
        assert ok.status_code == 200
    finally:
        monkeypatch.delenv("TRUST_PROXY_HEADERS")
        get_settings.cache_clear()


def test_signup_race_returns_409_not_500(client: TestClient, monkeypatch):
    """Review finding 5: the unique constraint, not the pre-check, is the final word."""
    from app.api import auth as auth_api

    signup(client, email="race@example.com")
    client.cookies.clear()
    monkeypatch.setattr(auth_api, "_identity_taken", lambda *a, **k: False)
    res = signup(client, email="race@example.com")
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "ACCOUNT_EXISTS"


def test_unhandled_error_keeps_error_shape():
    """Review finding 5: every error body is {"error": {code, message}}, even a crash."""
    from app.main import create_app

    app = create_app()

    @app.get("/api/boom")
    def boom():
        raise RuntimeError("secret internals")

    res = TestClient(app, raise_server_exceptions=False).get("/api/boom")
    assert res.status_code == 500
    assert res.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "secret internals" not in res.text


def test_me_requires_valid_cookie(client: TestClient):
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.set("hf_session", "tampered.token.value")
    res = client.get("/api/auth/me")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "NOT_AUTHENTICATED"
    assert 'hf_session=""' in res.headers.get("set-cookie", "") or "max-age=0" in res.headers.get(
        "set-cookie", ""
    ).lower()


def test_me_and_logout(client: TestClient):
    signup(client, email="prashant@example.com", preferred_locale="hi")
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["preferred_locale"] == "hi"
    assert client.post("/api/auth/logout", headers=CSRF).status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_unsafe_method_requires_csrf_header(client: TestClient):
    res = client.post(
        "/api/auth/signup",
        json={"full_name": "X Y", "email": "x@example.com", "password": "sunrise-roof-42"},
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "CSRF_HEADER_MISSING"


def test_security_headers_present(client: TestClient):
    res = client.get("/api/health")
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"
    assert res.headers["referrer-policy"] == "strict-origin-when-cross-origin"

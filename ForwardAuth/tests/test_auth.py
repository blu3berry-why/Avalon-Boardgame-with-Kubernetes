from time import time

import jwt
import pytest

from conftest import TEST_SECRET, load_app_module

HEADER = "Avalon-Header-Logged-In-User-Username"


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def token(payload, key=TEST_SECRET):
    return jwt.encode(payload, key, algorithm="HS256")


def register(client, username="alice", password="pw"):
    return client.post("/register", json={"username": username, "password": password})


def login(client, username="alice", password="pw"):
    return client.post("/login", json={"username": username, "password": password})


# --- signing key -------------------------------------------------------------

def test_refuses_to_start_without_signing_key(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(SystemExit) as exc:
        load_app_module("forwardauth_app_nokey")
    assert "JWT_SECRET" in str(exc.value)


def test_token_signed_with_old_hardcoded_key_is_rejected(client):
    old = token({"username": "alice", "expire": time() + 60}, key="secret")
    assert client.get("/auth", headers=bearer(old)).status_code == 401


# --- /auth -------------------------------------------------------------------

def test_valid_token_returns_identity_header(client):
    good = token({"username": "alice", "expire": time() + 60})
    response = client.get("/auth", headers=bearer(good))
    assert response.status_code == 200
    assert response.headers[HEADER] == "alice"


@pytest.mark.parametrize("headers", [
    {},
    {"Authorization": "Basic YWxpY2U6cHc="},
    {"Authorization": "Bearer not-a-jwt"},
    {"Authorization": "Bearer "},
], ids=["missing", "not-bearer", "malformed", "empty"])
def test_bad_header_is_401_json(client, headers):
    response = client.get("/auth", headers=headers)
    assert response.status_code == 401
    assert response.is_json and "message" in response.get_json()


def test_expired_token_is_401(client):
    expired = token({"username": "alice", "expire": time() - 1})
    assert client.get("/auth", headers=bearer(expired)).status_code == 401


@pytest.mark.parametrize("payload", [
    {"username": "alice"},
    {"expire": time() + 60},
    {"username": "alice", "expire": "tomorrow"},
], ids=["no-expire", "no-username", "string-expire"])
def test_token_missing_claims_is_401(client, payload):
    assert client.get("/auth", headers=bearer(token(payload))).status_code == 401


# --- /login ------------------------------------------------------------------

def test_login_issues_token_accepted_by_auth(client):
    register(client)
    response = login(client)
    assert response.status_code == 200
    body = response.get_json()
    assert body["username"] == "alice"
    auth = client.get("/auth", headers=bearer(body["token"]))
    assert auth.status_code == 200 and auth.headers[HEADER] == "alice"


def test_login_token_expires_in_24_hours(client):
    register(client)
    issued = jwt.decode(login(client).get_json()["token"], TEST_SECRET, algorithms=["HS256"])
    assert abs(issued["expire"] - (time() + 24 * 60 * 60)) < 60


def test_login_unknown_user_is_404_json(client):
    response = login(client, username="nobody")
    assert response.status_code == 404
    assert response.is_json and "message" in response.get_json()


def test_login_wrong_password_is_403_json(client):
    register(client)
    response = login(client, password="wrong")
    assert response.status_code == 403
    assert response.is_json and "message" in response.get_json()


# --- /register ---------------------------------------------------------------

def test_register_new_user_then_login(client):
    assert register(client, "bob", "secret-pw").status_code == 200
    assert login(client, "bob", "secret-pw").status_code == 200


def test_register_duplicate_is_409_json(client):
    register(client)
    response = register(client)
    assert response.status_code == 409
    assert response.is_json and "message" in response.get_json()

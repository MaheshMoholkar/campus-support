from datetime import UTC, datetime, timedelta

import pytest

from app.core.enums import Role
from app.core.security import COOKIE_NAME, create_session_token, hash_password
from tests.factories import make_user

PASSWORD = "correct horse battery"
LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"


@pytest.fixture
def reporter(db):
    return make_user(
        db,
        Role.REPORTER,
        email="asha.kale@tarangini.example",
        password_hash=hash_password(PASSWORD),
    )


def test_login_sets_cookie_and_me_returns_the_user(client, reporter):
    response = client.post(
        LOGIN, json={"email": " Asha.Kale@Tarangini.example ", "password": PASSWORD}
    )

    assert response.status_code == 200
    assert response.json()["role"] == "reporter"
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    me = client.get(ME)
    assert me.status_code == 200
    assert me.json()["id"] == reporter.id
    assert "password_hash" not in me.json()


@pytest.mark.parametrize(
    "email,password",
    [("asha.kale@tarangini.example", "wrong"), ("nobody@tarangini.example", PASSWORD)],
)
def test_login_rejects_bad_credentials_with_one_message(client, reporter, email, password):
    response = client.post(LOGIN, json={"email": email, "password": password})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


def test_inactive_user_cannot_log_in_or_keep_using_a_cookie(client, db, reporter):
    client.post(LOGIN, json={"email": reporter.email, "password": PASSWORD})
    reporter.is_active = False
    db.commit()

    assert client.get(ME).status_code == 401
    assert (
        client.post(LOGIN, json={"email": reporter.email, "password": PASSWORD}).status_code == 401
    )


def test_me_requires_a_cookie(client):
    assert client.get(ME).status_code == 401


@pytest.mark.parametrize("hours_old", [0, 13])
def test_garbage_and_expired_tokens_are_rejected(client, reporter, hours_old):
    token = (
        "not-a-token"
        if hours_old == 0
        else create_session_token(reporter.id, datetime.now(UTC) - timedelta(hours=hours_old))
    )
    client.cookies.set(COOKIE_NAME, token)

    assert client.get(ME).status_code == 401


def test_logout_clears_the_cookie(client, reporter):
    client.post(LOGIN, json={"email": reporter.email, "password": PASSWORD})

    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get(ME).status_code == 401

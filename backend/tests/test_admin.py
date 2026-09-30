import pytest

ADMIN = "/api/v1/admin"


def test_admin_routes_are_admin_only(as_user, world):
    for user in (world.reporter, world.approver, world.lead, world.dev):
        assert as_user(user).get(f"{ADMIN}/users").status_code == 403
    assert as_user(world.admin).get(f"{ADMIN}/users").status_code == 200


@pytest.mark.parametrize(
    "path,body,changed",
    [
        (
            "institutes",
            {"name": "School of Design", "code": "SOD"},
            {"name": "School of Art", "code": "SOA"},
        ),
        ("sections", {"name": "Dean Office"}, {"name": "Dean's Office"}),
        (
            "modules",
            {"name": "Alumni", "url_prefix": "https://erp.tarangini.example/alumni"},
            {"name": "Alumni Portal", "url_prefix": "https://erp.tarangini.example/alumni"},
        ),
    ],
)
def test_master_data_create_list_update(as_user, world, path, body, changed):
    admin = as_user(world.admin)

    created = admin.post(f"{ADMIN}/{path}", json=body)
    assert created.status_code == 201
    row_id = created.json()["id"]
    assert admin.post(f"{ADMIN}/{path}", json=body).status_code == 409
    updated = admin.put(f"{ADMIN}/{path}/{row_id}", json=changed)
    assert updated.status_code == 200
    assert updated.json()["name"] == changed["name"]
    assert row_id in {row["id"] for row in admin.get(f"{ADMIN}/{path}").json()}
    assert admin.put(f"{ADMIN}/{path}/999999", json=changed).status_code == 404
    assert admin.post(f"{ADMIN}/{path}", json={**body, "name": " "}).status_code == 422


def new_user(world, **overrides) -> dict:
    body = {
        "name": "Meera Joshi",
        "email": "Meera.Joshi@Tarangini.example",
        "password": "a-long-password",
        "role": "reporter",
        "institute_id": world.institute.id,
    }
    body.update(overrides)
    return body


def test_created_user_can_log_in(as_user, client, world):
    admin = as_user(world.admin)

    created = admin.post(f"{ADMIN}/users", json=new_user(world))

    assert created.status_code == 201
    assert created.json()["email"] == "meera.joshi@tarangini.example"
    assert "password" not in created.text
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "meera.joshi@tarangini.example", "password": "a-long-password"},
    )
    assert login.status_code == 200
    assert admin.post(f"{ADMIN}/users", json=new_user(world)).status_code == 409


def test_user_validation(as_user, world):
    admin = as_user(world.admin)

    for overrides in (
        {"password": "short"},
        {"email": "not-an-email"},
        {"role": "approver"},  # no approval section
        {"role": "approver", "approval_section_id": 999999},
        {"institute_id": 999999},
        {"role": "owner"},
    ):
        response = admin.post(f"{ADMIN}/users", json=new_user(world, **overrides))
        assert response.status_code == 422, overrides


def test_update_user_changes_role_password_and_active_flag(as_user, client, world):
    admin = as_user(world.admin)
    user_id = admin.post(f"{ADMIN}/users", json=new_user(world)).json()["id"]

    updated = admin.patch(
        f"{ADMIN}/users/{user_id}",
        json={
            "role": "approver",
            "approval_section_id": world.section.id,
            "password": "another-long-password",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["role"] == "approver"
    credentials = {"email": "meera.joshi@tarangini.example", "password": "another-long-password"}
    assert client.post("/api/v1/auth/login", json=credentials).status_code == 200

    assert admin.patch(f"{ADMIN}/users/{user_id}", json={"is_active": False}).status_code == 200
    assert client.post("/api/v1/auth/login", json=credentials).status_code == 401
    assert admin.patch(f"{ADMIN}/users/999999", json={"name": "Nobody"}).status_code == 404


def test_admin_cannot_lock_themself_out(as_user, world):
    admin = as_user(world.admin)
    url = f"{ADMIN}/users/{world.admin.id}"

    assert admin.patch(url, json={"is_active": False}).status_code == 409
    assert admin.patch(url, json={"role": "lead"}).status_code == 409
    assert admin.patch(url, json={"name": "Renamed Admin"}).status_code == 200

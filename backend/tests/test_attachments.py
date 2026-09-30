import pytest

from app.services.attachments import MAX_BYTES
from tests.factories import ticket_values

API = "/api/v1"


def presign(client, **overrides):
    body = {"file_name": "screen shot.png", "content_type": "image/png", "size_bytes": 2048}
    body.update(overrides)
    return client.post(f"{API}/attachments/presign", json=body)


def uploaded(client, storage, **overrides) -> str:
    """Presign, then simulate the browser's upload."""
    response = presign(client, **overrides)
    assert response.status_code == 200, response.text
    return storage.put(response.json()["key"])


def test_presign_returns_a_key_under_the_callers_prefix(as_user, world):
    response = presign(as_user(world.reporter))

    assert response.status_code == 200
    body = response.json()
    assert body["key"].startswith(f"uploads/{world.reporter.id}/")
    assert body["key"].endswith("/screen_shot.png")
    assert body["upload_url"].startswith("https://")


@pytest.mark.parametrize(
    "overrides",
    [
        {"content_type": "application/x-msdownload"},
        {"size_bytes": MAX_BYTES + 1},
        {"size_bytes": 0},
        {"file_name": ""},
    ],
)
def test_presign_rejects_bad_type_size_and_name(as_user, world, overrides):
    assert presign(as_user(world.reporter), **overrides).status_code == 422


def test_ticket_can_be_created_with_attachments(as_user, world, storage):
    reporter = as_user(world.reporter)
    key = uploaded(reporter, storage)

    response = reporter.post(f"{API}/tickets", json=ticket_values(world, attachment_keys=[key]))

    assert response.status_code == 201
    attachment = response.json()["attachments"][0]
    assert attachment["file_name"] == "screen_shot.png"
    assert attachment["mime_type"] == "image/png"
    assert attachment["event_id"] is None


def test_message_attachments_are_linked_to_the_message(as_user, world, storage):
    reporter = as_user(world.reporter)
    ticket_id = reporter.post(f"{API}/tickets", json=ticket_values(world)).json()["id"]
    key = uploaded(reporter, storage, file_name="clearer.png")

    detail = reporter.post(
        f"{API}/tickets/{ticket_id}/messages",
        json={"body": "A clearer screenshot.", "attachment_keys": [key]},
    ).json()

    assert detail["attachments"][0]["event_id"] == detail["events"][-1]["id"]


def test_attach_rejects_bad_keys(as_user, world, storage):
    reporter = as_user(world.reporter)
    someone_elses = uploaded(as_user(world.other_reporter), storage)
    never_uploaded = presign(reporter).json()["key"]
    too_big = presign(reporter).json()["key"]
    storage.put(too_big, size_bytes=MAX_BYTES + 1)
    wrong_type = presign(reporter).json()["key"]
    storage.put(wrong_type, content_type="application/x-msdownload")
    used = uploaded(reporter, storage)
    assert (
        reporter.post(
            f"{API}/tickets", json=ticket_values(world, attachment_keys=[used])
        ).status_code
        == 201
    )
    six = [uploaded(reporter, storage) for _ in range(6)]
    twice = uploaded(reporter, storage)
    traversal = storage.put(f"uploads/{world.reporter.id}/../{world.other_reporter.id}/photo.png")

    for keys in (
        [someone_elses],
        [never_uploaded],
        [too_big],
        [wrong_type],
        [used],
        six,
        [twice, twice],
        [traversal],
    ):
        response = reporter.post(f"{API}/tickets", json=ticket_values(world, attachment_keys=keys))
        assert response.status_code == 422, keys

    total = as_user(world.lead).get(f"{API}/tickets").json()["total"]
    assert total == 1  # the failed requests created no tickets


def test_download_redirects_viewers_and_hides_from_others(as_user, world, storage):
    reporter = as_user(world.reporter)
    key = uploaded(reporter, storage)
    created = reporter.post(
        f"{API}/tickets", json=ticket_values(world, attachment_keys=[key])
    ).json()
    url = f"{API}/attachments/{created['attachments'][0]['id']}/download"

    allowed = as_user(world.approver).get(url, follow_redirects=False)
    assert allowed.status_code == 307
    assert allowed.headers["location"] == f"https://fake.storage/get/{key}"
    assert as_user(world.other_reporter).get(url, follow_redirects=False).status_code == 404
    assert reporter.get(f"{API}/attachments/999999/download").status_code == 404


def test_reply_can_carry_attachments(as_user, world, storage):
    reporter, approver = as_user(world.reporter), as_user(world.approver)
    ticket_id = reporter.post(f"{API}/tickets", json=ticket_values(world)).json()["id"]
    actions = f"{API}/tickets/{ticket_id}/actions"
    asked = approver.post(
        f"{actions}/request_info",
        json={"side_status": "poor_quality_images", "remark": "Screenshot is unreadable"},
    )
    assert asked.status_code == 200
    key = uploaded(reporter, storage, file_name="clearer.png")

    detail = reporter.post(
        f"{actions}/reply", json={"remark": "A clearer one.", "attachment_keys": [key]}
    ).json()

    assert detail["status"] == "pending_for_approval"
    assert detail["events"][-1]["event_type"] == "status_change"
    assert detail["attachments"][0]["event_id"] == detail["events"][-1]["id"]


def test_attachments_are_refused_on_other_actions(as_user, world, storage):
    approver = as_user(world.approver)
    ticket_id = (
        as_user(world.reporter).post(f"{API}/tickets", json=ticket_values(world)).json()["id"]
    )
    key = uploaded(approver, storage)

    response = approver.post(
        f"{API}/tickets/{ticket_id}/actions/approve",
        json={"remark": "Approved", "attachment_keys": [key]},
    )

    assert response.status_code == 422
    detail = approver.get(f"{API}/tickets/{ticket_id}").json()
    assert (detail["status"], detail["attachments"]) == ("pending_for_approval", [])

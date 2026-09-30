from tests.factories import ticket_values

API = "/api/v1"


def do(client, ticket_id, action, **body):
    return client.post(f"{API}/tickets/{ticket_id}/actions/{action}", json=body)


def create(client, world, **overrides) -> dict:
    response = client.post(f"{API}/tickets", json=ticket_values(world, **overrides))
    assert response.status_code == 201, response.text
    return response.json()


def queued(as_user, w) -> int:
    ticket_id = create(as_user(w.reporter), w)["id"]
    assert do(as_user(w.approver), ticket_id, "approve", remark="Approved").status_code == 200
    assert do(as_user(w.lead), ticket_id, "assign", assignee_id=w.dev.id).status_code == 200
    return ticket_id


def test_full_lifecycle_across_roles(as_user, world):
    w = world
    reporter, approver, lead, dev = (as_user(u) for u in (w.reporter, w.approver, w.lead, w.dev))

    created = create(reporter, w)
    ticket_id = created["id"]
    assert created["status"] == "pending_for_approval"
    assert created["reporter"]["id"] == w.reporter.id

    asked = do(
        approver,
        ticket_id,
        "request_info",
        side_status="clarification_required",
        remark="Which page?",
    )
    assert asked.json()["status"] == "clarification_required"
    replied = do(reporter, ticket_id, "reply", remark="The admissions page.")
    assert replied.json()["status"] == "pending_for_approval"
    approved = do(approver, ticket_id, "approve", remark="Approved")
    assert approved.json()["status"] == "waiting_in_queue"
    assigned = do(lead, ticket_id, "assign", assignee_id=w.dev.id, estimate_minutes=90).json()
    assert assigned["status"] == "waiting_in_queue"
    assert assigned["assignee"]["id"] == w.dev.id
    assert assigned["estimate_minutes"] == 90
    started = do(dev, ticket_id, "start").json()
    assert (started["status"], started["timer_running"]) == ("in_process", True)
    closed = do(dev, ticket_id, "close", remark="Fixed the template.").json()
    assert (closed["status"], closed["timer_running"]) == ("ticket_closed", False)

    detail = reporter.get(f"{API}/tickets/{ticket_id}").json()
    assert [e["event_type"] for e in detail["events"]] == [
        "created",
        "status_change",
        "status_change",
        "status_change",
        "assign",
        "estimate_change",
        "status_change",
        "status_change",
    ]
    assert detail["events"][3]["body"] == "Approved"
    assert detail["events"][3]["actor"]["id"] == w.approver.id
    assert detail["allowed_actions"] == []


def test_internal_ticket_from_a_developer_skips_approval(as_user, world):
    created = create(as_user(world.dev), world, approval_section_id=None)

    assert created["source"] == "internal"
    assert created["status"] == "waiting_in_queue"


def test_requests_need_a_session(client, world):
    assert client.get(f"{API}/tickets").status_code == 401
    assert client.post(f"{API}/tickets", json=ticket_values(world)).status_code == 401


def test_invisible_tickets_are_404(as_user, world):
    ticket_id = create(as_user(world.reporter), world)["id"]

    for stranger in (world.other_reporter, world.other_approver):
        client = as_user(stranger)
        assert client.get(f"{API}/tickets/{ticket_id}").status_code == 404
        assert do(client, ticket_id, "approve", remark="ok").status_code == 404
        assert (
            client.post(f"{API}/tickets/{ticket_id}/messages", json={"body": "hi"}).status_code
            == 404
        )


def test_wrong_relationship_is_403(as_user, world):
    w = world
    ticket_id = queued(as_user, w)

    response = do(as_user(w.other_dev), ticket_id, "start")

    assert response.status_code == 403
    assert response.json() == {"detail": "You are not allowed to do this on this ticket"}
    assert as_user(w.lead).get(f"{API}/tickets/{ticket_id}").json()["status"] == "waiting_in_queue"


def test_wrong_status_is_409_and_bad_input_is_422(as_user, world):
    w = world
    ticket_id = create(as_user(w.reporter), w)["id"]

    assert do(as_user(w.dev), ticket_id, "start").status_code == 409
    assert do(as_user(w.approver), ticket_id, "request_info", remark="?").status_code == 422
    assert do(as_user(w.approver), ticket_id, "approve").status_code == 422
    assert do(as_user(w.approver), ticket_id, "fly").status_code == 422
    assert (
        as_user(w.reporter)
        .post(f"{API}/tickets", json=ticket_values(w, description="short"))
        .status_code
        == 422
    )
    assert (
        as_user(w.reporter)
        .post(f"{API}/tickets", json=ticket_values(w, ticket_for="printing"))
        .status_code
        == 422
    )


def test_list_filters_and_scoping(as_user, world):
    w = world
    assigned = queued(as_user, w)
    pending = create(as_user(w.reporter), w, ticket_for="graphics")["id"]

    def ids(user, query="") -> set[int]:
        response = as_user(user).get(f"{API}/tickets{query}")
        assert response.status_code == 200
        return {item["id"] for item in response.json()["items"]}

    assert ids(w.lead) == {assigned, pending}
    assert ids(w.lead, "?status=waiting_in_queue") == {assigned}
    assert ids(w.lead, "?ticket_for=graphics") == {pending}
    assert ids(w.dev, "?mine=true") == {assigned}
    assert ids(w.other_reporter) == set()
    assert ids(w.other_approver) == set()
    assert as_user(w.lead).get(f"{API}/tickets?limit=1").json()["total"] == 2
    assert as_user(w.lead).get(f"{API}/tickets?status=done").status_code == 422


def test_detail_shows_actions_for_the_viewer(as_user, world):
    w = world
    ticket_id = queued(as_user, w)

    def actions(user) -> set[str]:
        return set(as_user(user).get(f"{API}/tickets/{ticket_id}").json()["allowed_actions"])

    assert actions(w.dev) == {"request_info", "start"}
    assert actions(w.lead) == {"assign", "set_estimate", "request_info"}
    assert actions(w.reporter) == set()


def test_messages_appear_in_the_timeline(as_user, world):
    ticket_id = create(as_user(world.reporter), world)["id"]

    response = as_user(world.lead).post(
        f"{API}/tickets/{ticket_id}/messages", json={"body": "  Looking into it.  "}
    )

    assert response.status_code == 201
    last = response.json()["events"][-1]
    assert (last["event_type"], last["body"]) == ("message", "Looking into it.")
    assert (
        as_user(world.lead)
        .post(f"{API}/tickets/{ticket_id}/messages", json={"body": "   "})
        .status_code
        == 422
    )


def test_bulk_assign_is_lead_only_and_all_or_nothing(as_user, world):
    w = world
    lead = as_user(w.lead)
    approved = create(as_user(w.reporter), w)["id"]
    do(as_user(w.approver), approved, "approve", remark="Approved")
    still_pending = create(as_user(w.reporter), w)["id"]

    assert (
        as_user(w.dev)
        .post(
            f"{API}/tickets/bulk-assign",
            json={"ticket_ids": [approved], "assignee_id": w.dev.id},
        )
        .status_code
        == 403
    )

    failed = lead.post(
        f"{API}/tickets/bulk-assign",
        json={"ticket_ids": [approved, still_pending], "assignee_id": w.dev.id},
    )
    assert failed.status_code == 409
    assert lead.get(f"{API}/tickets/{approved}").json()["assignee"] is None

    done = lead.post(
        f"{API}/tickets/bulk-assign",
        json={"ticket_ids": [approved], "assignee_id": w.dev.id, "estimate_minutes": 60},
    )
    assert done.status_code == 200
    assert done.json()[0]["assignee"]["id"] == w.dev.id


def test_lookups_list_master_data_and_active_developers(as_user, world):
    response = as_user(world.reporter).get(f"{API}/lookups")

    assert response.status_code == 200
    body = response.json()
    assert {s["id"] for s in body["approval_sections"]} == {
        world.section.id,
        world.other_section.id,
    }
    assert {d["id"] for d in body["developers"]} == {world.dev.id, world.other_dev.id}
    assert body["institutes"][0]["id"] == world.institute.id

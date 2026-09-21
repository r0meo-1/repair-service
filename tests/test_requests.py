from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Request as ServiceRequest, StatusEnum, User


def login(client, username):
    response = client.post(
        "/login", data={"username": username, "password": "pass123"},
        follow_redirects=False,
    )
    assert response.status_code == 302


def create_request(client, database):
    response = client.post("/", data={
        "clientName": "Test Client", "phone": "1234567890",
        "address": "Test Address", "problemText": "Test Problem",
    })
    assert response.status_code == 200
    with database() as db:
        request = db.query(ServiceRequest).one()
        assert request.status == StatusEnum.new
        assert request.assignedTo is None
        assert request.problemText == "Test Problem"
        return request.id


def assign_request(client, database, request_id):
    login(client, "disp")
    with database() as db:
        master_id = db.query(User).filter_by(username="mstr").one().id
    response = client.post(
        f"/dispatcher/assign/{request_id}", data={"master_id": master_id},
        follow_redirects=False,
    )
    assert response.status_code == 302
    with database() as db:
        request = db.get(ServiceRequest, request_id)
        assert request.status == StatusEnum.assigned
        assert request.assignedTo == master_id


def test_public_create_request(client, database):
    create_request(client, database)


def test_assigned_master_lifecycle(client, database):
    request_id = create_request(client, database)
    assign_request(client, database, request_id)
    login(client, "mstr")
    response = client.post(f"/master/take/{request_id}", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/master"
    with database() as db:
        assert db.get(ServiceRequest, request_id).status == StatusEnum.in_progress
    assert client.post(f"/master/take/{request_id}").status_code == 409
    response = client.post(f"/master/done/{request_id}", follow_redirects=False)
    assert response.status_code == 302
    with database() as db:
        assert db.get(ServiceRequest, request_id).status == StatusEnum.done


@pytest.mark.parametrize("route,success", [("api/requests", 200), ("master", 302)])
def test_concurrent_take_has_exactly_one_winner(client, database, route, success):
    request_id = create_request(client, database)
    assign_request(client, database, request_id)
    barrier = Barrier(5)

    def take_request(_):
        # Each worker gets its own cookie jar and DB session.
        with TestClient(app) as worker:
            if route == "master":
                login(worker, "mstr")
            barrier.wait(timeout=15)
            return worker.post(
                f"/api/requests/{request_id}/take" if route == "api/requests"
                else f"/master/take/{request_id}",
                follow_redirects=False,
            ).status_code

    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(take_request, range(5)))
    assert sorted(results) == [success, 409, 409, 409, 409]
    with database() as db:
        assert db.get(ServiceRequest, request_id).status == StatusEnum.in_progress


def test_unassigned_request_cannot_be_taken(client, database):
    request_id = create_request(client, database)
    assert client.post(f"/api/requests/{request_id}/take").status_code == 409
    with database() as db:
        assert db.get(ServiceRequest, request_id).status == StatusEnum.new


def test_master_actions_require_login(client, database):
    request_id = create_request(client, database)
    for action in ("take", "done"):
        assert client.post(f"/master/{action}/{request_id}").status_code == 403
    with database() as db:
        assert db.get(ServiceRequest, request_id).status == StatusEnum.new

import pytest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

from app.models import Request as ServiceRequest, RoleEnum, StatusEnum, User


def sign_in(client, username="mstr"):
    response = client.post("/login", data={"username": username, "password": "pass123"},
                           follow_redirects=False)
    assert response.status_code == 302
    return response


@pytest.fixture
def assigned(database, password_hash):
    with database() as db:
        owner = db.query(User).filter_by(username="mstr").one()
        db.add(User(username="other", password_hash=password_hash, role=RoleEnum.master))
        request = ServiceRequest(clientName="Owner", phone="123", address="Address",
                                 problemText="Problem", status=StatusEnum.assigned,
                                 assignedTo=owner.id)
        db.add(request)
        db.commit()
        return request.id


@pytest.mark.parametrize("cookie", ["1", "not-a-number", "999999999999999999999999"])
def test_unsigned_user_cookie_cannot_authenticate(client, cookie):
    client.cookies.set("user_id", cookie)
    response = client.get("/dispatcher", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_session_cookie_tampering_and_logout(client):
    response = sign_in(client)
    cookie = ";".join(response.headers.get_list("set-cookie")).lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    session = client.cookies.get("session")
    client.cookies.clear()
    client.cookies.set("session", "x" + session)
    assert client.get("/master", follow_redirects=False).headers["location"] == "/login"
    client.cookies.clear()
    sign_in(client)
    client.get("/logout", follow_redirects=False)
    assert client.get("/master", follow_redirects=False).headers["location"] == "/login"


def test_expired_session_cannot_authenticate(client):
    with patch("itsdangerous.timed.TimestampSigner.get_timestamp", return_value=1):
        sign_in(client)
    response = client.get("/master", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_session_uses_current_database_role(client, database):
    sign_in(client, "disp")
    with database() as db:
        db.query(User).filter_by(username="disp").one().role = RoleEnum.master
        db.commit()
    assert client.get("/dispatcher", follow_redirects=False).headers["location"] == "/login"


@pytest.mark.parametrize("actor", [None, "disp", "other"])
@pytest.mark.parametrize("route", ["master/take", "master/done", "api"])
def test_only_assigned_master_can_mutate(client, database, assigned, actor, route):
    initial = StatusEnum.in_progress if route == "master/done" else StatusEnum.assigned
    with database() as db:
        db.get(ServiceRequest, assigned).status = initial
        db.commit()
    if actor:
        sign_in(client, actor)
    url = f"/api/requests/{assigned}/take" if route == "api" else f"/{route}/{assigned}"
    response = client.post(url, follow_redirects=False)
    assert response.status_code in (403, 409)
    with database() as db:
        assert db.get(ServiceRequest, assigned).status == initial


@pytest.mark.parametrize("status", [StatusEnum.new, StatusEnum.assigned,
                                   StatusEnum.done, StatusEnum.canceled])
def test_done_requires_in_progress(client, database, assigned, status):
    with database() as db:
        db.get(ServiceRequest, assigned).status = status
        db.commit()
    sign_in(client)
    assert client.post(f"/master/done/{assigned}", follow_redirects=False).status_code == 409
    with database() as db:
        assert db.get(ServiceRequest, assigned).status == status


@pytest.mark.parametrize("master_id", [1, 9999])
def test_assignment_requires_existing_master(client, database, assigned, master_id):
    sign_in(client, "disp")
    response = client.post(f"/dispatcher/assign/{assigned}", data={"master_id": master_id},
                           follow_redirects=False)
    assert response.status_code == 400
    with database() as db:
        assert db.get(ServiceRequest, assigned).assignedTo == 2


@pytest.mark.parametrize("status", [StatusEnum.done, StatusEnum.canceled])
@pytest.mark.parametrize("action", ["assign", "cancel"])
def test_terminal_requests_cannot_be_changed(client, database, assigned, status, action):
    with database() as db:
        db.get(ServiceRequest, assigned).status = status
        db.commit()
    sign_in(client, "disp")
    response = client.post(f"/dispatcher/{action}/{assigned}", data={"master_id": 2},
                           follow_redirects=False)
    assert response.status_code == 409
    with database() as db:
        assert db.get(ServiceRequest, assigned).status == status


def test_in_progress_request_cannot_be_reassigned(client, database, assigned):
    with database() as db:
        db.get(ServiceRequest, assigned).status = StatusEnum.in_progress
        other_id = db.query(User).filter_by(username="other").one().id
        db.commit()
    sign_in(client, "disp")
    response = client.post(f"/dispatcher/assign/{assigned}", data={"master_id": other_id},
                           follow_redirects=False)
    assert response.status_code == 409
    with database() as db:
        assert db.get(ServiceRequest, assigned).assignedTo != other_id


@pytest.mark.parametrize("status", [StatusEnum.new, StatusEnum.assigned, StatusEnum.in_progress])
def test_dispatcher_can_cancel_active_request(client, database, assigned, status):
    with database() as db:
        db.get(ServiceRequest, assigned).status = status
        db.commit()
    sign_in(client, "disp")
    assert client.post(f"/dispatcher/cancel/{assigned}", follow_redirects=False).status_code == 302
    with database() as db:
        assert db.get(ServiceRequest, assigned).status == StatusEnum.canceled


def test_done_and_cancel_race_has_one_terminal_winner(client, database, assigned):
    with database() as db:
        db.get(ServiceRequest, assigned).status = StatusEnum.in_progress
        db.commit()
    barrier = Barrier(2)

    def change(action):
        with TestClient(app) as worker:
            sign_in(worker, "mstr" if action == "done" else "disp")
            barrier.wait(timeout=15)
            prefix = "master" if action == "done" else "dispatcher"
            response = worker.post(f"/{prefix}/{action}/{assigned}", follow_redirects=False)
            return action, response.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = dict(pool.map(change, ["done", "cancel"]))
    assert sorted(outcomes.values()) == [302, 409]
    expected = StatusEnum.done if outcomes["done"] == 302 else StatusEnum.canceled
    with database() as db:
        assert db.get(ServiceRequest, assigned).status == expected

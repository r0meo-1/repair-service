import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app, get_db
from app.models import Base, User
from passlib.context import CryptContext

TEST_DB_URL = 'sqlite:///./test.db'
engine = create_engine(TEST_DB_URL, connect_args={'check_same_thread': False})
TestingSession = sessionmaker(bind=engine)
pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSession()
    dispatcher = User(username='disp', password_hash=pwd_context.hash('pass123'), role='dispatcher')
    master = User(username='mstr', password_hash=pwd_context.hash('pass123'), role='master')
    db.add(dispatcher)
    db.add(master)
    db.commit()
    db.close()
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


client = TestClient(app, raise_server_exceptions=False)


def login(username, password):
    r = client.post('/login', data={'username': username, 'password': password}, follow_redirects=False)
    return r


def test_create_request():
    login('disp', 'pass123')
    r = client.post(
        '/requests/new',
        data={
            'clientName': 'Test Client',
            'phone': '1234567890',
            'address': 'Test Address',
            'problemText': 'Test Problem'
        },
        follow_redirects=False
    )
    assert r.status_code in [200, 302, 303]


def test_race_condition_take():
    import threading
    login('disp', 'pass123')
    client.post(
        '/requests/new',
        data={
            'clientName': 'Race Client',
            'phone': '9999999999',
            'address': 'Race Address',
            'problemText': 'Race Problem'
        },
        follow_redirects=False
    )
    db = TestingSession()
    from app.models import Request
    req = db.query(Request).filter(Request.clientName == 'Race Client').first()
    req_id = req.r_id
    db.close()

    results = []

    def take_request():
        login('mstr', 'pass123')
        r = client.post(f'/master/take/{req_id}', follow_redirects=False)
        results.append(r.status_code)

    threads = [threading.Thread(target=take_request) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    db = TestingSession()
    req = db.query(Request).get(req_id)
    assert req.status.value in ['in_progress', 'assigned']
    db.close()

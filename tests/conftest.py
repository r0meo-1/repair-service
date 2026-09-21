import os

# app.main creates tables at import time. Never open the developer's database.
os.environ["DATABASE_URL"] = "sqlite://"

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app, get_db
from app.models import Base, RoleEnum, User


@pytest.fixture(scope="session")
def password_hash():
    return bcrypt.hashpw(b"pass123", bcrypt.gensalt()).decode()


@pytest.fixture
def database(tmp_path, password_hash):
    engine = create_engine(
        "sqlite:///" + (tmp_path / "requests.db").as_posix(),
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    with sessions() as db:
        db.add_all([
            User(username="disp", password_hash=password_hash, role=RoleEnum.dispatcher),
            User(username="mstr", password_hash=password_hash, role=RoleEnum.master),
        ])
        db.commit()

    def override_get_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield sessions
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


@pytest.fixture
def client(database):
    with TestClient(app) as client:
        yield client

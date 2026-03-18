from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.session import build_engine, get_session
from app.main import app
from app.services.bootstrap import seed_reference_data


@pytest.fixture
def testing_session_local(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'test.db'}")
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as session:
        seed_reference_data(session)
    yield TestingSessionLocal
    engine.dispose()


@pytest.fixture
def db_session(testing_session_local):
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(testing_session_local) -> Generator[TestClient, None, None]:
    def override_get_session():
        session = testing_session_local()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

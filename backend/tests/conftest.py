import os
import importlib
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-only-secret-key-with-more-than-32-characters")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import main
from app.database import Base, get_db
from app.services import inference_service


@pytest.fixture
def client(monkeypatch):
    backend_dir = Path(__file__).resolve().parents[1]
    monkeypatch.setattr(
        inference_service.settings,
        "model_path",
        str(backend_dir / "models" / "tls_64byte_dropout_autoencoder.keras"),
    )
    monkeypatch.setattr(main, "create_all_tables", lambda: True)
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[get_db] = override_get_db
    websocket_api = importlib.import_module("app.api.websocket")
    ingest_api = importlib.import_module("app.broker.ingest")
    training_api = importlib.import_module("app.services.training_service")
    monkeypatch.setattr(websocket_api, "SessionLocal", TestingSession)
    monkeypatch.setattr(ingest_api, "SessionLocal", TestingSession)
    monkeypatch.setattr(training_api, "SessionLocal", TestingSession)
    with TestClient(main.app) as test_client:
        yield test_client
    main.app.dependency_overrides.clear()
    engine.dispose()


def create_user(client, email):
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "correct-horse-battery"},
    )
    assert response.status_code == 200, response.text
    response = client.post(
        "/api/auth/login",
        data={"username": email, "password": "correct-horse-battery"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}

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


def test_ingestion_scoring_and_user_isolation(client):
    owner_headers = create_user(client, "owner@example.com")
    other_headers = create_user(client, "other@example.com")
    interfaces = client.get("/api/monitoring/interfaces", headers=owner_headers).json()["interfaces"]
    assert interfaces

    created = client.post(
        "/api/monitoring/sessions",
        headers=owner_headers,
        json={
            "name": "Test session",
            "interface": interfaces[0],
            "packet_capture_limit_bytes": 32,
        },
    )
    assert created.status_code == 200, created.text
    session = created.json()
    assert client.post(
        f"/api/monitoring/sessions/{session['id']}/start",
        headers=owner_headers,
    ).status_code == 200

    invalid = client.post(
        "/api/packets/ingest",
        headers=owner_headers,
        json={"session_id": session["id"], "payload_hex": "not-hex"},
    )
    assert invalid.status_code == 422

    ingested = client.post(
        "/api/packets/ingest",
        headers=owner_headers,
        json={
            "session_id": session["id"],
            "payload_hex": "00" * 64,
            "src_ip": "192.0.2.1",
            "dst_ip": "192.0.2.2",
            "src_port": 12345,
            "dst_port": 443,
            "protocol": "tcp",
        },
    )
    assert ingested.status_code == 200, ingested.text
    result = ingested.json()
    assert result["status"] == "processed"
    assert result["anomaly_score"] >= 0
    assert result["threshold"] > 0

    packets = client.get("/api/packets", headers=owner_headers).json()
    assert len(packets) == 1
    assert packets[0]["packet_size"] == 32
    assert packets[0]["id"] == result["packet_id"]
    assert client.get("/api/packets", headers=other_headers).json() == []
    assert client.get(f"/api/packets/{result['packet_id']}", headers=other_headers).status_code == 404
    assert client.get("/api/dashboard/summary", headers=other_headers).json()["total_packets"] == 0


def test_training_requires_reviewed_normal_samples(client):
    headers = create_user(client, "trainer@example.com")
    response = client.post("/api/models/train", headers=headers)
    assert response.status_code == 422
    assert "Label at least 10 packets" in response.json()["detail"]


def test_auth_rejects_invalid_token(client):
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert response.status_code == 401


def test_default_placeholder_secret_is_rejected():
    import pytest
    from pydantic import ValidationError

    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(secret_key="change-me-in-production-super-secret-key")


def test_websocket_streams_authenticated_packet_event(client):
    headers = create_user(client, "live@example.com")
    interface = client.get("/api/monitoring/interfaces", headers=headers).json()["interfaces"][0]
    session = client.post(
        "/api/monitoring/sessions",
        headers=headers,
        json={"name": "Live", "interface": interface, "packet_capture_limit_bytes": 64},
    ).json()
    assert client.post(
        f"/api/monitoring/sessions/{session['id']}/start",
        headers=headers,
    ).status_code == 200
    token = headers["Authorization"].split(" ", 1)[1]

    with client.websocket_connect(f"/ws/monitoring/{session['id']}") as websocket:
        websocket.send_json({"token": token})
        response = client.post(
            "/api/packets/ingest",
            headers=headers,
            json={"session_id": session["id"], "payload_hex": "00" * 64},
        )
        assert response.status_code == 200, response.text
        event = websocket.receive_json()
        assert event["event"] == "packet"
        assert event["packet_size"] == 64
        assert event["session_id"] == session["id"]


def test_zeek_bridge_authenticates_and_persists_running_session(client, monkeypatch):
    import importlib

    bridge = importlib.import_module("app.broker.ingest")
    monkeypatch.setenv("ZEEK_SHARED_TOKEN", "test-bridge-secret-long-enough-to-pass")
    headers = create_user(client, "zeek@example.com")
    interface = client.get("/api/monitoring/interfaces", headers=headers).json()["interfaces"][0]
    session = client.post(
        "/api/monitoring/sessions",
        headers=headers,
        json={"name": "Zeek", "interface": interface, "packet_capture_limit_bytes": 8},
    ).json()
    client.post(f"/api/monitoring/sessions/{session['id']}/start", headers=headers)

    bridge.process_zeek_message(
        {"token": "wrong", "session_id": session["id"], "payload_hex": "00" * 8}
    )
    bridge.process_zeek_message(
        {
            "token": "test-bridge-secret-long-enough-to-pass",
            "session_id": session["id"],
            "payload_hex": "00" * 16,
        }
    )
    packets = client.get("/api/packets", headers=headers).json()
    assert len(packets) == 1
    assert packets[0]["packet_size"] == 8


def test_reviewed_samples_train_and_activate_model(client, monkeypatch, tmp_path):
    monkeypatch.setenv("MODEL_DIR", str(tmp_path))
    monkeypatch.setenv("TRAINING_EPOCHS", "1")
    monkeypatch.setenv("TRAINING_BATCH_SIZE", "4")
    headers = create_user(client, "training@example.com")
    interface = client.get("/api/monitoring/interfaces", headers=headers).json()["interfaces"][0]
    session = client.post(
        "/api/monitoring/sessions",
        headers=headers,
        json={"name": "Training", "interface": interface, "packet_capture_limit_bytes": 64},
    ).json()
    client.post(f"/api/monitoring/sessions/{session['id']}/start", headers=headers)

    packet_ids = []
    for sample in range(10):
        response = client.post(
            "/api/packets/ingest",
            headers=headers,
            json={"session_id": session["id"], "payload_hex": (bytes([sample]) * 64).hex()},
        )
        assert response.status_code == 200, response.text
        packet_ids.append(response.json()["packet_id"])
    for packet_id in packet_ids:
        response = client.patch(
            f"/api/packets/{packet_id}/label",
            headers=headers,
            json={"training_label": "normal"},
        )
        assert response.status_code == 200

    queued = client.post("/api/models/train", headers=headers)
    assert queued.status_code == 202, queued.text
    job_id = queued.json()["job_id"]
    job = client.get(f"/api/models/jobs/{job_id}", headers=headers).json()
    assert job["status"] == "completed", job
    model = next(model for model in client.get("/api/models", headers=headers).json() if model["status"] == "trained")
    assert model["threshold"] is not None
    assert client.post(
        "/api/models/activate",
        headers=headers,
        json={"model_id": model["id"]},
    ).status_code == 200

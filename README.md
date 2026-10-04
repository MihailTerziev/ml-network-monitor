# ML Network Monitor

A responsive web dashboard and Python backend for recording TCP payload samples, scoring them with a TensorFlow autoencoder, reviewing detections, and training per-user model versions from reviewed normal traffic.

## What works

- FastAPI backend with PostgreSQL persistence, JWT login, and registration.
- Monitoring-session configuration, including a local network-interface list and a maximum payload size.
- Authenticated packet ingestion, payload validation/truncation, model inference, and atomic packet/result storage.
- A newline-delimited JSON Zeek bridge (enabled only when `ZEEK_SHARED_TOKEN` is set).
- Session-scoped packet/detection APIs, dashboard counters, and authenticated WebSocket updates.
- Model listing/activation and background retraining from packets explicitly labeled `normal`.
- A same-origin responsive web dashboard for accounts, sessions, detections, labels, models, and retraining.
- A bundled 64-byte autoencoder, automatically registered on first startup when its configured file exists.

## Start with Docker Compose

1. Create a `.env` file in the repository root with `SECRET_KEY`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, and optionally `ZEEK_SHARED_TOKEN` and `DEFAULT_THRESHOLD`.
2. Replace `SECRET_KEY` with a random secret (for example, `openssl rand -hex 32`). Change `POSTGRES_PASSWORD` too; use URL-safe characters such as letters, digits, `_`, and `-`.
3. From the repository root, run:

   ```bash
   docker compose up --build
   ```

   If your `.env` is instead `backend/.env`, run `docker compose --env-file backend/.env up --build` from the repository root.

4. Open <http://localhost:8000>, create a local account, then create a monitoring session.
5. Interactive API documentation is at <http://localhost:8000/docs>.

Compose exposes PostgreSQL only on localhost. It persists PostgreSQL data in a named volume and uses the model checked into `backend/models`.
The default host bindings are loopback-only; expose the API/bridge deliberately and place them behind TLS/access controls before using other devices.

## Run the backend directly

Run PostgreSQL locally, create a `.env` (see the variables above), set `DATABASE_URL` to your local PostgreSQL URL, replace the secrets, then:

```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

On Windows, activate the environment with `venv\Scripts\activate`. TensorFlow wheel availability depends on the OS and Python version; use a TensorFlow-supported Python environment.

## Packet flow and Zeek bridge

The backend listens on TCP port `9999` only when `ZEEK_SHARED_TOKEN` is non-empty. The bridge expects one JSON object per line:

```json
{"token":"<same shared token>","session_id":"<running session UUID>","payload_hex":"160301...","src_ip":"192.0.2.1","dst_ip":"192.0.2.2","src_port":51515,"dst_port":443,"protocol":"tcp"}
```

The Zeek-side producer must run where the selected interface is visible, include the running session UUID and shared token, and send each complete JSON object followed by `\n` to the backend's port `9999`. The server validates the token/session, truncates payloads to the session's configured byte limit, runs inference, stores the packet and result in one database transaction, and emits a WebSocket event. The bridge intentionally ignores records for stopped/unknown sessions and malformed input.

**Capture boundary:** creating or starting a session does not install or launch Zeek, grant packet-capture privileges, or make a Docker container see host interfaces. This repository supplies the authenticated receiver and control/data APIs, not a Zeek deployment or host sensor. Configure your existing Zeek producer separately. The dashboard also supports API-driven packet ingestion for testing:

```bash
curl -X POST http://localhost:8000/api/packets/ingest \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"session_id":"<session UUID>","payload_hex":"1603010001","src_ip":"192.0.2.1","dst_ip":"192.0.2.2","src_port":51515,"dst_port":443,"protocol":"tcp"}'
```

The packet payload is retained only up to the configured capture limit. Use synthetic/sanitized data during development; captured payloads can contain sensitive information.
The bundled model and current training pipeline use 64-byte windows, so the session cap is limited to 64 bytes; shorter samples are zero-padded for inference.

## Models and retraining

The bundled model expects a 512-bit vector (64 bytes). Inference inspects the loaded model's input shape and rejects incompatible shapes. Each session's byte cap is applied before data is stored and scored; shorter payloads are zero-padded by preprocessing.

Detection thresholds are stored per model. The bundled model uses `DEFAULT_THRESHOLD` from the environment (default `0.18`); treat this as a starting value, not a calibrated production threshold. Set it using your held-out data and measured false-positive/false-negative rates. Training in the dashboard uses only packets that a user labels `normal`, reserves a validation slice, trains an autoencoder in a background API task, and derives a threshold from validation reconstruction losses. New models remain inactive until explicitly activated.

Training runs inside the API process and uses local disk for model files; a process restart interrupts a running job. For production, move training to a durable worker/queue and use shared model storage.

## API overview

- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`
- `GET /api/monitoring/interfaces`, session create/list/update/start/stop
- `POST /api/packets/ingest`, `GET /api/packets`, `GET /api/detections`
- `PATCH /api/packets/{packet_id}/label`, `GET /api/results/{packet_id}`
- `GET /api/dashboard/summary`, `WS /ws/monitoring/{session_id}`
- `GET /api/models`, `POST /api/models/score`, `POST /api/models/activate`
- `POST /api/models/train`, `GET /api/models/jobs/{job_id}`
- `GET /health`

The Typer CLI calls the same authenticated APIs. Set `MLNM_TOKEN` to a bearer token and optionally `API_BASE_URL`, then use `python -m app.cli --help` from `backend/` to list commands.

## Tests

Install test dependencies and run focused backend tests:

```bash
cd backend
pip install -r requirements.txt pytest
pytest
```

Tests use an isolated in-memory SQLite database and the checked-in TensorFlow model; PostgreSQL/Zeek integration still needs a local end-to-end run.

## Current scope and operational notes

This is a web-based proof of concept, not a packaged native desktop/mobile app or a production deployment. Authentication uses bearer tokens and local account passwords; email verification, password reset, TLS termination, rate limiting, audit logging, durable background jobs, automated Zeek lifecycle management, and schema migration tooling remain deployment work. Keep the API and bridge on a trusted network, set strong secrets, and put public deployments behind TLS and appropriate access controls.

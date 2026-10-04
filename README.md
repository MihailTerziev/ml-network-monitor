# ML Network Monitor

This project provides a backend foundation for a packet-monitoring system that captures traffic, stores it in PostgreSQL, evaluates it with a TensorFlow autoencoder, and exposes APIs for dashboard and model management.

## Stack

- FastAPI
- PostgreSQL
- Redis
- SQLAlchemy
- TensorFlow
- Typer CLI
- Docker Compose

## Structure

- `backend/app` - FastAPI application and backend logic
- `backend/app/api` - API routes
- `backend/app/models` - SQLAlchemy ORM models
- `backend/app/services` - packet ingestion, inference, training, auth services
- `backend/app/broker` - Zeek/packet consumer helpers
- `docker-compose.yml` - local database and service orchestration

## Quick start

1. Copy `.env.example` to `.env`
2. Install Python dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```
3. Start local dependencies:
   ```bash
   docker compose up -d postgres redis
   ```
4. Run the app:
   ```bash
   cd backend
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
5. Check health:
   ```bash
   curl http://localhost:8000/health
   ```

## Core backend flow

1. Zeek emits packet payloads
2. Python consumer listens for the payload stream
3. Packet is saved to PostgreSQL
4. TensorFlow model scores the payload using the autoencoder reconstruction error
5. Result is stored with anomaly metadata and timestamp
6. Dashboard reads the results from API and WebSocket endpoints

## Main endpoints

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/monitoring/interfaces`
- `POST /api/monitoring/sessions`
- `GET /api/monitoring/sessions`
- `POST /api/packets/ingest`
- `GET /api/packets`
- `GET /api/detections`
- `POST /api/models/train`

## Notes

This is the first backend-ready scaffold for your master’s project. It is intentionally structured so you can connect your Zeek emission logic and your TensorFlow autoencoder without rebuilding the architecture.

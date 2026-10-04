# ML Network Monitor

A backend starter for a network-monitoring application that captures packets, stores them in PostgreSQL, scores them with a TensorFlow autoencoder, and exposes APIs for dashboard and model management.

## Stack

- FastAPI
- PostgreSQL
- Redis
- SQLAlchemy
- TensorFlow
- Typer CLI
- Docker Compose

## Quick start

1. Copy `.env.example` to `.env`
2. Install dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```
3. Run PostgreSQL and Redis with Docker:
   ```bash
   docker compose up -d postgres redis
   ```
4. Start the backend:
   ```bash
   cd backend
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
5. Visit http://localhost:8000/health

## Key endpoints

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/monitoring/interfaces`
- `POST /api/monitoring/sessions`
- `GET /api/monitoring/sessions`
- `GET /api/packets`
- `GET /api/detections`
- `POST /api/models/train`

## Notes

This is the initial project scaffold. It is ready for integration with your Zeek Broker producer and your TensorFlow autoencoder script.

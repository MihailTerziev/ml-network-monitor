from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.monitoring import router as monitoring_router
from app.api.models import router as models_router
from app.api.packets import router as packets_router
from app.api.websocket import router as websocket_router
from app.broker.ingest import process_zeek_message
from app.broker.zeek_consumer import ZeekSocketConsumer
from app.config import get_settings
from app.database import create_all_tables

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_all_tables()
    consumer = None
    if settings.zeek_shared_token:
        consumer = ZeekSocketConsumer(
            host=settings.zeek_host,
            port=settings.zeek_port,
            on_message=process_zeek_message,
        )
        consumer.start()
        app.state.zeek_consumer = consumer
    try:
        yield
    finally:
        if consumer:
            consumer.stop()


app = FastAPI(title="ML Network Monitor", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(monitoring_router)
app.include_router(packets_router)
app.include_router(models_router)
app.include_router(dashboard_router)
app.include_router(websocket_router)

project_root = Path(__file__).resolve().parents[2]
frontend_dir = project_root / "frontend"
if frontend_dir.is_dir():
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/", include_in_schema=False)
def frontend():
    return FileResponse(frontend_dir / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

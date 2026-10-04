from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all_tables():
    from app.models.user import User
    from app.models.monitoring_session import MonitoringSession
    from app.models.packet import CapturedPacket
    from app.models.detection_result import DetectionResult
    from app.models.model_version import ModelVersion
    from app.models.training_job import TrainingJob

    Base.metadata.create_all(bind=engine)
    return True

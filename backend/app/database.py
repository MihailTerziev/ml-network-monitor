from pathlib import Path

from sqlalchemy import create_engine, inspect, text
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
    _migrate_columns()
    _register_bundled_model()
    return True


def _migrate_columns():
    migrations = {
        "captured_packets": {"training_label": "VARCHAR"},
        "model_versions": {
            "threshold": "FLOAT",
            "owner_user_id": "UUID" if engine.dialect.name == "postgresql" else "CHAR(32)",
        },
    }
    with engine.begin() as connection:
        inspector = inspect(connection)
        for table_name, columns in migrations.items():
            existing = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, column_type in columns.items():
                if column_name not in existing:
                    connection.execute(
                        text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
                    )


def _register_bundled_model():
    from app.config import get_settings
    from app.models.model_version import ModelVersion

    settings = get_settings()
    model_path = str(Path(settings.model_path).resolve())
    if not Path(model_path).is_file():
        return

    db = SessionLocal()
    try:
        model = db.query(ModelVersion).filter(ModelVersion.version == "bundled-tls64-v1").first()
        if model is None:
            model = ModelVersion(
                version="bundled-tls64-v1",
                file_path=model_path,
                status="active",
                trained_on_samples=0,
                threshold=settings.default_threshold,
            )
            db.add(model)
            db.commit()
    finally:
        db.close()

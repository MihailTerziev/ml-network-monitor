from datetime import datetime
from sqlalchemy.orm import Session

from app.models.model_version import ModelVersion


def start_training_job(db: Session, user_id: str):
    model_version = ModelVersion(
        version="v0.1.0",
        file_path="models/active_model.keras",
        status="training",
        trained_on_samples=0,
        accuracy=0.0,
        loss=0.0,
        created_at=datetime.utcnow(),
    )
    db.add(model_version)
    db.commit()
    db.refresh(model_version)
    return {"job_id": str(model_version.id), "status": "pending"}

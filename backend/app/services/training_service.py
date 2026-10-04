from datetime import datetime
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models.model_version import ModelVersion
from app.models.packet import CapturedPacket
from app.models.training_job import TrainingJob


def create_training_job(db: Session, user_id: str):
    total_packets = db.query(CapturedPacket.id).count()

    model_version = ModelVersion(
        version=f"v{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        file_path="models/active_model.keras",
        status="training",
        trained_on_samples=total_packets,
        accuracy=0.0,
        loss=0.0,
        created_at=datetime.utcnow(),
    )

    db.add(model_version)
    db.commit()
    db.refresh(model_version)

    job = TrainingJob(
        user_id=user_id,
        model_version_id=model_version.id,
        status="completed",
        samples_used=total_packets,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    model_version.status = "trained"
    db.commit()

    return {
        "job_id": str(job.id),
        "model_version_id": str(model_version.id),
        "model_version": model_version.version,
        "status": "completed",
        "samples_used": total_packets,
    }

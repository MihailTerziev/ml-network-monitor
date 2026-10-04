from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.detection_result import DetectionResult
from app.models.model_version import ModelVersion
from app.models.monitoring_session import MonitoringSession
from app.models.packet import CapturedPacket
from app.models.training_job import TrainingJob
from app.schemas.model import ModelVersionOut, TrainingJobOut
from app.services.training_service import create_training_job

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("", response_model=List[ModelVersionOut])
def list_models(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return db.query(ModelVersion).order_by(ModelVersion.created_at.desc()).all()


@router.post("/train")
def trigger_training(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return create_training_job(db, str(current_user.id))


@router.get("/jobs/{job_id}", response_model=TrainingJobOut)
def get_job_status(job_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Training job not found")
    return job


@router.post("/{model_id}/activate")
def activate_model(model_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    model = db.query(ModelVersion).filter(ModelVersion.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    active_models = db.query(ModelVersion).filter(ModelVersion.status == "active").all()
    for active in active_models:
        active.status = "trained"

    model.status = "active"
    model.activated_at = datetime.utcnow()
    db.commit()
    return {"status": "activated", "model_id": model_id, "version": model.version}


@router.get("/summary")
def model_summary(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    total_models = db.query(func.count(ModelVersion.id)).scalar() or 0
    active_model = db.query(ModelVersion).filter(ModelVersion.status == "active").first()
    total_packets = db.query(func.count(CapturedPacket.id)).scalar() or 0
    return {
        "total_models": total_models,
        "active_model": active_model.version if active_model else None,
        "total_packets": total_packets,
    }

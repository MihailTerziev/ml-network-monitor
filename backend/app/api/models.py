from __future__ import annotations

from pathlib import Path
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.model_version import ModelVersion
from app.models.training_job import TrainingJob
from app.models.packet import CapturedPacket
from app.models.monitoring_session import MonitoringSession
from app.services.inference_service import AutoencoderInferenceService
from app.services.training_service import create_training_job, train_model_job

router = APIRouter(prefix="/api/models", tags=["models"])


class ModelActivationIn(BaseModel):
    model_id: UUID


class PayloadScoreIn(BaseModel):
    payload_hex: str = Field(min_length=2, max_length=131070)


@router.get("")
def list_models(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    models = (
        db.query(ModelVersion)
        .filter((ModelVersion.owner_user_id == current_user.id) | (ModelVersion.owner_user_id.is_(None)))
        .order_by(ModelVersion.created_at.desc())
        .all()
    )
    return [
        {
            "id": str(m.id),
            "version": m.version,
            "file_path": m.file_path,
            "status": m.status,
            "trained_on_samples": m.trained_on_samples,
            "accuracy": m.accuracy,
            "loss": m.loss,
            "threshold": m.threshold,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in models
    ]


@router.post("/activate")
def activate_model(
    payload: ModelActivationIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    model = (
        db.query(ModelVersion)
        .filter(ModelVersion.id == payload.model_id, ModelVersion.owner_user_id == current_user.id)
        .first()
    )
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    if model.status not in {"trained", "active"} or not Path(model.file_path).is_file():
        raise HTTPException(status_code=409, detail="Only trained models with an available file can be activated")

    for active in (
        db.query(ModelVersion)
        .filter(ModelVersion.status == "active", ModelVersion.owner_user_id == current_user.id)
        .all()
    ):
        active.status = "trained"

    model.status = "active"
    model.activated_at = datetime.utcnow()
    db.commit()
    return {"status": "activated", "model_id": str(model.id), "version": model.version}


@router.post("/score")
def score_payload(
    payload: PayloadScoreIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    model = (
        db.query(ModelVersion)
        .filter(ModelVersion.status == "active")
        .filter((ModelVersion.owner_user_id == current_user.id) | (ModelVersion.owner_user_id.is_(None)))
        .order_by(ModelVersion.owner_user_id.is_(None), ModelVersion.created_at.desc())
        .first()
    )
    model_path = model.file_path if model else None
    scorer = AutoencoderInferenceService(
        model_path=model_path,
        threshold=model.threshold if model and model.threshold is not None else None,
    )
    result = scorer.score_payload(payload.payload_hex)
    return {"status": "ok", **result}


@router.post("/train", status_code=202)
def train_model(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        job = create_training_job(db, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    background_tasks.add_task(train_model_job, str(job.id))
    return {"job_id": str(job.id), "status": job.status, "samples_used": job.samples_used}


@router.get("/jobs/{job_id}")
def get_training_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    job = (
        db.query(TrainingJob)
        .filter(TrainingJob.id == job_id, TrainingJob.user_id == current_user.id)
        .first()
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Training job not found")
    return {
        "id": str(job.id),
        "status": job.status,
        "samples_used": job.samples_used,
        "model_version_id": str(job.model_version_id) if job.model_version_id else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "error_message": job.error_message,
    }


@router.get("/summary")
def model_summary(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    model = (
        db.query(ModelVersion)
        .filter(ModelVersion.status == "active")
        .filter((ModelVersion.owner_user_id == current_user.id) | (ModelVersion.owner_user_id.is_(None)))
        .order_by(ModelVersion.owner_user_id.is_(None), ModelVersion.created_at.desc())
        .first()
    )
    total_packets = (
        db.query(CapturedPacket.id)
        .join(MonitoringSession, MonitoringSession.id == CapturedPacket.session_id)
        .filter(MonitoringSession.user_id == current_user.id)
        .count()
    )
    return {
        "active_model": model.version if model else None,
        "total_packets": total_packets,
    }

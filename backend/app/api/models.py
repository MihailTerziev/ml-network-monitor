from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.model_version import ModelVersion
from app.models.training_job import TrainingJob
from app.schemas.model import ModelVersionOut, TrainingJobOut
from app.services.training_service import start_training_job

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("", response_model=List[ModelVersionOut])
def list_models(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return db.query(ModelVersion).order_by(ModelVersion.created_at.desc()).all()


@router.post("/train")
def trigger_training(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return start_training_job(db=db, user_id=str(current_user.id))


@router.get("/jobs/{job_id}", response_model=TrainingJobOut)
def get_job_status(job_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Training job not found")
    return job

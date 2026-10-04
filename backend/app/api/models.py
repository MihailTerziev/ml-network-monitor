from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.model_version import ModelVersion
from app.models.packet import CapturedPacket
from app.services.inference_service import AutoencoderInferenceService

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("")
def list_models(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    models = db.query(ModelVersion).order_by(ModelVersion.created_at.desc()).all()
    return [
        {
            "id": str(m.id),
            "version": m.version,
            "file_path": m.file_path,
            "status": m.status,
            "trained_on_samples": m.trained_on_samples,
            "accuracy": m.accuracy,
            "loss": m.loss,
        }
        for m in models
    ]


@router.post("/activate")
def activate_model(payload: Dict[str, Any], db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    model_id = payload.get("model_id") or payload.get("id")
    if not model_id:
        raise HTTPException(status_code=400, detail="model_id is required")

    model = db.query(ModelVersion).filter(ModelVersion.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    for active in db.query(ModelVersion).filter(ModelVersion.status == "active").all():
        active.status = "trained"

    model.status = "active"
    db.commit()
    return {"status": "activated", "model_id": str(model.id), "version": model.version}


@router.post("/score")
def score_payload(payload: Dict[str, Any], db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    packet_hex = payload.get("payload_hex")
    if not packet_hex:
        raise HTTPException(status_code=400, detail="payload_hex is required")

    model = db.query(ModelVersion).filter(ModelVersion.status == "active").first()
    model_path = model.file_path if model else None
    scorer = AutoencoderInferenceService(model_path=model_path)
    result = scorer.score_payload(str(packet_hex))
    return {"status": "ok", **result}


@router.get("/summary")
def model_summary(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    model = db.query(ModelVersion).filter(ModelVersion.status == "active").first()
    total_packets = db.query(CapturedPacket.id).count()
    return {
        "active_model": model.version if model else None,
        "total_packets": total_packets,
    }

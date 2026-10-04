from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.detection_result import DetectionResult
from app.models.monitoring_session import MonitoringSession
from app.models.packet import CapturedPacket

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
def dashboard_summary(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    total_packets = db.query(func.count(CapturedPacket.id)).scalar() or 0
    total_anomalies = db.query(func.count(DetectionResult.id)).filter(DetectionResult.is_anomalous.is_(True)).scalar() or 0
    total_benign = db.query(func.count(DetectionResult.id)).filter(DetectionResult.is_anomalous.is_(False)).scalar() or 0
    active_sessions = db.query(func.count(MonitoringSession.id)).filter(MonitoringSession.status == "running").scalar() or 0

    today = datetime.utcnow().date()
    packets_today = db.query(func.count(CapturedPacket.id)).filter(func.date(CapturedPacket.captured_at) == today).scalar() or 0

    return {
        "total_packets": total_packets,
        "anomalies": total_anomalies,
        "benign": total_benign,
        "packets_today": packets_today,
        "active_sessions": active_sessions,
    }

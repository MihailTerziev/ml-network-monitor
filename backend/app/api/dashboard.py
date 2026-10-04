from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.detection_result import DetectionResult
from app.models.monitoring_session import MonitoringSession
from app.models.packet import CapturedPacket

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
def dashboard_summary(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    owned_session_ids = db.query(MonitoringSession.id).filter(MonitoringSession.user_id == current_user.id)
    total_packets = db.query(func.count(CapturedPacket.id)).filter(CapturedPacket.session_id.in_(owned_session_ids)).scalar() or 0
    owned_packet_ids = db.query(CapturedPacket.id).filter(CapturedPacket.session_id.in_(owned_session_ids))
    total_anomalies = db.query(func.count(DetectionResult.id)).filter(DetectionResult.packet_id.in_(owned_packet_ids), DetectionResult.is_anomalous.is_(True)).scalar() or 0
    total_benign = db.query(func.count(DetectionResult.id)).filter(DetectionResult.packet_id.in_(owned_packet_ids), DetectionResult.is_anomalous.is_(False)).scalar() or 0
    active_sessions = db.query(func.count(MonitoringSession.id)).filter(MonitoringSession.user_id == current_user.id, MonitoringSession.status == "running").scalar() or 0
    packets_today = db.query(func.count(CapturedPacket.id)).filter(CapturedPacket.session_id.in_(owned_session_ids), func.date(CapturedPacket.captured_at) == datetime.utcnow().date()).scalar() or 0

    return {
        "total_packets": total_packets,
        "anomalies": total_anomalies,
        "benign": total_benign,
        "packets_today": packets_today,
        "active_sessions": active_sessions,
    }

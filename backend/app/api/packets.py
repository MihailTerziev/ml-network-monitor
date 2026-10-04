from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.monitoring_session import MonitoringSession
from app.models.detection_result import DetectionResult
from app.models.packet import CapturedPacket
from app.schemas.monitoring import MonitoringSessionCreate, MonitoringSessionOut, MonitoringSessionUpdate
from app.services.packet_pipeline import create_packet_and_score

router = APIRouter(prefix="/api", tags=["packets"])


@router.post("/packets/ingest")
def ingest_packet_payload(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    session = db.query(MonitoringSession).filter(MonitoringSession.id == str(session_id)).first()
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    packet_hex = payload.get("payload_hex") or payload.get("payload")
    if not packet_hex:
        raise HTTPException(status_code=400, detail="payload_hex is required")

    result = create_packet_and_score(
        db=db,
        session_id=str(session_id),
        payload_hex=str(packet_hex),
        src_ip=payload.get("src_ip"),
        dst_ip=payload.get("dst_ip"),
        src_port=payload.get("src_port"),
        dst_port=payload.get("dst_port"),
        protocol=payload.get("protocol", "tcp"),
    )

    return {"status": "processed", **result}


@router.get("/packets")
def list_packets(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    packets = db.query(CapturedPacket).order_by(CapturedPacket.captured_at.desc()).all()
    return [
        {
            "id": str(packet.id),
            "session_id": str(packet.session_id),
            "src_ip": packet.src_ip,
            "dst_ip": packet.dst_ip,
            "src_port": packet.src_port,
            "dst_port": packet.dst_port,
            "protocol": packet.protocol,
            "packet_size": packet.packet_size,
            "payload_hex": packet.payload_hex,
            "captured_at": packet.captured_at.isoformat() if packet.captured_at else None,
            "is_processed": packet.is_processed,
        }
        for packet in packets
    ]


@router.get("/results/{packet_id}")
def get_packet_result(packet_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    try:
        packet_uuid = uuid.UUID(packet_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="packet_id must be a valid UUID")
    row = (
        db.query(CapturedPacket, DetectionResult)
        .join(DetectionResult, DetectionResult.packet_id == CapturedPacket.id)
        .join(MonitoringSession, MonitoringSession.id == CapturedPacket.session_id)
        .filter(CapturedPacket.id == packet_uuid, MonitoringSession.user_id == current_user.id)
        .order_by(DetectionResult.checked_at.desc())
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Result not found")
    packet, result = row
    return {
        "packet_id": str(packet.id),
        "result_id": str(result.id),
        "anomaly_score": result.anomaly_score,
        "threshold": result.threshold_value,
        "model_version": result.model_version,
        "is_anomalous": result.is_anomalous,
        "verdict": "anomalous" if result.is_anomalous else "normal",
        "checked_at": result.checked_at.isoformat() if result.checked_at else None,
    }


@router.get("/packets/{packet_id}")
def get_packet(packet_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    packet = db.query(CapturedPacket).filter(CapturedPacket.id == packet_id).first()
    if not packet:
        raise HTTPException(status_code=404, detail="Packet not found")
    return {
        "id": str(packet.id),
        "session_id": str(packet.session_id),
        "src_ip": packet.src_ip,
        "dst_ip": packet.dst_ip,
        "src_port": packet.src_port,
        "dst_port": packet.dst_port,
        "protocol": packet.protocol,
        "packet_size": packet.packet_size,
        "payload_hex": packet.payload_hex,
        "captured_at": packet.captured_at.isoformat() if packet.captured_at else None,
        "is_processed": packet.is_processed,
    }

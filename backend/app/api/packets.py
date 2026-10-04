from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.broker.zeek_consumer import event_hub
from app.database import get_db
from app.deps import get_current_user
from app.models.monitoring_session import MonitoringSession
from app.models.detection_result import DetectionResult
from app.models.packet import CapturedPacket
from app.schemas.packet import PacketIn, PacketLabelIn
from app.services.packet_pipeline import create_packet_and_score

router = APIRouter(prefix="/api", tags=["packets"])


@router.post("/packets/ingest")
def ingest_packet_payload(
    payload: PacketIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    session_id = payload.session_id
    session = db.query(MonitoringSession).filter(MonitoringSession.id == session_id).first()
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "running":
        raise HTTPException(status_code=409, detail="Start the monitoring session before ingesting packets")
    try:
        result = create_packet_and_score(
            db=db,
            session_id=session_id,
            payload_hex=payload.payload_hex,
            src_ip=payload.src_ip,
            dst_ip=payload.dst_ip,
            src_port=payload.src_port,
            dst_port=payload.dst_port,
            protocol=payload.protocol,
            maximum_bytes=session.packet_capture_limit_bytes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    event_hub.publish(str(session_id), {"event": "packet", **result["packet"], **result})
    return {"status": "processed", **{key: value for key, value in result.items() if key != "packet"}}


@router.get("/packets")
def list_packets(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not 1 <= limit <= 100 or offset < 0:
        raise HTTPException(status_code=422, detail="limit must be 1-100 and offset cannot be negative")
    packets = (
        db.query(CapturedPacket)
        .join(MonitoringSession, MonitoringSession.id == CapturedPacket.session_id)
        .filter(MonitoringSession.user_id == current_user.id)
        .order_by(CapturedPacket.captured_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
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
            "training_label": packet.training_label,
            "anomaly_score": packet.detections[-1].anomaly_score if packet.detections else None,
            "is_anomalous": packet.detections[-1].is_anomalous if packet.detections else None,
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


@router.get("/detections")
def list_detections(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not 1 <= limit <= 100 or offset < 0:
        raise HTTPException(status_code=422, detail="limit must be 1-100 and offset cannot be negative")
    rows = (
        db.query(DetectionResult, CapturedPacket)
        .join(CapturedPacket, CapturedPacket.id == DetectionResult.packet_id)
        .join(MonitoringSession, MonitoringSession.id == CapturedPacket.session_id)
        .filter(MonitoringSession.user_id == current_user.id)
        .order_by(DetectionResult.checked_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(result.id),
            "packet_id": str(packet.id),
            "session_id": str(packet.session_id),
            "src_ip": packet.src_ip,
            "dst_ip": packet.dst_ip,
            "protocol": packet.protocol,
            "packet_size": packet.packet_size,
            "anomaly_score": result.anomaly_score,
            "threshold": result.threshold_value,
            "model_version": result.model_version,
            "is_anomalous": result.is_anomalous,
            "training_label": packet.training_label,
            "checked_at": result.checked_at.isoformat() if result.checked_at else None,
        }
        for result, packet in rows
    ]


@router.patch("/packets/{packet_id}/label")
def set_packet_training_label(
    packet_id: str,
    payload: PacketLabelIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        packet_uuid = uuid.UUID(packet_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="packet_id must be a valid UUID") from exc
    packet = (
        db.query(CapturedPacket)
        .join(MonitoringSession, MonitoringSession.id == CapturedPacket.session_id)
        .filter(CapturedPacket.id == packet_uuid, MonitoringSession.user_id == current_user.id)
        .first()
    )
    if packet is None:
        raise HTTPException(status_code=404, detail="Packet not found")
    packet.training_label = payload.training_label
    db.commit()
    return {"packet_id": str(packet.id), "training_label": packet.training_label}


@router.get("/packets/{packet_id}")
def get_packet(packet_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    try:
        packet_uuid = uuid.UUID(packet_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="packet_id must be a valid UUID") from exc
    packet = (
        db.query(CapturedPacket)
        .join(MonitoringSession, MonitoringSession.id == CapturedPacket.session_id)
        .filter(CapturedPacket.id == packet_uuid, MonitoringSession.user_id == current_user.id)
        .first()
    )
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

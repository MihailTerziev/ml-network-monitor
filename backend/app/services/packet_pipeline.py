from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.detection_result import DetectionResult
from app.models.model_version import ModelVersion
from app.models.packet import CapturedPacket
from app.models.monitoring_session import MonitoringSession
from app.services.inference_service import AutoencoderInferenceService


def normalize_payload_hex(payload_hex: str, maximum_bytes: int) -> str:
    if not payload_hex:
        raise ValueError("payload_hex must not be empty")
    try:
        payload = bytes.fromhex(payload_hex)
    except ValueError as exc:
        raise ValueError("payload_hex must contain valid hexadecimal bytes") from exc
    if not payload:
        raise ValueError("payload_hex must contain at least one byte")
    return payload[:maximum_bytes].hex()


def create_packet_and_score(
    db: Session,
    session_id: uuid.UUID,
    payload_hex: str,
    src_ip: Optional[str] = None,
    dst_ip: Optional[str] = None,
    src_port: Optional[int] = None,
    dst_port: Optional[int] = None,
    protocol: Optional[str] = "tcp",
    model_path: Optional[str] = None,
    threshold: Optional[float] = None,
    training_label: Optional[str] = None,
    maximum_bytes: int = 64,
) -> Dict[str, Any]:
    session = db.query(MonitoringSession).filter(MonitoringSession.id == session_id).first()
    if session is None:
        raise ValueError(f"Monitoring session {session_id} does not exist")
    active_model = (
        db.query(ModelVersion)
        .filter(ModelVersion.status == "active")
        .filter((ModelVersion.owner_user_id == session.user_id) | (ModelVersion.owner_user_id.is_(None)))
        .order_by(ModelVersion.owner_user_id.is_(None), ModelVersion.created_at.desc())
        .first()
    )
    selected_model_path = model_path or (active_model.file_path if active_model else None)
    selected_threshold = threshold
    if selected_threshold is None and active_model is not None:
        selected_threshold = active_model.threshold
    started_at = perf_counter()
    scorer = AutoencoderInferenceService(model_path=selected_model_path, threshold=selected_threshold)
    payload_hex = normalize_payload_hex(payload_hex, min(maximum_bytes, scorer.number_of_bytes))
    score = scorer.score_payload(payload_hex)
    inference_time_ms = (perf_counter() - started_at) * 1000

    packet = CapturedPacket(
        session_id=session.id,
        src_ip=src_ip,
        dst_ip=dst_ip,
        src_port=src_port,
        dst_port=dst_port,
        protocol=protocol,
        packet_size=len(payload_hex) // 2 if payload_hex else 0,
        payload_hex=payload_hex,
        captured_at=datetime.utcnow(),
        is_processed=True,
        processed_at=datetime.utcnow(),
        training_label=training_label,
    )
    packet.id = uuid.uuid4()

    result = DetectionResult(
        packet_id=packet.id,
        model_version=active_model.version if active_model else Path(scorer.model_path).stem,
        model_path=model_path or scorer.model_path,
        threshold_value=float(score["threshold"]),
        anomaly_score=float(score["anomaly_score"]),
        is_anomalous=bool(score["is_anomalous"]),
        inference_time_ms=inference_time_ms,
        checked_at=datetime.utcnow(),
    )

    try:
        db.add(packet)
        db.add(result)
        db.commit()
        db.refresh(packet)
        db.refresh(result)
    except Exception:
        db.rollback()
        raise

    return {
        "packet_id": str(packet.id),
        "result_id": str(result.id),
        "anomaly_score": result.anomaly_score,
        "is_anomalous": result.is_anomalous,
        "threshold": result.threshold_value,
        "model_version": result.model_version,
        "checked_at": result.checked_at.isoformat() if result.checked_at else None,
        "packet": {
            "id": str(packet.id),
            "session_id": str(packet.session_id),
            "src_ip": packet.src_ip,
            "dst_ip": packet.dst_ip,
            "src_port": packet.src_port,
            "dst_port": packet.dst_port,
            "protocol": packet.protocol,
            "packet_size": packet.packet_size,
            "captured_at": packet.captured_at.isoformat(),
        },
    }

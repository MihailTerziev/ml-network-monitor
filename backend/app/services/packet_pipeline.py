from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.detection_result import DetectionResult
from app.models.packet import CapturedPacket
from app.services.inference_service import AutoencoderInferenceService


def create_packet_and_score(
    db: Session,
    session_id: str,
    payload_hex: str,
    src_ip: Optional[str] = None,
    dst_ip: Optional[str] = None,
    src_port: Optional[int] = None,
    dst_port: Optional[int] = None,
    protocol: Optional[str] = "tcp",
    model_path: Optional[str] = None,
    threshold: Optional[float] = None,
) -> Dict[str, Any]:
    packet = CapturedPacket(
        session_id=session_id,
        src_ip=src_ip,
        dst_ip=dst_ip,
        src_port=src_port,
        dst_port=dst_port,
        protocol=protocol,
        packet_size=len(payload_hex) // 2 if payload_hex else 0,
        payload_hex=payload_hex,
        captured_at=datetime.utcnow(),
        is_processed=False,
    )
    db.add(packet)
    db.commit()
    db.refresh(packet)

    scorer = AutoencoderInferenceService(model_path=model_path, threshold=threshold)
    score = scorer.score_payload(packet.payload_hex)

    result = DetectionResult(
        packet_id=packet.id,
        model_version="active",
        model_path=model_path or scorer.model_path,
        threshold_value=float(score["threshold"]),
        anomaly_score=float(score["anomaly_score"]),
        is_anomalous=bool(score["is_anomalous"]),
        inference_time_ms=0.0,
        checked_at=datetime.utcnow(),
    )

    db.add(result)
    packet.is_processed = True
    packet.processed_at = datetime.utcnow()
    db.commit()
    db.refresh(packet)
    db.refresh(result)

    return {
        "packet_id": str(packet.id),
        "result_id": str(result.id),
        "anomaly_score": result.anomaly_score,
        "is_anomalous": result.is_anomalous,
        "threshold": result.threshold_value,
        "model_version": result.model_version,
    }

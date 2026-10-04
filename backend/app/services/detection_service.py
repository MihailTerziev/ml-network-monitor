import json
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.detection_result import DetectionResult
from app.models.packet import CapturedPacket
from app.services.inference_service import AutoencoderInferenceService


def score_and_save_packet(db: Session, packet_id: str, model_path: Optional[str] = None, threshold: Optional[float] = None):
    packet = db.query(CapturedPacket).filter(CapturedPacket.id == packet_id).first()
    if packet is None:
        raise ValueError("Packet not found")

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
    return result

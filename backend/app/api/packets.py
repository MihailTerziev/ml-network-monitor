from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.detection_result import DetectionResult
from app.models.packet import CapturedPacket
from app.services.detection_service import score_and_save_packet

router = APIRouter(prefix="/api", tags=["packets"])


@router.post("/packets/{packet_id}/score")
def score_packet(
    packet_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        result = score_and_save_packet(db, packet_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"packet_id": packet_id, "status": "scored", "result_id": str(result.id), "is_anomalous": result.is_anomalous}


@router.get("/packets", response_model=List[dict])
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
            "captured_at": packet.captured_at.isoformat(),
            "is_processed": packet.is_processed,
        }
        for packet in packets
    ]


@router.get("/captures/{packet_id}")
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
        "captured_at": packet.captured_at.isoformat(),
        "is_processed": packet.is_processed,
    }


@router.get("/detections", response_model=List[dict])
def list_detections(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    results = db.query(DetectionResult).order_by(DetectionResult.checked_at.desc()).all()
    return [
        {
            "id": str(result.id),
            "packet_id": str(result.packet_id),
            "model_version": result.model_version,
            "model_path": result.model_path,
            "threshold_value": result.threshold_value,
            "anomaly_score": result.anomaly_score,
            "is_anomalous": result.is_anomalous,
            "inference_time_ms": result.inference_time_ms,
            "checked_at": result.checked_at.isoformat(),
        }
        for result in results
    ]

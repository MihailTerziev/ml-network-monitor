from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.packet import CapturedPacket
from app.models.detection_result import DetectionResult
from app.schemas.packet import PacketIn, PacketOut, DetectionResultOut
from app.services.packet_ingest import ingest_packet

router = APIRouter(prefix="/api", tags=["packets"])


@router.post("/packets/ingest")
def ingest_packet_route(payload: PacketIn, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    packet = ingest_packet(
        db=db,
        session_id=str(payload.session_id),
        src_ip=payload.src_ip,
        dst_ip=payload.dst_ip,
        src_port=payload.src_port,
        dst_port=payload.dst_port,
        protocol=payload.protocol,
        payload_hex=payload.payload_hex,
    )
    return {"packet_id": str(packet.id), "status": "saved"}


@router.get("/packets", response_model=List[PacketOut])
def list_packets(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return db.query(CapturedPacket).order_by(CapturedPacket.captured_at.desc()).all()


@router.get("/packets/{packet_id}", response_model=PacketOut)
def get_packet(packet_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    packet = db.query(CapturedPacket).filter(CapturedPacket.id == packet_id).first()
    if not packet:
        raise HTTPException(status_code=404, detail="Packet not found")
    return packet


@router.get("/detections", response_model=List[DetectionResultOut])
def list_detections(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return db.query(DetectionResult).order_by(DetectionResult.checked_at.desc()).all()

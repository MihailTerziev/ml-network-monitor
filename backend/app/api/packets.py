from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import CapturedPacket, DetectionResult
from app.schemas.packet import PacketOut, PacketIn, DetectionResultOut

router = APIRouter(prefix="/api", tags=["packets"])


@router.post("/packets/ingest")
def ingest_packet(payload: PacketIn, db: Session = Depends(get_db), current_user: object = Depends(get_current_user)):
    from app.services.packet_ingest import ingest_packet as save_packet

    packet = save_packet(
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
def list_packets(
    db: Session = Depends(get_db),
    current_user: object = Depends(get_current_user),
):
    packets = db.query(CapturedPacket).all()
    return packets


@router.get("/packets/{packet_id}", response_model=PacketOut)
def get_packet(packet_id: str, db: Session = Depends(get_db), current_user: object = Depends(get_current_user)):
    packet = db.query(CapturedPacket).filter(CapturedPacket.id == packet_id).first()
    if not packet:
        raise HTTPException(status_code=404, detail="Packet not found")
    return packet


@router.get("/detections", response_model=List[DetectionResultOut])
def list_detections(db: Session = Depends(get_db), current_user: object = Depends(get_current_user)):
    results = db.query(DetectionResult).order_by(DetectionResult.checked_at.desc()).all()
    return results

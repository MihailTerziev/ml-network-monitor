from typing import Optional
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.packet import CapturedPacket


def ingest_packet(
    db: Session,
    session_id: str,
    src_ip: Optional[str],
    dst_ip: Optional[str],
    src_port: Optional[int],
    dst_port: Optional[int],
    protocol: Optional[str],
    payload_hex: str,
):
    packet = CapturedPacket(
        session_id=session_id,
        src_ip=src_ip,
        dst_ip=dst_ip,
        src_port=src_port,
        dst_port=dst_port,
        protocol=protocol or "tcp",
        packet_size=len(payload_hex) // 2 if payload_hex else 0,
        payload_hex=payload_hex,
        captured_at=datetime.utcnow(),
        is_processed=False,
    )
    db.add(packet)
    db.commit()
    db.refresh(packet)
    return packet

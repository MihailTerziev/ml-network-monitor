from sqlalchemy import Column, String, DateTime, Integer, Boolean, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database import Base


class CapturedPacket(Base):
    __tablename__ = "captured_packets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("monitoring_sessions.id"), nullable=False)
    src_ip = Column(String, nullable=True)
    dst_ip = Column(String, nullable=True)
    src_port = Column(Integer, nullable=True)
    dst_port = Column(Integer, nullable=True)
    protocol = Column(String, nullable=True)
    packet_size = Column(Integer, nullable=True)
    payload_hex = Column(String, nullable=False)
    payload_bits_json = Column(String, nullable=True)
    training_label = Column(String, nullable=True)
    captured_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    is_processed = Column(Boolean, default=False)

    session = relationship("MonitoringSession", back_populates="packets")
    detections = relationship("DetectionResult", back_populates="packet")

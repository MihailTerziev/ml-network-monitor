from sqlalchemy import Column, String, DateTime, Float, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database import Base


class DetectionResult(Base):
    __tablename__ = "detection_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    packet_id = Column(UUID(as_uuid=True), ForeignKey("captured_packets.id"), nullable=False)
    model_version = Column(String, nullable=False)
    model_path = Column(String, nullable=True)
    threshold_value = Column(Float, nullable=False)
    anomaly_score = Column(Float, nullable=False)
    is_anomalous = Column(Boolean, default=False)
    inference_time_ms = Column(Float, nullable=True)
    checked_at = Column(DateTime, default=datetime.utcnow)

    packet = relationship("CapturedPacket", back_populates="detections")

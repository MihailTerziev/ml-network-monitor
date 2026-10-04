from sqlalchemy import Column, String, Boolean, DateTime, Integer, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sessions = relationship("MonitoringSession", back_populates="user")
    jobs = relationship("TrainingJob", back_populates="user")


class MonitoringSession(Base):
    __tablename__ = "monitoring_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    interface = Column(String, nullable=False)
    packet_capture_limit_bytes = Column(Integer, default=128)
    status = Column(String, default="stopped")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="sessions")
    packets = relationship("CapturedPacket", back_populates="session")


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
    captured_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    is_processed = Column(Boolean, default=False)

    session = relationship("MonitoringSession", back_populates="packets")
    detections = relationship("DetectionResult", back_populates="packet")


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


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version = Column(String, unique=True, nullable=False)
    file_path = Column(String, nullable=False)
    status = Column(String, default="trained")
    trained_on_samples = Column(Integer, default=0)
    accuracy = Column(Float, default=0.0)
    loss = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    activated_at = Column(DateTime, nullable=True)


class TrainingJob(Base):
    __tablename__ = "training_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    model_version_id = Column(UUID(as_uuid=True), ForeignKey("model_versions.id"), nullable=True)
    status = Column(String, default="pending")
    samples_used = Column(Integer, default=0)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(String, nullable=True)

    user = relationship("User", back_populates="jobs")

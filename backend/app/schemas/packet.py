from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class PacketIn(BaseModel):
    session_id: UUID
    src_ip: Optional[str] = None
    dst_ip: Optional[str] = None
    src_port: Optional[int] = None
    dst_port: Optional[int] = None
    protocol: Optional[str] = "tcp"
    payload_hex: str


class PacketOut(BaseModel):
    id: UUID
    session_id: UUID
    src_ip: Optional[str]
    dst_ip: Optional[str]
    src_port: Optional[int]
    dst_port: Optional[int]
    protocol: Optional[str]
    packet_size: Optional[int]
    payload_hex: str
    captured_at: str

    class Config:
        from_attributes = True


class DetectionResultOut(BaseModel):
    id: UUID
    packet_id: UUID
    model_version: str
    model_path: Optional[str]
    threshold_value: float
    anomaly_score: float
    is_anomalous: bool
    inference_time_ms: Optional[float]
    checked_at: str

    class Config:
        from_attributes = True

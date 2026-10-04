from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PacketIn(BaseModel):
    session_id: UUID
    src_ip: Optional[str] = Field(default=None, max_length=45)
    dst_ip: Optional[str] = Field(default=None, max_length=45)
    src_port: Optional[int] = Field(default=None, ge=0, le=65535)
    dst_port: Optional[int] = Field(default=None, ge=0, le=65535)
    protocol: Optional[str] = Field(default="tcp", max_length=32)
    payload_hex: str = Field(min_length=2, max_length=131070)


class PacketLabelIn(BaseModel):
    training_label: Optional[str] = Field(default=None, pattern="^(normal|anomalous|ignore)$")


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

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)

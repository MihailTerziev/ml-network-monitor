from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MonitoringSessionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    interface: str = Field(min_length=1, max_length=100)
    packet_capture_limit_bytes: int = Field(default=64, ge=1, le=64)


class MonitoringSessionUpdate(BaseModel):
    name: Optional[str] = None
    interface: Optional[str] = None
    packet_capture_limit_bytes: Optional[int] = Field(default=None, ge=1, le=64)


class MonitoringSessionOut(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    interface: str
    packet_capture_limit_bytes: int
    status: str

    model_config = ConfigDict(from_attributes=True)

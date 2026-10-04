from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class MonitoringSessionCreate(BaseModel):
    name: str
    interface: str
    packet_capture_limit_bytes: int = 128


class MonitoringSessionUpdate(BaseModel):
    name: Optional[str] = None
    interface: Optional[str] = None
    packet_capture_limit_bytes: Optional[int] = None


class MonitoringSessionOut(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    interface: str
    packet_capture_limit_bytes: int
    status: str

    class Config:
        from_attributes = True

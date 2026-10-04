from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ModelVersionOut(BaseModel):
    id: UUID
    version: str
    file_path: str
    status: str
    trained_on_samples: int
    accuracy: float
    loss: float

    class Config:
        from_attributes = True


class TrainingJobOut(BaseModel):
    id: UUID
    user_id: UUID
    model_version_id: Optional[UUID]
    status: str
    samples_used: int
    started_at: str
    completed_at: Optional[str]
    error_message: Optional[str]

    class Config:
        from_attributes = True

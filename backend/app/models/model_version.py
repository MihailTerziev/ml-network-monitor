from sqlalchemy import Column, String, DateTime, Integer, Float
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from app.database import Base


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

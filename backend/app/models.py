from app.database import Base
from app.models import User, MonitoringSession, CapturedPacket, DetectionResult, ModelVersion, TrainingJob

# Importing models makes tables discoverable for SQLAlchemy metadata

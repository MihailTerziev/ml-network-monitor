from __future__ import annotations

import logging
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np
from tensorflow import keras
from tensorflow.keras import layers
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models.model_version import ModelVersion
from app.models.packet import CapturedPacket
from app.models.monitoring_session import MonitoringSession
from app.models.training_job import TrainingJob
from app.services.inference_service import convert_payload_to_bits

logger = logging.getLogger(__name__)
_training_lock = threading.Lock()


def create_training_job(db: Session, user_id: uuid.UUID) -> TrainingJob:
    normal_samples = (
        db.query(CapturedPacket.id)
        .join(MonitoringSession, MonitoringSession.id == CapturedPacket.session_id)
        .filter(MonitoringSession.user_id == user_id, CapturedPacket.training_label == "normal")
        .count()
    )
    if normal_samples < 10:
        raise ValueError("Label at least 10 packets as normal before starting training")

    job = TrainingJob(user_id=user_id, status="pending", samples_used=normal_samples)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def train_model_job(job_id: str) -> None:
    with _training_lock:
        _run_training_job(job_id)


def _run_training_job(job_id: str) -> None:
    db = SessionLocal()
    model_file: Path | None = None
    temporary_file: Path | None = None
    try:
        job = db.query(TrainingJob).filter(TrainingJob.id == uuid.UUID(job_id)).first()
        if job is None:
            raise ValueError(f"Training job {job_id} was not found")
        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()

        rows = (
            db.query(CapturedPacket.payload_hex)
            .join(MonitoringSession, MonitoringSession.id == CapturedPacket.session_id)
            .filter(
                MonitoringSession.user_id == job.user_id,
                CapturedPacket.training_label == "normal",
            )
            .order_by(CapturedPacket.captured_at.asc())
            .all()
        )
        if len(rows) < 10:
            raise ValueError("At least 10 packets labeled normal are required")

        settings = get_settings()
        samples = np.asarray(
            [convert_payload_to_bits(row.payload_hex, number_of_bytes=64) for row in rows],
            dtype=np.float32,
        )
        shuffled_samples = samples[np.random.default_rng(42).permutation(len(samples))]
        split_at = max(2, int(len(shuffled_samples) * 0.8))
        if split_at >= len(samples):
            split_at = len(samples) - 1
        training, validation = shuffled_samples[:split_at], shuffled_samples[split_at:]
        model = keras.Sequential(
            [
                layers.Input(shape=(samples.shape[1],)),
                layers.Dense(256, activation="relu"),
                layers.Dropout(0.1),
                layers.Dense(128, activation="relu"),
                layers.Dense(64, activation="relu"),
                layers.Dense(128, activation="relu"),
                layers.Dense(256, activation="relu"),
                layers.Dense(samples.shape[1], activation="sigmoid"),
            ]
        )
        model.compile(optimizer="adam", loss="binary_crossentropy")
        model.fit(
            training,
            training,
            validation_data=(validation, validation),
            epochs=settings.training_epochs,
            batch_size=settings.training_batch_size,
            callbacks=[
                keras.callbacks.EarlyStopping(
                    monitor="val_loss",
                    min_delta=0.001,
                    patience=3,
                    restore_best_weights=True,
                )
            ],
            verbose=0,
        )

        predictions = model.predict(validation, batch_size=settings.training_batch_size, verbose=0)
        predictions = np.clip(predictions, 1e-7, 1.0 - 1e-7)
        losses = -np.mean(
            validation * np.log(predictions) + (1.0 - validation) * np.log(1.0 - predictions),
            axis=-1,
        )
        threshold = float(np.percentile(losses, settings.threshold_percentile))
        version = f"u{str(job.user_id)[:8]}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
        model_dir = Path(settings.model_dir).resolve()
        model_dir.mkdir(parents=True, exist_ok=True)
        model_file = model_dir / f"{version}.keras"
        temporary_file = model_dir / f".{version}.tmp.keras"
        model.save(temporary_file)
        os.replace(temporary_file, model_file)

        model_version = ModelVersion(
            version=version,
            file_path=str(model_file),
            owner_user_id=job.user_id,
            status="trained",
            trained_on_samples=len(samples),
            loss=float(np.mean(losses)),
            threshold=threshold,
        )
        db.add(model_version)
        db.flush()
        job.model_version_id = model_version.id
        job.samples_used = len(samples)
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("Training job %s failed", job_id)
        failed_job = db.query(TrainingJob).filter(TrainingJob.id == uuid.UUID(job_id)).first()
        if failed_job is not None:
            failed_job.status = "failed"
            failed_job.error_message = str(exc)[:1000]
            failed_job.completed_at = datetime.utcnow()
            db.commit()
        if model_file and model_file.exists():
            model_file.unlink()
    finally:
        if temporary_file and temporary_file.exists():
            temporary_file.unlink()
        db.close()

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import numpy as np
from fastapi import HTTPException
from tensorflow import keras

from app.config import get_settings

settings = get_settings()


def convert_payload_to_bits(hex_payload: str, number_of_bytes: int = 64):
    if not isinstance(hex_payload, str) or not hex_payload:
        raise HTTPException(status_code=422, detail="payload_hex must not be empty")
    try:
        bytes_sequence = bytes.fromhex(hex_payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"payload_hex is not valid hexadecimal: {exc}")
    bytes_sequence = bytes_sequence[:number_of_bytes].ljust(number_of_bytes, b"\x00")
    bytes_array = np.frombuffer(bytes_sequence, dtype=np.uint8)
    bits_array = np.unpackbits(bytes_array).astype(np.float32)
    return bits_array


@lru_cache(maxsize=4)
def _load_model(model_path: str):
    path = Path(model_path)
    if not path.is_file():
        raise HTTPException(status_code=503, detail=f"Model file not found: {path}")
    try:
        return keras.models.load_model(path)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=f"Unable to load model: {exc}") from exc


class AutoencoderInferenceService:
    def __init__(self, model_path: str | None = None, threshold: float | None = None):
        self.model_path = str(Path(model_path or settings.model_path).resolve())
        self.threshold = threshold if threshold is not None else settings.default_threshold
        self.model = _load_model(self.model_path)
        input_shape = self.model.input_shape
        if (
            isinstance(input_shape, list)
            or len(input_shape) != 2
            or not isinstance(input_shape[-1], int)
            or input_shape[-1] % 8
            or self.model.output_shape != input_shape
        ):
            raise HTTPException(status_code=503, detail="Model must accept a flat bit vector whose size is divisible by 8")
        self.number_of_bytes = input_shape[-1] // 8

    def reconstruction_error(self, data: np.ndarray):
        predictions = self.model.predict(data, batch_size=256, verbose=0)
        predictions = np.clip(predictions, 1e-7, 1.0 - 1e-7)
        loss = -np.mean(
            data * np.log(predictions) + (1.0 - data) * np.log(1.0 - predictions),
            axis=-1,
        )
        return loss

    def score_payload(self, payload_hex: str) -> Dict[str, Any]:
        bit_vector = convert_payload_to_bits(payload_hex, self.number_of_bytes)
        sample = bit_vector.reshape(1, -1).astype(np.float32)
        loss = float(self.reconstruction_error(sample)[0])
        is_anomalous = bool(loss > self.threshold)
        return {
            "anomaly_score": loss,
            "is_anomalous": is_anomalous,
            "threshold": self.threshold,
        }

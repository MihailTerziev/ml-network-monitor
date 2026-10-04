from typing import Any, Dict

import numpy as np
from fastapi import HTTPException
from tensorflow import keras

from app.config import get_settings

settings = get_settings()


def convert_payload_to_bits(hex_payload: str, number_of_bytes: int = 64):
    if not hex_payload:
        hex_payload = "00" * number_of_bytes
    hex_chars_count = number_of_bytes * 2
    payload_fragment = hex_payload[:hex_chars_count]
    payload_fragment = payload_fragment.ljust(hex_chars_count, "0")
    try:
        bytes_sequence = bytes.fromhex(payload_fragment)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"payload_hex is not valid hexadecimal: {exc}")
    bytes_array = np.frombuffer(bytes_sequence, dtype=np.uint8)
    bits_array = np.unpackbits(bytes_array).astype(np.float32)
    return bits_array


class AutoencoderInferenceService:
    def __init__(self, model_path: str | None = None, threshold: float | None = None):
        self.model_path = model_path or settings.model_path
        self.threshold = threshold if threshold is not None else settings.default_threshold
        self.model = keras.models.load_model(self.model_path)

    def reconstruction_error(self, data: np.ndarray):
        predictions = self.model.predict(data, batch_size=256, verbose=0)
        predictions = np.clip(predictions, 1e-7, 1.0 - 1e-7)
        loss = -np.mean(
            data * np.log(predictions) + (1.0 - data) * np.log(1.0 - predictions),
            axis=-1,
        )
        return loss

    def score_payload(self, payload_hex: str) -> Dict[str, Any]:
        bit_vector = convert_payload_to_bits(payload_hex)
        sample = bit_vector.reshape(1, -1).astype(np.float32)
        loss = float(self.reconstruction_error(sample)[0])
        is_anomalous = bool(loss > self.threshold)
        return {
            "anomaly_score": loss,
            "is_anomalous": is_anomalous,
            "threshold": self.threshold,
        }

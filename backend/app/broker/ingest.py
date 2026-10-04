from __future__ import annotations

import hmac
import logging
from typing import Any

from pydantic import ValidationError

from app.broker.zeek_consumer import event_hub
from app.config import get_settings
from app.database import SessionLocal
from app.models.monitoring_session import MonitoringSession
from app.schemas.packet import PacketIn
from app.services.packet_pipeline import create_packet_and_score

logger = logging.getLogger(__name__)


def process_zeek_message(message: dict[str, Any]) -> None:
    settings = get_settings()
    supplied_token = message.get("token")
    if not isinstance(supplied_token, str) or not settings.zeek_shared_token or not hmac.compare_digest(
        supplied_token, settings.zeek_shared_token
    ):
        logger.warning("Rejected Zeek bridge message with invalid token")
        return

    try:
        packet = PacketIn.model_validate(message)
    except ValidationError:
        logger.warning("Rejected malformed Zeek bridge packet")
        return

    db = SessionLocal()
    try:
        session = db.query(MonitoringSession).filter(MonitoringSession.id == packet.session_id).first()
        if session is None or session.status != "running":
            logger.warning("Ignoring packet for unknown or stopped monitoring session %s", packet.session_id)
            return
        result = create_packet_and_score(
            db=db,
            session_id=session.id,
            payload_hex=packet.payload_hex,
            src_ip=packet.src_ip,
            dst_ip=packet.dst_ip,
            src_port=packet.src_port,
            dst_port=packet.dst_port,
            protocol=packet.protocol,
            maximum_bytes=session.packet_capture_limit_bytes,
        )
        event_hub.publish(str(packet.session_id), {"event": "packet", **result["packet"], **result})
    finally:
        db.close()

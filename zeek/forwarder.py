import ipaddress
import json
import logging
import os
import signal
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

logger = logging.getLogger("ml-network-monitor.zeek")
stopping = False
active_process: subprocess.Popen[str] | None = None


def parse_capture_record(line: str, session_id: str, token: str) -> dict[str, object]:
    fields = line.rstrip("\r\n").split("|")
    if len(fields) != 6 or fields[0] != "MLNM":
        raise ValueError("expected an MLNM record with five fields")
    fields = fields[1:]

    src_ip = str(ipaddress.ip_address(fields[0]))
    src_port = int(fields[1])
    dst_ip = str(ipaddress.ip_address(fields[2]))
    dst_port = int(fields[3])
    payload_hex = fields[4].lower()
    if not 0 <= src_port <= 65535 or not 0 <= dst_port <= 65535:
        raise ValueError("port is outside the valid range")
    if not payload_hex or len(payload_hex) > 128 or len(payload_hex) % 2:
        raise ValueError("payload must contain between 1 and 64 bytes")
    if any(char not in "0123456789abcdef" for char in payload_hex):
        raise ValueError("payload is not valid hexadecimal")

    return {
        "token": token,
        "session_id": session_id,
        "payload_hex": payload_hex,
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "src_port": src_port,
        "dst_port": dst_port,
        "protocol": "tcp",
    }


class BridgeClient:
    def __init__(self, host: str, port: int) -> None:
        self.address = (host, port)
        self.connection: socket.socket | None = None

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def _connect(self) -> socket.socket:
        delay = 1
        while not stopping:
            try:
                return socket.create_connection(self.address, timeout=5)
            except OSError as exc:
                logger.warning("Cannot connect to the backend Zeek bridge: %s", exc)
                time.sleep(delay)
                delay = min(delay * 2, 10)
        raise InterruptedError("sensor is stopping")

    def send(self, record: dict[str, object]) -> None:
        if self.connection is None:
            self.connection = self._connect()
        try:
            message = json.dumps(record, separators=(",", ":")).encode("utf-8") + b"\n"
            self.connection.sendall(message)
        except OSError:
            self.close()
            raise


def required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} must be set to run the Zeek sensor")
    return value


def handle_stop_signal(signum: int, _frame: object) -> None:
    global active_process, stopping
    stopping = True
    if active_process is not None and active_process.poll() is None:
        active_process.terminate()


def run() -> int:
    global active_process
    interface = required_environment("ZEEK_INTERFACE")
    session_id = str(uuid.UUID(required_environment("MLNM_SESSION_ID")))
    token = required_environment("ZEEK_SHARED_TOKEN")
    if len(token) < 32:
        raise ValueError("ZEEK_SHARED_TOKEN must contain at least 32 characters")

    host = os.environ.get("ZEEK_BRIDGE_HOST", "127.0.0.1")
    port = int(os.environ.get("ZEEK_BRIDGE_PORT", "9999"))
    if not 1 <= port <= 65535:
        raise ValueError("ZEEK_BRIDGE_PORT must be between 1 and 65535")

    policy = Path(__file__).with_name("monitor.zeek")
    command = ["zeek", "-C", "-i", interface, str(policy)]
    logger.info("Starting Zeek capture on interface %s for session %s", interface, session_id)
    signal.signal(signal.SIGTERM, handle_stop_signal)
    signal.signal(signal.SIGINT, handle_stop_signal)
    process = subprocess.Popen(command, stdout=subprocess.PIPE, text=True, bufsize=1)
    active_process = process
    bridge = BridgeClient(host, port)

    try:
        assert process.stdout is not None
        for line in process.stdout:
            if stopping:
                break
            if not line.startswith("MLNM|"):
                continue
            try:
                record = parse_capture_record(line, session_id, token)
            except (ValueError, OverflowError) as exc:
                logger.error("Ignoring malformed Zeek output: %s", exc)
                continue
            try:
                bridge.send(record)
            except OSError as exc:
                logger.error("Dropping captured TCP content because bridge send failed: %s", exc)
        if stopping:
            process.terminate()
        return_code = process.wait()
        if return_code != 0 and not stopping:
            logger.error("Zeek exited with status %d", return_code)
        return 0 if stopping else return_code
    finally:
        active_process = None
        bridge.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    try:
        raise SystemExit(run())
    except (ValueError, OSError) as exc:
        logger.error("%s", exc)
        raise SystemExit(1) from exc

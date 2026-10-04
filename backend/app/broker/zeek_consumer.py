from __future__ import annotations

import asyncio
import json
import logging
import socket
import threading
from collections import defaultdict
from threading import Thread
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class MonitoringEventHub:
    def __init__(self):
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def subscribe(self, session_id: str) -> asyncio.Queue[dict[str, Any]]:
        self._loop = asyncio.get_running_loop()
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        self._subscribers[session_id].add(queue)
        return queue

    def unsubscribe(self, session_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers[session_id].discard(queue)

    def publish(self, session_id: str, event: dict[str, Any]) -> None:
        if self._loop is None or self._loop.is_closed():
            return

        def deliver() -> None:
            for queue in tuple(self._subscribers[session_id]):
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning("Dropping monitoring event for a slow websocket client")

        self._loop.call_soon_threadsafe(deliver)


event_hub = MonitoringEventHub()


class ZeekSocketConsumer:
    max_message_bytes = 262_144

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 9999,
        on_message: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.host = host
        self.port = port
        self.on_message = on_message
        self.server_socket: Optional[socket.socket] = None
        self.thread: Optional[Thread] = None
        self.running = False
        self._stop_event = threading.Event()
        self._started_event = threading.Event()
        self._startup_error: Optional[OSError] = None

    def start(self) -> None:
        if self.running:
            return
        self._stop_event.clear()
        self._started_event.clear()
        self._startup_error = None
        self.running = True
        self.thread = Thread(target=self._run, daemon=True)
        self.thread.start()
        if not self._started_event.wait(timeout=3):
            self.stop()
            raise RuntimeError("Timed out starting the Zeek bridge")
        if self._startup_error:
            raise RuntimeError(f"Unable to start the Zeek bridge: {self._startup_error}") from self._startup_error

    def stop(self) -> None:
        self._stop_event.set()
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        if self.thread:
            self.thread.join(timeout=2)

    def _run(self) -> None:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind((self.host, self.port))
                sock.listen(5)
                sock.settimeout(1)
                self.server_socket = sock
                self._started_event.set()
                while not self._stop_event.is_set():
                    try:
                        conn, _ = sock.accept()
                    except socket.timeout:
                        continue
                    try:
                        with conn:
                            conn.settimeout(1)
                            buffer = b""
                            while not self._stop_event.is_set():
                                try:
                                    data = conn.recv(4096)
                                except socket.timeout:
                                    continue
                                if not data:
                                    break
                                buffer += data
                                if len(buffer) > self.max_message_bytes and b"\n" not in buffer:
                                    logger.warning("Ignoring oversized Zeek bridge message")
                                    break
                                while b"\n" in buffer:
                                    line, buffer = buffer.split(b"\n", 1)
                                    if len(line) > self.max_message_bytes:
                                        logger.warning("Ignoring oversized Zeek bridge message")
                                        continue
                                    payload = line.decode("utf-8", errors="replace").strip()
                                    if not payload:
                                        continue
                                    try:
                                        message = json.loads(payload)
                                    except json.JSONDecodeError:
                                        logger.warning("Ignoring malformed Zeek bridge JSON")
                                        continue
                                    if not isinstance(message, dict):
                                        logger.warning("Ignoring non-object Zeek bridge message")
                                        continue
                                    if self.on_message:
                                        try:
                                            self.on_message(message)
                                        except Exception:
                                            logger.exception("Failed to process Zeek bridge message")
                    except OSError:
                        if not self._stop_event.is_set():
                            logger.exception("Zeek bridge socket failed")
                        break
        except OSError as exc:
            if not self._started_event.is_set():
                self._startup_error = exc
                self._started_event.set()
                logger.exception("Unable to bind Zeek bridge socket")
            elif not self._stop_event.is_set():
                logger.exception("Zeek bridge socket failed")
        finally:
            self.running = False

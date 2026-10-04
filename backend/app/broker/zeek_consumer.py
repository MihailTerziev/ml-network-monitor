from __future__ import annotations

import json
import socket
from threading import Thread
from typing import Any, Callable, Dict, Optional


class ZeekSocketConsumer:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 9999,
        on_message: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.host = host
        self.port = port
        self.on_message = on_message
        self.server_socket: Optional[socket.socket] = None
        self.thread: Optional[Thread] = None
        self.running = False

    def start(self) -> None:
        self.running = True
        self.thread = Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.running = False
        if self.server_socket:
            self.server_socket.close()

    def _run(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, self.port))
            sock.listen(5)
            self.server_socket = sock
            while self.running:
                try:
                    conn, _ = sock.accept()
                    with conn:
                        while self.running:
                            data = conn.recv(4096)
                            if not data:
                                break
                            payload = data.decode("utf-8", errors="replace").strip()
                            if not payload:
                                continue
                            try:
                                message = json.loads(payload)
                            except json.JSONDecodeError:
                                message = {"raw": payload}
                            if self.on_message:
                                self.on_message(message)
                except OSError:
                    break

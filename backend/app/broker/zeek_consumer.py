import socket
import json
from threading import Thread
from typing import Callable


class ZeekSocketConsumer:
    def __init__(self, host: str = "127.0.0.1", port: int = 9999, on_message: Callable | None = None):
        self.host = host
        self.port = port
        self.on_message = on_message
        self.socket = None
        self._thread = None
        self._running = False

    def start(self):
        self._running = True
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self.socket:
            self.socket.close()

    def _run(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, self.port))
            sock.listen(5)
            self.socket = sock
            while self._running:
                try:
                    conn, _ = sock.accept()
                    with conn:
                        while self._running:
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

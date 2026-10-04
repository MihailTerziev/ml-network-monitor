import json
import socket
import threading

from app.broker.zeek_consumer import ZeekSocketConsumer


def test_consumer_reads_fragmented_newline_delimited_messages():
    received = []
    all_messages = threading.Event()

    def on_message(message):
        received.append(message)
        if len(received) == 2:
            all_messages.set()

    consumer = ZeekSocketConsumer(host="127.0.0.1", port=0, on_message=on_message)
    consumer.start()
    try:
        port = consumer.server_socket.getsockname()[1]
        with socket.create_connection(("127.0.0.1", port), timeout=2) as client:
            first = json.dumps({"sequence": 1}).encode()
            second = json.dumps({"sequence": 2}).encode() + b"\n"
            client.sendall(first[:5])
            client.sendall(first[5:] + b"\n" + second)
        assert all_messages.wait(timeout=2)
        assert received == [{"sequence": 1}, {"sequence": 2}]
    finally:
        consumer.stop()

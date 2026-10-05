import pytest

from forwarder import parse_capture_record


SESSION_ID = "21a69ade-935b-4f7e-8f87-31d94ca792fa"
TOKEN = "t" * 32


def test_parse_capture_record_builds_bridge_message():
    record = parse_capture_record(
        "MLNM|192.0.2.1|51515|2001:db8::2|443|160301\r\n",
        SESSION_ID,
        TOKEN,
    )

    assert record == {
        "token": TOKEN,
        "session_id": SESSION_ID,
        "payload_hex": "160301",
        "src_ip": "192.0.2.1",
        "dst_ip": "2001:db8::2",
        "src_port": 51515,
        "dst_port": 443,
        "protocol": "tcp",
    }


@pytest.mark.parametrize(
    "line",
    [
        "not-a-record",
        "MLNM|192.0.2.1|70000|192.0.2.2|443|00",
        "MLNM|192.0.2.1|80|192.0.2.2|443|0",
        "MLNM|192.0.2.1|80|192.0.2.2|443|zz",
        f"MLNM|192.0.2.1|80|192.0.2.2|443|{'00' * 65}",
    ],
)
def test_parse_capture_record_rejects_invalid_fields(line):
    with pytest.raises(ValueError):
        parse_capture_record(line, SESSION_ID, TOKEN)

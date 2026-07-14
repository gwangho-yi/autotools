import json
import socket
import time


def test_motion_signal_emitted(qtbot):
    from core.ipc_server import IpcServer

    server = IpcServer()
    server.start()
    time.sleep(0.15)

    try:
        with qtbot.waitSignal(server.motion_received, timeout=2000) as blocker:
            with socket.create_connection(("127.0.0.1", 54321), timeout=1.0) as s:
                s.sendall(
                    json.dumps({"event": "motion", "x": 42, "y": 99}).encode() + b"\n"
                )
    finally:
        server.stop()

    assert blocker.args == [42, 99]


def test_invalid_message_ignored(qtbot):
    from core.ipc_server import IpcServer

    server = IpcServer()
    received = []
    server.motion_received.connect(lambda x, y: received.append((x, y)))
    server.start()
    time.sleep(0.15)

    try:
        with socket.create_connection(("127.0.0.1", 54321), timeout=1.0) as s:
            s.sendall(b"not json\n")
        time.sleep(0.2)
    finally:
        server.stop()

    assert received == []


def test_color_match_signal_emitted(qtbot):
    from core.ipc_server import IpcServer

    server = IpcServer()
    server.start()
    time.sleep(0.15)

    try:
        with qtbot.waitSignal(server.color_match_received, timeout=2000) as blocker:
            with socket.create_connection(("127.0.0.1", 54321), timeout=1.0) as s:
                s.sendall(
                    json.dumps({"event": "color_match", "x": 111, "y": 222}).encode() + b"\n"
                )
    finally:
        server.stop()

    assert blocker.args == [111, 222]

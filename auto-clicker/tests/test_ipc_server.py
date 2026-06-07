import json
import socket
import threading
import time


def _start_test_server(port: int):
    """Start a simple TCP server that accepts one connection and holds it."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(1)
    srv.settimeout(3.0)
    conns = []

    def _accept():
        try:
            conn, _ = srv.accept()
            conns.append(conn)
        except OSError:
            pass

    t = threading.Thread(target=_accept, daemon=True)
    t.start()
    return srv, conns, t


def test_motion_signal_emitted(qtbot):
    from core.ipc_client import IpcClient

    srv, conns, _ = _start_test_server(54321)
    client = IpcClient()
    client.start()
    time.sleep(0.2)  # wait for connection

    try:
        with qtbot.waitSignal(client.motion_received, timeout=2000) as blocker:
            assert conns, "client did not connect to test server"
            msg = json.dumps({"event": "motion", "x": 10, "y": 20}) + "\n"
            conns[0].sendall(msg.encode())
    finally:
        client.stop()
        srv.close()

    assert blocker.args == [10, 20]


def test_invalid_message_ignored(qtbot):
    from core.ipc_client import IpcClient

    srv, conns, _ = _start_test_server(54321)
    received = []
    client = IpcClient()
    client.motion_received.connect(lambda x, y: received.append((x, y)))
    client.start()
    time.sleep(0.2)

    try:
        assert conns, "client did not connect to test server"
        conns[0].sendall(b"not json\n")
        time.sleep(0.2)
    finally:
        client.stop()
        srv.close()

    assert received == []

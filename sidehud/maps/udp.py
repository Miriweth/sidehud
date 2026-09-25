import json
import socket
import threading


class UdpListener(threading.Thread):
    """One JSON object per datagram, see docs/plugin-spec.md. Binds localhost only."""

    def __init__(self, state, port, host="127.0.0.1"):
        super().__init__(daemon=True)
        self.state = state
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))
        self.port = self.sock.getsockname()[1]

    def run(self):
        while True:
            data, _ = self.sock.recvfrom(65535)
            try:
                msg = json.loads(data)
            except ValueError:
                continue
            self.state.update(msg, source="udp")

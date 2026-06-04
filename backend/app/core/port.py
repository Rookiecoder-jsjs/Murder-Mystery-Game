"""Port detection utility - finds available ports for the server."""

import json
import os
import socket


PORT_FILE = os.path.join(os.path.dirname(__file__), "..", "..", ".port.json")


def is_port_available(port: int) -> bool:
    """Check if a port is available on all interfaces."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.1)
        if s.connect_ex(("127.0.0.1", port)) == 0:
            return False

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def find_available_port(start_port: int = 8000, max_attempts: int = 100) -> int:
    """Find the first available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        if is_port_available(port):
            return port
    raise RuntimeError(
        f"No available port found in range {start_port}-{start_port + max_attempts}"
    )


def write_port_file(port: int) -> None:
    """Write the backend port to .port.json for the frontend to discover."""
    port_file = os.path.abspath(PORT_FILE)
    os.makedirs(os.path.dirname(port_file), exist_ok=True)
    with open(port_file, "w") as f:
        json.dump({"backend_port": port}, f)

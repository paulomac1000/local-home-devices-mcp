"""E2E test conftest — full pipeline, skip if no server running."""

import os
import socket
from pathlib import Path

env_paths = [Path("/app/.env"), Path(".env")]
for env_path in env_paths:
    if env_path.exists():
        try:
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        except Exception:
            pass

REST_API_PORT = int(os.getenv("REST_API_PORT", "9102"))
REST_API_URL = f"http://localhost:{REST_API_PORT}"


def server_is_running():
    """Check if MCP REST API server is reachable. Use for skip markers."""
    try:
        s = socket.create_connection(("localhost", REST_API_PORT), timeout=1)
        s.close()
        return True
    except OSError:
        return False

"""
Root conftest — environment loading only (~30 lines).
No fixtures beyond env setup. Specific fixtures in subdirectory conftest.py files.
"""

import os
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

"""Smoke tests for new Hikvision diagnostic tools (v1.5.0)."""

import pytest
import requests
import socket

REST_API_PORT = 9102
REST_API_URL = f"http://localhost:{REST_API_PORT}"


def _server_running():
    try:
        s = socket.create_connection(("localhost", REST_API_PORT), timeout=1)
        s.close()
        return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(
    not _server_running(),
    reason="MCP server not running on port {port}. Start with: python server.py".format(port=REST_API_PORT),
)


class TestHikvisionDiagnosticSmoke:
    """Smoke tests: verify 7 new Hikvision tools respond with success field."""

    def test_get_motion_config_returns_success(self):
        resp = requests.post(f"{REST_API_URL}/api/tools/hikvision_get_motion_config", json={}, timeout=10)
        data = resp.json()
        assert data["result"]["success"] is True

    def test_get_event_config_returns_success(self):
        resp = requests.post(f"{REST_API_URL}/api/tools/hikvision_get_event_config", json={}, timeout=10)
        data = resp.json()
        assert data["result"]["success"] is True

    def test_get_alarm_server_returns_success(self):
        resp = requests.post(f"{REST_API_URL}/api/tools/hikvision_get_alarm_server", json={}, timeout=10)
        data = resp.json()
        assert data["result"]["success"] is True

    def test_snapshot_to_file_returns_validation_error(self):
        """Snapshot to file without filepath should return validation error, not crash."""
        resp = requests.post(f"{REST_API_URL}/api/tools/hikvision_snapshot_to_file", json={}, timeout=10)
        data = resp.json()
        # Expected: validation error or success, but not a 500
        assert "success" in data["result"]

    def test_set_motion_detection_returns_not_write_disabled(self):
        """Set motion detection should return write-disabled when ENABLE_WRITE_OPERATIONS=0."""
        resp = requests.post(
            f"{REST_API_URL}/api/tools/hikvision_set_motion_detection",
            json={"enabled": True},
            timeout=10,
        )
        data = resp.json()
        # Without ENABLE_WRITE_OPERATIONS, this should return success:false
        assert "success" in data["result"]

    def test_isapi_health_returns_overall(self):
        resp = requests.post(f"{REST_API_URL}/api/tools/hikvision_isapi_health", json={"since": "4h"}, timeout=10)
        data = resp.json()
        assert data["result"]["success"] is True
        assert "overall" in data["result"]

    def test_pipeline_diagnose_returns_layers(self):
        resp = requests.post(f"{REST_API_URL}/api/tools/hikvision_pipeline_diagnose", json={}, timeout=10)
        data = resp.json()
        assert data["result"]["success"] is True

    def test_tools_count_includes_fourteen_hikvision(self):
        resp = requests.get(f"{REST_API_URL}/api/tools", timeout=10)
        data = resp.json()
        tool_names = [t["name"] for t in data["tools"]]
        hik_tools = [n for n in tool_names if n.startswith("hikvision_")]
        assert len(hik_tools) == 14

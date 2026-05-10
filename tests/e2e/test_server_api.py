"""E2E tests: full REST API pipeline."""

import pytest
import requests

from .conftest import REST_API_URL, server_is_running

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        not server_is_running(),
        reason="MCP server not running",
    ),
]


class TestServerAPI:
    """Server REST API integration tests."""

    def test_health_endpoint(self):
        resp = requests.get(f"{REST_API_URL}/health", timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    def test_api_health(self):
        resp = requests.get(f"{REST_API_URL}/api/health", timeout=5)
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_tools_list_endpoint(self):
        resp = requests.get(f"{REST_API_URL}/api/tools", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["total"] == 13
        tool_names = [t["name"] for t in data["tools"]]
        assert "iot_discover_devices" in tool_names
        assert "iot_get_device_info" in tool_names
        assert "iot_set_power" in tool_names

    def test_call_tool_via_rest(self):
        resp = requests.post(
            f"{REST_API_URL}/api/tools/iot_list_devices",
            json={},
            timeout=10,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["tool"] == "iot_list_devices"

    def test_nonexistent_tool_returns_404(self):
        resp = requests.post(
            f"{REST_API_URL}/api/tools/nonexistent_tool_xyz",
            json={},
            timeout=10,
        )
        assert resp.status_code == 404
        data = resp.json()
        assert data["success"] is False

    def test_tool_call_invalid_json(self):
        resp = requests.post(
            f"{REST_API_URL}/api/tools/iot_list_devices",
            data="not json",
            headers={"Content-Type": "text/plain"},
            timeout=10,
        )
        assert resp.status_code in (200, 400, 415, 500)

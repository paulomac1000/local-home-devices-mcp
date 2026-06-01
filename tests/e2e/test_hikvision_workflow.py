"""E2E tests: Hikvision doorbell REST API workflow."""

import pytest

from .conftest import REST_API_URL, server_is_running

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        not server_is_running(),
        reason="MCP server not running",
    ),
]


def _call_tool(tool_name, **params):
    import requests

    resp = requests.post(
        f"{REST_API_URL}/api/tools/{tool_name}",
        json=params,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


class TestHikvisionE2E:
    """Full pipeline: status -> check_vmd -> device_info -> snapshot."""

    def test_container_status_via_rest(self):
        data = _call_tool("hikvision_container_status")
        result = data["result"]
        assert result["success"] is True
        assert "running" in result["data"]

    def test_device_info_via_rest(self):
        data = _call_tool("hikvision_device_info")
        result = data["result"]
        assert result["success"] is True
        assert result["data"]["model"] == "DS-KV6113-WPE1(C)"

    def test_check_vmd_via_rest(self):
        data = _call_tool("hikvision_check_vmd", since="4h")
        result = data["result"]
        assert result["success"] is True

    def test_take_snapshot_via_rest(self):
        data = _call_tool("hikvision_take_snapshot")
        result = data["result"]
        assert result["success"] is True
        assert result["data"]["size_bytes"] > 0

    def test_container_logs_via_rest(self):
        data = _call_tool("hikvision_container_logs", since="1h", tail=10)
        result = data["result"]
        assert result["success"] is True

    def test_tools_include_hikvision(self):
        import requests

        resp = requests.get(f"{REST_API_URL}/api/tools", timeout=10)
        data = resp.json()
        tool_names = [t["name"] for t in data["tools"]]
        hik_tools = [n for n in tool_names if n.startswith("hikvision_")]
        assert len(hik_tools) == 7

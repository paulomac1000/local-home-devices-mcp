"""E2E test: OpenHASP full workflow against live panel."""

import pytest

from .conftest import REST_API_URL, server_is_running

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        not server_is_running(),
        reason="MCP server not running",
    ),
]

PANEL_IP = "192.168.0.239"


def _call_tool(tool_name, **params):
    import requests

    resp = requests.post(
        f"{REST_API_URL}/api/tools/{tool_name}",
        json=params,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


class TestOpenHASPE2EWorkflow:
    """Full pipeline: detect -> status -> diagnose -> fix -> verify."""

    def test_workflow_detect(self):
        data = _call_tool("openhasp_detect", ip_address=PANEL_IP)
        result = data["result"]
        assert result["success"] is True
        assert result["data"]["is_openhasp"] is True
        assert result["data"]["name"] == "plate"

    def test_workflow_status(self):
        data = _call_tool("openhasp_status", identifier=PANEL_IP)
        result = data["result"]
        assert result["success"] is True
        assert "bckl" in result["data"]

    def test_workflow_backlight_diag(self):
        data = _call_tool("openhasp_check_backlight", identifier=PANEL_IP)
        result = data["result"]
        assert result["success"] is True
        assert "issues" in result["data"]

    def test_workflow_config(self):
        data = _call_tool("openhasp_get_config", identifier=PANEL_IP)
        result = data["result"]
        assert result["success"] is True
        assert "hasp" in result["data"]["config"]

    def test_workflow_health(self):
        data = _call_tool("openhasp_health", identifier=PANEL_IP)
        result = data["result"]
        assert result["success"] is True
        assert result["data"]["health_level"] in ("healthy", "degraded", "critical")

    def test_workflow_iot_check_device(self):
        data = _call_tool("iot_check_device", ip_address=PANEL_IP)
        result = data["result"]
        assert result["success"] is True
        assert result["data"]["is_iot_device"] is True

    def test_workflow_tools_include_openhasp(self):
        """Verify OpenHASP tools are in the tool list."""
        import requests

        resp = requests.get(
            f"{REST_API_URL}/api/tools",
            timeout=10,
        )
        data = resp.json()
        tool_names = [t["name"] for t in data["tools"]]
        hasp_tools = [n for n in tool_names if n.startswith("openhasp_")]
        assert len(hasp_tools) == 20
        assert data["total"] == 51

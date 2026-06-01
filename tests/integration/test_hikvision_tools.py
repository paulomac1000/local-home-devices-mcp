"""Integration tests - Hikvision doorbell (Docker socket + ISAPI)."""

import json
import socket

import pytest

PANEL_IP = "192.168.1.101"


def _doorbell_reachable():
    try:
        s = socket.create_connection((PANEL_IP, 80), timeout=2)
        s.close()
        return True
    except OSError:
        return False


def _docker_available():
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect("/var/run/docker.sock")
        s.close()
        return True
    except (OSError, FileNotFoundError):
        return False


pytestmark = pytest.mark.skipif(
    not (_doorbell_reachable() or _docker_available()),
    reason="Hikvision doorbell or Docker socket not accessible",
)


def _get_result(mcp_client, tool_name, **kwargs):
    result = mcp_client.call_tool(tool_name, **kwargs)
    return json.loads(result) if isinstance(result, str) else result


def _get_data(mcp_client, tool_name, **kwargs):
    result = _get_result(mcp_client, tool_name, **kwargs)
    return result.get("data", {})


class TestHikvisionIntegration:
    def test_container_status_returns_success(self, mcp_client):
        data = _get_result(mcp_client, "hikvision_container_status")
        assert data["success"] is True
        assert "running" in data["data"]

    def test_device_info_returns_correct_model(self, mcp_client):
        data = _get_result(mcp_client, "hikvision_device_info")
        assert data["success"] is True
        assert data["data"]["model"] == "DS-KV6113-WPE1(C)"
        assert data["data"]["firmwareVersion"] == "V2.2.65"

    def test_check_vmd_returns_valid(self, mcp_client):
        data = _get_result(mcp_client, "hikvision_check_vmd", since="4h")
        assert data["success"] is True
        assert "vmd_count" in data["data"]
        assert "isapi_healthy" in data["data"]

    def test_container_logs_returns_content(self, mcp_client):
        data = _get_result(mcp_client, "hikvision_container_logs", since="1h", tail=10)
        assert data["success"] is True
        assert data["data"]["log_size_chars"] > 0

    def test_take_snapshot_success(self, mcp_client):
        data = _get_result(mcp_client, "hikvision_take_snapshot")
        assert data["success"] is True
        assert data["data"]["format"] == "jpeg"
        assert data["data"]["size_bytes"] > 1000

    def test_restart_container_write_guard(self, mcp_client):
        data = _get_result(mcp_client, "hikvision_restart_container")
        assert data["success"] is True

    def test_open_gate_write_guard(self, mcp_client):
        data = _get_result(mcp_client, "hikvision_open_gate")
        assert data["success"] is True

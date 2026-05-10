"""Integration tests — real MQTT broker and network devices (if available)."""

import json
import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not bool(os.getenv("MQTT_BROKER")),
        reason="MQTT_BROKER not configured — skipping integration tests",
    ),
]


def _get_result(mcp_client, tool_name, **kwargs):
    result = mcp_client.call_tool(tool_name, **kwargs)
    return json.loads(result) if isinstance(result, str) else result


def _get_data(mcp_client, tool_name, **kwargs):
    """Call tool and return the data portion of the response."""
    result = _get_result(mcp_client, tool_name, **kwargs)
    return result.get("data", {})


def _pick_device_name(mcp_client):
    """Get first cached device with a valid name, or return dummy."""
    data = _get_result(mcp_client, "iot_list_devices")
    if not data.get("success"):
        return {"name": "NoDevice", "ip": "192.168.1.199"}
    devices = _get_data(mcp_client, "iot_list_devices").get("devices", [])
    for dev in devices:
        name = dev.get("name")
        if name and name.strip() and name != "None":
            return {"name": name, "ip": dev.get("ip", "192.168.1.100")}
    return {"name": "NoDevice", "ip": "192.168.1.199"}


class TestIntegrationDiscovery:
    """Discovery against the real network."""

    def test_scan_discovers_devices(self, mcp_client):
        result = mcp_client.call_tool("iot_discover_devices")
        data = json.loads(result) if isinstance(result, str) else result
        assert data.get("success") is True

    def test_list_returns_cached_devices(self, mcp_client):
        result = mcp_client.call_tool("iot_list_devices")
        data = json.loads(result) if isinstance(result, str) else result
        assert data.get("success") is True

    def test_check_device_router(self, mcp_client):
        result = mcp_client.call_tool("iot_check_device", ip_address="192.168.0.1")
        data = json.loads(result) if isinstance(result, str) else result
        assert data.get("success") is True

    def test_find_device_by_name_nonexistent(self, mcp_client):
        result = mcp_client.call_tool("iot_find_device_by_name", name="nonexistent_device_xyz")
        data = json.loads(result) if isinstance(result, str) else result
        assert "success" in data


class TestIntegrationDeviceInfo:
    """Device info tools — error paths via MCP wrapper."""

    def test_get_device_info_name_not_found(self, mcp_client):
        data = _get_result(mcp_client, "iot_get_device_info", identifier="NoSuchDevice_XYZ")
        assert data["success"] is False
        assert "Could not resolve" in data["error"]["message"]

    def test_get_device_power_name_not_found(self, mcp_client):
        data = _get_result(mcp_client, "iot_get_device_power", identifier="NoSuchDevice_XYZ")
        assert data["success"] is False
        assert "Could not resolve" in data["error"]["message"]


class TestIntegrationControlErrors:
    """Control tools — error paths (no real devices needed)."""

    def test_set_power_name_not_found(self, mcp_client):
        data = _get_result(mcp_client, "iot_set_power", identifier="NoSuchDevice_XYZ", state="ON")
        assert data["success"] is False
        assert "Could not resolve" in data["error"]["message"]

    def test_set_power_invalid_state(self, mcp_client):
        data = _get_result(mcp_client, "iot_set_power", identifier="192.168.1.100", state="INVALID")
        assert data["success"] is False

    def test_set_brightness_name_not_found(self, mcp_client):
        data = _get_result(
            mcp_client,
            "iot_set_brightness",
            identifier="NoSuchDevice_XYZ",
            brightness=50,
        )
        assert data["success"] is False
        assert "Could not resolve" in data["error"]["message"]

    def test_restart_name_not_found(self, mcp_client):
        data = _get_result(mcp_client, "iot_restart_device", identifier="NoSuchDevice_XYZ")
        assert data["success"] is False
        assert "Could not resolve" in data["error"]["message"]

    def test_get_wifi_name_not_found(self, mcp_client):
        data = _get_result(mcp_client, "iot_get_wifi_config", identifier="NoSuchDevice_XYZ")
        assert data["success"] is False
        assert "Could not resolve" in data["error"]["message"]


class TestIntegrationDeviceErrorPaths:
    """Device error paths via unreachable IPs."""

    def test_get_device_info_unreachable_ip(self, mcp_client):
        data = _get_result(mcp_client, "iot_get_device_info", identifier="192.168.1.199")
        assert data["success"] is False

    def test_get_device_power_unreachable_ip(self, mcp_client):
        data = _get_result(mcp_client, "iot_get_device_power", identifier="192.168.1.199")
        assert data["success"] is False


class TestIntegrationMQTT:
    """MQTT operations against the configured broker."""

    def test_build_command_topic(self, mcp_client):
        data = _get_result(mcp_client, "iot_mqtt_build_command_topic", device_name="tasmota_test")
        assert data.get("success") is True

    def test_mqtt_publish(self, mcp_client):
        data = _get_result(
            mcp_client,
            "iot_mqtt_publish",
            topic="test/integration/ping",
            payload="pong",
        )
        assert "success" in data

    def test_mqtt_get_state_timeout(self, mcp_client):
        data = _get_result(
            mcp_client,
            "iot_mqtt_get_state",
            topic_prefix="nonexistent_device_test",
            timeout_seconds=2,
        )
        assert "success" in data


class TestIntegrationRealDeviceReadOnly:
    """Read-only operations against real discovered devices (safe, no state changes)."""

    @pytest.fixture(autouse=True)
    def _skip_if_no_devices(self, mcp_client):
        data = _get_result(mcp_client, "iot_list_devices")
        devices = data.get("data", {}).get("devices", [])
        if not devices:
            pytest.skip("No real devices in cache — CI environment with no Tasmota/OpenBK")

    def test_get_device_info_by_real_name(self, mcp_client):
        dev = _pick_device_name(mcp_client)
        data = _get_result(mcp_client, "iot_get_device_info", identifier=dev["name"])
        assert data["success"] is True
        assert data["data"]["device_type"] == "tasmota"
        assert "info" in data["data"]
        assert data["data"]["info"]["name"] is not None

    def test_get_device_power_by_real_name(self, mcp_client):
        dev = _pick_device_name(mcp_client)
        data = _get_result(mcp_client, "iot_get_device_power", identifier=dev["name"])
        assert data["success"] is True
        assert data["data"]["state"] in ("ON", "OFF")

    def test_get_wifi_by_real_name(self, mcp_client):
        dev = _pick_device_name(mcp_client)
        data = _get_result(mcp_client, "iot_get_wifi_config", identifier=dev["name"])
        assert data["success"] is True
        assert "wifi" in data["data"]

    def test_find_device_by_real_name(self, mcp_client):
        dev = _pick_device_name(mcp_client)
        data = _get_result(mcp_client, "iot_find_device_by_name", name=dev["name"])
        assert data["success"] is True
        assert data["data"]["device"]["ip"] == dev["ip"]

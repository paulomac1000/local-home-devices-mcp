"""Smoke tests: critical tools returning success via REST API."""

import pytest
import requests

from .conftest import REST_API_URL, server_is_running

pytestmark = pytest.mark.skipif(
    not server_is_running(),
    reason="MCP server not running",
)


def _call_tool(tool_name, **params):
    resp = requests.post(
        f"{REST_API_URL}/api/tools/{tool_name}",
        json=params,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


class TestDiscoverySmoke:
    """Smoke tests for discovery tools."""

    def test_discover_devices_returns_success(self):
        data = _call_tool("iot_discover_devices")
        assert data["success"] is True

    def test_list_devices_returns_success(self):
        data = _call_tool("iot_list_devices")
        assert data["success"] is True

    def test_check_device_returns_success(self):
        data = _call_tool("iot_check_device", ip_address="192.168.1.1")
        assert data["success"] is True

    def test_find_device_by_name_returns_success(self):
        data = _call_tool("iot_find_device_by_name", name="test")
        assert data["success"] is True


class TestDeviceSmoke:
    """Smoke tests for device info tools."""

    def test_get_device_info_returns_success(self):
        data = _call_tool("iot_get_device_info", identifier="192.168.1.100")
        assert data["success"] is True

    def test_get_device_power_returns_success(self):
        data = _call_tool("iot_get_device_power", identifier="192.168.1.100")
        assert data["success"] is True


class TestControlSmoke:
    """Smoke tests for control tools."""

    def test_set_power_returns_success(self):
        data = _call_tool("iot_set_power", identifier="192.168.1.100", state="ON")
        assert data["success"] is True

    def test_set_brightness_returns_success(self):
        data = _call_tool(
            "iot_set_brightness", identifier="192.168.1.100", brightness=50
        )
        assert data["success"] is True

    def test_restart_device_returns_success(self):
        data = _call_tool("iot_restart_device", identifier="192.168.1.100")
        assert data["success"] is True

    def test_get_wifi_config_returns_success(self):
        data = _call_tool("iot_get_wifi_config", identifier="192.168.1.100")
        assert data["success"] is True


class TestMqttSmoke:
    """Smoke tests for MQTT tools."""

    def test_mqtt_build_command_topic_returns_success(self):
        data = _call_tool("iot_mqtt_build_command_topic", device_name="tasmota_test")
        assert data["success"] is True

    def test_mqtt_publish_returns_success(self):
        data = _call_tool("iot_mqtt_publish", topic="test/topic", payload="ON")
        assert data["success"] is True

    def test_mqtt_get_state_returns_success(self):
        data = _call_tool("iot_mqtt_get_state", topic_prefix="tasmota_test", timeout=2)
        assert data["success"] is True


class TestResponseFormat:
    """Compliance: all tools must return success field."""

    ALL_TOOLS = [
        "iot_discover_devices",
        "iot_list_devices",
        "iot_check_device",
        "iot_find_device_by_name",
        "iot_get_device_info",
        "iot_get_device_power",
        "iot_set_power",
        "iot_set_brightness",
        "iot_restart_device",
        "iot_get_wifi_config",
        "iot_mqtt_publish",
        "iot_mqtt_get_state",
        "iot_mqtt_build_command_topic",
    ]

    @staticmethod
    def _call_safe(name, **kwargs):
        try:
            return _call_tool(name, **kwargs)
        except Exception:
            return None

    def test_all_13_tools_return_success_field(self):
        call_map = {
            "iot_discover_devices": {},
            "iot_list_devices": {},
            "iot_check_device": {"ip_address": "192.168.1.1"},
            "iot_find_device_by_name": {"name": "test"},
            "iot_get_device_info": {"identifier": "192.168.1.100"},
            "iot_get_device_power": {"identifier": "192.168.1.100"},
            "iot_set_power": {"identifier": "192.168.1.100", "state": "ON"},
            "iot_set_brightness": {"identifier": "192.168.1.100", "brightness": 50},
            "iot_restart_device": {"identifier": "192.168.1.100"},
            "iot_get_wifi_config": {"identifier": "192.168.1.100"},
            "iot_mqtt_publish": {"topic": "test/topic", "payload": "ON"},
            "iot_mqtt_get_state": {"topic_prefix": "tasmota_test", "timeout": 2},
            "iot_mqtt_build_command_topic": {"device_name": "tasmota_test"},
        }
        for tool_name in self.ALL_TOOLS:
            data = self._call_safe(tool_name, **call_map.get(tool_name, {}))
            assert data is not None, f"Tool '{tool_name}' did not respond"
            assert data.get("success") is not None, (
                f"Tool '{tool_name}' missing 'success' field"
            )

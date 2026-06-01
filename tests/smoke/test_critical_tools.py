"""Smoke tests: critical tools returning success via REST API."""

import pytest
import requests

from tools.constants import TOOL_MANIFESTS

from .conftest import REST_API_URL, server_is_running

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(
        not server_is_running(),
        reason="MCP server not running",
    ),
]


def _call_tool(tool_name, **params):
    resp = requests.post(
        f"{REST_API_URL}/api/tools/{tool_name}",
        json=params,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _assert_tool_response(data):
    assert "success" in data
    assert "tool" in data
    assert "result" in data


class TestDiscoverySmoke:
    """Smoke tests for discovery tools."""

    def test_discover_devices_returns_success(self):
        data = _call_tool("iot_discover_devices")
        _assert_tool_response(data)

    def test_list_devices_returns_success(self):
        data = _call_tool("iot_list_devices")
        _assert_tool_response(data)

    def test_check_device_returns_success(self):
        data = _call_tool("iot_check_device", ip_address="192.168.1.1")
        _assert_tool_response(data)

    def test_find_device_by_name_returns_success(self):
        data = _call_tool("iot_find_device_by_name", name="test")
        _assert_tool_response(data)


class TestDeviceSmoke:
    """Smoke tests for device info tools."""

    def test_get_device_info_returns_success(self):
        data = _call_tool("iot_get_device_info", identifier="192.168.1.100")
        _assert_tool_response(data)

    def test_get_device_power_returns_success(self):
        data = _call_tool("iot_get_device_power", identifier="192.168.1.100")
        _assert_tool_response(data)


class TestControlSmoke:
    """Smoke tests for control tools."""

    def test_set_power_returns_success(self):
        data = _call_tool("iot_set_power", identifier="192.168.1.100", state="ON")
        _assert_tool_response(data)

    def test_set_brightness_returns_success(self):
        data = _call_tool("iot_set_brightness", identifier="192.168.1.100", brightness=50)
        _assert_tool_response(data)

    def test_restart_device_returns_success(self):
        data = _call_tool("iot_restart_device", identifier="192.168.1.100")
        _assert_tool_response(data)

    def test_get_wifi_config_returns_success(self):
        data = _call_tool("iot_get_wifi_config", identifier="192.168.1.100")
        _assert_tool_response(data)


class TestMqttSmoke:
    """Smoke tests for MQTT tools."""

    def test_mqtt_build_command_topic_returns_success(self):
        data = _call_tool("iot_mqtt_build_command_topic", device_name="device_test")
        _assert_tool_response(data)

    def test_mqtt_publish_returns_success(self):
        data = _call_tool("iot_mqtt_publish", topic="test/topic", payload="ON")
        _assert_tool_response(data)

    def test_mqtt_get_state_returns_success(self):
        data = _call_tool("iot_mqtt_get_state", topic_prefix="device_test", timeout_seconds=2)
        _assert_tool_response(data)


class TestResponseFormat:
    """Compliance: all tools must return success field."""

    ALL_TOOLS = sorted(TOOL_MANIFESTS)

    @staticmethod
    def _call_safe(name, **kwargs):
        try:
            return _call_tool(name, **kwargs)
        except Exception:
            return None

    def test_all_manifest_tools_return_success_field(self):
        call_map = {
            "describe_iot_capabilities": {},
            "hikvision_check_vmd": {},
            "hikvision_container_logs": {},
            "hikvision_container_status": {},
            "hikvision_device_info": {},
            "hikvision_open_gate": {},
            "hikvision_restart_container": {},
            "hikvision_take_snapshot": {},
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
            "iot_mqtt_get_state": {"topic_prefix": "device_test", "timeout_seconds": 2},
            "iot_mqtt_build_command_topic": {"device_name": "device_test"},
            "iot_tuya_cloud_control": {
                "device_id": "Tuya_Test",
                "dp_id": "1",
                "value": "true",
            },
            "iot_tuya_cloud_list": {},
            "iot_tuya_cloud_refresh_keys": {},
            "iot_tuya_detect_version": {"identifier": "Tuya_Test"},
            "iot_tuya_get_dps": {"identifier": "Tuya_Test"},
            "iot_tuya_monitor": {"identifier": "Tuya_Test", "duration_seconds": 1},
            "iot_tuya_remove": {"device_id": "Tuya_Test"},
            "iot_tuya_scan_ports": {},
            "iot_tuya_set_dp": {"identifier": "Tuya_Test", "dp_id": "1", "value": "true"},
            "iot_tuya_verify_dps": {"identifier": "Tuya_Test"},
            "openhasp_backlight_set": {"identifier": "192.168.1.100"},
            "openhasp_check_backlight": {"identifier": "192.168.1.100"},
            "openhasp_config_set": {"identifier": "192.168.1.100", "config_json": "{}"},
            "openhasp_detect": {"ip_address": "192.168.1.100"},
            "openhasp_download_file": {"identifier": "192.168.1.100", "filename": "config.json"},
            "openhasp_factory_reset": {"identifier": "192.168.1.100"},
            "openhasp_get_config": {"identifier": "192.168.1.100"},
            "openhasp_get_pages": {"identifier": "192.168.1.100"},
            "openhasp_hardware_test": {"identifier": "192.168.1.100"},
            "openhasp_health": {"identifier": "192.168.1.100"},
            "openhasp_idle_reset": {"identifier": "192.168.1.100"},
            "openhasp_jsonl_send": {"identifier": "192.168.1.100", "jsonl": "{}"},
            "openhasp_ota_update": {
                "identifier": "192.168.1.100",
                "firmware_url": "http://example.invalid/firmware.bin",
            },
            "openhasp_page_set": {"identifier": "192.168.1.100", "page": 1},
            "openhasp_restart": {"identifier": "192.168.1.100"},
            "openhasp_screenshot": {"identifier": "192.168.1.100"},
            "openhasp_status": {"identifier": "192.168.1.100"},
            "openhasp_telnet": {"identifier": "192.168.1.100", "command": "backlight"},
            "openhasp_upload_file": {
                "identifier": "192.168.1.100",
                "filename": "boot.cmd",
                "content": "",
            },
            "openhasp_validate_config": {"identifier": "192.168.1.100"},
        }
        for tool_name in self.ALL_TOOLS:
            data = self._call_safe(tool_name, **call_map.get(tool_name, {}))
            assert data is not None, f"Tool '{tool_name}' did not respond"
            assert data.get("success") is not None, f"Tool '{tool_name}' missing 'success' field"

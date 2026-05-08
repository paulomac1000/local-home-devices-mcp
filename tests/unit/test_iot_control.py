"""
Unit tests for IoT MCP device control tools.

Tests power, brightness, restart, and WiFi config operations
with name resolution from the discovery cache.
"""

import json
from unittest.mock import MagicMock, patch

from tools.iot_control import (
    _get_wifi_config,
    _restart_device,
    _set_brightness,
    _set_power,
    register_iot_control_tools,
)


class TestPowerControl:
    """Tests for power control operations."""

    def test_set_power_tasmota_on(self):
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.100"):
            with patch(
                "tools.iot_discovery._detect_device_type",
                return_value="tasmota",
            ):
                with patch("tools.iot_control.requests.get") as mock_get:
                    resp = MagicMock()
                    resp.status_code = 200
                    resp.json.return_value = {"POWER1": "ON"}
                    mock_get.return_value = resp
                    result = _set_power("192.168.1.100", "ON")
                    data = json.loads(result)
                    assert data["success"] is True
                    assert data["device_type"] == "tasmota"
                    assert data["actual_state"] == "ON"
                    assert data["resolved_from"] == "192.168.1.100"

    def test_set_power_tasmota_toggle(self):
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.100"):
            with patch(
                "tools.iot_discovery._detect_device_type",
                return_value="tasmota",
            ):
                with patch("tools.iot_control.requests.get") as mock_get:
                    resp = MagicMock()
                    resp.status_code = 200
                    resp.json.return_value = {"POWER1": "ON"}
                    mock_get.return_value = resp
                    result = _set_power("192.168.1.100", "TOGGLE")
                    data = json.loads(result)
                    assert data["success"] is True
                    assert data["requested_state"] == "TOGGLE"

    def test_set_power_openbk(self):
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.101"):
            with patch(
                "tools.iot_discovery._detect_device_type",
                return_value="openbk",
            ):
                with patch("tools.iot_control.requests.get") as mock_get:
                    resp = MagicMock()
                    resp.status_code = 200
                    mock_get.return_value = resp
                    result = _set_power("192.168.1.101", "ON")
                    data = json.loads(result)
                    assert data["success"] is True
                    assert data["device_type"] == "openbk"

    def test_set_power_by_name(self):
        with patch(
            "tools.iot_discovery._resolve_ip",
            return_value="192.168.1.100",
        ):
            with patch(
                "tools.iot_discovery._detect_device_type",
                return_value="tasmota",
            ):
                with patch("tools.iot_control.requests.get") as mock_get:
                    resp = MagicMock()
                    resp.status_code = 200
                    resp.json.return_value = {"POWER": "ON"}
                    mock_get.return_value = resp
                    result = _set_power("Light_Bathroom", "ON")
                    data = json.loads(result)
                    assert data["success"] is True
                    assert data["resolved_from"] == "Light_Bathroom"
                    assert data["ip"] == "192.168.1.100"

    def test_set_power_name_not_found(self):
        with patch("tools.iot_discovery._resolve_ip", return_value=None):
            with patch("tools.iot_discovery._get_cached_devices", return_value=[]):
                result = _set_power("UnknownDevice", "ON")
                data = json.loads(result)
                assert data["success"] is False
                assert "Could not resolve" in data["error"]

    def test_set_power_invalid_state(self):
        with patch(
            "tools.iot_discovery._resolve_ip",
            return_value="192.168.1.100",
        ):
            with patch(
                "tools.iot_discovery._detect_device_type",
                return_value="tasmota",
            ):
                result = _set_power("192.168.1.100", "INVALID")
                data = json.loads(result)
                assert data["success"] is False
                assert "Invalid state" in data["error"]

    def test_set_power_device_not_found(self):
        with patch(
            "tools.iot_discovery._resolve_ip",
            return_value="192.168.1.200",
        ):
            with patch(
                "tools.iot_discovery._detect_device_type",
                return_value=None,
            ):
                result = _set_power("192.168.1.200", "ON")
                data = json.loads(result)
                assert data["success"] is False


class TestPowerControlErrors:
    """Edge case and error path tests for power control."""

    def test_set_power_tasmota_http_error(self):
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.100"):
            with patch(
                "tools.iot_discovery._detect_device_type", return_value="tasmota"
            ):
                with patch("tools.iot_control.requests.get") as mock_get:
                    resp = MagicMock()
                    resp.status_code = 500
                    mock_get.return_value = resp
                    result = _set_power("192.168.1.100", "ON")
                    data = json.loads(result)
                    assert data["success"] is False
                    assert "HTTP 500" in data["error"]

    def test_set_power_openbk_toggle(self):
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.101"):
            with patch(
                "tools.iot_discovery._detect_device_type", return_value="openbk"
            ):
                with patch("tools.iot_control.requests.get") as mock_get:
                    resp = MagicMock()
                    resp.status_code = 200
                    mock_get.return_value = resp
                    result = _set_power("192.168.1.101", "TOGGLE")
                    data = json.loads(result)
                    assert data["success"] is True
                    assert data["requested_state"] == "TOGGLE"

    def test_set_power_openbk_http_error(self):
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.101"):
            with patch(
                "tools.iot_discovery._detect_device_type", return_value="openbk"
            ):
                with patch("tools.iot_control.requests.get") as mock_get:
                    resp = MagicMock()
                    resp.status_code = 403
                    mock_get.return_value = resp
                    result = _set_power("192.168.1.101", "ON")
                    data = json.loads(result)
                    assert data["success"] is False
                    assert "HTTP 403" in data["error"]

    def test_set_power_unsupported_device_type(self):
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.100"):
            with patch(
                "tools.iot_discovery._detect_device_type", return_value="zigbee"
            ):
                result = _set_power("192.168.1.100", "ON")
                data = json.loads(result)
                assert data["success"] is False
                assert "Unsupported device type" in data["error"]


class TestBrightnessControl:
    """Tests for brightness control."""

    def test_set_brightness_tasmota(self):
        with patch(
            "tools.iot_discovery._resolve_ip",
            return_value="192.168.1.100",
        ):
            with patch(
                "tools.iot_discovery._detect_device_type",
                return_value="tasmota",
            ):
                with patch("tools.iot_control.requests.get") as mock_get:
                    resp = MagicMock()
                    resp.status_code = 200
                    mock_get.return_value = resp
                    result = _set_brightness("192.168.1.100", 75)
                    data = json.loads(result)
                    assert data["success"] is True
                    assert data["brightness"] == 75

    def test_set_brightness_by_name(self):
        with patch(
            "tools.iot_discovery._resolve_ip",
            return_value="192.168.1.101",
        ):
            with patch(
                "tools.iot_discovery._detect_device_type",
                return_value="openbk",
            ):
                with patch("tools.iot_control.requests.get") as mock_get:
                    resp = MagicMock()
                    resp.status_code = 200
                    mock_get.return_value = resp
                    result = _set_brightness("Light_LivingRoom", 50)
                    data = json.loads(result)
                    assert data["success"] is True
                    assert data["resolved_from"] == "Light_LivingRoom"

    def test_set_brightness_clamped_high(self):
        with patch(
            "tools.iot_discovery._resolve_ip",
            return_value="192.168.1.101",
        ):
            with patch(
                "tools.iot_discovery._detect_device_type",
                return_value="openbk",
            ):
                with patch("tools.iot_control.requests.get") as mock_get:
                    resp = MagicMock()
                    resp.status_code = 200
                    mock_get.return_value = resp
                    result = _set_brightness("192.168.1.101", 150)
                    data = json.loads(result)
                    assert data["success"] is True
                    assert data["brightness"] == 100

    def test_set_brightness_clamped_low(self):
        with patch(
            "tools.iot_discovery._resolve_ip",
            return_value="192.168.1.101",
        ):
            with patch(
                "tools.iot_discovery._detect_device_type",
                return_value="openbk",
            ):
                with patch("tools.iot_control.requests.get") as mock_get:
                    resp = MagicMock()
                    resp.status_code = 200
                    mock_get.return_value = resp
                    result = _set_brightness("192.168.1.101", -10)
                    data = json.loads(result)
                    assert data["success"] is True
                    assert data["brightness"] == 0


class TestBrightnessControlErrors:
    """Edge case and error path tests for brightness control."""

    def test_set_brightness_name_not_resolved(self):
        with patch("tools.iot_discovery._resolve_ip", return_value=None):
            with patch("tools.iot_discovery._get_cached_devices", return_value=[]):
                result = _set_brightness("UnknownDevice", 50)
                data = json.loads(result)
                assert data["success"] is False
                assert "Could not resolve" in data["error"]

    def test_set_brightness_device_not_found(self):
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.200"):
            with patch("tools.iot_discovery._detect_device_type", return_value=None):
                result = _set_brightness("192.168.1.200", 50)
                data = json.loads(result)
                assert data["success"] is False
                assert "No IoT device found" in data["error"]

    def test_set_brightness_unsupported_type(self):
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.100"):
            with patch(
                "tools.iot_discovery._detect_device_type", return_value="esphome"
            ):
                result = _set_brightness("192.168.1.100", 50)
                data = json.loads(result)
                assert data["success"] is False
                assert "Unsupported device type" in data["error"]

    def test_set_brightness_tasmota_http_error(self):
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.100"):
            with patch(
                "tools.iot_discovery._detect_device_type", return_value="tasmota"
            ):
                with patch("tools.iot_control.requests.get") as mock_get:
                    resp = MagicMock()
                    resp.status_code = 500
                    mock_get.return_value = resp
                    result = _set_brightness("192.168.1.100", 80)
                    data = json.loads(result)
                    assert data["success"] is False


class TestRestart:
    """Tests for device restart."""

    def test_restart_tasmota(self):
        with patch(
            "tools.iot_discovery._resolve_ip",
            return_value="192.168.1.100",
        ):
            with patch(
                "tools.iot_discovery._detect_device_type",
                return_value="tasmota",
            ):
                with patch("tools.iot_control.requests.get") as mock_get:
                    resp = MagicMock()
                    resp.status_code = 200
                    mock_get.return_value = resp
                    result = _restart_device("192.168.1.100")
                    data = json.loads(result)
                    assert data["success"] is True
                    assert "Restart command sent" in data["message"]

    def test_restart_openbk(self):
        with patch(
            "tools.iot_discovery._resolve_ip",
            return_value="192.168.1.101",
        ):
            with patch(
                "tools.iot_discovery._detect_device_type",
                return_value="openbk",
            ):
                with patch("tools.iot_control.requests.get") as mock_get:
                    resp = MagicMock()
                    resp.status_code = 200
                    mock_get.return_value = resp
                    result = _restart_device("192.168.1.101")
                    data = json.loads(result)
                    assert data["success"] is True
                    assert data["device_type"] == "openbk"

    def test_restart_by_name(self):
        with patch(
            "tools.iot_discovery._resolve_ip",
            return_value="192.168.1.100",
        ):
            with patch(
                "tools.iot_discovery._detect_device_type",
                return_value="tasmota",
            ):
                with patch("tools.iot_control.requests.get") as mock_get:
                    resp = MagicMock()
                    resp.status_code = 200
                    mock_get.return_value = resp
                    result = _restart_device("Curtains_LivingRoom")
                    data = json.loads(result)
                    assert data["success"] is True
                    assert data["resolved_from"] == "Curtains_LivingRoom"


class TestRestartErrors:
    """Edge case and error path tests for device restart."""

    def test_restart_name_not_resolved(self):
        with patch("tools.iot_discovery._resolve_ip", return_value=None):
            with patch("tools.iot_discovery._get_cached_devices", return_value=[]):
                result = _restart_device("UnknownDevice")
                data = json.loads(result)
                assert data["success"] is False
                assert "Could not resolve" in data["error"]

    def test_restart_tasmota_http_error(self):
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.100"):
            with patch(
                "tools.iot_discovery._detect_device_type", return_value="tasmota"
            ):
                with patch("tools.iot_control.requests.get") as mock_get:
                    resp = MagicMock()
                    resp.status_code = 500
                    mock_get.return_value = resp
                    result = _restart_device("192.168.1.100")
                    data = json.loads(result)
                    assert data["success"] is False
                    assert "Device not found" in data["error"]

    def test_restart_unsupported_type(self):
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.100"):
            with patch("tools.iot_discovery._detect_device_type", return_value="wiz"):
                result = _restart_device("192.168.1.100")
                data = json.loads(result)
                assert data["success"] is False
                assert "Device not found" in data["error"]


class TestWifiConfig:
    """Tests for WiFi configuration retrieval."""

    def test_get_wifi_tasmota(self):
        with patch(
            "tools.iot_discovery._resolve_ip",
            return_value="192.168.1.100",
        ):
            with patch(
                "tools.iot_discovery._detect_device_type",
                return_value="tasmota",
            ):
                with patch("tools.iot_control.requests.get") as mock_get:
                    resp = MagicMock()
                    resp.status_code = 200
                    resp.json.return_value = {
                        "StatusSTS": {
                            "Wifi": {
                                "SSId": "MyNetwork",
                                "RSSI": -60,
                                "Signal": -60,
                                "Mac": "AA:BB:CC:DD:EE:FF",
                                "IPAddress": "192.168.1.100",
                                "Gateway": "192.168.1.1",
                                "Mode": "11n",
                            }
                        }
                    }
                    mock_get.return_value = resp
                    result = _get_wifi_config("192.168.1.100")
                    data = json.loads(result)
                    assert data["success"] is True
                    assert data["wifi"]["ssid"] == "MyNetwork"
                    assert data["wifi"]["rssi"] == -60
                    assert data["wifi"]["mac"] == "AA:BB:CC:DD:EE:FF"

    def test_get_wifi_openbk(self):
        with patch(
            "tools.iot_discovery._resolve_ip",
            return_value="192.168.1.101",
        ):
            with patch(
                "tools.iot_discovery._detect_device_type",
                return_value="openbk",
            ):
                with patch("tools.iot_control.requests.get") as mock_get:
                    resp = MagicMock()
                    resp.status_code = 200
                    resp.text = """
                    <html><head><title>My Light</title></head>
                    <body>
                    <h5>Wifi RSSI: Good (-55dBm)</h5>
                    <h5>Device MAC: 18:DE:50:34:F6:5F</h5>
                    </body></html>
                    """
                    mock_get.return_value = resp
                    result = _get_wifi_config("192.168.1.101")
                    data = json.loads(result)
                    assert data["success"] is True
                    assert data["wifi"]["rssi"] == -55

    def test_get_wifi_by_name(self):
        with patch(
            "tools.iot_discovery._resolve_ip",
            return_value="192.168.1.100",
        ):
            with patch(
                "tools.iot_discovery._detect_device_type",
                return_value="tasmota",
            ):
                with patch("tools.iot_control.requests.get") as mock_get:
                    resp = MagicMock()
                    resp.status_code = 200
                    resp.json.return_value = {
                        "StatusSTS": {"Wifi": {"SSId": "HomeWiFi", "RSSI": -70}}
                    }
                    mock_get.return_value = resp
                    result = _get_wifi_config("Light_Bathroom")
                    data = json.loads(result)
                    assert data["success"] is True
                    assert data["resolved_from"] == "Light_Bathroom"


class TestWifiConfigErrors:
    """Edge case and error path tests for WiFi config."""

    def test_get_wifi_name_not_resolved(self):
        with patch("tools.iot_discovery._resolve_ip", return_value=None):
            with patch("tools.iot_discovery._get_cached_devices", return_value=[]):
                result = _get_wifi_config("UnknownDevice")
                data = json.loads(result)
                assert data["success"] is False
                assert "Could not resolve" in data["error"]

    def test_get_wifi_tasmota_http_error(self):
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.100"):
            with patch(
                "tools.iot_discovery._detect_device_type", return_value="tasmota"
            ):
                with patch("tools.iot_control.requests.get") as mock_get:
                    resp = MagicMock()
                    resp.status_code = 503
                    mock_get.return_value = resp
                    result = _get_wifi_config("192.168.1.100")
                    data = json.loads(result)
                    assert data["success"] is False
                    assert "Device not found" in data["error"]

    def test_get_wifi_unsupported_type(self):
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.100"):
            with patch(
                "tools.iot_discovery._detect_device_type", return_value="matter"
            ):
                result = _get_wifi_config("192.168.1.100")
                data = json.loads(result)
                assert data["success"] is False
                assert "Device not found" in data["error"]


class TestRegistrationWrappers:
    """Tests for MCP tool registration wrappers and exception handlers."""

    def test_registration_creates_four_tools(self, mock_mcp):
        register_iot_control_tools(mock_mcp)
        assert "iot_set_power" in mock_mcp._tools
        assert "iot_set_brightness" in mock_mcp._tools
        assert "iot_restart_device" in mock_mcp._tools
        assert "iot_get_wifi_config" in mock_mcp._tools

    def test_iot_set_power_wrapper(self, mock_mcp):
        register_iot_control_tools(mock_mcp)
        fn = mock_mcp.get_tool("iot_set_power")
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.100"):
            with patch(
                "tools.iot_discovery._detect_device_type", return_value="tasmota"
            ):
                with patch("tools.iot_control.requests.get") as mock_get:
                    resp = MagicMock()
                    resp.status_code = 200
                    resp.json.return_value = {"POWER1": "ON"}
                    mock_get.return_value = resp
                    result = fn("192.168.1.100", "ON")
                    data = json.loads(result)
                    assert data["success"] is True

    def test_iot_set_brightness_wrapper(self, mock_mcp):
        register_iot_control_tools(mock_mcp)
        fn = mock_mcp.get_tool("iot_set_brightness")
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.100"):
            with patch(
                "tools.iot_discovery._detect_device_type", return_value="tasmota"
            ):
                with patch("tools.iot_control.requests.get") as mock_get:
                    resp = MagicMock()
                    resp.status_code = 200
                    mock_get.return_value = resp
                    result = fn("192.168.1.100", 50)
                    data = json.loads(result)
                    assert data["success"] is True

    def test_iot_restart_device_wrapper(self, mock_mcp):
        register_iot_control_tools(mock_mcp)
        fn = mock_mcp.get_tool("iot_restart_device")
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.100"):
            with patch(
                "tools.iot_discovery._detect_device_type", return_value="tasmota"
            ):
                with patch("tools.iot_control.requests.get") as mock_get:
                    resp = MagicMock()
                    resp.status_code = 200
                    mock_get.return_value = resp
                    result = fn("192.168.1.100")
                    data = json.loads(result)
                    assert data["success"] is True

    def test_iot_get_wifi_config_wrapper(self, mock_mcp):
        register_iot_control_tools(mock_mcp)
        fn = mock_mcp.get_tool("iot_get_wifi_config")
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.100"):
            with patch(
                "tools.iot_discovery._detect_device_type", return_value="tasmota"
            ):
                with patch("tools.iot_control.requests.get") as mock_get:
                    resp = MagicMock()
                    resp.status_code = 200
                    resp.json.return_value = {
                        "StatusSTS": {
                            "Wifi": {
                                "SSId": "TestNet",
                                "RSSI": -80,
                                "Signal": -80,
                                "Mac": "00:00:00:00:00:00",
                                "IPAddress": "192.168.1.100",
                                "Gateway": "192.168.1.1",
                                "Mode": "11g",
                            }
                        }
                    }
                    mock_get.return_value = resp
                    result = fn("192.168.1.100")
                    data = json.loads(result)
                    assert data["success"] is True

    def test_set_power_wrapper_exception_handler(self, mock_mcp):
        register_iot_control_tools(mock_mcp)
        fn = mock_mcp.get_tool("iot_set_power")
        with patch("tools.iot_control._set_power", side_effect=RuntimeError("boom")):
            result = fn("192.168.1.100", "ON")
            data = json.loads(result)
            assert data["success"] is False
            assert "boom" in data["error"]

    def test_set_brightness_wrapper_exception_handler(self, mock_mcp):
        register_iot_control_tools(mock_mcp)
        fn = mock_mcp.get_tool("iot_set_brightness")
        with patch("tools.iot_control._set_brightness", side_effect=ValueError("bad")):
            result = fn("192.168.1.100", 50)
            data = json.loads(result)
            assert data["success"] is False
            assert "bad" in data["error"]

    def test_restart_wrapper_exception_handler(self, mock_mcp):
        register_iot_control_tools(mock_mcp)
        fn = mock_mcp.get_tool("iot_restart_device")
        with patch("tools.iot_control._restart_device", side_effect=OSError("io")):
            result = fn("192.168.1.100")
            data = json.loads(result)
            assert data["success"] is False
            assert "io" in data["error"]

    def test_get_wifi_wrapper_exception_handler(self, mock_mcp):
        register_iot_control_tools(mock_mcp)
        fn = mock_mcp.get_tool("iot_get_wifi_config")
        with patch("tools.iot_control._get_wifi_config", side_effect=Exception("fail")):
            result = fn("192.168.1.100")
            data = json.loads(result)
            assert data["success"] is False
            assert "fail" in data["error"]

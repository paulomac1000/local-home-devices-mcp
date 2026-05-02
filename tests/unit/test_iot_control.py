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

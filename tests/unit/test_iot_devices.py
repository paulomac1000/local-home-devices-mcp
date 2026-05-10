"""
Unit tests for IoT MCP device information tools.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from tools.iot_devices import (
    _get_device_info,
    _get_device_power,
    _get_openbk_status,
    _get_tasmota_status,
    register_iot_device_tools,
)

pytestmark = pytest.mark.unit


class TestGetOpenBKStatus:
    """Tests for OpenBK status retrieval."""

    def test_get_openbk_status_success(self):
        """Should parse OpenBK HTML and extract status."""
        with patch("tools.iot_devices.requests.get") as mock_get:
            resp = MagicMock()
            resp.status_code = 200
            resp.text = """
            <html><head><title>My Light</title></head>
            <body>
            <h5>Channel 0 = 1.00, Channel 1 = 0.00</h5>
            <h5>Wifi RSSI: Good (-55dBm)</h5>
            <h5>Device MAC: 18:DE:50:34:F6:5F</h5>
            <h5>MQTT State: <span style="color:green">connected</span></h5>
            <h5>Reboot reason: 0 - Pwr</h5>
            version 1.17.273
            </body></html>
            """
            mock_get.return_value = resp

            status = _get_openbk_status("192.168.1.101")

            assert status["name"] == "My Light"
            assert status["rssi"] == -55
            assert status["mac"] == "18:DE:50:34:F6:5F"
            assert status["version"] == "1.17.273"
            assert status["mqtt_connected"] is True
            assert status["reboot_reason"]["code"] == 0
            assert len(status["channels"]) == 2

    def test_get_openbk_status_http_error(self):
        """Should return error on HTTP failure."""
        with patch("tools.iot_devices.requests.get") as mock_get:
            resp = MagicMock()
            resp.status_code = 404
            mock_get.return_value = resp

            status = _get_openbk_status("192.168.1.101")
            assert "error" in status
            assert "404" in status["error"]

    def test_get_openbk_status_timeout(self):
        """Should return error on timeout."""
        with patch(
            "tools.iot_devices.requests.get",
            side_effect=Exception("Connection timeout"),
        ):
            status = _get_openbk_status("192.168.1.101")
            assert "error" in status

    def test_get_openbk_status_uptime(self):
        """Should extract uptime from data-initial attribute."""
        with patch("tools.iot_devices.requests.get") as mock_get:
            resp = MagicMock()
            resp.status_code = 200
            resp.text = (
                '<html><head><title>Test</title></head><body data-initial="3600"></body></html>'
            )
            mock_get.return_value = resp
            status = _get_openbk_status("192.168.1.101")
            assert status["uptime_seconds"] == 3600


class TestGetTasmotaStatus:
    """Tests for Tasmota status retrieval."""

    def test_get_tasmota_status_success(self):
        """Should parse Tasmota JSON and extract status."""
        with patch("tools.iot_devices.requests.get") as mock_get:

            def mock_response(url, **kwargs):
                resp = MagicMock()
                resp.status_code = 200
                if "Status%200" in url:
                    resp.json.return_value = {
                        "Status": {
                            "FriendlyName": ["TestDevice"],
                            "DeviceName": "TestDevice",
                            "Topic": "tasmota_test",
                            "Power": 1,
                            "Version": "12.5.0",
                            "Module": 0,
                            "SaveData": 1,
                            "PowerOnState": 3,
                        }
                    }
                elif "Status%205" in url:
                    resp.json.return_value = {
                        "StatusSTS": {
                            "Wifi": {
                                "RSSI": -65,
                                "SSId": "MyNetwork",
                                "Mac": "AA:BB:CC:DD:EE:FF",
                                "IPAddress": "192.168.1.100",
                                "Mode": "11n",
                            }
                        }
                    }
                elif "Power" in url and "%20" not in url:
                    resp.json.return_value = {"POWER": "ON"}
                return resp

            mock_get.side_effect = mock_response

            status = _get_tasmota_status("192.168.1.100")

            assert status["name"] == "TestDevice"
            assert status["power_state"] == 1
            assert status["current_power"] == "ON"
            assert status["version"] == "12.5.0"
            assert status["rssi"] == -65
            assert status["mac"] == "AA:BB:CC:DD:EE:FF"

    def test_get_tasmota_status_no_wifi(self):
        """Should handle missing WiFi data gracefully."""
        with patch("tools.iot_devices.requests.get") as mock_get:

            def mock_response(url, **kwargs):
                resp = MagicMock()
                if "Status%200" in url:
                    resp.status_code = 200
                    resp.json.return_value = {
                        "Status": {
                            "FriendlyName": ["TestDevice"],
                            "Version": "12.5.0",
                        }
                    }
                else:
                    resp.status_code = 404
                return resp

            mock_get.side_effect = mock_response

            status = _get_tasmota_status("192.168.1.100")
            assert status["name"] == "TestDevice"
            assert status["rssi"] is None

    def test_get_tasmota_status_http_error(self):
        """Should return error on non-200 Status response."""
        with patch("tools.iot_devices.requests.get") as mock_get:
            resp = MagicMock()
            resp.status_code = 500
            mock_get.return_value = resp
            status = _get_tasmota_status("192.168.1.100")
            assert status == {"error": "HTTP 500"}

    def test_get_tasmota_status_wifi_exception(self):
        """Should handle WiFi request exception gracefully."""
        with patch("tools.iot_devices.requests.get") as mock_get:

            def mock_response(url, **kwargs):
                resp = MagicMock()
                if "Status%200" in url:
                    resp.status_code = 200
                    resp.json.return_value = {
                        "Status": {
                            "FriendlyName": ["TestDevice"],
                            "Version": "12.5.0",
                        }
                    }
                elif "Status%205" in url:
                    raise Exception("WiFi timeout")
                else:
                    resp.status_code = 404
                return resp

            mock_get.side_effect = mock_response

            status = _get_tasmota_status("192.168.1.100")
            assert status["name"] == "TestDevice"
            assert status["rssi"] is None

    def test_get_tasmota_status_power_exception(self):
        """Should handle Power request exception gracefully."""
        with patch("tools.iot_devices.requests.get") as mock_get:

            def mock_response(url, **kwargs):
                resp = MagicMock()
                if "Status%200" in url:
                    resp.status_code = 200
                    resp.json.return_value = {
                        "Status": {
                            "FriendlyName": ["TestDevice"],
                            "Version": "12.5.0",
                        }
                    }
                elif "Power" in url and "%20" not in url:
                    raise Exception("Power timeout")
                else:
                    resp.status_code = 404
                return resp

            mock_get.side_effect = mock_response

            status = _get_tasmota_status("192.168.1.100")
            assert status["name"] == "TestDevice"
            assert status["current_power"] is None

    def test_get_tasmota_status_outer_exception(self):
        """Should catch outer exception from primary request."""
        with patch(
            "tools.iot_devices.requests.get",
            side_effect=Exception("Connection refused"),
        ):
            status = _get_tasmota_status("192.168.1.100")
            assert status == {"error": "Connection refused"}


class TestGetDeviceInfo:
    """Tests for device info tool."""

    def test_get_device_info_by_ip(self):
        """Should resolve IP directly and return info."""
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.100"):
            with patch(
                "tools.iot_discovery._detect_device_type",
                return_value="tasmota",
            ):
                with patch("tools.iot_devices._get_tasmota_status") as mock_status:
                    mock_status.return_value = {
                        "name": "TestDevice",
                        "power_state": 0,
                    }
                    result = _get_device_info("192.168.1.100")
                    data = json.loads(result)
                    assert data["success"] is True
                    assert data["data"]["ip_address"] == "192.168.1.100"

    def test_get_device_info_name_not_found(self):
        """Should suggest discovery when name not in cache."""
        with patch("tools.iot_discovery._resolve_ip", return_value=None):
            with patch("tools.iot_discovery._get_cached_devices", return_value=[]):
                result = _get_device_info("UnknownDevice")
                data = json.loads(result)
                assert data["success"] is False
                assert "Could not resolve" in data["error"]["message"]

    def test_get_device_info_openbk(self):
        """Should route to OpenBK status for openbk devices."""
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.101"):
            with patch(
                "tools.iot_discovery._detect_device_type",
                return_value="openbk",
            ):
                with patch("tools.iot_devices._get_openbk_status") as mock_status:
                    mock_status.return_value = {
                        "name": "OpenBK_Test",
                        "channels": [],
                    }
                    result = _get_device_info("192.168.1.101")
                    data = json.loads(result)
                    assert data["success"] is True
                    assert data["data"]["device_type"] == "openbk"

    def test_get_device_info_device_not_found_at_ip(self):
        """Should error when no device detected at IP."""
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.200"):
            with patch("tools.iot_discovery._detect_device_type", return_value=None):
                result = _get_device_info("192.168.1.200")
                data = json.loads(result)
                assert data["success"] is False
                assert "No IoT device found" in data["error"]["message"]

    def test_get_device_info_unknown_type(self):
        """Should error for unsupported device type."""
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.100"):
            with patch(
                "tools.iot_discovery._detect_device_type",
                return_value="esphome",
            ):
                result = _get_device_info("192.168.1.100")
                data = json.loads(result)
                assert data["success"] is False
                assert "Unknown device type" in data["error"]["message"]

    def test_get_device_info_status_error_propagation(self):
        """Should propagate error from status function."""
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.100"):
            with patch(
                "tools.iot_discovery._detect_device_type",
                return_value="tasmota",
            ):
                with patch("tools.iot_devices._get_tasmota_status") as mock_status:
                    mock_status.return_value = {"error": "Device unreachable"}
                    result = _get_device_info("192.168.1.100")
                    data = json.loads(result)
                    assert data["success"] is False
                    assert "Device unreachable" in data["error"]["message"]


class TestGetDevicePower:
    """Tests for power state query."""

    def test_get_device_power_tasmota(self):
        """Should query Tasmota power state."""
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.100"):
            with patch(
                "tools.iot_discovery._detect_device_type",
                return_value="tasmota",
            ):
                with patch("tools.iot_devices.requests.get") as mock_get:
                    resp = MagicMock()
                    resp.status_code = 200
                    resp.json.return_value = {"POWER": "ON"}
                    mock_get.return_value = resp

                    result = _get_device_power("192.168.1.100")
                    data = json.loads(result)
                    assert data["success"] is True
                    assert data["data"]["state"] == "ON"

    def test_get_device_power_openbk(self):
        """Should query OpenBK power state."""
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.101"):
            with patch(
                "tools.iot_discovery._detect_device_type",
                return_value="openbk",
            ):
                with patch("tools.iot_devices._get_openbk_status") as mock_status:
                    mock_status.return_value = {
                        "channels": [
                            {"channel": 0, "value": 1.0},
                        ]
                    }
                    result = _get_device_power("192.168.1.101")
                    data = json.loads(result)
                    assert data["success"] is True
                    assert data["data"]["state"] == "ON"
                    assert data["data"]["value"] == 1.0

    def test_get_device_power_name_not_resolved(self):
        """Should suggest discovery when name not in cache."""
        with patch("tools.iot_discovery._resolve_ip", return_value=None):
            with patch("tools.iot_discovery._get_cached_devices", return_value=[]):
                result = _get_device_power("UnknownDevice")
                data = json.loads(result)
                assert data["success"] is False
                assert "Could not resolve" in data["error"]["message"]

    def test_get_device_power_tasmota_exception(self):
        """Should handle Tasmota power request exception."""
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.100"):
            with patch(
                "tools.iot_discovery._detect_device_type",
                return_value="tasmota",
            ):
                with patch(
                    "tools.iot_devices.requests.get",
                    side_effect=Exception("Timeout"),
                ):
                    result = _get_device_power("192.168.1.100")
                    data = json.loads(result)
                    assert data["success"] is False
                    assert "Timeout" in data["error"]["message"]

    def test_get_device_power_unknown_type(self):
        """Should error for unsupported device type."""
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.100"):
            with patch(
                "tools.iot_discovery._detect_device_type",
                return_value="zigbee",
            ):
                result = _get_device_power("192.168.1.100")
                data = json.loads(result)
                assert data["success"] is False
                assert "Device not found or unsupported" in data["error"]["message"]


class TestDeviceRegistrationWrappers:
    """Tests for MCP tool registration wrappers."""

    def test_registration_creates_two_tools(self, mock_mcp):
        register_iot_device_tools(mock_mcp)
        assert "iot_get_device_info" in mock_mcp._tools
        assert "iot_get_device_power" in mock_mcp._tools

    def test_iot_get_device_info_wrapper(self, mock_mcp):
        register_iot_device_tools(mock_mcp)
        fn = mock_mcp.get_tool("iot_get_device_info")
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.100"):
            with patch(
                "tools.iot_discovery._detect_device_type",
                return_value="tasmota",
            ):
                with patch("tools.iot_devices._get_tasmota_status") as mock_status:
                    mock_status.return_value = {"name": "TestDevice", "power_state": 0}
                    result = fn("192.168.1.100")
                    data = json.loads(result)
                    assert data["success"] is True

    def test_iot_get_device_power_wrapper(self, mock_mcp):
        register_iot_device_tools(mock_mcp)
        fn = mock_mcp.get_tool("iot_get_device_power")
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.100"):
            with patch(
                "tools.iot_discovery._detect_device_type",
                return_value="tasmota",
            ):
                with patch("tools.iot_devices.requests.get") as mock_get:
                    resp = MagicMock()
                    resp.status_code = 200
                    resp.json.return_value = {"POWER": "ON"}
                    mock_get.return_value = resp
                    result = fn("192.168.1.100")
                    data = json.loads(result)
                    assert data["success"] is True

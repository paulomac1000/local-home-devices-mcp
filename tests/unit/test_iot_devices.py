"""
Unit tests for IoT MCP device information tools.
"""

import json
from unittest.mock import MagicMock, patch

from tools.iot_devices import (
    _get_device_info,
    _get_device_power,
    _get_openbk_status,
    _get_tasmota_status,
)


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


class TestGetDeviceInfo:
    """Tests for device info tool."""

    def test_get_device_info_by_ip(self):
        """Should resolve IP directly and return info."""
        with patch("tools.iot_discovery._resolve_ip", return_value="192.168.1.100"):
            with patch(
                "tools.iot_discovery._detect_device_type",
                return_value="tasmota",
            ):
                with patch(
                    "tools.iot_devices._get_tasmota_status"
                ) as mock_status:
                    mock_status.return_value = {
                        "name": "TestDevice",
                        "power_state": 0,
                    }
                    result = _get_device_info("192.168.1.100")
                    data = json.loads(result)
                    assert data["success"] is True
                    assert data["ip_address"] == "192.168.1.100"

    def test_get_device_info_name_not_found(self):
        """Should suggest discovery when name not in cache."""
        with patch("tools.iot_discovery._resolve_ip", return_value=None):
            with patch(
                "tools.iot_discovery._get_cached_devices", return_value=[]
            ):
                result = _get_device_info("UnknownDevice")
                data = json.loads(result)
                assert data["success"] is False
                assert "Could not resolve" in data["error"]


class TestGetDevicePower:
    """Tests for power state query."""

    def test_get_device_power_tasmota(self):
        """Should query Tasmota power state."""
        with patch(
            "tools.iot_discovery._resolve_ip", return_value="192.168.1.100"
        ):
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
                    assert data["state"] == "ON"

    def test_get_device_power_openbk(self):
        """Should query OpenBK power state."""
        with patch(
            "tools.iot_discovery._resolve_ip", return_value="192.168.1.101"
        ):
            with patch(
                "tools.iot_discovery._detect_device_type",
                return_value="openbk",
            ):
                with patch(
                    "tools.iot_devices._get_openbk_status"
                ) as mock_status:
                    mock_status.return_value = {
                        "channels": [
                            {"channel": 0, "value": 1.0},
                        ]
                    }
                    result = _get_device_power("192.168.1.101")
                    data = json.loads(result)
                    assert data["success"] is True
                    assert data["state"] == "ON"
                    assert data["value"] == 1.0

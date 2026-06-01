"""
Unit tests for IoT MCP device discovery tools.

Tests the dynamic discovery system with nmap scanning and persistent cache.
"""

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from tools.iot_discovery import (
    _detect_device_type,
    _find_device_by_identifier,
    _get_cached_devices,
    _iot_check_device,
    _iot_discover_devices,
    _iot_find_device_by_name,
    _iot_list_devices,
    _is_cache_fresh,
    _load_cache,
    _probe_device_info,
    _resolve_ip,
    _save_cache,
    _scan_network,
    register_iot_discovery_tools,
)

pytestmark = pytest.mark.unit


class TestDetectDeviceType:
    """Tests for device type detection."""

    def test_detect_tasmota(self):
        with patch("tools.iot_discovery.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '{"Status":{"Module":0}}'
            mock_get.return_value = mock_resp
            result = _detect_device_type("192.168.1.100")
            assert result == "tasmota"

    def test_detect_openbk(self):
        with patch("tools.iot_discovery.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = "<html><body>openbeken</body></html>"
            mock_get.return_value = mock_resp
            result = _detect_device_type("192.168.1.101")
            assert result == "openbk"

    def test_detect_openbk_openshw(self):
        with patch("tools.iot_discovery.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '<a href="https://github.com/openshwprojects/">Link</a>'
            mock_get.return_value = mock_resp
            result = _detect_device_type("192.168.1.102")
            assert result == "openbk"

    def test_detect_unknown(self):
        with patch("tools.iot_discovery.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = "<html><body>Regular router</body></html>"
            mock_get.return_value = mock_resp
            result = _detect_device_type("192.168.1.1")
            assert result is None

    def test_detect_timeout(self):
        with patch(
            "tools.iot_discovery.requests.get",
            side_effect=Exception("Timeout"),
        ):
            result = _detect_device_type("192.168.1.200")
            assert result is None


class TestProbeDeviceInfo:
    """Tests for device info probing."""

    def test_probe_tasmota(self):
        with patch("tools.iot_discovery.requests.get") as mock_get:

            def mock_response(url, **kwargs):
                resp = MagicMock()
                resp.status_code = 200
                if "Status%200" in url:
                    resp.json.return_value = {
                        "Status": {
                            "FriendlyName": ["TestDevice"],
                            "Version": "12.5.0",
                            "DeviceName": "TestDevice",
                            "Topic": "device_test",
                            "Module": 0,
                            "PowerOnState": 3,
                        }
                    }
                elif "Status%205" in url:
                    resp.json.return_value = {
                        "StatusSTS": {
                            "Wifi": {
                                "RSSI": -65,
                                "Mac": "AA:BB:CC:DD:EE:FF",
                                "SSId": "MyNetwork",
                            }
                        }
                    }
                return resp

            mock_get.side_effect = mock_response
            info = _probe_device_info("192.168.1.100", "tasmota")
            assert info["type"] == "tasmota"
            assert info["name"] == "TestDevice"
            assert info["version"] == "12.5.0"
            assert info["rssi"] == -65
            assert info["mac"] == "AA:BB:CC:DD:EE:FF"
            assert info["ip"] == "192.168.1.100"

    def test_probe_tasmota_no_wifi_data(self):
        with patch("tools.iot_discovery.requests.get") as mock_get:

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
            info = _probe_device_info("192.168.1.100", "tasmota")
            assert info["ip"] == "192.168.1.100"

    def test_probe_openbk(self):
        with patch("tools.iot_discovery.requests.get") as mock_get:
            resp = MagicMock()
            resp.status_code = 200
            resp.text = """
            <html><head><title>My Light</title></head>
            <body>
            <h5>Wifi RSSI: Good (-55dBm)</h5>
            <h5>Device MAC: 18:DE:50:34:F6:5F</h5>
            version 1.17.273
            </body></html>
            """
            mock_get.return_value = resp
            info = _probe_device_info("192.168.1.101", "openbk")
            assert info["type"] == "openbk"
            assert info["name"] == "My Light"
            assert info["rssi"] == -55
            assert info["mac"] == "18:DE:50:34:F6:5F"
            assert info["ip"] == "192.168.1.101"

    def test_probe_unreachable(self):
        with patch(
            "tools.iot_discovery.requests.get",
            side_effect=Exception("Connection refused"),
        ):
            info = _probe_device_info("192.168.1.200", "tasmota")
            assert info["reachable"] is False
            assert info["type"] == "tasmota"
            assert info["ip"] == "192.168.1.200"


class TestScanNetwork:
    """Tests for nmap network scanning."""

    def test_scan_finds_hosts(self):
        mock_output = """
        Host: 192.168.1.1 ()\tStatus: Up
        Host: 192.168.1.100 ()\tStatus: Up
        """
        with patch("tools.iot_discovery.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=mock_output, stderr="")
            result = _scan_network("192.168.1.0/24")
            assert "192.168.1.1" in result
            assert "192.168.1.100" in result

    def test_scan_no_hosts(self):
        with patch("tools.iot_discovery.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", stderr="")
            result = _scan_network("10.0.0.0/24")
            assert result == []

    def test_scan_nmap_not_installed(self):
        with patch(
            "tools.iot_discovery.subprocess.run",
            side_effect=FileNotFoundError("nmap"),
        ):
            with pytest.raises(RuntimeError, match="nmap is not installed"):
                _scan_network("192.168.1.0/24")

    def test_scan_timeout(self):
        import subprocess

        with patch(
            "tools.iot_discovery.subprocess.run",
            side_effect=subprocess.TimeoutExpired("nmap", 120),
        ):
            with pytest.raises(RuntimeError, match="timed out"):
                _scan_network("192.168.1.0/24")


class TestCacheOperations:
    """Tests for device cache read/write."""

    def test_load_empty_cache(self, tmp_path, monkeypatch):
        fake_cache = tmp_path / "discovered_devices.json"
        monkeypatch.setattr("tools.iot_discovery.CACHE_FILE", str(fake_cache))
        result = _load_cache()
        assert result["devices"] == []
        assert result["last_scan"] is None

    def test_save_and_load_cache(self, tmp_path, monkeypatch):
        fake_cache = tmp_path / "discovered_devices.json"
        monkeypatch.setattr("tools.iot_discovery.CACHE_FILE", str(fake_cache))
        devices = [
            {
                "ip": "192.168.1.100",
                "type": "tasmota",
                "name": "Light1",
                "reachable": True,
            },
        ]
        _save_cache(devices)
        loaded = _load_cache()
        assert loaded["device_count"] == 1
        assert len(loaded["devices"]) == 1
        assert loaded["last_scan"] is not None

    def test_get_cached_devices(self, tmp_path, monkeypatch):
        fake_cache = tmp_path / "discovered_devices.json"
        monkeypatch.setattr("tools.iot_discovery.CACHE_FILE", str(fake_cache))
        _save_cache([{"ip": "192.168.1.100", "name": "Test"}])
        result = _get_cached_devices()
        assert len(result) == 1
        assert result[0]["name"] == "Test"

    def test_load_corrupted_cache(self, tmp_path, monkeypatch):
        fake_cache = tmp_path / "discovered_devices.json"
        fake_cache.write_text("not json {{ broken")
        monkeypatch.setattr("tools.iot_discovery.CACHE_FILE", str(fake_cache))
        result = _load_cache()
        assert result["devices"] == []

    def test_is_cache_fresh(self, tmp_path, monkeypatch):
        fake_cache = tmp_path / "discovered_devices.json"
        monkeypatch.setattr("tools.iot_discovery.CACHE_FILE", str(fake_cache))
        _save_cache([{"ip": "192.168.1.100", "name": "Test"}])
        assert _is_cache_fresh() is True

    def test_is_cache_stale(self, tmp_path, monkeypatch):
        fake_cache = tmp_path / "discovered_devices.json"
        monkeypatch.setattr("tools.iot_discovery.CACHE_FILE", str(fake_cache))
        # Write cache with old timestamp
        old_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 7200))
        import json as _json

        fake_cache.write_text(
            _json.dumps(
                {
                    "version": 1,
                    "last_scan": old_time,
                    "device_count": 1,
                    "devices": [],
                }
            )
        )
        assert _is_cache_fresh() is False


class TestNameResolution:
    """Tests for resolving device identifiers."""

    def test_resolve_ip_address(self):
        assert _resolve_ip("192.168.1.100") == "192.168.1.100"

    def test_resolve_by_exact_name(self, tmp_path, monkeypatch):
        fake_cache = tmp_path / "discovered_devices.json"
        monkeypatch.setattr("tools.iot_discovery.CACHE_FILE", str(fake_cache))
        _save_cache(
            [
                {
                    "ip": "192.168.1.100",
                    "name": "Light_Bathroom_1",
                    "type": "tasmota",
                }
            ]
        )
        assert _resolve_ip("Light_Bathroom_1") == "192.168.1.100"

    def test_resolve_by_partial_name(self, tmp_path, monkeypatch):
        fake_cache = tmp_path / "discovered_devices.json"
        monkeypatch.setattr("tools.iot_discovery.CACHE_FILE", str(fake_cache))
        _save_cache(
            [
                {
                    "ip": "192.168.1.100",
                    "name": "Light_Bathroom_1",
                    "type": "tasmota",
                }
            ]
        )
        assert _resolve_ip("Bathroom") == "192.168.1.100"

    def test_resolve_not_found(self, tmp_path, monkeypatch):
        fake_cache = tmp_path / "discovered_devices.json"
        monkeypatch.setattr("tools.iot_discovery.CACHE_FILE", str(fake_cache))
        _save_cache([])
        assert _resolve_ip("UnknownDevice") is None

    def test_find_device_by_identifier_ip(self, tmp_path, monkeypatch):
        fake_cache = tmp_path / "discovered_devices.json"
        monkeypatch.setattr("tools.iot_discovery.CACHE_FILE", str(fake_cache))
        _save_cache([{"ip": "192.168.1.100", "name": "Light1", "type": "tasmota"}])
        result = _find_device_by_identifier("192.168.1.100")
        assert result["name"] == "Light1"


class TestDiscoveryToolImpls:
    """Tests for MCP discovery tool internal implementations."""

    def test_iot_discover_devices_success(self):
        with patch(
            "tools.iot_discovery._scan_network",
            return_value=["192.168.1.100", "192.168.1.101"],
        ):
            with patch("tools.iot_discovery._detect_device_type") as mock_detect:
                with patch("tools.iot_discovery._probe_device_info") as mock_probe:
                    with patch("tools.iot_discovery._save_cache") as mock_save:
                        mock_detect.side_effect = ["tasmota", "openbk"]
                        mock_probe.side_effect = [
                            {
                                "ip": "192.168.1.100",
                                "type": "tasmota",
                                "name": "Dev1",
                                "reachable": True,
                            },
                            {
                                "ip": "192.168.1.101",
                                "type": "openbk",
                                "name": "Dev2",
                                "reachable": True,
                            },
                        ]
                        result = _iot_discover_devices("192.168.1.0/24")
                        data = json.loads(result)
                        assert data["success"] is True
                        assert data["data"]["total_found"] == 2
                        assert mock_save.called

    def test_iot_discover_no_alive_hosts(self):
        with patch("tools.iot_discovery._scan_network", return_value=[]):
            result = _iot_discover_devices("10.0.0.0/24")
            data = json.loads(result)
            assert data["success"] is True
            assert data["data"]["total_found"] == 0

    def test_iot_list_devices_empty_cache(self, tmp_path, monkeypatch):
        fake_cache = tmp_path / "discovered_devices.json"
        monkeypatch.setattr("tools.iot_discovery.CACHE_FILE", str(fake_cache))
        result = _iot_list_devices()
        data = json.loads(result)
        assert data["data"]["device_count"] == 0
        assert "suggestion" in data["data"]

    def test_iot_list_devices_with_cache(self, tmp_path, monkeypatch):
        fake_cache = tmp_path / "discovered_devices.json"
        monkeypatch.setattr("tools.iot_discovery.CACHE_FILE", str(fake_cache))
        _save_cache(
            [
                {
                    "ip": "192.168.1.100",
                    "name": "Light1",
                    "type": "tasmota",
                    "reachable": True,
                }
            ]
        )
        result = _iot_list_devices()
        data = json.loads(result)
        assert data["data"]["device_count"] == 1
        assert data["data"]["cached"] is True
        assert "cache_fresh" in data["data"]

    def test_iot_check_device_found(self):
        with patch(
            "tools.iot_discovery._detect_device_type",
            return_value="tasmota",
        ):
            with patch("tools.iot_discovery._probe_device_info") as mock_probe:
                mock_probe.return_value = {
                    "ip": "192.168.1.100",
                    "type": "tasmota",
                    "name": "Test",
                    "reachable": True,
                }
                result = _iot_check_device("192.168.1.100")
                data = json.loads(result)
                assert data["success"] is True
                assert data["data"]["is_iot_device"] is True

    def test_iot_check_device_not_found(self):
        with patch("tools.iot_discovery._detect_device_type", return_value=None):
            result = _iot_check_device("192.168.1.1")
            data = json.loads(result)
            assert data["success"] is True
            assert data["data"]["is_iot_device"] is False

    def test_iot_find_device_by_name_found(self, tmp_path, monkeypatch):
        fake_cache = tmp_path / "discovered_devices.json"
        monkeypatch.setattr("tools.iot_discovery.CACHE_FILE", str(fake_cache))
        _save_cache(
            [
                {
                    "ip": "192.168.1.100",
                    "name": "Light_Bathroom",
                    "type": "tasmota",
                }
            ]
        )
        result = _iot_find_device_by_name("Bathroom")
        data = json.loads(result)
        assert data["success"] is True
        assert data["data"]["device"]["ip"] == "192.168.1.100"

    def test_iot_find_device_by_name_not_found(self, tmp_path, monkeypatch):
        fake_cache = tmp_path / "discovered_devices.json"
        monkeypatch.setattr("tools.iot_discovery.CACHE_FILE", str(fake_cache))
        _save_cache([])
        result = _iot_find_device_by_name("Unknown")
        data = json.loads(result)
        assert data["success"] is False
        assert "not found" in data["error"]["message"]


class TestCacheEdgeCases:
    """Edge case tests for cache freshness checks."""

    def test_cache_fresh_null_timestamp(self, tmp_path, monkeypatch):
        fake_cache = tmp_path / "discovered_devices.json"
        monkeypatch.setattr("tools.iot_discovery.CACHE_FILE", str(fake_cache))
        import json as _json

        fake_cache.write_text(_json.dumps({"version": 1, "last_scan": None, "devices": []}))
        assert _is_cache_fresh() is False

    def test_cache_fresh_invalid_timestamp(self, tmp_path, monkeypatch):
        fake_cache = tmp_path / "discovered_devices.json"
        monkeypatch.setattr("tools.iot_discovery.CACHE_FILE", str(fake_cache))
        import json as _json

        fake_cache.write_text(_json.dumps({"version": 1, "last_scan": "not-a-date", "devices": []}))
        assert _is_cache_fresh() is False


class TestProbeDeviceInfoErrors:
    """Error path tests for device info probing."""

    def test_probe_tasmota_wifi_exception(self):
        with patch("tools.iot_discovery.requests.get") as mock_get:

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
                return resp

            mock_get.side_effect = mock_response
            info = _probe_device_info("192.168.1.100", "tasmota")
            assert info["ip"] == "192.168.1.100"
            assert info["reachable"] is True

    def test_probe_openbk_outer_exception(self):
        with patch("tools.iot_discovery.requests.get") as mock_get:
            mock_get.side_effect = Exception("Connection refused")
            info = _probe_device_info("192.168.1.101", "openbk")
            assert info["reachable"] is False


class TestScanNetworkErrors:
    """Error path tests for nmap scanning."""

    def test_scan_generic_exception(self):
        with patch(
            "tools.iot_discovery.subprocess.run",
            side_effect=OSError("Permission denied"),
        ):
            with pytest.raises(RuntimeError, match="nmap scan failed"):
                _scan_network("192.168.1.0/24")


class TestDiscoverErrors:
    """Error path tests for the discover tool internal implementation."""

    def test_discover_default_network_range(self):
        with patch("tools.iot_discovery._scan_network", return_value=[]) as mock_scan:
            result = _iot_discover_devices(None)
            data = json.loads(result)
            assert data["success"] is True
            assert mock_scan.called

    def test_discover_runtime_error(self):
        with patch(
            "tools.iot_discovery._scan_network",
            side_effect=RuntimeError("nmap is not installed"),
        ):
            result = _iot_discover_devices("192.168.1.0/24")
            data = json.loads(result)
            assert data["success"] is False
            assert "nmap is not installed" in data["error"]["message"]

    def test_discover_generic_exception(self):
        with patch(
            "tools.iot_discovery._scan_network",
            side_effect=ValueError("unexpected error"),
        ):
            result = _iot_discover_devices("192.168.1.0/24")
            data = json.loads(result)
            assert data["success"] is False
            assert "Discovery failed" in data["error"]["message"]


class TestListDevicesErrors:
    """Error path for list devices."""

    def test_list_devices_exception(self):
        with patch(
            "tools.iot_discovery._load_cache",
            side_effect=OSError("disk full"),
        ):
            result = _iot_list_devices()
            data = json.loads(result)
            assert data["success"] is False
            assert "disk full" in data["error"]["message"]


class TestCheckDeviceErrors:
    """Error path for check device."""

    def test_check_device_exception(self):
        with patch(
            "tools.iot_discovery._detect_device_type",
            side_effect=ValueError("bad input"),
        ):
            result = _iot_check_device("192.168.1.100")
            data = json.loads(result)
            assert data["success"] is False
            assert "bad input" in data["error"]["message"]


class TestFindDeviceByNameErrors:
    """Error path for find device by name."""

    def test_find_device_by_name_exception(self):
        with patch(
            "tools.iot_discovery._find_device_by_identifier",
            side_effect=RuntimeError("cache corrupted"),
        ):
            result = _iot_find_device_by_name("test")
            data = json.loads(result)
            assert data["success"] is False
            assert "cache corrupted" in data["error"]["message"]


class TestDiscoveryRegistrationWrappers:
    """Tests for MCP tool registration wrappers."""

    def test_registration_creates_four_tools(self, mock_mcp):
        register_iot_discovery_tools(mock_mcp)
        assert "iot_discover_devices" in mock_mcp._tools
        assert "iot_list_devices" in mock_mcp._tools
        assert "iot_check_device" in mock_mcp._tools
        assert "iot_find_device_by_name" in mock_mcp._tools

    def test_iot_discover_devices_wrapper(self, mock_mcp):
        register_iot_discovery_tools(mock_mcp)
        fn = mock_mcp.get_tool("iot_discover_devices")
        with patch("tools.iot_discovery._scan_network", return_value=[]):
            with patch("tools.iot_discovery._save_cache"):
                result = fn()
                data = json.loads(result)
                assert data["success"] is True

    def test_iot_list_devices_wrapper(self, mock_mcp, tmp_path, monkeypatch):
        register_iot_discovery_tools(mock_mcp)
        fn = mock_mcp.get_tool("iot_list_devices")
        fake_cache = tmp_path / "discovered_devices.json"
        monkeypatch.setattr("tools.iot_discovery.CACHE_FILE", str(fake_cache))
        result = fn()
        data = json.loads(result)
        assert data["success"] is True

    def test_iot_check_device_wrapper(self, mock_mcp):
        register_iot_discovery_tools(mock_mcp)
        fn = mock_mcp.get_tool("iot_check_device")
        with patch("tools.iot_discovery._detect_device_type", return_value=None):
            result = fn("192.168.1.1")
            data = json.loads(result)
            assert data["success"] is True

    def test_iot_find_device_by_name_wrapper(self, mock_mcp, tmp_path, monkeypatch):
        register_iot_discovery_tools(mock_mcp)
        fn = mock_mcp.get_tool("iot_find_device_by_name")
        fake_cache = tmp_path / "discovered_devices.json"
        monkeypatch.setattr("tools.iot_discovery.CACHE_FILE", str(fake_cache))
        _save_cache([{"ip": "192.168.1.100", "name": "TestLight", "type": "tasmota"}])
        result = fn("TestLight")
        data = json.loads(result)
        assert data["success"] is True

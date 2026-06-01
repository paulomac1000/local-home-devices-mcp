"""Unit tests for Tuya IoT tools (fully mocked)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from tools.constants import _success_response

FAKE_DEVICE_ID = "bf5397fdf1491fc79ac2gr"
FAKE_IP = "192.168.1.150"
FAKE_LOCAL_KEY = "abc123def4567890"
FAKE_DPS = {
    "1": True,
    "4": "smart",
    "5": "standby",
    "6": 120,
    "8": 85,
    "9": "strong",
}


def _json(data):
    return _success_response(data)


class TestTuyaClientFactories:
    def test_cloud_client_requires_credentials(self):
        import tools.iot_tuya as mod
        from tools.iot_tuya import _get_tuya_cloud

        with patch.object(mod, "TUYA_ACCESS_ID", ""), patch.object(mod, "TUYA_ACCESS_SECRET", ""):
            assert _get_tuya_cloud() is None

    def test_cloud_client_requires_tinytuya(self):
        import tools.iot_tuya as mod
        from tools.iot_tuya import _get_tuya_cloud

        with (
            patch.object(mod, "_import_tinytuya", return_value=False),
            patch.object(mod, "TUYA_ACCESS_ID", "test"),
            patch.object(mod, "TUYA_ACCESS_SECRET", "test"),
        ):
            assert _get_tuya_cloud() is None

    def test_local_client_requires_tinytuya(self):
        import tools.iot_tuya as mod
        from tools.iot_tuya import _get_tuya_local

        with patch.object(mod, "_import_tinytuya", return_value=False):
            assert _get_tuya_local("a", "10.0.0.1", "key") is None

    def test_local_client_returns_device(self):
        from tools.iot_tuya import _get_tuya_local, _import_tinytuya

        _import_tinytuya()
        import tinytuya

        mock_device = MagicMock()
        with patch.object(tinytuya, "Device", return_value=mock_device):
            device = _get_tuya_local(FAKE_DEVICE_ID, FAKE_IP, FAKE_LOCAL_KEY, 3.3)
            assert device is mock_device


class TestTuyaCache:
    def test_load_empty_cache(self, tmp_path):
        import tools.iot_tuya as mod
        from tools.iot_tuya import _load_tuya_devices

        fake_file = tmp_path / "tuya.json"
        with patch.object(mod, "TUYA_DEVICES_FILE", str(fake_file)):
            assert _load_tuya_devices() == {"version": 1, "devices": {}}

    def test_load_valid_cache(self, tmp_path):
        import tools.iot_tuya as mod
        from tools.iot_tuya import _load_tuya_devices

        fake_file = tmp_path / "tuya.json"
        fake_file.write_text(
            json.dumps(
                {
                    "version": 1,
                    "devices": {FAKE_DEVICE_ID: {"device_id": FAKE_DEVICE_ID, "name": "Test"}},
                }
            )
        )
        with patch.object(mod, "TUYA_DEVICES_FILE", str(fake_file)):
            assert FAKE_DEVICE_ID in _load_tuya_devices()["devices"]

    def test_save_and_reload(self, tmp_path):
        import tools.iot_tuya as mod
        from tools.iot_tuya import _load_tuya_devices, _save_tuya_devices

        fake_file = tmp_path / "tuya.json"
        with patch.object(mod, "TUYA_DEVICES_FILE", str(fake_file)):
            _save_tuya_devices(
                {
                    "version": 1,
                    "devices": {FAKE_DEVICE_ID: {"device_id": FAKE_DEVICE_ID, "name": "Saved"}},
                }
            )
            assert _load_tuya_devices()["devices"][FAKE_DEVICE_ID]["name"] == "Saved"

    def test_find_by_device_id(self):
        import tools.iot_tuya as mod
        from tools.iot_tuya import _find_tuya_in_cache, _save_tuya_devices

        with patch.object(mod, "TUYA_DEVICES_FILE", "/tmp/test_tuya_cache.json"):
            _save_tuya_devices(
                {
                    "version": 1,
                    "devices": {
                        FAKE_DEVICE_ID: {
                            "device_id": FAKE_DEVICE_ID,
                            "name": "Test_Name",
                            "ip": FAKE_IP,
                        }
                    },
                }
            )
            entry = _find_tuya_in_cache(FAKE_DEVICE_ID)
            assert entry is not None
            assert entry["name"] == "Test_Name"

    def test_find_by_name(self):
        import tools.iot_tuya as mod
        from tools.iot_tuya import _find_tuya_in_cache

        with patch.object(mod, "TUYA_DEVICES_FILE", "/tmp/test_tuya_cache.json"):
            entry = _find_tuya_in_cache("Test_Name")
            assert entry is not None


class TestTuyaStatus:
    def test_not_in_cache(self):
        import tools.iot_tuya as mod
        from tools.iot_tuya import _tuya_status

        with patch.object(mod, "_load_tuya_devices", return_value={"version": 1, "devices": {}}):
            result = _tuya_status("nonexistent")
            assert json.loads(result)["success"] is False

    def test_local_status_success(self):
        import tools.iot_tuya as mod
        from tools.iot_tuya import _tuya_status

        mock_device = MagicMock()
        mock_device.status.return_value = {"dps": FAKE_DPS}
        cache_entry = {
            "device_id": FAKE_DEVICE_ID,
            "ip": FAKE_IP,
            "local_key": FAKE_LOCAL_KEY,
            "version": 3.3,
            "name": "Test",
        }

        with (
            patch.object(mod, "_find_tuya_in_cache", return_value=cache_entry),
            patch.object(mod, "_get_tuya_local", return_value=mock_device),
        ):
            result = _tuya_status(FAKE_DEVICE_ID)
            parsed = json.loads(result)
            assert parsed["success"] is True
            assert parsed["data"]["transport"] == "local"


class TestTuyaSetValue:
    def test_set_value_local(self):
        import tools.iot_tuya as mod
        from tools.iot_tuya import _tuya_set_value

        mock_device = MagicMock()
        mock_device.set_value.return_value = {}
        mock_device.status.return_value = {"dps": {"1": True}}
        cache_entry = {
            "device_id": FAKE_DEVICE_ID,
            "ip": FAKE_IP,
            "local_key": FAKE_LOCAL_KEY,
            "version": 3.3,
            "name": "Test",
        }
        with (
            patch.object(mod, "_find_tuya_in_cache", return_value=cache_entry),
            patch.object(mod, "_get_tuya_local", return_value=mock_device),
        ):
            result = _tuya_set_value(FAKE_DEVICE_ID, "1", True)
            assert json.loads(result)["success"] is True

    def test_set_value_not_in_cache(self):
        import tools.iot_tuya as mod
        from tools.iot_tuya import _tuya_set_value

        with patch.object(mod, "_find_tuya_in_cache", return_value=None):
            result = _tuya_set_value("nonexistent", "1", True)
            assert json.loads(result)["success"] is False


class TestTuyaDetectVersion:
    def test_detect_not_in_cache(self):
        import tools.iot_tuya as mod
        from tools.iot_tuya import _tuya_detect_version

        with patch.object(mod, "_find_tuya_in_cache", return_value=None):
            assert json.loads(_tuya_detect_version("nonexistent"))["success"] is False

    def test_detect_tinytuya_missing(self):
        import tools.iot_tuya as mod
        from tools.iot_tuya import _tuya_detect_version

        with (
            patch.object(
                mod,
                "_find_tuya_in_cache",
                return_value={
                    "device_id": FAKE_DEVICE_ID,
                    "ip": FAKE_IP,
                    "local_key": FAKE_LOCAL_KEY,
                },
            ),
            patch.object(mod, "_import_tinytuya", return_value=False),
        ):
            assert json.loads(_tuya_detect_version(FAKE_DEVICE_ID))["success"] is False

    def test_detect_no_ip_or_key(self):
        import tools.iot_tuya as mod
        from tools.iot_tuya import _tuya_detect_version

        with (
            patch.object(
                mod,
                "_find_tuya_in_cache",
                return_value={"device_id": FAKE_DEVICE_ID, "ip": "", "local_key": ""},
            ),
            patch.object(mod, "_import_tinytuya", return_value=True),
        ):
            assert json.loads(_tuya_detect_version(FAKE_DEVICE_ID))["success"] is False


class TestTuyaScanPorts:
    def test_scan_no_open_ports(self):
        from tools.iot_tuya import _tuya_scan_ports

        with (
            patch("tools.constants.START_IP", "192.168.1.1"),
            patch("tools.constants.END_IP", "192.168.1.5"),
            patch("tools.iot_tuya.socket.socket") as mock_sock_cls,
        ):
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 1
            mock_sock_cls.return_value = mock_sock
            parsed = json.loads(_tuya_scan_ports())
            assert parsed["success"] is True
            assert parsed["data"]["devices_found"] == 0

    def test_scan_finds_device(self):
        from tools.iot_tuya import _tuya_scan_ports

        with (
            patch("tools.constants.START_IP", "192.168.1.100"),
            patch("tools.constants.END_IP", "192.168.1.100"),
            patch("tools.iot_tuya.socket.socket") as mock_sock_cls,
        ):
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 0
            mock_sock_cls.return_value = mock_sock
            parsed = json.loads(_tuya_scan_ports())
            assert parsed["success"] is True
            assert parsed["data"]["devices_found"] == 1


class TestTuyaVerifyDPS:
    def test_verify_all_valid(self):
        import tools.iot_tuya as mod
        from tools.iot_tuya import _tuya_verify_dps

        valid_dps = {"4": "smart", "5": "standby", "8": 85, "1": True}
        mock_result = _json({"device_id": FAKE_DEVICE_ID, "transport": "local", "dps": valid_dps})
        with patch.object(mod, "_tuya_status", return_value=mock_result):
            parsed = json.loads(_tuya_verify_dps(FAKE_DEVICE_ID))
            assert parsed["success"] is True
            assert parsed["data"]["all_valid"] is True

    def test_verify_with_errors(self):
        import tools.iot_tuya as mod
        from tools.iot_tuya import _tuya_verify_dps

        bad_dps = {"4": "INVALID_MODE", "8": -1, "1": "not_bool"}
        mock_result = _json({"device_id": FAKE_DEVICE_ID, "transport": "local", "dps": bad_dps})
        with patch.object(mod, "_tuya_status", return_value=mock_result):
            parsed = json.loads(_tuya_verify_dps(FAKE_DEVICE_ID))
            assert parsed["success"] is True
            assert not parsed["data"]["all_valid"]


class TestTuyaToolRegistration:
    @pytest.fixture
    def mcp(self, mock_mcp):
        from tools.iot_tuya import register_iot_tuya_tools

        register_iot_tuya_tools(mock_mcp)
        return mock_mcp

    def test_all_nine_tools_registered(self, mcp):
        tuya_tools = [n for n in mcp._tools if n.startswith("iot_tuya_")]
        assert len(tuya_tools) == 10

    def test_cloud_list_with_devices(self, mcp):
        mock_cloud = MagicMock()
        mock_cloud.getdevices.return_value = [
            {
                "id": FAKE_DEVICE_ID,
                "name": "Test_Vacuum",
                "online": True,
                "ip": FAKE_IP,
                "key": FAKE_LOCAL_KEY,
            }
        ]
        with (
            patch("tools.iot_tuya._get_tuya_cloud", return_value=mock_cloud),
            patch("tools.iot_tuya.TUYA_ACCESS_ID", "test"),
            patch("tools.iot_tuya.TUYA_ACCESS_SECRET", "test"),
            patch("tools.iot_tuya._load_tuya_devices", return_value={"version": 1, "devices": {}}),
            patch("tools.iot_tuya._save_tuya_devices") as mock_save,
        ):
            result = mcp.get_tool("iot_tuya_cloud_list")()
            parsed = json.loads(result)
            assert parsed["success"] is True
            assert parsed["data"]["devices"][0]["device_id"] == FAKE_DEVICE_ID
            assert "local_key" not in parsed["data"]["devices"][0]
            mock_save.assert_not_called()

    def test_cloud_list_no_tinytuya(self, mcp):
        with (
            patch("tools.iot_tuya._get_tuya_cloud", return_value=None),
            patch("tools.iot_tuya.TUYA_ACCESS_ID", "test"),
            patch("tools.iot_tuya.TUYA_ACCESS_SECRET", "test"),
        ):
            result = mcp.get_tool("iot_tuya_cloud_list")()
            assert json.loads(result)["success"] is False

    def test_get_dps_local(self, mcp):
        mock_device = MagicMock()
        mock_device.status.return_value = {"dps": FAKE_DPS}
        cache_entry = {
            "device_id": FAKE_DEVICE_ID,
            "ip": FAKE_IP,
            "local_key": FAKE_LOCAL_KEY,
            "version": 3.3,
            "name": "Test",
        }
        with (
            patch("tools.iot_tuya._find_tuya_in_cache", return_value=cache_entry),
            patch("tools.iot_tuya._get_tuya_local", return_value=mock_device),
        ):
            result = mcp.get_tool("iot_tuya_get_dps")(identifier=FAKE_DEVICE_ID)
            assert json.loads(result)["success"] is True

    def test_get_dps_with_dp_id(self, mcp):
        mock_device = MagicMock()
        mock_device.status.return_value = {"dps": FAKE_DPS}
        cache_entry = {
            "device_id": FAKE_DEVICE_ID,
            "ip": FAKE_IP,
            "local_key": FAKE_LOCAL_KEY,
            "version": 3.3,
            "name": "Test",
        }
        with (
            patch("tools.iot_tuya._find_tuya_in_cache", return_value=cache_entry),
            patch("tools.iot_tuya._get_tuya_local", return_value=mock_device),
        ):
            result = mcp.get_tool("iot_tuya_get_dps")(identifier=FAKE_DEVICE_ID, dp_id="8")
            parsed = json.loads(result)
            assert parsed["success"] is True
            assert parsed["data"]["dp_id"] == "8"

    def test_get_dps_nonexistent_dp_id(self, mcp):
        mock_device = MagicMock()
        mock_device.status.return_value = {"dps": FAKE_DPS}
        cache_entry = {
            "device_id": FAKE_DEVICE_ID,
            "ip": FAKE_IP,
            "local_key": FAKE_LOCAL_KEY,
            "version": 3.3,
            "name": "Test",
        }
        with (
            patch("tools.iot_tuya._find_tuya_in_cache", return_value=cache_entry),
            patch("tools.iot_tuya._get_tuya_local", return_value=mock_device),
        ):
            result = mcp.get_tool("iot_tuya_get_dps")(identifier=FAKE_DEVICE_ID, dp_id="999")
            assert json.loads(result)["success"] is False

    def test_set_dp_write_disabled(self, mcp):
        with patch("tools.iot_tuya.check_write_enabled", side_effect=Exception("write disabled")):
            result = mcp.get_tool("iot_tuya_set_dp")(
                identifier=FAKE_DEVICE_ID, dp_id="1", value="true"
            )
            assert json.loads(result)["success"] is False

    def test_detect_version(self, mcp):
        import tinytuya

        cache_entry = {
            "device_id": FAKE_DEVICE_ID,
            "ip": FAKE_IP,
            "local_key": FAKE_LOCAL_KEY,
            "name": "Test",
        }
        with patch("tools.iot_tuya._find_tuya_in_cache", return_value=cache_entry):
            mock_dev = MagicMock()
            mock_dev.generate_payload.return_value = b"\x00" * 24
            mock_dev.receive.side_effect = [Exception("fail"), Exception("fail"), {"dps": FAKE_DPS}]
            with (
                patch.object(tinytuya, "Device") as mock_dev_cls,
                patch.object(tinytuya, "DP_QUERY", 2),
            ):
                mock_dev_cls.return_value = mock_dev
                result = mcp.get_tool("iot_tuya_detect_version")(identifier=FAKE_DEVICE_ID)
                assert "success" in json.loads(result)

    def test_verify_dps(self, mcp):
        mock_device = MagicMock()
        mock_device.status.return_value = {"dps": {"1": True, "4": "smart", "8": 85}}
        cache_entry = {
            "device_id": FAKE_DEVICE_ID,
            "ip": FAKE_IP,
            "local_key": FAKE_LOCAL_KEY,
            "version": 3.3,
            "name": "Test",
        }
        with (
            patch("tools.iot_tuya._find_tuya_in_cache", return_value=cache_entry),
            patch("tools.iot_tuya._get_tuya_local", return_value=mock_device),
        ):
            result = mcp.get_tool("iot_tuya_verify_dps")(identifier=FAKE_DEVICE_ID)
            parsed = json.loads(result)
            assert parsed["success"] is True
            assert parsed["data"]["all_valid"] is True

    def test_verify_dps_custom_spec(self, mcp):
        mock_device = MagicMock()
        mock_device.status.return_value = {"dps": {"1": True}}
        cache_entry = {
            "device_id": FAKE_DEVICE_ID,
            "ip": FAKE_IP,
            "local_key": FAKE_LOCAL_KEY,
            "version": 3.3,
            "name": "Test",
        }
        custom_spec = json.dumps({"bools": {"1": "power"}, "integers": {}, "enums": {}})
        with (
            patch("tools.iot_tuya._find_tuya_in_cache", return_value=cache_entry),
            patch("tools.iot_tuya._get_tuya_local", return_value=mock_device),
        ):
            result = mcp.get_tool("iot_tuya_verify_dps")(
                identifier=FAKE_DEVICE_ID, spec=custom_spec
            )
            assert json.loads(result)["success"] is True

    def test_verify_dps_invalid_json(self, mcp):
        result = mcp.get_tool("iot_tuya_verify_dps")(
            identifier=FAKE_DEVICE_ID, spec="not valid json"
        )
        assert json.loads(result)["success"] is False

    def test_scan_ports(self, mcp):
        with (
            patch("tools.constants.START_IP", "192.168.1.100"),
            patch("tools.constants.END_IP", "192.168.1.100"),
            patch("tools.iot_tuya.socket.socket") as mock_sock_cls,
        ):
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 0
            mock_sock_cls.return_value = mock_sock
            result = mcp.get_tool("iot_tuya_scan_ports")()
            assert json.loads(result)["success"] is True

    def test_remove_device(self, mcp):
        with (
            patch(
                "tools.iot_tuya._load_tuya_devices",
                return_value={
                    "version": 1,
                    "devices": {FAKE_DEVICE_ID: {"device_id": FAKE_DEVICE_ID, "name": "Test"}},
                },
            ),
            patch("tools.iot_tuya._save_tuya_devices"),
            patch("tools.iot_tuya.check_write_enabled", return_value=None),
        ):
            result = mcp.get_tool("iot_tuya_remove")(device_id=FAKE_DEVICE_ID)
            parsed = json.loads(result)
            assert parsed["success"] is True
            assert parsed["data"]["removed"] is True

    def test_remove_not_found(self, mcp):
        with (
            patch("tools.iot_tuya._load_tuya_devices", return_value={"version": 1, "devices": {}}),
            patch("tools.iot_tuya.check_write_enabled", return_value=None),
        ):
            result = mcp.get_tool("iot_tuya_remove")(device_id=FAKE_DEVICE_ID)
            parsed = json.loads(result)
            assert parsed["success"] is False
            assert parsed["error"]["code"] == "TUYA_NOT_FOUND"

    def test_cloud_control(self, mcp):
        mock_cloud = MagicMock()
        mock_cloud.sendcommand.return_value = {}
        mock_cloud.getdevices.return_value = [
            {"id": FAKE_DEVICE_ID, "status": [{"code": "1", "value": True}]}
        ]
        mock_device = MagicMock()
        mock_device.set_value.side_effect = Exception("local fail")
        cache_entry = {
            "device_id": FAKE_DEVICE_ID,
            "ip": FAKE_IP,
            "local_key": FAKE_LOCAL_KEY,
            "version": 3.3,
            "name": "Test",
        }
        with (
            patch("tools.iot_tuya._find_tuya_in_cache", return_value=cache_entry),
            patch("tools.iot_tuya._get_tuya_local", return_value=mock_device),
            patch("tools.iot_tuya._get_tuya_cloud", return_value=mock_cloud),
            patch("tools.iot_tuya.check_write_enabled", return_value=None),
        ):
            result = mcp.get_tool("iot_tuya_cloud_control")(
                device_id=FAKE_DEVICE_ID, dp_id="1", value="true"
            )
            assert json.loads(result)["success"] is True

    def test_cloud_refresh_keys(self, mcp):
        mock_cloud = MagicMock()
        mock_cloud.getdevices.return_value = [
            {
                "id": FAKE_DEVICE_ID,
                "name": "Test",
                "online": True,
                "ip": FAKE_IP,
                "key": FAKE_LOCAL_KEY,
            }
        ]
        with (
            patch("tools.iot_tuya._get_tuya_cloud", return_value=mock_cloud),
            patch("tools.iot_tuya.TUYA_ACCESS_ID", "test"),
            patch("tools.iot_tuya.TUYA_ACCESS_SECRET", "test"),
            patch("tools.iot_tuya._save_tuya_devices"),
            patch("tools.iot_tuya.check_write_enabled", return_value=None),
        ):
            result = mcp.get_tool("iot_tuya_cloud_refresh_keys")()
            parsed = json.loads(result)
            assert parsed["success"] is True
            assert "local_key" not in parsed["data"]["devices"][0]

    def test_monitor_success(self, mcp):
        mock_device = MagicMock()
        mock_device.status.return_value = {"dps": FAKE_DPS}
        mock_device.receive.return_value = None
        cache_entry = {
            "device_id": FAKE_DEVICE_ID,
            "ip": FAKE_IP,
            "local_key": FAKE_LOCAL_KEY,
            "version": 3.3,
            "name": "Test",
        }
        mock_tinytuya = MagicMock()
        mock_tinytuya.Device.return_value = mock_device

        with (
            patch("tools.iot_tuya._find_tuya_in_cache", return_value=cache_entry),
            patch("tools.iot_tuya._import_tinytuya", return_value=True),
            patch("tools.iot_tuya._tinytuya", mock_tinytuya),
        ):
            result = mcp.get_tool("iot_tuya_monitor")(identifier=FAKE_DEVICE_ID, duration_seconds=1)
            parsed = json.loads(result)
            assert parsed["success"] is True
            assert "initial_dps" in parsed["data"]
            assert "changes" in parsed["data"]

"""Integration tests - OpenHASP live panel at 192.168.1.100 + mocked Telnet."""

import json
import socket
from unittest.mock import MagicMock, patch

import pytest

PANEL_IP = "192.168.1.100"
TUYA_PANEL_IP = "192.168.1.101"  # Tuya_Test


def _panel_reachable():
    try:
        s = socket.create_connection((PANEL_IP, 80), timeout=1)
        s.close()
        return True
    except OSError:
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _panel_reachable(),
        reason=f"OpenHASP panel not reachable at {PANEL_IP}",
    ),
]


def _get_result(mcp_client, tool_name, **kwargs):
    result = mcp_client.call_tool(tool_name, **kwargs)
    return json.loads(result) if isinstance(result, str) else result


# =============================================================================
# Live panel tests (read operations - always safe)
# =============================================================================


class TestOpenHASPLiveRead:
    def test_detect_live(self, mcp_client):
        data = _get_result(mcp_client, "openhasp_detect", ip_address=PANEL_IP)
        assert data["success"] is True
        assert data["data"]["is_openhasp"] is True
        assert data["data"]["name"] == "plate"
        assert data["data"]["gui"]["bckl"] is not None

    def test_status_live(self, mcp_client):
        data = _get_result(mcp_client, "openhasp_status", identifier=PANEL_IP)
        assert data["success"] is True
        assert data["data"]["bckl"] is not None
        assert data["data"]["objects_count"] >= 0

    def test_check_backlight_live(self, mcp_client):
        data = _get_result(mcp_client, "openhasp_check_backlight", identifier=PANEL_IP)
        assert data["success"] is True
        assert "issues" in data["data"]
        assert "status" in data["data"]

    def test_get_config_live(self, mcp_client):
        data = _get_result(mcp_client, "openhasp_get_config", identifier=PANEL_IP)
        assert data["success"] is True
        config = data["data"]["config"]
        assert "hasp" in config
        assert "gui" in config
        assert "mqtt" in config

    def test_get_pages_live(self, mcp_client):
        data = _get_result(mcp_client, "openhasp_get_pages", identifier=PANEL_IP)
        assert data["success"] is True
        assert data["data"]["objects_count"] == 1

    def test_download_file_live(self, mcp_client):
        data = _get_result(
            mcp_client, "openhasp_download_file", identifier=PANEL_IP, filename="config.json"
        )
        assert data["success"] is True
        assert len(data["data"]["content"]) > 0
        assert json.loads(data["data"]["content"])

    def test_health_live(self, mcp_client):
        data = _get_result(mcp_client, "openhasp_health", identifier=PANEL_IP)
        assert data["success"] is True
        assert "health_score" in data["data"]
        assert data["data"]["health_level"] in ("healthy", "degraded", "critical")

    def test_validate_config_live(self, mcp_client):
        data = _get_result(mcp_client, "openhasp_validate_config", identifier=PANEL_IP)
        assert data["success"] is True
        assert "valid" in data["data"]

    def test_iot_check_device_live(self, mcp_client):
        data = _get_result(mcp_client, "iot_check_device", ip_address=PANEL_IP)
        assert data["success"] is True
        assert data["data"]["is_iot_device"] is True

    def test_iot_get_device_info_live(self, mcp_client):
        data = _get_result(mcp_client, "iot_get_device_info", identifier=PANEL_IP)
        assert data["success"] is True
        assert data["data"]["device_type"] == "openhasp"
        assert data["data"]["info"]["name"] == "plate"


# =============================================================================
# Mocked Telnet tests - based on real device MSGR responses
# =============================================================================

# Raw telnet responses captured from panel at 192.168.1.100 (MSGR, no MQTT)
MOCK_MSGR_BACKLIGHT_QUERY = "#backlight\r\nMSGR: backlight\r\n#backlight\r\n#"
MOCK_MSGR_BACKLIGHT_SET = "#backlight 255\r\nMSGR: backlight=255\r\n#"
MOCK_MSGR_BACKLIGHT_ON = "#backlight on\r\nMSGR: backlight=on\r\n#"
MOCK_MSGR_IDLE_OFF = "#idle off\r\nMSGR: idle=off\r\n#"
MOCK_MSGR_PAGE_SET = "#page 1\r\nMSGR: page=1\r\n#"
MOCK_MSGR_CONFIG = "#config/gui\r\nMSGR: config/gui\r\n#"
MOCK_MSGR_SAVECONFIG = "#saveconfig\r\n"


class TestOpenHASPTelnetMocked:
    """Telnet parsing tests with real device MSGR response patterns."""

    def test_parse_backlight_query_msgr(self):
        from tools.openhasp.telnet import OpenHASPTelnet

        tn = OpenHASPTelnet("1.2.3.4")
        result = tn.parse_response(MOCK_MSGR_BACKLIGHT_QUERY)
        assert result == "backlight"

    def test_parse_backlight_set_msgr(self):
        from tools.openhasp.telnet import OpenHASPTelnet

        tn = OpenHASPTelnet("1.2.3.4")
        result = tn.parse_response(MOCK_MSGR_BACKLIGHT_SET)
        assert result == {"backlight": "255"}

    def test_parse_idle_off_msgr(self):
        from tools.openhasp.telnet import OpenHASPTelnet

        tn = OpenHASPTelnet("1.2.3.4")
        result = tn.parse_response(MOCK_MSGR_IDLE_OFF)
        assert result == {"idle": "off"}

    def test_parse_page_set_msgr(self):
        from tools.openhasp.telnet import OpenHASPTelnet

        tn = OpenHASPTelnet("1.2.3.4")
        result = tn.parse_response(MOCK_MSGR_PAGE_SET)
        assert result == {"page": "1"}

    def test_parse_mqtt_pub_format(self):
        from tools.openhasp.telnet import OpenHASPTelnet

        tn = OpenHASPTelnet("1.2.3.4")
        raw = 'MQTT PUB: backlight => {"state":"on","brightness":255}\r\n#'
        result = tn.parse_response(raw)
        assert result == {"state": "on", "brightness": 255}

    def test_parse_empty(self):
        from tools.openhasp.telnet import OpenHASPTelnet

        tn = OpenHASPTelnet("1.2.3.4")
        result = tn.parse_response("")
        assert result is None

    def test_parse_only_comments(self):
        from tools.openhasp.telnet import OpenHASPTelnet

        tn = OpenHASPTelnet("1.2.3.4")
        result = tn.parse_response("#comment\r\n")
        assert result is None

    def test_parse_ansi_escape_stripping(self):
        from tools.openhasp.telnet import OpenHASPTelnet

        tn = OpenHASPTelnet("1.2.3.4")
        raw = "\x1b[1000D\x1b[0KMSGR: backlight=255\r\n\x1b]2;title\x07"
        result = tn.parse_response(raw)
        assert result == {"backlight": "255"}


# =============================================================================
# Write tool tests through integration wrapper (ENABLE_WRITE=1 in conftest)
# =============================================================================


class TestOpenHASPWriteTools:
    """Write tools tested through mocked Telnet with real response patterns."""

    def test_telnet_command_backlight_query(self, mcp_client):
        with patch("tools.iot_openhasp._get_telnet_client") as mock_tn:
            mock_telnet = MagicMock()
            mock_telnet.send_command.return_value = MOCK_MSGR_BACKLIGHT_QUERY
            mock_telnet.parse_response.return_value = "backlight"
            mock_tn.return_value = mock_telnet

            data = _get_result(
                mcp_client, "openhasp_telnet", identifier=PANEL_IP, command="backlight"
            )
            assert data["success"] is True
            assert data["data"]["parsed"] == "backlight"

    def test_telnet_command_backlight_set(self, mcp_client):
        with patch("tools.iot_openhasp._get_telnet_client") as mock_tn:
            mock_telnet = MagicMock()
            mock_telnet.send_command.return_value = MOCK_MSGR_BACKLIGHT_SET
            mock_telnet.parse_response.return_value = {"backlight": "255"}
            mock_tn.return_value = mock_telnet

            data = _get_result(
                mcp_client, "openhasp_telnet", identifier=PANEL_IP, command="backlight 255"
            )
            assert data["success"] is True
            assert data["data"]["parsed"] == {"backlight": "255"}

    def test_backlight_set_mocked(self, mcp_client):
        with patch("tools.iot_openhasp._get_telnet_client") as mock_tn:
            mock_telnet = MagicMock()
            mock_telnet.send_command.return_value = MOCK_MSGR_BACKLIGHT_ON
            mock_telnet.backlight_set.return_value = MOCK_MSGR_BACKLIGHT_ON
            mock_tn.return_value = mock_telnet

            data = _get_result(
                mcp_client,
                "openhasp_backlight_set",
                identifier=PANEL_IP,
                state="on",
                brightness=255,
            )
            assert data["success"] is True
            assert data["data"]["state"] == "on"
            mock_telnet.idle_off.assert_called_once()

    def test_idle_reset_mocked(self, mcp_client):
        with patch("tools.iot_openhasp._get_telnet_client") as mock_tn:
            mock_telnet = MagicMock()
            mock_telnet.send_command.return_value = MOCK_MSGR_IDLE_OFF
            mock_telnet.parse_response.return_value = {"idle": "off"}
            mock_tn.return_value = mock_telnet

            data = _get_result(mcp_client, "openhasp_idle_reset", identifier=PANEL_IP)
            assert data["success"] is True

    def test_page_set_mocked(self, mcp_client):
        with patch("tools.iot_openhasp._get_telnet_client") as mock_tn:
            mock_telnet = MagicMock()
            mock_telnet.send_command.return_value = MOCK_MSGR_PAGE_SET
            mock_telnet.parse_response.return_value = {"page": "1"}
            mock_tn.return_value = mock_telnet

            data = _get_result(mcp_client, "openhasp_page_set", identifier=PANEL_IP, page=1)
            assert data["success"] is True

    def test_config_set_mocked(self, mcp_client):
        with patch("tools.iot_openhasp._get_telnet_client") as mock_tn:
            mock_telnet = MagicMock()
            mock_telnet.send_command.return_value = MOCK_MSGR_SAVECONFIG
            mock_tn.return_value = mock_telnet

            data = _get_result(
                mcp_client, "openhasp_config_set", identifier=PANEL_IP, config_json='{"idle1":30}'
            )
            assert data["success"] is True
            assert data["data"]["saved"] is True
            assert mock_telnet.send_command.call_count >= 2

    def test_jsonl_send_mocked(self, mcp_client):
        with patch("tools.iot_openhasp._get_telnet_client") as mock_tn:
            mock_telnet = MagicMock()
            mock_telnet.send_command.return_value = ""
            mock_telnet.parse_response.return_value = None
            mock_tn.return_value = mock_telnet

            data = _get_result(
                mcp_client,
                "openhasp_jsonl_send",
                identifier=PANEL_IP,
                jsonl='{"page":1,"obj":"btn","x":10}',
            )
            assert data["success"] is True

    def test_upload_file_mocked(self, mcp_client):
        with patch("tools.iot_openhasp._get_http_client") as mock_http:
            mock_client = MagicMock()
            mock_client.upload_file.return_value = True
            mock_http.return_value = mock_client

            data = _get_result(
                mcp_client,
                "openhasp_upload_file",
                identifier=PANEL_IP,
                filename="boot.cmd",
                content="# test",
            )
            assert data["success"] is True
            assert data["data"]["uploaded"] is True

    def test_health_score_mocked(self, mcp_client):
        with (
            patch("tools.iot_openhasp._get_http_client") as mock_http,
            patch("tools.iot_openhasp._get_telnet_client") as mock_tn,
        ):
            mock_client = MagicMock()
            mock_client.get_json.return_value = {
                "hasp": {"theme": "dark"},
                "gui": {"bckl": 255},
                "mqtt": {"host": "192.168.1.100", "name": "plate"},
                "wifi": {"ssid": "test"},
            }
            mock_client.count_objects.return_value = 1
            mock_http.return_value = mock_client

            mock_telnet = MagicMock()
            mock_telnet.statusupdate.return_value = {
                "version": "0.7.0-rc13",
                "tftDriver": "ST7796",
                "heapFree": 80000,
                "uptime": 3600,
                "rssi": -45,
                "mac": "AA:BB:CC:DD:EE:FF",
            }
            mock_tn.return_value = mock_telnet

            data = _get_result(mcp_client, "openhasp_health", identifier=PANEL_IP)
            assert data["success"] is True
            assert data["data"]["health_score"] == 100
            assert data["data"]["health_level"] == "healthy"

    def test_health_critical_tft_other(self, mcp_client):
        with (
            patch("tools.iot_openhasp._get_http_client") as mock_http,
            patch("tools.iot_openhasp._get_telnet_client") as mock_tn,
        ):
            mock_client = MagicMock()
            mock_client.get_json.return_value = {
                "hasp": {},
                "gui": {"bckl": 0},
                "mqtt": {"host": ""},
                "wifi": {"ssid": ""},
            }
            mock_client.count_objects.return_value = 60
            mock_http.return_value = mock_client

            mock_telnet = MagicMock()
            mock_telnet.statusupdate.return_value = {"tftDriver": "Other", "heapFree": 10000}
            mock_tn.return_value = mock_telnet

            data = _get_result(mcp_client, "openhasp_health", identifier=PANEL_IP)
            assert data["success"] is True
            assert data["data"]["health_level"] == "critical"
            assert data["data"]["health_score"] < 50

    def test_hardware_test_mocked(self, mcp_client):
        with patch("tools.iot_openhasp._get_telnet_client") as mock_tn:
            mock_telnet = MagicMock()
            mock_telnet.backlight_query.return_value = {"state": "on", "brightness": 255}
            mock_telnet.statusupdate.return_value = {
                "version": "0.7.0",
                "tftDriver": "ST7796",
                "heapFree": 80000,
            }
            mock_tn.return_value = mock_telnet

            data = _get_result(mcp_client, "openhasp_hardware_test", identifier=PANEL_IP)
            assert data["success"] is True
            assert data["data"]["backlight_state"] == {"state": "on", "brightness": 255}
            assert data["data"]["tft_driver"] == "ST7796"

    def test_iot_get_device_power_openhasp(self, mcp_client):
        with patch("tools.openhasp.telnet.OpenHASPTelnet") as mock_tn_cls:
            mock_telnet = MagicMock()
            mock_telnet.connect.return_value = True
            mock_telnet.backlight_query.return_value = {"state": "on", "brightness": 255}
            mock_tn_cls.return_value = mock_telnet

            data = _get_result(mcp_client, "iot_get_device_power", identifier=PANEL_IP)
            assert data["success"] is True
            assert data["data"]["device_type"] == "openhasp"
            assert data["data"]["state"] == "ON"

    def test_iot_set_power_openhasp(self, mcp_client):
        with patch("tools.openhasp.telnet.OpenHASPTelnet") as mock_tn_cls:
            mock_telnet = MagicMock()
            mock_telnet.connect.return_value = True
            mock_tn_cls.return_value = mock_telnet

            data = _get_result(mcp_client, "iot_set_power", identifier=PANEL_IP, state="ON")
            assert data["success"] is True
            assert data["data"]["device_type"] == "openhasp"
            mock_telnet.idle_off.assert_called_once()

    def test_iot_set_brightness_openhasp(self, mcp_client):
        with patch("tools.openhasp.telnet.OpenHASPTelnet") as mock_tn_cls:
            mock_telnet = MagicMock()
            mock_telnet.connect.return_value = True
            mock_tn_cls.return_value = mock_telnet

            data = _get_result(mcp_client, "iot_set_brightness", identifier=PANEL_IP, brightness=50)
            assert data["success"] is True
            assert data["data"]["device_type"] == "openhasp"
            assert data["data"]["brightness"] == 50
            assert data["data"]["raw_brightness"] == 127

    def test_iot_get_wifi_config_openhasp(self, mcp_client):
        with patch("tools.openhasp.http_client.OpenHASPHTTPClient") as mock_http_cls:
            mock_client = MagicMock()
            mock_client.get_json.return_value = {"wifi": {"ssid": "TestWiFi"}, "hasp": {}}
            mock_http_cls.return_value = mock_client

            data = _get_result(mcp_client, "iot_get_wifi_config", identifier=PANEL_IP)
            assert data["success"] is True
            assert data["data"]["device_type"] == "openhasp"
            assert data["data"]["wifi"]["ssid"] == "TestWiFi"

    def test_iot_restart_device_openhasp(self, mcp_client):
        with patch("tools.openhasp.telnet.OpenHASPTelnet") as mock_tn_cls:
            mock_telnet = MagicMock()
            mock_telnet.connect.return_value = True
            mock_tn_cls.return_value = mock_telnet

            data = _get_result(mcp_client, "iot_restart_device", identifier=PANEL_IP)
            assert data["success"] is True
            assert data["data"]["device_type"] == "openhasp"
            mock_telnet.restart.assert_called_once()

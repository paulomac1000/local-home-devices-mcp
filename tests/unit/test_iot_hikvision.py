"""Unit tests for Hikvision doorbell tools (fully mocked)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from tools.constants import _success_response

FAKE_HOST = "192.168.1.101"
FAKE_USER = "hikvision_user"
FAKE_PASS = "test_password"

FAKE_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<DeviceInfo xmlns="http://www.isapi.org/ver20/XMLSchema">'
    "<deviceName>Videodoorbell</deviceName>"
    "<model>DS-KV6113-WPE1(C)</model>"
    "<firmwareVersion>V2.2.65</firmwareVersion>"
    "<serialNumber>DS-KV6113-WPE1(C)0120250625RRGC0255224</serialNumber>"
    "<macAddress>a4:d5:c2:6c:54:3b</macAddress>"
    "</DeviceInfo>"
)


def _json(data):
    return _success_response(data)


class TestHikvisionDockerClient:
    def test_container_running(self):
        from tools.hikvision.docker_client import get_container_status

        with patch("tools.hikvision.docker_client._docker_request") as mock_req:
            mock_req.return_value = (
                200,
                json.dumps(
                    {
                        "State": {
                            "Running": True,
                            "Status": "running",
                            "StartedAt": "2026-06-01T18:43:11Z",
                            "Health": {"Status": "healthy"},
                        }
                    }
                ),
            )
            result = get_container_status()
            assert result["running"] is True
            assert result["status"] == "running"
            assert result["health"] == "healthy"

    def test_container_not_found(self):
        from tools.hikvision.docker_client import get_container_status

        with patch("tools.hikvision.docker_client._docker_request") as mock_req:
            mock_req.return_value = (404, "")
            result = get_container_status()
            assert result["running"] is False
            assert result["status"] == "not_found"

    def test_container_error(self):
        from tools.hikvision.docker_client import get_container_status

        with patch("tools.hikvision.docker_client._docker_request") as mock_req:
            mock_req.return_value = None
            result = get_container_status()
            assert result["running"] is False
            assert result["status"] == "not_found"

    def test_count_vmd_events_with_events(self):
        from tools.hikvision.docker_client import count_vmd_events

        with patch("tools.hikvision.docker_client.get_container_logs") as mock_logs:
            mock_logs.return_value = "2026-06-01 Motion detected from Gate\n" * 5
            result = count_vmd_events(since="4h")
            assert result["vmd_count"] == 5
            assert result["isapi_healthy"] is True

    def test_count_vmd_events_isapi_dead(self):
        from tools.hikvision.docker_client import count_vmd_events

        with patch("tools.hikvision.docker_client.get_container_logs") as mock_logs:
            mock_logs.return_value = "(empty - no events)\n"
            result = count_vmd_events(since="4h")
            assert result["vmd_count"] == 0
            assert result["isapi_healthy"] is False

    def test_restart_container_success(self):
        from tools.hikvision.docker_client import restart_container

        with patch("tools.hikvision.docker_client._docker_request") as mock_req:
            mock_req.return_value = (204, "")
            result = restart_container()
            assert result["success"] is True

    def test_restart_container_failure(self):
        from tools.hikvision.docker_client import restart_container

        with patch("tools.hikvision.docker_client._docker_request") as mock_req:
            mock_req.return_value = (500, "error")
            result = restart_container()
            assert result["success"] is False

    def test_get_container_logs_success(self):
        from tools.hikvision.docker_client import get_container_logs

        with patch("tools.hikvision.docker_client._docker_request") as mock_req:
            mock_req.return_value = (200, "log line 1\nlog line 2\n")
            result = get_container_logs(since="1h", tail=50)
            assert "log line 1" in result


class TestHikvisionISAPIClient:
    def test_get_device_info_success(self):
        from tools.hikvision.isapi_client import HikvisionISAPIClient

        with patch("tools.hikvision.isapi_client.requests.Session") as MockSession:
            mock_resp = MagicMock(status_code=200, text=FAKE_XML)
            MockSession.return_value.get.return_value = mock_resp
            client = HikvisionISAPIClient(FAKE_HOST, FAKE_USER, FAKE_PASS)
            info = client.get_device_info()
            assert info is not None
            assert info["model"] == "DS-KV6113-WPE1(C)"
            assert info["firmwareVersion"] == "V2.2.65"

    def test_get_snapshot_success(self):
        from tools.hikvision.isapi_client import HikvisionISAPIClient

        with patch("tools.hikvision.isapi_client.requests.Session") as MockSession:
            mock_resp = MagicMock(status_code=200, content=b"fake_jpeg")
            MockSession.return_value.get.return_value = mock_resp
            client = HikvisionISAPIClient(FAKE_HOST, FAKE_USER, FAKE_PASS)
            assert client.get_snapshot() == b"fake_jpeg"

    def test_get_snapshot_auth_failure(self):
        from tools.hikvision.isapi_client import HikvisionISAPIClient

        with patch("tools.hikvision.isapi_client.requests.Session") as MockSession:
            mock_resp = MagicMock(status_code=401)
            mock_resp.raise_for_status.side_effect = Exception("401")
            MockSession.return_value.get.return_value = mock_resp
            client = HikvisionISAPIClient(FAKE_HOST, FAKE_USER, "wrong")
            assert client.get_snapshot() is None

    def test_get_device_info_network_error(self):
        from tools.hikvision.isapi_client import HikvisionISAPIClient

        with patch("tools.hikvision.isapi_client.requests.Session") as MockSession:
            MockSession.return_value.get.side_effect = Exception("Timeout")
            client = HikvisionISAPIClient(FAKE_HOST, FAKE_USER, FAKE_PASS)
            assert client.get_device_info() is None

    def test_open_door_success(self):
        from tools.hikvision.isapi_client import HikvisionISAPIClient

        with patch("tools.hikvision.isapi_client.requests.Session") as MockSession:
            mock_resp = MagicMock(status_code=200)
            MockSession.return_value.put.return_value = mock_resp
            client = HikvisionISAPIClient(FAKE_HOST, FAKE_USER, FAKE_PASS)
            assert client.open_door() is True

    def test_open_door_failure(self):
        from tools.hikvision.isapi_client import HikvisionISAPIClient

        with patch("tools.hikvision.isapi_client.requests.Session") as MockSession:
            mock_resp = MagicMock(status_code=403)
            mock_resp.raise_for_status.side_effect = Exception("403")
            MockSession.return_value.put.return_value = mock_resp
            client = HikvisionISAPIClient(FAKE_HOST, FAKE_USER, FAKE_PASS)
            assert client.open_door() is False

    def test_ping_reachable(self):
        from tools.hikvision.isapi_client import HikvisionISAPIClient

        with patch("tools.hikvision.isapi_client.requests.Session") as MockSession:
            mock_resp = MagicMock(status_code=302)
            MockSession.return_value.get.return_value = mock_resp
            client = HikvisionISAPIClient(FAKE_HOST, FAKE_USER, FAKE_PASS)
            assert client.ping() is True


class TestHikvisionTools:
    def test_container_status_success(self):
        from tools.iot_hikvision import _hikvision_container_status

        with patch("tools.iot_hikvision.get_container_status") as mock:
            mock.return_value = {"running": True, "status": "running"}
            result = _hikvision_container_status()
            assert '"success": true' in result
            assert '"running": true' in result

    def test_container_logs_return_size(self):
        from tools.iot_hikvision import _hikvision_container_logs

        with patch("tools.iot_hikvision.get_container_logs") as mock:
            mock.return_value = "2026-06-01 Motion detected from Gate\n"
            result = _hikvision_container_logs(since="1h", tail=50)
            assert '"success": true' in result
            assert '"log_size_chars"' in result

    def test_check_vmd_isapi_dead(self):
        from tools.iot_hikvision import _hikvision_check_vmd

        with patch("tools.iot_hikvision.count_vmd_events") as mock:
            mock.return_value = {"vmd_count": 0, "isapi_healthy": False, "check_window": "4h"}
            result = _hikvision_check_vmd(since="4h")
            assert '"isapi_healthy": false' in result

    def test_check_vmd_isapi_alive(self):
        from tools.iot_hikvision import _hikvision_check_vmd

        with patch("tools.iot_hikvision.count_vmd_events") as mock:
            mock.return_value = {"vmd_count": 5, "isapi_healthy": True, "check_window": "4h"}
            result = _hikvision_check_vmd(since="4h")
            assert '"isapi_healthy": true' in result

    def test_restart_container_success(self):
        from tools.iot_hikvision import _hikvision_restart_container

        with patch("tools.iot_hikvision.restart_container") as mock:
            mock.return_value = {"success": True, "message": "restarted"}
            result = _hikvision_restart_container()
            assert '"success": true' in result

    def test_restart_container_error(self):
        from tools.iot_hikvision import _hikvision_restart_container

        with patch("tools.iot_hikvision.restart_container") as mock:
            mock.return_value = {"success": False, "message": "docker error"}
            result = _hikvision_restart_container()
            assert '"DOCKER_ERROR"' in result

    def test_device_info_success(self):
        from tools.iot_hikvision import _hikvision_device_info

        with patch("tools.iot_hikvision.create_isapi_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.get_device_info.return_value = {
                "model": "DS-KV6113-WPE1(C)",
                "firmwareVersion": "V2.2.65",
            }
            mock_factory.return_value = mock_client
            result = _hikvision_device_info()
            assert '"DS-KV6113-WPE1(C)"' in result

    def test_device_info_missing_creds(self):
        from tools.iot_hikvision import _hikvision_device_info

        with patch("tools.iot_hikvision.create_isapi_client") as mock_factory:
            mock_factory.side_effect = ValueError("missing creds")
            result = _hikvision_device_info()
            assert '"MISSING_CREDENTIALS"' in result


class TestHikvisionToolRegistration:
    @pytest.fixture
    def mcp(self, mock_mcp):
        from tools.iot_hikvision import register_hikvision_tools

        register_hikvision_tools(mock_mcp)
        return mock_mcp

    def test_all_seven_tools_registered(self, mcp):
        hik_tools = [n for n in mcp._tools if n.startswith("hikvision_")]
        assert len(hik_tools) == 7

    def test_container_status_tool(self, mcp):
        with patch(
            "tools.iot_hikvision._hikvision_container_status", return_value=_json({"running": True})
        ):
            result = mcp.get_tool("hikvision_container_status")()
            assert json.loads(result)["success"] is True

    def test_container_logs_tool(self, mcp):
        with patch(
            "tools.iot_hikvision._hikvision_container_logs",
            return_value=_json({"logs": "test log"}),
        ):
            result = mcp.get_tool("hikvision_container_logs")(since="1h", tail=10)
            assert json.loads(result)["success"] is True

    def test_check_vmd_tool(self, mcp):
        with patch(
            "tools.iot_hikvision._hikvision_check_vmd", return_value=_json({"isapi_healthy": True})
        ):
            result = mcp.get_tool("hikvision_check_vmd")()
            assert json.loads(result)["success"] is True

    def test_restart_container_write_guard(self, mcp):
        with patch(
            "tools.iot_hikvision.check_write_enabled", side_effect=Exception("write disabled")
        ):
            result = mcp.get_tool("hikvision_restart_container")()
            assert json.loads(result)["success"] is False

    def test_open_gate_write_guard(self, mcp):
        with patch(
            "tools.iot_hikvision.check_write_enabled", side_effect=Exception("write disabled")
        ):
            result = mcp.get_tool("hikvision_open_gate")(door_id=1)
            assert json.loads(result)["success"] is False

    def test_device_info_tool(self, mcp):
        with patch(
            "tools.iot_hikvision._hikvision_device_info",
            return_value=_json({"model": "DS-KV6113-WPE1(C)"}),
        ):
            result = mcp.get_tool("hikvision_device_info")()
            assert json.loads(result)["success"] is True

    def test_exception_handler(self, mcp):
        with patch(
            "tools.iot_hikvision._hikvision_container_status", side_effect=Exception("BOOM")
        ):
            result = mcp.get_tool("hikvision_container_status")()
            parsed = json.loads(result)
            assert parsed["success"] is False
            assert "BOOM" in parsed["error"]["message"]


class TestHikvisionDockerClientDeep:
    def test_decode_chunked_normal(self):
        from tools.hikvision.docker_client import _decode_chunked

        assert _decode_chunked("5\r\nhello\r\n0\r\n\r\n") == "hello"

    def test_decode_chunked_empty(self):
        from tools.hikvision.docker_client import _decode_chunked

        assert _decode_chunked("") == ""

    def test_decode_chunked_no_chunks(self):
        from tools.hikvision.docker_client import _decode_chunked

        assert _decode_chunked("plain text") == "plain text"

    def test_get_container_status_invalid_json(self):
        from tools.hikvision.docker_client import get_container_status

        with patch("tools.hikvision.docker_client._docker_request") as mock_req:
            mock_req.return_value = (200, "not json")
            result = get_container_status()
            assert result["running"] is False

    def test_get_container_logs_error(self):
        from tools.hikvision.docker_client import get_container_logs

        with patch("tools.hikvision.docker_client._docker_request") as mock_req:
            mock_req.return_value = (500, "server error")
            result = get_container_logs(since="1h")
            assert "HTTP 500" in result

    def test_get_container_logs_unreachable(self):
        from tools.hikvision.docker_client import get_container_logs

        with patch("tools.hikvision.docker_client._docker_request") as mock_req:
            mock_req.return_value = None
            result = get_container_logs(since="1h")
            assert "unreachable" in result.lower()

    def test_restart_container_unreachable(self):
        from tools.hikvision.docker_client import restart_container

        with patch("tools.hikvision.docker_client._docker_request") as mock_req:
            mock_req.return_value = None
            result = restart_container()
            assert result["success"] is False

    def test_count_vmd_events_direct(self):
        from tools.hikvision.docker_client import count_vmd_events

        with patch("tools.hikvision.docker_client.get_container_logs") as mock_logs:
            mock_logs.return_value = "2026-06-01 Motion detected from Gate\n"
            result = count_vmd_events(since="4h")
            assert result["vmd_count"] == 1


class TestHikvisionISAPIClientDeep:
    """Additional ISAPI client tests for uncovered edge cases."""

    def test_ping_reachable(self):
        from tools.hikvision.isapi_client import HikvisionISAPIClient

        with patch("tools.hikvision.isapi_client.requests.Session") as MockSession:
            mock_resp = MagicMock(status_code=302)
            MockSession.return_value.get.return_value = mock_resp
            client = HikvisionISAPIClient(FAKE_HOST, FAKE_USER, FAKE_PASS)
            assert client.ping() is True

    def test_ping_unreachable(self):
        from tools.hikvision.isapi_client import HikvisionISAPIClient

        with patch("tools.hikvision.isapi_client.requests.Session") as MockSession:
            MockSession.return_value.get.side_effect = Exception("timeout")
            client = HikvisionISAPIClient(FAKE_HOST, FAKE_USER, FAKE_PASS)
            assert client.ping() is False

    def test_get_device_info_xml_parse_failure(self):
        from tools.hikvision.isapi_client import HikvisionISAPIClient

        with patch("tools.hikvision.isapi_client.requests.Session") as MockSession:
            mock_resp = MagicMock(status_code=200, text="not valid xml ><")
            MockSession.return_value.get.return_value = mock_resp
            client = HikvisionISAPIClient(FAKE_HOST, FAKE_USER, FAKE_PASS)
            assert client.get_device_info() is None

    def test_get_snapshot_http_error(self):
        from tools.hikvision.isapi_client import HikvisionISAPIClient

        with patch("tools.hikvision.isapi_client.requests.Session") as MockSession:
            mock_resp = MagicMock(status_code=500)
            mock_resp.raise_for_status.side_effect = Exception("500")
            MockSession.return_value.get.return_value = mock_resp
            client = HikvisionISAPIClient(FAKE_HOST, FAKE_USER, FAKE_PASS)
            assert client.get_snapshot() is None

    def test_create_isapi_client_missing_creds(self):
        from tools.hikvision.isapi_client import create_isapi_client

        with (
            patch("tools.hikvision.isapi_client.HIKVISION_DOORBELL_USER", ""),
            patch("tools.hikvision.isapi_client.HIKVISION_DOORBELL_PASSWORD", ""),
        ):
            try:
                create_isapi_client()
                assert False, "Should raise ValueError"
            except ValueError as exc:
                assert "HIKVISION_DOORBELL_USER" in str(exc)

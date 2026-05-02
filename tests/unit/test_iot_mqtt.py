"""
Unit tests for IoT MCP MQTT tools.
"""

import json
from unittest.mock import MagicMock, patch

from tools.iot_mqtt import (
    _get_mqtt_client,
    _mqtt_build_command_topic,
    _mqtt_get_state,
    _mqtt_publish,
)


class TestGetMqttClient:
    """Tests for MQTT client creation."""

    def test_get_client_success(self):
        """Should return a configured MQTT client."""
        with patch("paho.mqtt.client.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            with patch("tools.iot_mqtt.MQTT_USER", "testuser"):
                with patch("tools.iot_mqtt.MQTT_PASSWORD", "testpass"):
                    client = _get_mqtt_client()
                    assert client is not None
                    mock_client.username_pw_set.assert_called_once_with(
                        "testuser", "testpass"
                    )

    def test_get_client_no_paho(self):
        """Should return None when paho-mqtt is not installed."""
        with patch.dict("sys.modules", {"paho": None, "paho.mqtt": None, "paho.mqtt.client": None}):
            client = _get_mqtt_client()
            assert client is None

    def test_get_client_v2_api(self):
        """Should use VERSION1 callback API for paho-mqtt >= 2.0."""
        with patch("paho.mqtt.client.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            # Simulate v2 API availability
            import paho.mqtt.client as mqtt
            orig_cb = getattr(mqtt, "CallbackAPIVersion", None)
            mqtt.CallbackAPIVersion = MagicMock()
            mqtt.CallbackAPIVersion.VERSION1 = "VERSION1"
            try:
                with patch("tools.iot_mqtt.MQTT_USER", ""):
                    client = _get_mqtt_client()
                    assert client is mock_client
                    mock_client_class.assert_called_once_with(
                        callback_api_version="VERSION1"
                    )
            finally:
                if orig_cb is not None:
                    mqtt.CallbackAPIVersion = orig_cb
                else:
                    delattr(mqtt, "CallbackAPIVersion")

    def test_get_client_v1_api(self):
        """Should fall back to plain Client() for paho-mqtt < 2.0."""
        with patch("paho.mqtt.client.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            # Simulate v1 API (no CallbackAPIVersion)
            import paho.mqtt.client as mqtt
            orig_cb = getattr(mqtt, "CallbackAPIVersion", None)
            if hasattr(mqtt, "CallbackAPIVersion"):
                delattr(mqtt, "CallbackAPIVersion")
            try:
                with patch("tools.iot_mqtt.MQTT_USER", ""):
                    client = _get_mqtt_client()
                    assert client is mock_client
                    mock_client_class.assert_called_once_with()
            finally:
                if orig_cb is not None:
                    mqtt.CallbackAPIVersion = orig_cb


class TestMqttPublish:
    """Tests for MQTT publish."""

    def test_publish_success(self):
        """Should publish message and return success."""
        with patch("tools.iot_mqtt._get_mqtt_client") as mock_get_client:
            mock_client = MagicMock()
            mock_result = MagicMock()
            mock_result.rc = 0
            mock_client.publish.return_value = mock_result
            mock_get_client.return_value = mock_client

            result = _mqtt_publish("cmnd/test/Power", "ON")
            data = json.loads(result)

            assert data["success"] is True
            assert data["topic"] == "cmnd/test/Power"
            assert data["payload"] == "ON"
            assert data["mqtt_result"] == 0
            mock_client.connect.assert_called_once()
            mock_client.disconnect.assert_called_once()

    def test_publish_no_client(self):
        """Should return error when paho-mqtt is not installed."""
        with patch("tools.iot_mqtt._get_mqtt_client", return_value=None):
            result = _mqtt_publish("cmnd/test/Power", "ON")
            data = json.loads(result)
            assert data["success"] is False
            assert "paho-mqtt not installed" in data["error"]

    def test_publish_connection_error(self):
        """Should handle connection errors gracefully."""
        with patch("tools.iot_mqtt._get_mqtt_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.connect.side_effect = Exception("Connection refused")
            mock_get_client.return_value = mock_client

            result = _mqtt_publish("cmnd/test/Power", "ON")
            data = json.loads(result)
            assert data["success"] is False
            assert "Connection refused" in data["error"]


class TestMqttGetState:
    """Tests for MQTT state retrieval."""

    def test_get_state_success(self):
        """Should receive and return state message."""
        with patch("tools.iot_mqtt._get_mqtt_client") as mock_get_client:
            mock_client = MagicMock()

            def capture_on_message(*args, **kwargs):
                if mock_client.on_message:
                    msg = MagicMock()
                    msg.topic = "tele/test/STATE"
                    msg.payload = b'{"POWER":"ON"}'
                    mock_client.on_message(mock_client, None, msg)

            mock_client.loop_start.side_effect = capture_on_message
            mock_get_client.return_value = mock_client

            with patch("tools.iot_mqtt.time.sleep"):
                result = _mqtt_get_state("test", timeout_sec=1)
                data = json.loads(result)

                assert data["success"] is True
                assert data["topic"] == "tele/test/STATE"
                assert data["state"]["POWER"] == "ON"

    def test_get_state_no_client(self):
        """Should return error when paho-mqtt is not installed."""
        with patch("tools.iot_mqtt._get_mqtt_client", return_value=None):
            result = _mqtt_get_state("test")
            data = json.loads(result)
            assert data["success"] is False
            assert "paho-mqtt not installed" in data["error"]

    def test_get_state_timeout(self):
        """Should return error when no message received."""
        with patch("tools.iot_mqtt._get_mqtt_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            with patch("tools.iot_mqtt.time.sleep"):
                result = _mqtt_get_state("test", timeout_sec=1)
                data = json.loads(result)
                assert data["success"] is False
                assert "No state message" in data["error"]


class TestMqttBuildCommandTopic:
    """Tests for MQTT topic builder."""

    def test_build_topic(self):
        """Should build correct MQTT topics."""
        result = _mqtt_build_command_topic("tasmota_12345", "Power")
        data = json.loads(result)

        assert data["success"] is True
        assert data["command_topic"] == "cmnd/tasmota_12345/Power"
        assert data["state_topic"] == "stat/tasmota_12345/Power"
        assert data["telemetry_topic"] == "tele/tasmota_12345/STATE"
        assert "ON" in data["example_payloads"]

    def test_build_topic_default_command(self):
        """Should default to Power command."""
        result = _mqtt_build_command_topic("tasmota_12345")
        data = json.loads(result)
        assert data["command"] == "Power"

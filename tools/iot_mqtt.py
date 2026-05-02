"""
IoT MQTT Integration Tools

Interact with IoT devices via MQTT broker.
"""

import json
import os
import time
from typing import Dict

__all__ = ["register_iot_mqtt_tools", "_get_mqtt_client", "_mqtt_publish"]

MQTT_BROKER = os.getenv("MQTT_BROKER", "192.168.0.101")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")


def _get_mqtt_client():
    """Get configured MQTT client.

    Returns:
        Configured mqtt.Client instance or None if paho-mqtt is not installed.
    """
    try:
        import paho.mqtt.client as mqtt

        try:
            # paho-mqtt >= 2.0 requires callback_api_version
            client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION1)
        except (AttributeError, TypeError):
            # paho-mqtt < 2.0
            client = mqtt.Client()

        if MQTT_USER:
            client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

        return client
    except ImportError:
        return None


def _mqtt_publish(topic: str, payload: str, retain: bool = False) -> str:
    """Publish an MQTT message.

    Args:
        topic: MQTT topic (e.g. "cmnd/tasmota_389AF7/Power").
        payload: Message payload (e.g. "ON", "OFF", "TOGGLE").
        retain: Whether to retain the message.

    Returns:
        JSON string with result.
    """
    client = _get_mqtt_client()
    if not client:
        return json.dumps(
            {
                "success": False,
                "error": (
                    "paho-mqtt not installed. Install with: pip install paho-mqtt"
                ),
            },
            indent=2,
        )

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 5)
        result = client.publish(topic, payload, retain=retain)
        client.disconnect()

        return json.dumps(
            {
                "success": True,
                "broker": f"{MQTT_BROKER}:{MQTT_PORT}",
                "topic": topic,
                "payload": payload,
                "retain": retain,
                "mqtt_result": result.rc,
            },
            indent=2,
        )
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)}, indent=2)


def _mqtt_get_state(topic_prefix: str, timeout_sec: int = 5) -> str:
    """Get current state of a device via MQTT.

    Subscribes to the state topic and returns the latest value.

    Args:
        topic_prefix: Device topic prefix (e.g. "tasmota_389AF7").
        timeout_sec: How long to wait for state message in seconds.

    Returns:
        JSON string with device state.
    """
    client = _get_mqtt_client()
    if not client:
        return json.dumps(
            {"success": False, "error": "paho-mqtt not installed"},
            indent=2,
        )

    state_topic = f"tele/{topic_prefix}/STATE"
    received_messages: list[Dict[str, str]] = []

    def on_message(_client, _userdata, msg):
        received_messages.append({"topic": msg.topic, "payload": msg.payload.decode()})

    client.on_message = on_message
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 5)
        client.subscribe(state_topic)
        client.loop_start()
        time.sleep(timeout_sec)
        client.loop_stop()
        client.disconnect()
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)}, indent=2)

    if not received_messages:
        return json.dumps(
            {
                "success": False,
                "error": "No state message received within timeout",
                "topic": state_topic,
                "timeout": timeout_sec,
            },
            indent=2,
        )

    latest = received_messages[-1]
    try:
        payload = json.loads(latest["payload"])
    except json.JSONDecodeError:
        payload = latest["payload"]

    return json.dumps(
        {
            "success": True,
            "topic": latest["topic"],
            "state": payload,
            "messages_received": len(received_messages),
        },
        indent=2,
    )


def _mqtt_build_command_topic(device_name: str, command: str = "Power") -> str:
    """Build MQTT command topic for a device.

    Args:
        device_name: Device MQTT topic (e.g. "tasmota_389AF7").
        command: Command name (default "Power").

    Returns:
        JSON string with topic information.
    """
    topic = f"cmnd/{device_name}/{command}"
    state_topic = f"stat/{device_name}/{command}"
    tele_topic = f"tele/{device_name}/STATE"

    return json.dumps(
        {
            "success": True,
            "device_name": device_name,
            "command": command,
            "command_topic": topic,
            "state_topic": state_topic,
            "telemetry_topic": tele_topic,
            "example_payloads": {
                "ON": "Turn device ON",
                "OFF": "Turn device OFF",
                "TOGGLE": "Toggle device state",
                "0": "Set brightness/channel to 0",
                "100": "Set brightness/channel to 100",
            },
        },
        indent=2,
    )


def register_iot_mqtt_tools(mcp) -> None:
    """Register IoT MQTT tools with the MCP server."""

    @mcp.tool()
    def iot_mqtt_publish(topic: str, payload: str, retain: bool = False) -> str:
        """Publish an MQTT message to control an IoT device.

        Args:
            topic: MQTT topic (e.g. "cmnd/tasmota_389AF7/Power").
            payload: Message payload (e.g. "ON", "OFF", "TOGGLE").
            retain: Whether to retain the message (default False).

        Returns:
            JSON with result.
        """
        return _mqtt_publish(topic, payload, retain)

    @mcp.tool()
    def iot_mqtt_get_state(topic_prefix: str, timeout: int = 5) -> str:
        """Get current state of a device via MQTT.

        Subscribes to the state topic and returns the latest value.

        Args:
            topic_prefix: Device topic prefix (e.g. "tasmota_389AF7").
            timeout: How long to wait for state message (seconds).

        Returns:
            JSON with device state.
        """
        return _mqtt_get_state(topic_prefix, timeout)

    @mcp.tool()
    def iot_mqtt_build_command_topic(device_name: str, command: str = "Power") -> str:
        """Build MQTT command topic for a device.

        Args:
            device_name: Device MQTT topic (e.g. "tasmota_389AF7").
            command: Command name (default "Power").

        Returns:
            JSON with topic information.
        """
        return _mqtt_build_command_topic(device_name, command)

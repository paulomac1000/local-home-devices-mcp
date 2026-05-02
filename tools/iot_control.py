"""
IoT Device Control Tools

Control OpenBK and Tasmota devices (power, brightness, etc.)
Supports lookup by IP address or device name from the discovery cache.
"""

import json
from typing import Optional

import requests

__all__ = [
    "register_iot_control_tools",
    "_set_power",
    "_set_brightness",
    "_restart_device",
    "_get_wifi_config",
]


def _resolve_or_fail(identifier: str) -> Optional[str]:
    """Resolve identifier to IP or return None and let caller handle error.

    Internal helper to avoid duplicating the resolution logic.
    """
    from tools.iot_discovery import _resolve_ip

    return _resolve_ip(identifier)


def _build_unresolved_response(identifier: str) -> str:
    """Build standard JSON response when identifier cannot be resolved."""
    from tools.iot_discovery import _get_cached_devices

    available = sorted(
        set(
            d.get("name", "Unknown")
            for d in _get_cached_devices()
            if d.get("name")
        )
    )
    return json.dumps(
        {
            "success": False,
            "error": f"Could not resolve '{identifier}' to an IP address",
            "suggestion": (
                "Run iot_discover_devices() first, "
                "then use iot_list_devices()"
            ),
            "available_names": available[:50],
        },
        indent=2,
    )


def _set_power(identifier: str, state: str, channel: int = 1) -> str:
    """Set power state of an IoT device channel.

    Args:
        identifier: IP address or device name.
        state: Power state - "ON", "OFF", or "TOGGLE".
        channel: Channel number (1-based, default 1).

    Returns:
        JSON string with result.
    """
    from tools.iot_discovery import _detect_device_type

    ip_address = _resolve_or_fail(identifier)
    if not ip_address:
        return _build_unresolved_response(identifier)

    device_type = _detect_device_type(ip_address)
    if not device_type:
        return json.dumps(
            {
                "success": False,
                "error": (
                    f"No IoT device found at {ip_address} "
                    f"(resolved from '{identifier}')"
                ),
            },
            indent=2,
        )

    state = state.upper()
    if state not in ("ON", "OFF", "TOGGLE"):
        return json.dumps(
            {
                "success": False,
                "error": f"Invalid state: {state}. Use ON, OFF, or TOGGLE",
            },
            indent=2,
        )

    if device_type == "tasmota":
        resp = requests.get(
            f"http://{ip_address}/cm?cmnd=Power{channel}%20{state}",
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            power_key = f"POWER{channel}"
            result_state = data.get(power_key) or data.get("POWER")
            return json.dumps(
                {
                    "success": True,
                    "device_type": "tasmota",
                    "resolved_from": identifier,
                    "ip": ip_address,
                    "channel": channel,
                    "requested_state": state,
                    "actual_state": result_state,
                },
                indent=2,
            )
        return json.dumps(
            {"success": False, "error": f"HTTP {resp.status_code}"},
            indent=2,
        )

    if device_type == "openbk":
        if state == "TOGGLE":
            resp = requests.get(
                f"http://{ip_address}/index?tgl={channel}", timeout=5
            )
        else:
            value = 1 if state == "ON" else 0
            resp = requests.get(
                f"http://{ip_address}/index?set={channel}&val={value}",
                timeout=5,
            )
        if resp.status_code == 200:
            return json.dumps(
                {
                    "success": True,
                    "device_type": "openbk",
                    "resolved_from": identifier,
                    "ip": ip_address,
                    "channel": channel,
                    "requested_state": state,
                    "note": "Command sent successfully",
                },
                indent=2,
            )
        return json.dumps(
            {"success": False, "error": f"HTTP {resp.status_code}"},
            indent=2,
        )

    return json.dumps(
        {"success": False, "error": f"Unsupported device type: {device_type}"},
        indent=2,
    )


def _set_brightness(identifier: str, brightness: int, channel: int = 1) -> str:
    """Set brightness of an IoT device channel (0-100).

    Args:
        identifier: IP address or device name.
        brightness: Brightness value (0-100).
        channel: Channel number (1-based, default 1).

    Returns:
        JSON string with result.
    """
    from tools.iot_discovery import _detect_device_type

    ip_address = _resolve_or_fail(identifier)
    if not ip_address:
        return _build_unresolved_response(identifier)

    device_type = _detect_device_type(ip_address)
    if not device_type:
        return json.dumps(
            {
                "success": False,
                "error": f"No IoT device found at {ip_address}",
            },
            indent=2,
        )

    brightness = max(0, min(100, brightness))

    if device_type == "tasmota":
        resp = requests.get(
            f"http://{ip_address}/cm?cmnd=Channel{channel}%20{brightness}",
            timeout=5,
        )
        if resp.status_code == 200:
            return json.dumps(
                {
                    "success": True,
                    "device_type": "tasmota",
                    "resolved_from": identifier,
                    "ip": ip_address,
                    "channel": channel,
                    "brightness": brightness,
                },
                indent=2,
            )

    elif device_type == "openbk":
        resp = requests.get(
            f"http://{ip_address}/index?set={channel}&val={brightness}",
            timeout=5,
        )
        if resp.status_code == 200:
            return json.dumps(
                {
                    "success": True,
                    "device_type": "openbk",
                    "resolved_from": identifier,
                    "ip": ip_address,
                    "channel": channel,
                    "brightness": brightness,
                },
                indent=2,
            )

    return json.dumps(
        {"success": False, "error": f"Unsupported device type: {device_type}"},
        indent=2,
    )


def _restart_device(identifier: str) -> str:
    """Restart an IoT device.

    WARNING: This will temporarily disconnect the device!

    Args:
        identifier: IP address or device name.

    Returns:
        JSON string with result.
    """
    from tools.iot_discovery import _detect_device_type

    ip_address = _resolve_or_fail(identifier)
    if not ip_address:
        return _build_unresolved_response(identifier)

    device_type = _detect_device_type(ip_address)

    if device_type == "tasmota":
        resp = requests.get(
            f"http://{ip_address}/cm?cmnd=Restart%201", timeout=5
        )
        if resp.status_code == 200:
            return json.dumps(
                {
                    "success": True,
                    "device_type": "tasmota",
                    "resolved_from": identifier,
                    "ip": ip_address,
                    "message": "Restart command sent",
                },
                indent=2,
            )

    elif device_type == "openbk":
        resp = requests.get(
            f"http://{ip_address}/index?restart=1", timeout=5
        )
        if resp.status_code == 200:
            return json.dumps(
                {
                    "success": True,
                    "device_type": "openbk",
                    "resolved_from": identifier,
                    "ip": ip_address,
                    "message": "Restart command sent",
                },
                indent=2,
            )

    return json.dumps(
        {"success": False, "error": "Device not found"}, indent=2
    )


def _get_wifi_config(identifier: str) -> str:
    """Get WiFi configuration from an IoT device.

    Args:
        identifier: IP address or device name.

    Returns:
        JSON string with WiFi configuration.
    """
    from tools.iot_discovery import _detect_device_type
    from tools.iot_devices import _get_openbk_status

    ip_address = _resolve_or_fail(identifier)
    if not ip_address:
        return _build_unresolved_response(identifier)

    device_type = _detect_device_type(ip_address)

    if device_type == "tasmota":
        resp = requests.get(
            f"http://{ip_address}/cm?cmnd=Status%205", timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            wifi = data.get("StatusSTS", {}).get("Wifi", {})
            return json.dumps(
                {
                    "success": True,
                    "device_type": "tasmota",
                    "resolved_from": identifier,
                    "ip": ip_address,
                    "wifi": {
                        "ssid": wifi.get("SSId"),
                        "rssi": wifi.get("RSSI"),
                        "signal": wifi.get("Signal"),
                        "mac": wifi.get("Mac"),
                        "ip": wifi.get("IPAddress"),
                        "gateway": wifi.get("Gateway"),
                        "mode": wifi.get("Mode"),
                    },
                },
                indent=2,
            )

    elif device_type == "openbk":
        info = _get_openbk_status(ip_address)
        return json.dumps(
            {
                "success": True,
                "device_type": "openbk",
                "resolved_from": identifier,
                "ip": ip_address,
                "wifi": {
                    "rssi": info.get("rssi"),
                    "signal_quality": info.get("signal_quality"),
                    "mac": info.get("mac"),
                },
            },
            indent=2,
        )

    return json.dumps(
        {"success": False, "error": "Device not found"}, indent=2
    )


def register_iot_control_tools(mcp) -> None:
    """Register IoT device control tools with the MCP server."""

    @mcp.tool()
    def iot_set_power(identifier: str, state: str, channel: int = 1) -> str:
        """Set power state of an IoT device channel.

        Accepts either an IP address or a device name from the discovery cache.

        Args:
            identifier: IP address or device name.
            state: Power state - "ON", "OFF", or "TOGGLE".
            channel: Channel number (1-based, default 1).

        Returns:
            JSON with result.
        """
        try:
            return _set_power(identifier, state, channel)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)}, indent=2)

    @mcp.tool()
    def iot_set_brightness(
        identifier: str, brightness: int, channel: int = 1
    ) -> str:
        """Set brightness of an IoT device channel (0-100).

        Accepts either an IP address or a device name from the discovery cache.

        Args:
            identifier: IP address or device name.
            brightness: Brightness value (0-100).
            channel: Channel number (1-based, default 1).

        Returns:
            JSON with result.
        """
        try:
            return _set_brightness(identifier, brightness, channel)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)}, indent=2)

    @mcp.tool()
    def iot_restart_device(identifier: str) -> str:
        """Restart an IoT device.

        WARNING: This will temporarily disconnect the device!

        Accepts either an IP address or a device name from the discovery cache.

        Args:
            identifier: IP address or device name.

        Returns:
            JSON with result.
        """
        try:
            return _restart_device(identifier)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)}, indent=2)

    @mcp.tool()
    def iot_get_wifi_config(identifier: str) -> str:
        """Get WiFi configuration from an IoT device.

        Accepts either an IP address or a device name from the discovery cache.

        Args:
            identifier: IP address or device name.

        Returns:
            JSON with WiFi configuration.
        """
        try:
            return _get_wifi_config(identifier)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)}, indent=2)

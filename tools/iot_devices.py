# mypy: disable-error-code="untyped-decorator"
"""
IoT Device Information Tools

Get status and information from OpenBK and Tasmota devices.
Supports lookup by IP address or device name from the discovery cache.
"""

import re
from typing import Any

import requests

from tools.constants import (
    _error_response_extended,
    _success_response,
    increment_tool_count,
    start_tool_context,
)

__all__ = [
    "register_iot_device_tools",
    "_get_openbk_status",
    "_get_tasmota_status",
    "_get_device_info",
    "_get_device_power",
]


def _get_openbk_status(ip: str, timeout: int = 5) -> dict[str, Any]:
    """Get full status from an OpenBK device.

    Args:
        ip: IP address of the device.
        timeout: Request timeout in seconds.

    Returns:
        Dictionary with device status or {"error": ...} on failure.
    """
    try:
        resp = requests.get(f"http://{ip}/index", timeout=timeout)
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}"}

        text = resp.text
        status: dict[str, Any] = {
            "name": None,
            "channels": [],
            "rssi": None,
            "mac": None,
            "version": None,
            "uptime_seconds": None,
            "mqtt_connected": False,
            "reboot_reason": None,
        }

        title_match = re.search(r"<title>([^<]+)</title>", text)
        if title_match:
            status["name"] = title_match.group(1).strip()

        channels = re.findall(r"Channel\s+(\d+)\s+=\s+([\d.]+)", text)
        status["channels"] = [{"channel": int(c[0]), "value": float(c[1])} for c in channels]

        rssi_match = re.search(r"Wifi RSSI:\s+([\w\s]+)\s*\((-?\d+)dBm\)", text)
        if rssi_match:
            status["rssi"] = int(rssi_match.group(2))
            status["signal_quality"] = rssi_match.group(1).strip()

        mac_match = re.search(r"Device MAC:\s*([0-9A-Fa-f:]{17})", text)
        if mac_match:
            status["mac"] = mac_match.group(1)

        ver_match = re.search(r"version\s+([\d.]+)", text)
        if ver_match:
            status["version"] = ver_match.group(1)

        uptime_match = re.search(r'data-initial="(\d+)"', text)
        if uptime_match:
            status["uptime_seconds"] = int(uptime_match.group(1))

        if 'MQTT State: <span style="color:green">connected</span>' in text:
            status["mqtt_connected"] = True

        reboot_match = re.search(r"Reboot reason:\s*(\d+)\s*-\s*(\w+)", text)
        if reboot_match:
            status["reboot_reason"] = {
                "code": int(reboot_match.group(1)),
                "reason": reboot_match.group(2),
            }

        return status
    except Exception as exc:
        return {"error": str(exc)}


def _get_tasmota_status(ip: str, timeout: int = 5) -> dict[str, Any]:
    """Get full status from a Tasmota device.

    Args:
        ip: IP address of the device.
        timeout: Request timeout in seconds.

    Returns:
        Dictionary with device status or {"error": ...} on failure.
    """
    try:
        resp = requests.get(f"http://{ip}/cm?cmnd=Status%200", timeout=timeout)
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}"}

        data = resp.json()
        status = data.get("Status", {})

        wifi_data: dict[str, Any] = {}
        try:
            wifi_resp = requests.get(f"http://{ip}/cm?cmnd=Status%205", timeout=timeout)
            if wifi_resp.status_code == 200:
                wifi_json = wifi_resp.json()
                wifi_data = wifi_json.get("StatusSTS", {}).get("Wifi", {})
        except Exception:
            pass

        current_power = None
        try:
            power_resp = requests.get(f"http://{ip}/cm?cmnd=Power", timeout=timeout)
            if power_resp.status_code == 200:
                current_power = power_resp.json().get("POWER")
        except Exception:
            pass

        return {
            "name": status.get("FriendlyName", ["Unknown"])[0],
            "device_name": status.get("DeviceName", "Unknown"),
            "topic": status.get("Topic", ""),
            "power_state": status.get("Power", 0),
            "current_power": current_power,
            "version": status.get("Version", "Unknown"),
            "module": status.get("Module", 0),
            "rssi": wifi_data.get("RSSI"),
            "ssid": wifi_data.get("SSId"),
            "mac": wifi_data.get("Mac"),
            "ip": wifi_data.get("IPAddress"),
            "wifi_mode": wifi_data.get("Mode"),
            "save_data": status.get("SaveData", 0),
            "power_on_state": status.get("PowerOnState", 0),
        }
    except Exception as exc:
        return {"error": str(exc)}


def _get_device_info(identifier: str, timeout_seconds: int = 10) -> str:
    """Get detailed information about an IoT device.

    Args:
        identifier: IP address or device name from the discovery cache.
        timeout_seconds: Request timeout in seconds.

    Returns:
        JSON string with device information.
    """
    from tools.iot_discovery import (
        _detect_device_type,
        _resolve_ip,
    )

    ip_address = _resolve_ip(identifier)

    if not ip_address:
        return _error_response_extended(
            code="NAME_NOT_RESOLVED",
            message=f"Could not resolve '{identifier}' to an IP address",
            suggestion=(
                "Run iot_discover_devices() to populate the cache, then use iot_list_devices()"
            ),
        )

    device_type = _detect_device_type(ip_address, timeout_seconds)

    if not device_type:
        return _error_response_extended(
            code="DEVICE_NOT_FOUND",
            message=f"No IoT device found at {ip_address} (resolved from '{identifier}')",
        )

    if device_type == "openbk":
        info = _get_openbk_status(ip_address, timeout_seconds)
    elif device_type == "tasmota":
        info = _get_tasmota_status(ip_address, timeout_seconds)
    else:
        return _error_response_extended(
            code="UNSUPPORTED_TYPE",
            message=f"Unknown device type: {device_type}",
        )

    if "error" in info:
        return _error_response_extended(code="INTERNAL_ERROR", message=info["error"])

    return _success_response(
        {
            "resolved_from": identifier,
            "ip_address": ip_address,
            "device_type": device_type,
            "info": info,
        }
    )


def _get_device_power(identifier: str, channel: int = 1, timeout_seconds: int = 10) -> str:
    """Get power state of a specific channel on an IoT device.

    Args:
        identifier: IP address or device name.
        channel: Channel number (1-based, default 1).
        timeout_seconds: Request timeout in seconds.

    Returns:
        JSON string with power state.
    """
    from tools.iot_discovery import (
        _detect_device_type,
        _resolve_ip,
    )

    ip_address = _resolve_ip(identifier)

    if not ip_address:
        return _error_response_extended(
            code="NAME_NOT_RESOLVED",
            message=f"Could not resolve '{identifier}' to an IP address",
            suggestion="Run iot_discover_devices() first, then use iot_list_devices()",
        )

    device_type = _detect_device_type(ip_address, timeout_seconds)

    if device_type == "tasmota":
        try:
            resp = requests.get(f"http://{ip_address}/cm?cmnd=Power", timeout=timeout_seconds)
            if resp.status_code == 200:
                data = resp.json()
                power_key = f"POWER{channel}"
                state = data.get(power_key) or data.get("POWER")
                return _success_response(
                    {
                        "device_type": "tasmota",
                        "resolved_from": identifier,
                        "ip": ip_address,
                        "channel": channel,
                        "state": state,
                    }
                )
        except Exception as exc:
            return _error_response_extended(code="INTERNAL_ERROR", message=str(exc))

    elif device_type == "openbk":
        info = _get_openbk_status(ip_address, timeout_seconds)
        channels = info.get("channels", [])
        channel_info = next((c for c in channels if c["channel"] == channel - 1), None)
        return _success_response(
            {
                "device_type": "openbk",
                "resolved_from": identifier,
                "ip": ip_address,
                "channel": channel,
                "state": ("ON" if channel_info and channel_info["value"] > 0 else "OFF"),
                "value": channel_info["value"] if channel_info else 0,
            }
        )

    return _error_response_extended(
        code="UNSUPPORTED_TYPE",
        message="Device not found or unsupported",
    )


def register_iot_device_tools(mcp: Any) -> None:
    """Register IoT device information tools with the MCP server."""

    @mcp.tool()
    def iot_get_device_info(identifier: str, timeout_seconds: int = 10) -> str:
        """Get detailed information about an IoT device.

        Accepts either an IP address or a device name from the discovery cache.

        Args:
            identifier: IP address (e.g. "192.168.0.241") or device name.
            timeout_seconds: Request timeout in seconds (default 10).

        Returns:
            JSON with device information.

        @since v1.2.0
        """
        try:
            start_tool_context()
            increment_tool_count("iot_get_device_info")
            return _get_device_info(identifier, timeout_seconds)
        except Exception as exc:
            return _error_response_extended(code="INTERNAL_ERROR", message=str(exc))

    @mcp.tool()
    def iot_get_device_power(identifier: str, channel: int = 1, timeout_seconds: int = 10) -> str:
        """Get power state of a specific channel on an IoT device.

        Accepts either an IP address or a device name from the discovery cache.

        Args:
            identifier: IP address or device name.
            channel: Channel number (1-based, default 1).
            timeout_seconds: Request timeout in seconds (default 10).

        Returns:
            JSON with power state.

        @since v1.2.0
        """
        try:
            start_tool_context()
            increment_tool_count("iot_get_device_power")
            return _get_device_power(identifier, channel, timeout_seconds)
        except Exception as exc:
            return _error_response_extended(code="INTERNAL_ERROR", message=str(exc))

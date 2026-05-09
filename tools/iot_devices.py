"""
IoT Device Information Tools

Get status and information from OpenBK and Tasmota devices.
Supports lookup by IP address or device name from the discovery cache.
"""

import json
import re
from typing import Any

import requests

from tools.constants import _error, _success

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


def _get_device_info(identifier: str) -> str:
    """Get detailed information about an IoT device.

    Args:
        identifier: IP address or device name from the discovery cache.

    Returns:
        JSON string with device information.
    """
    from tools.iot_discovery import (
        _detect_device_type,
        _get_cached_devices,
        _resolve_ip,
    )

    ip_address = _resolve_ip(identifier)

    if not ip_address:
        sorted(set(d.get("name", "Unknown") for d in _get_cached_devices() if d.get("name")))
        return json.dumps(
            _error(
                f"Could not resolve '{identifier}' to an IP address",
                code="NAME_NOT_RESOLVED",
                suggestion="Run iot_discover_devices() to populate the cache, then use iot_list_devices()",
            ),
            indent=2,
        )

    device_type = _detect_device_type(ip_address)

    if not device_type:
        return json.dumps(
            _error(
                f"No IoT device found at {ip_address} (resolved from '{identifier}')",
                code="DEVICE_NOT_FOUND",
            ),
            indent=2,
        )

    if device_type == "openbk":
        info = _get_openbk_status(ip_address)
    elif device_type == "tasmota":
        info = _get_tasmota_status(ip_address)
    else:
        return json.dumps(
            _error(
                f"Unknown device type: {device_type}",
                code="UNSUPPORTED_TYPE",
            ),
            indent=2,
        )

    if "error" in info:
        return json.dumps(
            _error(info["error"], code="INTERNAL_ERROR"),
            indent=2,
        )

    return json.dumps(
        _success(
            {
                "resolved_from": identifier,
                "ip_address": ip_address,
                "device_type": device_type,
                "info": info,
            }
        ),
        indent=2,
        ensure_ascii=False,
    )


def _get_device_power(identifier: str, channel: int = 1) -> str:
    """Get power state of a specific channel on an IoT device.

    Args:
        identifier: IP address or device name.
        channel: Channel number (1-based, default 1).

    Returns:
        JSON string with power state.
    """
    from tools.iot_discovery import (
        _detect_device_type,
        _get_cached_devices,
        _resolve_ip,
    )

    ip_address = _resolve_ip(identifier)

    if not ip_address:
        sorted(set(d.get("name", "Unknown") for d in _get_cached_devices() if d.get("name")))
        return json.dumps(
            _error(
                f"Could not resolve '{identifier}' to an IP address",
                code="NAME_NOT_RESOLVED",
                suggestion="Run iot_discover_devices() first, then use iot_list_devices()",
            ),
            indent=2,
        )

    device_type = _detect_device_type(ip_address)

    if device_type == "tasmota":
        try:
            resp = requests.get(f"http://{ip_address}/cm?cmnd=Power", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                power_key = f"POWER{channel}"
                state = data.get(power_key) or data.get("POWER")
                return json.dumps(
                    _success(
                        {
                            "device_type": "tasmota",
                            "resolved_from": identifier,
                            "ip": ip_address,
                            "channel": channel,
                            "state": state,
                        }
                    ),
                    indent=2,
                )
        except Exception as exc:
            return json.dumps(
                _error(str(exc), code="INTERNAL_ERROR"),
                indent=2,
            )

    elif device_type == "openbk":
        info = _get_openbk_status(ip_address)
        channels = info.get("channels", [])
        channel_info = next((c for c in channels if c["channel"] == channel - 1), None)
        return json.dumps(
            _success(
                {
                    "device_type": "openbk",
                    "resolved_from": identifier,
                    "ip": ip_address,
                    "channel": channel,
                    "state": ("ON" if channel_info and channel_info["value"] > 0 else "OFF"),
                    "value": channel_info["value"] if channel_info else 0,
                }
            ),
            indent=2,
        )

    return json.dumps(
        _error("Device not found or unsupported", code="UNSUPPORTED_TYPE"),
        indent=2,
    )


def register_iot_device_tools(mcp) -> None:
    """Register IoT device information tools with the MCP server."""

    @mcp.tool()
    def iot_get_device_info(identifier: str) -> str:
        """[READ] Get detailed information about an IoT device.

        Accepts either an IP address or a device name from the discovery cache.

        Args:
            identifier: IP address (e.g. "192.168.0.241") or device name.

        Returns:
            JSON with device information.
        """
        return _get_device_info(identifier)

    @mcp.tool()
    def iot_get_device_power(identifier: str, channel: int = 1) -> str:
        """[READ] Get power state of a specific channel on an IoT device.

        Accepts either an IP address or a device name from the discovery cache.

        Args:
            identifier: IP address or device name.
            channel: Channel number (1-based, default 1).

        Returns:
            JSON with power state.
        """
        return _get_device_power(identifier, channel)

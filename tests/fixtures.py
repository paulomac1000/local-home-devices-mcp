"""
Mock data constants for Local Home Devices MCP tests.

All mock devices use generic names (Tasmota_Test, OpenBK_Test).
No real device names, IPs, or credentials.
"""

MOCK_TASMOTA_DEVICE = {
    "ip": "192.168.1.100",
    "type": "tasmota",
    "name": "Tasmota_Test",
    "mac": "AA:BB:CC:DD:EE:FF",
}

MOCK_OPENBK_DEVICE = {
    "ip": "192.168.1.101",
    "type": "openbk",
    "name": "OpenBK_Test",
}

MOCK_DEVICE_STATUS_RESPONSE = {
    "Status": {
        "DeviceName": "Tasmota_Test",
        "FriendlyName": ["Test_Light"],
        "POWER": "ON",
        "Wifi": {"RSSI": 85, "Signal": -45},
    }
}

MOCK_POWER_RESPONSE = {"POWER": "ON"}

MOCK_BRIGHTNESS_RESPONSE = {"POWER": "ON", "Dimmer": 75}

MOCK_DISCOVERED_DEVICES = [
    {
        "ip": "192.168.1.100",
        "type": "tasmota",
        "name": "Tasmota_Test",
        "mac": "AA:BB:CC:DD:EE:FF",
        "channels": 4,
    },
    {
        "ip": "192.168.1.101",
        "type": "openbk",
        "name": "OpenBK_Test",
        "channels": 2,
    },
]

MOCK_CACHE_DATA = {
    "discovery_time": 1700000000,
    "network_range": "192.168.1.0/24",
    "devices": MOCK_DISCOVERED_DEVICES,
}

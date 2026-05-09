import os

MQTT_BROKER = os.getenv("MQTT_BROKER", "192.168.0.101")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
START_IP = os.getenv("START_IP", "192.168.0.1")
END_IP = os.getenv("END_IP", "192.168.0.254")
NETWORK_RANGE = os.getenv("NETWORK_RANGE")
MCP_SSE_PORT = int(os.getenv("MCP_SSE_PORT", "9101"))
REST_API_PORT = int(os.getenv("REST_API_PORT", "9102"))

HEALTH_CHECK_PORT = int(os.getenv("HEALTH_CHECK_PORT", "9100"))

BIND_HOST = os.getenv("BIND_HOST", "127.0.0.1")
ALLOW_PUBLIC_BIND = os.getenv("ALLOW_PUBLIC_BIND", "0") == "1"

# Build default network range for discovery (CIDR notation)
_DEFAULT_OCTETS = START_IP.rsplit(".", 1)[0]
DEFAULT_NETWORK_RANGE = NETWORK_RANGE or f"{_DEFAULT_OCTETS}.0/24"


def _success(data):
    """Build consistent success response dict. Caller wraps with json.dumps."""
    return {"success": True, "data": data}


def _error(message, code="INTERNAL_ERROR", retryable=False, suggestion=None):
    """Build consistent error response dict. Caller wraps with json.dumps."""
    err = {"code": code, "message": message, "retryable": retryable}
    if suggestion:
        err["suggestion"] = suggestion
    return {"success": False, "error": err}


TOOLS_VERSION = "1.2.0"

TOOL_MANIFESTS = {
    "iot_discover_devices": {"risk": "READ", "idempotent": True, "timeout_ms": 120000},
    "iot_list_devices": {"risk": "READ", "idempotent": True, "timeout_ms": 1000},
    "iot_check_device": {"risk": "READ", "idempotent": True, "timeout_ms": 10000},
    "iot_find_device_by_name": {"risk": "READ", "idempotent": True, "timeout_ms": 1000},
    "iot_get_device_info": {"risk": "READ", "idempotent": True, "timeout_ms": 10000},
    "iot_get_device_power": {"risk": "READ", "idempotent": True, "timeout_ms": 10000},
    "iot_set_power": {"risk": "WRITE", "idempotent": False, "timeout_ms": 10000},
    "iot_set_brightness": {"risk": "WRITE", "idempotent": False, "timeout_ms": 10000},
    "iot_restart_device": {"risk": "DANGEROUS", "idempotent": False, "timeout_ms": 10000},
    "iot_get_wifi_config": {"risk": "READ", "idempotent": True, "timeout_ms": 10000},
    "iot_mqtt_publish": {"risk": "WRITE", "idempotent": False, "timeout_ms": 5000},
    "iot_mqtt_get_state": {"risk": "READ", "idempotent": True, "timeout_ms": 10000},
    "iot_mqtt_build_command_topic": {"risk": "READ", "idempotent": True, "timeout_ms": 100},
}

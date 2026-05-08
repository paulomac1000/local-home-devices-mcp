import os

MQTT_BROKER = os.getenv("MQTT_BROKER", "192.168.0.101")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
START_IP = os.getenv("START_IP", "192.168.0.1")
END_IP = os.getenv("END_IP", "192.168.0.254")
NETWORK_RANGE = os.getenv("NETWORK_RANGE")
MCP_SSE_PORT = int(os.getenv("MCP_SSE_PORT", "9101"))
REST_API_PORT = int(os.getenv("REST_API_PORT", "9102"))

# Build default network range for discovery (CIDR notation)
_DEFAULT_OCTETS = START_IP.rsplit(".", 1)[0]
DEFAULT_NETWORK_RANGE = NETWORK_RANGE or f"{_DEFAULT_OCTETS}.0/24"

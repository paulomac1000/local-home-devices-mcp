# Tasmota-OpenBK-MCP

[![CI](https://github.com/paulomac1000/tasmota-openbk-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/paulomac1000/tasmota-openbk-mcp/actions/workflows/ci.yml)
[![Docker](https://github.com/paulomac1000/tasmota-openbk-mcp/actions/workflows/publish.yml/badge.svg)](https://github.com/paulomac1000/tasmota-openbk-mcp/actions/workflows/publish.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

MCP (Model Context Protocol) server for IoT device management. Enables AI assistants (Claude Desktop, LibreChat, Cline) to discover and control OpenBK (OpenBeken) and Tasmota devices on your local network.

## What is MCP?

MCP (Model Context Protocol) is a standardized protocol that allows AI assistants to call external tools through a defined interface. Think of it as a bridge between AI models and your local network:

- **AI Assistant** → sends request → **MCP Server** → queries devices
- **AI Assistant** ← receives response ← **MCP Server** ← returns device data

This project exposes your IoT devices as MCP tools, so you can control them using natural language through any MCP-compatible client.

## Requirements

- Docker (recommended) or Python 3.11+ (for local use)
- MQTT broker (optional - required only for MQTT tools)
- OpenBK or Tasmota devices on the same local network
- **nmap** - installed automatically in Docker; for local use, install via `apt-get install nmap` (may require root/sudo)

**Note on networking:** Docker uses `--network host` mode to access the local network where your IoT devices are located. This is required for nmap scanning and direct HTTP communication with devices.

## Quick Start

### 1. Configure

```bash
cp .env.example .env
# Edit .env with your MQTT_BROKER and network range
```

### 2. Run with Docker

**Option A -- Pre-built image from GitHub Container Registry:**

```bash
docker run -d \
  --name tasmota-openbk-mcp \
  --network host \
  -e MQTT_BROKER=192.168.0.101 \
  -e START_IP=192.168.0.1 \
  -e END_IP=192.168.0.254 \
  -v tasmota-data:/app/data \
  ghcr.io/paulomac1000/tasmota-openbk-mcp:latest
```

**Option B -- with docker compose:**

```bash
cp .env.example .env
# edit .env with your settings
docker compose up -d
```

**Option C -- Build locally:**

```bash
docker build -t tasmota-openbk-mcp .
docker run -d \
  --network host \
  -e MQTT_BROKER=192.168.0.101 \
  -e START_IP=192.168.0.1 \
  -e END_IP=192.168.0.254 \
  -v tasmota-data:/app/data \
  tasmota-openbk-mcp
```

### 3. Run locally (Python 3.11+)

```bash
pip install -r requirements.txt
MQTT_BROKER=192.168.0.101 START_IP=192.168.0.1 END_IP=192.168.0.254 python server.py
```

## Architecture

| Port | Protocol | Purpose | Endpoint |
|------|----------|---------|----------|
| 9100 | HTTP | Health check | `GET /health` |
| 9101 | SSE | MCP transport | `/sse`, `/messages` |
| 9102 | HTTP | REST API | `/api/*` |

### Verify

```bash
# Health check
curl http://localhost:9100/health

# List all MCP tools
curl http://localhost:9102/api/tools

# Call a tool via REST API
curl -X POST http://localhost:9102/api/tools/iot_list_devices \
  -H "Content-Type: application/json" \
  -d '{}'
```

## Available Tools

### Device Discovery

All read-only operations — no device state is modified.

| Tool | Risk | Description |
|------|------|-------------|
| `iot_discover_devices` | [READ] | Scan local network for OpenBK and Tasmota devices |
| `iot_list_devices` | [READ] | List all previously discovered devices from cache |
| `iot_check_device` | [READ] | Quick connectivity and status check for a specific IP |
| `iot_find_device_by_name` | [READ] | Find a device by its friendly name |

### Device Information

All read-only operations — no device state is modified.

| Tool | Risk | Description |
|------|------|-------------|
| `iot_get_device_info` | [READ] | Full device information (name, firmware, chip type, etc.) |
| `iot_get_device_power` | [READ] | Current power state of a specific channel |
| `iot_get_wifi_config` | [READ] | WiFi SSID, RSSI signal strength, MAC, IP address |

### Device Control

| Tool | Risk | Description |
|------|------|-------------|
| `iot_set_power` | [WRITE] | Turn a channel ON, OFF, or TOGGLE |
| `iot_set_brightness` | [WRITE] | Set brightness level (0-100%) |
| `iot_restart_device` | [DESTRUCTIVE] | Restart the device (temporarily disconnects) |

### Introspection

| Tool | Risk | Description |
|------|------|-------------|
| `describe_iot_capabilities` | [READ] | Describe all IoT tools, manifests, and transports |

### MQTT Integration

| Tool | Risk | Description |
|------|------|-------------|
| `iot_mqtt_publish` | [WRITE] | Publish a command via MQTT |
| `iot_mqtt_get_state` | [READ] | Get device state from MQTT broker |
| `iot_mqtt_build_command_topic` | [READ] | Build MQTT command topic for a device |

## Configuration

All configuration is via environment variables. See `.env.example` for a complete template.

### Required for MQTT tools (optional otherwise)

| Variable | Description | Example |
|----------|-------------|---------|
| `MQTT_BROKER` | MQTT broker IP address | `192.168.0.101` |

> **Tip:** Without MQTT broker, device discovery and HTTP control still work. Set `MQTT_BROKER` only if you need MQTT-based tools (`iot_mqtt_publish`, `iot_mqtt_get_state`, etc.).

### Network Scanning

| Variable | Default | Description |
|----------|---------|-------------|
| `START_IP` | `192.168.0.1` | First IP in the scan range |
| `END_IP` | `192.168.0.254` | Last IP in the scan range |
| `NETWORK_RANGE` | `192.168.0.0/24` | CIDR range for nmap scan (overrides START_IP/END_IP if set) |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_WRITE_OPERATIONS` | `0` | Set to `1` to enable write/destructive tools (set_power, restart, etc.) |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `MQTT_USER` | -- | MQTT username |
| `MQTT_PASSWORD` | -- | MQTT password |
| `MCP_SSE_PORT` | `9101` | MCP SSE transport port |
| `REST_API_PORT` | `9102` | REST API port |

## Project Structure

- `tools/constants.py` — All shared configuration defaults (no hardcoded IPs in tool files)
- `tools/iot_control.py` — Power/brightness/restart/WiFi control (4 tools)
- `tools/iot_devices.py` — Device info/power state (2 tools)
- `tools/iot_discovery.py` — Network scanning/device discovery/cache (4 tools)
- `tools/iot_mqtt.py` — MQTT publish/state/topic (3 tools)
- `tools/iot_meta.py` — Capability introspection, manifests and transports (1 tool)

## Supported Devices

### OpenBK (OpenBeken)

- **Chips**: BK7231N, BK7231T, XR809, BL602
- **Devices**: Lights, switches, curtains, sensors
- **Detection**: HTTP `GET /index` returns HTML containing `"openbeken"`

### Tasmota

- **Chips**: ESP8266, ESP32
- **Devices**: Lights, switches, sensors, fans, plugs
- **Detection**: HTTP `GET /cm?cmnd=Status` returns JSON with `"Status"` key

## Testing

The project has a 4-tier test hierarchy (see `AGENTS.md` for details):

| Suite | Tests | Coverage | Command |
|-------|-------|----------|---------|
| Unit | 183 | **>80%** | `pytest tests/unit/ -v --tb=short` |
| Integration | 20 | **66%** | `pytest tests/integration/ -q` |
| Smoke | 17 | HTTP validation | `pytest tests/smoke/ -q` |
| E2E | 6 | HTTP validation | `pytest tests/e2e/ -q` |

Unit tests run in CI. Integration, smoke, and e2e tests skip when their dependencies (MQTT broker, running server) are absent.

The server follows the `mcp_standards.md` conventions at L2/L3 maturity level. All tools return structured JSON with a `success` field, use extended error codes (`TIMEOUT`, `NAME_NOT_RESOLVED`, `DEVICE_NOT_FOUND`, `INTERNAL_ERROR`), and expose capability manifests via `/api/tools/{name}/manifest`.

## Claude Desktop Configuration

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "tasmota-openbk": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://localhost:9101/sse"]
    }
  }
}
```

## License

MIT -- see [LICENSE](LICENSE) for details.

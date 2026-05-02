# Tasmota-OpenBK-MCP Documentation

> MCP (Model Context Protocol) server for IoT device management.
> Supports OpenBK (OpenBeken) and Tasmota devices.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Quick Start](#quick-start)
4. [Configuration](#configuration)
5. [MCP Tools](#mcp-tools)
6. [REST API](#rest-api)
7. [Supported Devices](#supported-devices)
8. [Testing](#testing)
9. [Development](#development)
10. [Troubleshooting](#troubleshooting)

---

## Overview

Tasmota-OpenBK-MCP is a Model Context Protocol server that discovers and controls IoT devices on your local network. It supports two popular open-source firmware platforms:

- **OpenBK (OpenBeken)** — For BK7231N/T, XR809, BL602 chips
- **Tasmota** — For ESP8266, ESP32 chips

**Key features:**
- **Automatic device discovery** — Network scan finds all compatible devices
- **HTTP + MQTT control** — Direct HTTP API or MQTT broker integration
- **Read-only by default** — Status and info tools; control tools explicitly named
- **Standalone** — Single Python process, no external databases

---

## Architecture

```
┌─────────────────┐      ┌──────────────────────┐      ┌─────────────────┐
│  MCP Client     │      │  Tasmota-OpenBK-MCP  │      │  IoT Devices    │
│  (LibreChat,    │◄────►│  Port 9100-9102      │◄────►│  (HTTP/MQTT)    │
│   Claude, etc.) │ MCP   │  - Health (9100)     │      │  OpenBK/Tasmota │
│                 │ SSE   │  - MCP SSE (9101)    │      │                 │
│                 │       │  - REST API (9102)   │      │  MQTT Broker    │
└─────────────────┘       └──────────────────────┘      └─────────────────┘
```

| Port | Protocol | Purpose |
|------|----------|---------|
| 9100 | HTTP | Health check (`GET /health`) |
| 9101 | SSE | MCP transport (`/sse`, `/messages`) |
| 9102 | HTTP | REST API (`/api/*`) |

---

## Quick Start

### Prerequisites

- Docker and Docker Compose
- MQTT broker (e.g., Mosquitto) accessible on your network
- OpenBK or Tasmota devices on the same local network

### 1. Configure

```bash
cp .env.example .env
# Edit .env with your MQTT_BROKER and network range (START_IP, END_IP)
```

### 2. Start

```bash
# Option A: Pre-built image from GitHub Container Registry
docker compose up -d

# Option B: Build locally
docker build -t tasmota-openbk-mcp .
docker run -d --network host \
  -e MQTT_BROKER=192.168.0.101 \
  -e START_IP=192.168.0.1 \
  -e END_IP=192.168.0.254 \
  -v tasmota-data:/app/data \
  tasmota-openbk-mcp
```

### 3. Verify

```bash
# Health check
curl http://localhost:9100/health

# List MCP tools
curl http://localhost:9102/api/tools
```

---

## Configuration

All configuration via environment variables. See `.env.example` for a complete template.

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `MQTT_BROKER` | MQTT broker IP address | `192.168.0.101` |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `START_IP` | `192.168.0.1` | First IP in the nmap scan range |
| `END_IP` | `192.168.0.254` | Last IP in the nmap scan range |
| `NETWORK_RANGE` | `192.168.0.0/24` | CIDR range for scanning (overrides START_IP/END_IP if set) |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `MQTT_USER` | — | MQTT username (if authentication enabled) |
| `MQTT_PASSWORD` | — | MQTT password (if authentication enabled) |
| `MCP_SSE_PORT` | `9101` | MCP SSE transport port |
| `REST_API_PORT` | `9102` | REST API port |
| `IOT_SCAN_ENABLED` | `1` | Enable automatic device discovery on startup |
| `IOT_DATA_PATH` | `/app/data` | Persistent directory for device cache |

---

## MCP Tools

### Discovery

| Tool | Description |
|------|-------------|
| `iot_discover_devices` | Scan local network for OpenBK and Tasmota devices |
| `iot_check_device` | Quick connectivity and status check for a single device |

### Device Information

| Tool | Description |
|------|-------------|
| `iot_get_device_info` | Full device information (name, firmware version, chip type, etc.) |
| `iot_get_device_power` | Current power state of a specific channel |
| `iot_get_wifi_config` | WiFi SSID, RSSI signal strength, MAC, IP address |

### Device Control

| Tool | Description |
|------|-------------|
| `iot_set_power` | Turn a channel ON, OFF, or TOGGLE |
| `iot_set_brightness` | Set brightness level (0-100%) |
| `iot_restart_device` | Restart the device |

### MQTT Integration

| Tool | Description |
|------|-------------|
| `iot_mqtt_publish` | Publish a command to a device via MQTT |
| `iot_mqtt_get_state` | Get device state from MQTT broker |
| `iot_mqtt_build_command_topic` | Build the MQTT command topic for a device |

---

## REST API

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/tools` | List all registered tools |
| POST | `/api/tools/{name}` | Call a tool by name |

### Example: Discover Devices

```bash
curl -X POST http://localhost:9102/api/tools/iot_discover_devices \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

## Supported Devices

### OpenBK (OpenBeken)

| Chip | Devices |
|------|---------|
| BK7231N | Lights, switches, curtains |
| BK7231T | Lights, switches, sensors |
| XR809 | Switches, sensors |
| BL602 | Lights, switches |

**Detection**: HTTP `GET http://{ip}/index` returns HTML containing `"openbeken"`

**API**: `http://{ip}/index` with query parameters for status and control

### Tasmota

| Chip | Devices |
|------|---------|
| ESP8266 | Lights, switches, sensors, plugs |
| ESP32 | Lights, switches, sensors, fans |

**Detection**: HTTP `GET http://{ip}/cm?cmnd=Status` returns JSON with `"Status"` key

**API**: `http://{ip}/cm?cmnd={command}` for control

---

## Testing

### Unit Tests

No real devices required — all HTTP and MQTT calls are mocked.

```bash
pytest tests/unit/ -v --tb=short
```

### Integration Tests

Requires real devices on the local network:

```bash
export MQTT_BROKER=192.168.0.101
pytest tests/integration/ -v
```

---

## Development

### Project Structure

```
.
├── server.py              # Main server (MCP + REST API)
├── requirements.txt       # Dependencies
├── Dockerfile             # Container image
├── docker-compose.yml     # Quick start
├── .env.example           # Configuration template
├── tools/
│   ├── iot_discovery.py   # Network scanning and detection
│   ├── iot_devices.py     # Device info and status
│   ├── iot_control.py     # Device control (power, brightness)
│   ├── iot_mqtt.py        # MQTT integration
│   └── __init__.py
├── tests/
│   ├── unit/              # Unit tests
│   ├── integration/       # Integration tests
│   └── __init__.py
└── docs/
    └── README.md          # This documentation
```

### Adding Device Support

1. Add detection logic in `tools/iot_discovery.py`
2. Add info/control methods in `tools/iot_devices.py` / `tools/iot_control.py`
3. Register tools in `server.py`
4. Add tests in `tests/unit/`

---

## Troubleshooting

### Devices not discovered

1. Ensure devices are on the same network as the server
2. Check `IOT_SCAN_ENABLED=1` in `.env`
3. Verify devices respond to HTTP on port 80
4. Try manual check: `curl http://{device_ip}/cm?cmnd=Status`

### MQTT commands fail

1. Verify `MQTT_BROKER` IP is correct and reachable
2. Check MQTT port (default 1883) is not blocked
3. Ensure MQTT credentials are correct (if authentication enabled)
4. Verify device is configured with the same MQTT broker

### Control commands fail

1. Check device IP is correct and reachable
2. Verify device supports the command (e.g., brightness for dimmable lights)
3. Check device is not in safe mode or recovery mode
4. Review device logs via `iot_get_device_info`

---

## License

MIT License — see [LICENSE](../LICENSE) for details.

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

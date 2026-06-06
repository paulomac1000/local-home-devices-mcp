# Changelog

## [1.5.0] — 2026-06-06

### Added
- **Hikvision diagnostic tools** (7 new tools) — motion detection config (get/set), event trigger inspection, alarm server config, snapshot-to-file, composite ISAPI health check, cross-layer pipeline diagnosis
- `hikvision_get_motion_config` — fetch VMD motion detection configuration (enabled, sensitivity, grid map)
- `hikvision_set_motion_detection` — enable/disable VMD or adjust sensitivity via read-modify-write ISAPI (write-guarded)
- `hikvision_get_event_config` — list all ISAPI event triggers with notification details
- `hikvision_get_alarm_server` — fetch HTTP notification host (alarm server) configuration
- `hikvision_snapshot_to_file` — capture JPEG and save directly to specified file path (write-guarded)
- `hikvision_isapi_health` — composite health check aggregating container status, VMD events, and call events
- `hikvision_pipeline_diagnose` — full pipeline trace across container, ISAPI, events, MQTT triggers, and snapshot filesystem
- `HikvisionISAPIClient` extended with 5 new methods: `get_motion_config`, `set_motion_config`, `get_event_triggers`, `get_alarm_server`, `save_snapshot`
- `count_call_events()` Docker client function — counts doorbell ring events in container logs
- `CAMERA_GATE_SNAPSHOTS_DIR` constant for snapshot archive path (env-overridable)
- 33 new unit tests, 5 integration, 8 smoke, 3 E2E tests for Hikvision diagnostic tools

### Changed
- `hikvision_check_vmd` soft-deprecated — docstring updated to recommend `hikvision_isapi_health`
- `hikvision_snapshot_to_file` risk level corrected from READ to WRITE (writes to filesystem)
- `_hikvision_set_motion_detection` adds sensitivity bounds validation (0-100)
- `_hikvision_pipeline_diagnose` uses `CAMERA_GATE_SNAPSHOTS_DIR` constant instead of hardcoded path
- Test fixture IPs replaced with RFC 5737 documentation addresses (`192.0.2.1`)

All notable changes to this project.

## [1.4.0] — 2026-06-01

### Added
- **Tuya device support** (10 tools) — cloud API listing, local key retrieval, DPS read/write with local+cloud fallback, protocol version auto-detection, DPS verification against known specs, TCP port scanning, real-time DPS monitoring for diagnostics
- **OpenHASP panel support** (20 tools) — panel detection, full status (HTTP + Telnet), backlight diagnostics with recommendations, config/page download, file upload, OTA firmware update, Telnet control (raw TCP socket, NOT telnetlib), backlight set with idle override, runtime config via `config/gui`, health scoring (0-100), hardware diagnostic sequence
- **Hikvision DS-KV6113-WPE1(C) video doorbell support** (7 tools) — Docker container status and logs via Unix socket API, VMD event counting (ISAPI health canary), container restart, JPEG snapshot via ISAPI HTTP Digest Auth, electric gate control via XML RemoteControl, device metadata (model, firmware, serial)
- **Project renamed** from `tasmota-openbk-mcp` → `local-home-devices-mcp`
- **iot_tuya_monitor** — real-time DPS change monitoring for Tuya device diagnostics
- `describe_iot_capabilities` returns manifests for all 51 tools

### Changed
- `_detect_device_type()` extended with Tuya TCP probe (port 6668) and OpenHASP config.json probe
- `_probe_device_info()` auto-identifies Tuya devices by trying cached local keys
- `iot_get_device_info`, `iot_get_device_power`, `iot_set_power`, `iot_set_brightness`, `iot_restart_device`, `iot_get_wifi_config` dispatch to OpenHASP, Tuya, and Hikvision branches
- `iot_tuya_scan_ports` now scans full network range for Tuya devices
- Health endpoints expose `tool_count` alongside `tools`/`total`

### Fixed
- Server version bumped from 1.3.0 → 1.4.0
- Docker build installs `tinytuya` via optional `[tuya]` extras
- Tuya cloud API uses `dev.get("key")` not `dev.get("local_key")`
- Docker client uses Unix socket HTTP API (no Docker CLI dependency)
- All 51 tools have risk manifests and pass consistency matrix
- `tool_count` added to all health endpoints per MCP standard

### Documentation
- README, AGENTS.md, docs/README.md updated with Tuya, OpenHASP, and Hikvision sections
- `.env.example` updated with all new environment variables
- Tool counts updated across CI config (51 tools)

## [1.3.0] — 2026-05-17

### Added
- **Write Guard** — server-level authorization gate (`ENABLE_WRITE_OPERATIONS`) for write/destructive tools. All WRITE and DESTRUCTIVE tools return `WRITE_DISABLED` before any I/O unless explicitly enabled.
- **Manifest factories** — `_make_manifest()`, `_make_write_manifest()`, `_make_destructive_manifest()` enforce Risk Consistency Matrix compliance at construction time. No ad-hoc manifest dicts.
- **`describe_iot_capabilities` tool** — zero-I/O [READ] introspection tool exposing full tool catalog with manifests over MCP transport (closes SSE agent gap).
- **Response payload sanitization** — `sanitize_response_data()` redacts credential patterns at the `_success_response()` boundary. No tool can leak tokens/passwords.
- **Enriched health endpoint** — `/health` returns `tools` count and `tools_version` alongside health status.
- **L3 manifest fields** — `impact`, `privacy`, `reversible` on all 14 manifests.
- **`[tool.bandit]` section** in `pyproject.toml`.
- **`mypy`** added to dev dependencies.
- 22 new unit tests — write guard disabled paths, `iot_meta` introspection, `sanitize_response_data`, manifest factories, Risk Consistency Matrix.

### Changed
- **`iot_restart_device`** risk reclassified from `DANGEROUS` to `DESTRUCTIVE` (fixed command set, not arbitrary shell execution).
- **WRITE tool manifests** corrected: `idempotent: true`, `retryable: true` (were `false`).
- **`request_id`** in `_build_meta()` now reads from tool context (`get_request_id()`) instead of generating a fresh UUID — enables log↔response correlation.
- **`iot_get_device_info`** and **`iot_get_wifi_config`** manifest `privacy` set to `"metadata"`.
- **Smoke test** tool count updated from 13 to 14.

### Fixed
- Smoke test `test_tools_list_returns_13_tools` → `test_tools_list_returns_14_tools` (connectivity test).
- `available_names` capped at 50 entries to prevent oversized error responses.

## [1.2.0] — 2026-05-08

### Added
- `tools/constants.py` — single source of truth for all configuration defaults; eliminates duplicated IP/port values across 3 files
- `tests/fixtures.py` — mock data constants (`MOCK_TASMOTA_DEVICE`, `MOCK_OPENBK_DEVICE`, etc.)
- `tests/conftest.py` — environment loading only (no fixtures)
- `tests/unit/conftest.py` — unit test fixtures (`mock_mcp`, `mock_requests`, `mock_mqtt_client`)
- `tests/smoke/` — REST API smoke test suite (3 connectivity + 14 critical tools tests)
- `tests/integration/` — real MQTT/device integration test suite (20 tests, MCPWrapper pattern)
- `tests/e2e/` — full pipeline E2E test suite (6 REST API endpoint tests)
- `AGENTS.md` — comprehensive agent instructions aligned with ha-mcp-readonly standards
- `CHANGELOG.md` — this file
- `tools/validators.py` — centralized input validation module (`ValidationError`, `validate_power_state`, `validate_brightness`, `validate_ip_format`, `validate_cidr`)
- Dynamic risk prefix injection — `inject_tool_risk_prefix()` decorator injects `[READ]`/`[WRITE]`/`[DANGEROUS]` from `TOOL_MANIFESTS` into all 13 tool docstrings
- Log sanitization — `sanitize_log_line()` and `SanitizingFormatter` redact Bearer tokens, passwords, and IP addresses from log output
- CI smoke-test Docker job — starts container, curls health/tools endpoints, stops container
- Dynamic skip pattern for smoke/e2e tests — socket-based server detection instead of hardcoded `True`
- 70 new unit tests across all modules — 130 total, 100% line coverage

### Changed
- `server.py` — imports configuration from `tools/constants.py`, removed hardcoded defaults
- `tools/iot_mqtt.py` — imports `MQTT_BROKER`, `MQTT_PORT` from `tools/constants.py`
- `tools/iot_discovery.py` — imports `START_IP`, `END_IP`, `NETWORK_RANGE` from `tools/constants.py`
- `Dockerfile` — removed `COPY conftest.py` and `COPY tests/` (production image only)
- `LICENSE` — fixed Polish character (`Paweł` → `Pawel`)
- `README.md` — updated testing section with 4-tier hierarchy
- `docs/README.md` — updated project structure and test documentation
- Smoke/e2e conftest — replaced `skipif(True, ...)` with dynamic socket connection check

### Removed
- Root `conftest.py` — fixtures moved to `tests/unit/conftest.py`; env loading moved to `tests/conftest.py`
- `brief.md` — development planning document, no longer needed

### Fixed
- Missing `HEALTH_CHECK_PORT` and `LOG_LEVEL` in `.env.example`
- Missing CIDR validation for `network_range` parameter before nmap scan
- Duplicated IP/port defaults across `server.py`, `iot_mqtt.py`, `iot_discovery.py`
- Production Docker image containing development-only test files
- 0% coverage on MCP tool registration wrappers and exception handlers (now 100%)
- Smoke/e2e tests permanently skipped due to `skipif(True, ...)` (now dynamic)
- `iot_get_wifi_config` RSSI null handling for certain Tasmota firmware versions

### Coverage
| Suite | Coverage | Tests |
|-------|----------|-------|
| Unit | 100% (523/523 stmts) | 130 |
| Integration | 66% (345/523 stmts) | 20 |
| Smoke | 0% (external process) | 17 |
| E2E | 0% (external process) | 6 |

## [1.0.0] — initial release
- 13 MCP tools across 4 categories
- Docker support
- README/docs

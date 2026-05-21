# Changelog

All notable changes to this project.

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

# ToDo: Hikvision MCP Tools — 7 new diagnostic/config tools

**Created**: 2026-06-05
**Session context**: Diagnosing Hikvision DS-KV6113 doorbell revealed that debugging required 11+ raw `curl` commands to ISAPI endpoints. This todo adds typed MCP tools covering motion detection, event inspection, alarm server, and composite diagnostics.

**Where**: `/home/pablo/tasmota-openbk-mcp/`
**Branch**: create `feature/hikvision-diagnostic-tools`

---

## 1. WHY — Real-world problems each tool group solves

| Problem | Discovery | Solution |
|---------|-----------|----------|
| VMD motion detection was DISABLED on the device. Took 3 separate curl commands and an XML parsing error to find `<enabled>false</enabled>`. | Manual ISAPI probing | `hikvision_get_motion_config` + `hikvision_set_motion_detection` |
| Checking if the doorbell is "alive" required checking VMD AND call events separately. ISAPI could be alive for calls but dead for VMD. | Manual dual-query | `hikvision_isapi_health` — composite health check |
| Tracing a broken detection pipeline required 15+ manual checks across container, ISAPI, MQTT, and filesystem layers. | Manual cross-layer tracing | `hikvision_pipeline_diagnose` — full pipeline in one call |
| Checking event trigger config needed raw ISAPI XML parsing. | Manual curl | `hikvision_get_event_config` |
| Verifying alarm server URL needed ISAPI probe. | Manual curl | `hikvision_get_alarm_server` |
| Saving snapshots to disk for HA/NVR required post-processing the base64 response. | Manual decode-save step | `hikvision_snapshot_to_file` |

---

## 2. IMPLEMENTATION

### File: `tools/hikvision/isapi_client.py`

**Add 5 new methods** to `HikvisionISAPIClient` class.

#### 2a. `get_motion_config()`

```python
def get_motion_config(self) -> dict | None:
```

| Field | Value |
|-------|-------|
| ISAPI endpoint | `GET /ISAPI/System/Video/inputs/channels/1/MotionDetection` |
| Response XML shape | `<MotionDetection><enabled>true/false</enabled><MotionDetectionLayout><sensitivityLevel>int</sensitivityLevel><layout><gridMap>hex_string</gridMap></layout></MotionDetectionLayout></MotionDetection>` |
| XML parsing | `_xml_to_dict()` is flat-only (first-level children). For nested `sensitivityLevel` under `MotionDetectionLayout`, either add a `_xml_to_dict_nested()` helper or manually traverse `root.findall()`. **Recommended**: manual `find()` + `.text` for the 3 fields. |
| Returns | `{"enabled": bool, "sensitivity": int, "grid_map": str}` or `None` on failure |
| Error handling | `try/except Exception` returning `None` (same pattern as `get_device_info()`) |

**Implementation steps:**
1. Build URL: `f"{self.base_url}/ISAPI/System/Video/inputs/channels/1/MotionDetection"`
2. GET with `session.get(url, auth=self.auth, timeout=self.timeout)`
3. `resp.raise_for_status()`
4. Parse with `SafeET.fromstring(resp.text)`
5. Extract: `enabled_text = root.findtext(f"{{{ISAPI_NS}}}enabled", default="false")` → convert to bool
6. Extract sensitivity: `root.find(f".//{{{ISAPI_NS}}}sensitivityLevel")` → `.text` → int
7. Extract grid_map: `root.find(f".//{{{ISAPI_NS}}}gridMap")` → `.text`
8. Return dict or None

**Test (in `test_iot_hikvision.py` → `TestHikvisionISAPIClient`):**
- Mock `session.get` returning XML with `<enabled>true</enabled>`, `<sensitivityLevel>70</sensitivityLevel>`, `<gridMap>0F.../gridMap>`
- Assert `client.get_motion_config()["enabled"] is True`
- Assert `client.get_motion_config()["sensitivity"] == 70`

---

#### 2b. `set_motion_config()`

```python
def set_motion_config(self, enabled: bool | None = None, sensitivity: int | None = None) -> bool:
```

| Field | Value |
|-------|-------|
| ISAPI endpoint | `PUT /ISAPI/System/Video/inputs/channels/1/MotionDetection` |
| **CRITICAL** | The doorbell REQUIRES complete XML on PUT. Missing any field → `badParameters` error. Algorithm: 1) GET current config, 2) parse ALL fields, 3) modify only `enabled`/`sensitivityLevel`, 4) reconstruct complete XML, 5) PUT |
| Content-Type | `application/xml` |
| Returns | `True` on success, `False` on failure |

**Reconstruction — every field that must be preserved:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<MotionDetection xmlns="http://www.isapi.org/ver20/XMLSchema">
  <enabled>true</enabled>
  <regionType>grid</regionType>
  <Grid>
    <rowGranularity>18x18</rowGranularity>
    <columnGranularity>22x22</columnGranularity>
  </Grid>
  <MotionDetectionLayout>
    <sensitivityLevel>70</sensitivityLevel>
    <layout>
      <gridMap>0F0F0F0F0F...</gridMap>
    </layout>
  </MotionDetectionLayout>
</MotionDetection>
```

**Implementation steps:**
1. Call `self.get_motion_config()` first to get current values
2. If `get_motion_config()` returns `None`, construct sensible defaults (enabled=true, sensitivity=70, gridMap from a permissive default)
3. Create `ET.Element("MotionDetection")` with `xmlns` attribute `{http://www.isiapi.org/ver20/XMLSchema}`
4. Add `enabled` sub-element
5. Add `regionType` sub-element (reuse current value or default `"grid"`)
6. Add `Grid` sub-element with `rowGranularity`, `columnGranularity`
7. Add `MotionDetectionLayout` sub-element with `sensitivityLevel` and `layout/gridMap`
8. Serialize with `ET.tostring(root, encoding="unicode", xml_declaration=True)`
9. PUT with `headers={"Content-Type": "application/xml"}`
10. `resp.raise_for_status()`, return `True`

**Test (in `test_iot_hikvision.py` → `TestHikvisionISAPIClient`):**
- Mock `get_motion_config` to return a known config
- Mock `session.put` to return 200
- Assert `client.set_motion_config(enabled=False)` returns `True`
- Assert PUT body contains `<enabled>false</enabled>` and all original fields preserved
- Test partial update (only sensitivity=None — should modify enabled, keep sensitivity)
- Test ISAPI failure returns `False`

---

#### 2c. `get_event_triggers()`

```python
def get_event_triggers(self) -> list[dict] | None:
```

| Field | Value |
|-------|-------|
| ISAPI endpoint | `GET /ISAPI/Event/triggers` |
| Response XML shape | `<EventTriggerList><EventTrigger><id>vmd-1</id><eventType>VMD</eventType><EventTriggerNotificationList><EventTriggerNotification><id>center</id><notificationMethod>center</notificationMethod></EventTriggerNotification></EventTriggerNotificationList></EventTrigger></EventTriggerList>` |
| Returns | `[{"id": "vmd-1", "event_type": "VMD", "notifications": [{"id": "center", "method": "center"}]}]` or `None` |

**Implementation steps:**
1. GET `f"{self.base_url}/ISAPI/Event/triggers"`
2. Parse with `SafeET.fromstring()`
3. Find all `EventTrigger` elements with `root.findall(f".//{{{ISAPI_NS}}}EventTrigger")`
4. For each: extract `id`, `eventType` text values
5. Find `EventTriggerNotificationList` → extract each notification's `id` and `notificationMethod`
6. Return list of dicts

**Test:**
- Mock XML response with 2 triggers (VMD + videoloss)
- Assert `len(result) == 2`
- Assert `result[0]["event_type"] == "VMD"`

---

#### 2d. `get_alarm_server()`

```python
def get_alarm_server(self) -> dict | None:
```

| Field | Value |
|-------|-------|
| ISAPI endpoint | `GET /ISAPI/Event/notification/httpHosts` |
| Response XML shape | `<HttpHostNotificationList><HttpHostNotification><id>1</id><url>/api/hikvision</url><protocolType>HTTP</protocolType><ipAddress>192.168.0.101</ipAddress><portNo>8123</portNo></HttpHostNotification></HttpHostNotificationList>` |
| Returns | `{"id": "1", "url": "/api/hikvision", "protocol": "HTTP", "ip": "192.168.0.101", "port": "8123"}` or `None` |

**Implementation steps:**
1. GET `f"{self.base_url}/ISAPI/Event/notification/httpHosts"`
2. Parse with `SafeET.fromstring()`
3. Find first `HttpHostNotification` element
4. Extract fields using `findtext()` with namespace
5. Return flat dict

**Test:**
- Mock XML with alarm server config
- Assert `result["url"] == "/api/hikvision"`
- Assert `result["ip"] == "192.168.0.101"`

---

#### 2e. `save_snapshot()`

```python
def save_snapshot(self, filepath: str) -> dict:
```

| Field | Value |
|-------|-------|
| ISAPI endpoint | `GET /ISAPI/Streaming/channels/101/picture` (same as `get_snapshot`) |
| Returns | `{"filepath": str, "size_bytes": int}` |
| Side-effect | Writes JPEG bytes to `filepath` on disk |

**Implementation steps:**
1. Call `self.get_snapshot(channel=1)` — reuse existing method
2. If `None`, raise or return error
3. Use `pathlib.Path(filepath).write_bytes(img_bytes)` to write
4. Return `{"filepath": str(filepath), "size_bytes": len(img_bytes)}`

**Note**: `get_snapshot(channel=1)` uses URL `/ISAPI/Streaming/channels/101/picture` — the `channel` param maps to `{channel}01`. Channel 1 → 101.

---

### File: `tools/hikvision/docker_client.py`

**Add 1 new function** — `count_call_events()`.

#### 2f. `count_call_events()`

```python
def count_call_events(since: str = "4h") -> dict[str, Any]:
```

**Pattern**: Identical to `count_vmd_events()` (lines 187-205 of `docker_client.py`) — copy that function and change:
- Function name: `count_call_events`
- Log pattern to search: `"Doorbell ringing"` (instead of `"Motion detected from Gate"`)
- Return key: `"call_count"` (instead of `"vmd_count"`)
- Health key: `"has_calls"` (instead of `"isapi_healthy"`)

```python
def count_call_events(since: str = "4h") -> dict[str, Any]:
    """Count call events in container logs.

    Call events appear as: 'Doorbell ringing'
    Zero events indicates the doorbell button may not be working.

    Args:
        since: Time window (default "4h").

    Returns:
        Dict with: call_count (int), has_calls (bool), check_window (str).
    """
    logs = get_container_logs(since=since, tail=200)
    call_count = logs.count("Doorbell ringing")
    return {
        "call_count": call_count,
        "has_calls": call_count > 0,
        "check_window": since,
    }
```

**Test (in `test_iot_hikvision.py` → `TestHikvisionDockerClient`):**
- Test `count_call_events` with 3 "Doorbell ringing" entries → assert `call_count == 3`, `has_calls is True`
- Test with zero matching lines → assert `call_count == 0`, `has_calls is False`

---

### File: `tools/iot_hikvision.py`

**Add 7 new `_hikvision_*` wrapper functions, update `__all__`, and add 7 new `@mcp.tool()` registrations inside `register_hikvision_tools()`**.

#### New imports
Add to existing imports:
```python
from tools.hikvision.docker_client import count_call_events  # new
from tools.validators import validate_required_string  # new (for snapshot_to_file)
import os  # new (for pipeline_diagnose)
from pathlib import Path  # new (for save_snapshot wrapper)
```

#### 2g. `_hikvision_get_motion_config()`

```python
def _hikvision_get_motion_config() -> str:
    """Fetch VMD motion detection configuration from the doorbell."""
    try:
        client = create_isapi_client()
        config = client.get_motion_config()
        if config:
            return _success_response(config)
        return _error_response_extended(
            code="ISAPI_ERROR",
            message="Failed to fetch motion detection config.",
        )
    except ValueError as exc:
        return _error_response_extended(code="MISSING_CREDENTIALS", message=str(exc))
    except Exception as exc:
        return _error_response_extended(code="INTERNAL_ERROR", message=str(exc))
```

#### 2h. `_hikvision_set_motion_detection()`

```python
def _hikvision_set_motion_detection(enabled: bool | None = None, sensitivity: int | None = None) -> str:
    """Enable/disable VMD motion detection or adjust sensitivity."""
    # Note: Only one of enabled/sensitivity must be provided? Both are optional.
    # If both are None, return error saying at least one is required.
    try:
        client = create_isapi_client()
        success = client.set_motion_config(enabled=enabled, sensitivity=sensitivity)
        if success:
            return _success_response({
                "enabled": enabled,
                "sensitivity": sensitivity,
                "message": "Motion detection config updated",
            })
        return _error_response_extended(
            code="ISAPI_ERROR",
            message="Failed to update motion detection config. Check ISAPI connectivity.",
        )
    except ValueError as exc:
        return _error_response_extended(code="MISSING_CREDENTIALS", message=str(exc))
    except Exception as exc:
        return _error_response_extended(code="INTERNAL_ERROR", message=str(exc))
```

**Write guard**: Inside the `@mcp.tool()` registration, call `check_write_enabled()` before `_hikvision_set_motion_detection()`.

#### 2i. `_hikvision_get_event_config()`

```python
def _hikvision_get_event_config() -> str:
    """Fetch event trigger configuration from the doorbell."""
    try:
        client = create_isapi_client()
        triggers = client.get_event_triggers()
        if triggers is not None:
            return _success_response({"triggers": triggers, "count": len(triggers)})
        return _error_response_extended(
            code="ISAPI_ERROR",
            message="Failed to fetch event triggers.",
        )
    except ValueError as exc:
        return _error_response_extended(code="MISSING_CREDENTIALS", message=str(exc))
    except Exception as exc:
        return _error_response_extended(code="INTERNAL_ERROR", message=str(exc))
```

#### 2j. `_hikvision_get_alarm_server()`

```python
def _hikvision_get_alarm_server() -> str:
    """Fetch alarm server (HTTP notification host) configuration."""
    try:
        client = create_isapi_client()
        server = client.get_alarm_server()
        if server:
            return _success_response({"alarm_server": server})
        return _error_response_extended(
            code="ISAPI_ERROR",
            message="Failed to fetch alarm server config.",
        )
    except ValueError as exc:
        return _error_response_extended(code="MISSING_CREDENTIALS", message=str(exc))
    except Exception as exc:
        return _error_response_extended(code="INTERNAL_ERROR", message=str(exc))
```

#### 2k. `_hikvision_snapshot_to_file()`

```python
def _hikvision_snapshot_to_file(filepath: str) -> str:
    """Capture a JPEG snapshot and save it directly to a file on disk."""
    try:
        validated_path = validate_required_string(filepath, "filepath")
        client = create_isapi_client()
        result = client.save_snapshot(filepath=validated_path)
        return _success_response(result)
    except ValidationError as exc:
        return _error_response_extended(code="VALIDATION_ERROR", message=str(exc))
    except ValueError as exc:
        return _error_response_extended(code="MISSING_CREDENTIALS", message=str(exc))
    except Exception as exc:
        return _error_response_extended(code="INTERNAL_ERROR", message=str(exc))
```

**Note**: `ValidationError` is already imported via `from tools.validators import ValidationError` at the top of the file.

#### 2l. `_hikvision_isapi_health()`

```python
def _hikvision_isapi_health(since: str = "4h") -> str:
    """Composite health check: container, ISAPI auth, VMD events, call events."""
    try:
        status = get_container_status()
        vmd = count_vmd_events(since=since)
        calls = count_call_events(since=since)

        # Determine overall health
        container_ok = status.get("running", False)
        vmd_ok = vmd.get("vmd_count", 0) > 0
        calls_ok = calls.get("call_count", 0) > 0
        auth_ok = "Connected to doorbell" in _get_recent_log_auth()  # see note

        if container_ok and (vmd_ok or calls_ok):
            overall = "healthy"
        elif container_ok and not vmd_ok and not calls_ok:
            # Container running, ISAPI connected but no events
            overall = "degraded"
        else:
            overall = "down"

        issues = []
        if not container_ok:
            issues.append(f"Container not running: {status.get('status', 'unknown')}")
        if not vmd_ok and calls_ok:
            issues.append("VMD event pipeline is dead (call events still flowing)")
        if not vmd_ok and not calls_ok:
            issues.append("No VMD or call events — ISAPI may be disconnected")

        return _success_response({
            "overall": overall,
            "since": since,
            "container": status,
            "vmd": vmd,
            "calls": calls,
            "issues": issues,
        })
    except ValueError as exc:
        return _error_response_extended(code="MISSING_CREDENTIALS", message=str(exc))
    except Exception as exc:
        return _error_response_extended(code="INTERNAL_ERROR", message=str(exc))
```

**Note on `_get_recent_log_auth()`**: For the auth check, you can either:
- Option A (simpler): Skip the auth log check — just use `container.running AND (vmd_count > 0 OR call_count > 0)` as the health signal. This avoids an extra log fetch.
- Option B (more accurate): Add a helper `_check_auth_in_logs()` that fetches `get_container_logs(since=since, tail=50)` and checks `"Connected to doorbell" in logs`.

**Recommendation**: Option A for simplicity. If the container is running and events are flowing, ISAPI auth must be working. The "degraded" state (container running but no VMD events) already catches ISAPI disconnection.

#### 2m. `_hikvision_pipeline_diagnose()`

```python
def _hikvision_pipeline_diagnose() -> str:
    """Trace the full camera detection pipeline across all layers."""
    try:
        # Layer 1: Container + ISAPI
        status = get_container_status()
        container_running = status.get("running", False)
        logs = get_container_logs(since="1h", tail=100)
        isapi_auth = "Connected to doorbell" in logs

        # Layer 2: Events
        vmd_count = logs.count("Motion detected from Gate")
        call_count = logs.count("Doorbell ringing")

        # Layer 3: MQTT trigger
        mqtt_triggers = logs.count("Invoking device trigger automation")

        # Layer 4: Snapshots on disk
        snapshots_dir = "/config/www/archive/camera_gate"
        # Note: /config/www/archive/camera_gate is a HA path. The container
        # volumes map it. If the MCP server runs outside HA, this path may
        # not exist — handle gracefully.
        snapshot_files = []
        has_snapshots = False
        try:
            if os.path.isdir(snapshots_dir):
                snapshot_files = sorted(os.listdir(snapshots_dir), reverse=True)[:5]
                has_snapshots = len(snapshot_files) > 0
        except OSError:
            pass

        # Build issues
        issues = []
        if not container_running:
            issues.append("Cannot start — docker container is not running")
        if not isapi_auth:
            issues.append("Layer 1: ISAPI not authenticated — doorbell may be unreachable or credentials wrong")
        if vmd_count == 0 and call_count == 0:
            issues.append("Layer 2: No events of any kind — ISAPI connection may be dead")
        elif vmd_count == 0 and call_count > 0:
            issues.append("Layer 2: VMD events stopped (call events still flowing — motion detection may be disabled)")
        if mqtt_triggers == 0:
            issues.append("Layer 3: No MQTT automation triggers — check hikvision-doorbell container MQTT config")
        if not has_snapshots:
            issues.append("Layer 4: No snapshots on disk — check camera_gate archive directory")

        overall = "healthy" if len(issues) == 0 else "degraded"

        return _success_response({
            "overall": overall,
            "layers": {
                "container": {
                    "running": container_running,
                    "status": status.get("status", "unknown"),
                },
                "isapi": {
                    "authenticated": isapi_auth,
                },
                "events": {
                    "vmd_count": vmd_count,
                    "call_count": call_count,
                },
                "mqtt": {
                    "triggers_published": mqtt_triggers,
                },
                "snapshots": {
                    "has_snapshots": has_snapshots,
                    "recent_files": snapshot_files,
                    "directory": snapshots_dir,
                },
            },
            "issues": issues,
        })
    except ValueError as exc:
        return _error_response_extended(code="MISSING_CREDENTIALS", message=str(exc))
    except Exception as exc:
        return _error_response_extended(code="INTERNAL_ERROR", message=str(exc))
```

#### Update `__all__`

Add these function names to the `__all__` list at the top of `tools/iot_hikvision.py`:

```python
__all__ = [
    "register_hikvision_tools",
    "_hikvision_container_status",
    "_hikvision_container_logs",
    "_hikvision_check_vmd",
    "_hikvision_restart_container",
    "_hikvision_take_snapshot",
    "_hikvision_open_gate",
    "_hikvision_device_info",
    # New tools:
    "_hikvision_get_motion_config",
    "_hikvision_set_motion_detection",
    "_hikvision_get_event_config",
    "_hikvision_get_alarm_server",
    "_hikvision_snapshot_to_file",
    "_hikvision_isapi_health",
    "_hikvision_pipeline_diagnose",
]
```

#### Inside `register_hikvision_tools()` — add 7 new registrations

For each new tool, follow the exact pattern from existing registrations (lines 139-334 of `iot_hikvision.py`):

```python
@mcp.tool()
@inject_tool_risk_prefix
def hikvision_get_motion_config() -> str:
    """Fetch VMD motion detection configuration from the doorbell.

    Reads the current MotionDetection XML from the ISAPI endpoint.
    Returns enabled/disabled status, sensitivity level (0-100),
    and grid map data.

    Use before hikvision_set_motion_detection to understand current state.

    Returns:
        JSON with enabled (bool), sensitivity (int), grid_map (str).

    @since v1.5.0
    """
    try:
        start_tool_context()
        increment_tool_count("hikvision_get_motion_config")
        return _hikvision_get_motion_config()
    except Exception as exc:
        return _error_response_extended(code="INTERNAL_ERROR", message=str(exc))


@mcp.tool()
@inject_tool_risk_prefix
def hikvision_set_motion_detection(enabled: bool | None = None, sensitivity: int | None = None) -> str:
    """Enable or disable VMD motion detection, or adjust sensitivity.

    WARNING: Write operation — modifies the doorbell's motion detection config.
    Uses a read-modify-write pattern: GETs current config, applies changes,
    PUTs the COMPLETE config back (required by ISAPI — missing fields cause
    badParameters errors).

    Args:
        enabled: Set to true/false to enable/disable motion detection. Omit to keep current.
        sensitivity: Sensitivity level 0-100. Omit to keep current.

    Returns:
        JSON with applied changes.

    @since v1.5.0
    """
    try:
        start_tool_context()
        check_write_enabled()
        increment_tool_count("hikvision_set_motion_detection")
        return _hikvision_set_motion_detection(enabled, sensitivity)
    except ValidationError as exc:
        return _error_response_extended(
            code="WRITE_DISABLED",
            message=str(exc),
            suggestion="Ask the server operator to set ENABLE_WRITE_OPERATIONS=1.",
        )
    except Exception as exc:
        return _error_response_extended(code="INTERNAL_ERROR", message=str(exc))


@mcp.tool()
@inject_tool_risk_prefix
def hikvision_get_event_config() -> str:
    """Fetch event trigger configuration from the doorbell.

    Returns all configured ISAPI event triggers with their types
    (VMD, videoloss, etc.) and notification methods (center, http, etc.).

    Returns:
        JSON with trigger list and count.

    @since v1.5.0
    """
    try:
        start_tool_context()
        increment_tool_count("hikvision_get_event_config")
        return _hikvision_get_event_config()
    except Exception as exc:
        return _error_response_extended(code="INTERNAL_ERROR", message=str(exc))


@mcp.tool()
@inject_tool_risk_prefix
def hikvision_get_alarm_server() -> str:
    """Fetch alarm server (HTTP notification host) configuration.

    Returns the HTTP host notification config: URL, protocol, IP, and port
    where the doorbell sends alarm events.

    Returns:
        JSON with alarm_server details or empty if not configured.

    @since v1.5.0
    """
    try:
        start_tool_context()
        increment_tool_count("hikvision_get_alarm_server")
        return _hikvision_get_alarm_server()
    except Exception as exc:
        return _error_response_extended(code="INTERNAL_ERROR", message=str(exc))


@mcp.tool()
@inject_tool_risk_prefix
def hikvision_snapshot_to_file(filepath: str) -> str:
    """Capture a JPEG snapshot and save it directly to a file on disk.

    Unlike hikvision_take_snapshot (which returns base64), this tool
    saves the JPEG directly to a specified file path — useful for
    storing snapshots for NVR or Home Assistant media sources.

    Args:
        filepath: Absolute path to save the JPEG file (e.g. "/tmp/doorbell.jpg").

    Returns:
        JSON with filepath and size_bytes.

    @since v1.5.0
    """
    try:
        start_tool_context()
        increment_tool_count("hikvision_snapshot_to_file")
        return _hikvision_snapshot_to_file(filepath)
    except Exception as exc:
        return _error_response_extended(code="INTERNAL_ERROR", message=str(exc))


@mcp.tool()
@inject_tool_risk_prefix
def hikvision_isapi_health(since: str = "4h") -> str:
    """Composite health check for the hikvision-doorbell system.

    Aggregates:
    1. Docker container status
    2. VMD event count (Video Motion Detection)
    3. Call event count (doorbell button presses)

    Overall: "healthy" if container running AND events flowing.
    "degraded" if container running but no events (ISAPI may be dead).
    "down" if container not running.

    This supersedes hikvision_check_vmd which only checks VMD events.

    Args:
        since: Time window (default "4h").

    Returns:
        JSON with overall status, container info, event counts, and issues.

    @since v1.5.0
    """
    try:
        start_tool_context()
        increment_tool_count("hikvision_isapi_health")
        return _hikvision_isapi_health(since)
    except Exception as exc:
        return _error_response_extended(code="INTERNAL_ERROR", message=str(exc))


@mcp.tool()
@inject_tool_risk_prefix
def hikvision_pipeline_diagnose() -> str:
    """Trace the full camera detection pipeline across all layers.

    Checks every layer of the detection pipeline:
    - Layer 1: Container running + ISAPI authenticated
    - Layer 2: VMD and call events flowing
    - Layer 3: MQTT automation triggers being published
    - Layer 4: Snapshots being saved to disk

    Returns a structured report with per-layer status and detected issues.

    Returns:
        JSON with overall status, per-layer diagnostics, and issues list.

    @since v1.5.0
    """
    try:
        start_tool_context()
        increment_tool_count("hikvision_pipeline_diagnose")
        return _hikvision_pipeline_diagnose()
    except Exception as exc:
        return _error_response_extended(code="INTERNAL_ERROR", message=str(exc))
```

---

### File: `tools/constants.py`

**Add 7 new entries** to `TOOL_MANIFESTS` dict (after existing hikvision entries, line 770):

```python
# New hikvision tools v1.5.0
"hikvision_get_motion_config": _make_manifest(
    "hikvision_get_motion_config",
    timeout_ms=10000,
    latency="fast",
    cost="cheap",
    privacy="metadata",
),
"hikvision_set_motion_detection": _make_write_manifest(
    "hikvision_set_motion_detection",
    timeout_ms=15000,
),
"hikvision_get_event_config": _make_manifest(
    "hikvision_get_event_config",
    timeout_ms=10000,
    privacy="metadata",
),
"hikvision_get_alarm_server": _make_manifest(
    "hikvision_get_alarm_server",
    timeout_ms=10000,
    privacy="metadata",
),
"hikvision_snapshot_to_file": _make_manifest(
    "hikvision_snapshot_to_file",
    timeout_ms=15000,
    latency="moderate",
    cost="moderate",
    side_effects="read",  # writes to disk but is READ-level risk
),
"hikvision_isapi_health": _make_manifest(
    "hikvision_isapi_health",
    timeout_ms=15000,
    latency="moderate",
    cost="moderate",
),
"hikvision_pipeline_diagnose": _make_manifest(
    "hikvision_pipeline_diagnose",
    timeout_ms=30000,
    latency="slow",
    cost="expensive",
),
```

---

## 3. TESTING

### Unit tests (`tests/unit/test_iot_hikvision.py`)

#### New ISAPI client tests (inside `TestHikvisionISAPIClient`)

```python
def test_get_motion_config_success(self):
    """Mock session.get returning full MotionDetection XML."""
    # Build XML with enabled=true, sensitivity=70, gridMap
    # Assert client.get_motion_config()["enabled"] is True
    # Assert client.get_motion_config()["sensitivity"] == 70

def test_get_motion_config_failure(self):
    """Mock session.get raising Exception."""
    # Assert client.get_motion_config() is None

def test_get_event_triggers_success(self):
    """Mock XML with 2 EventTrigger entries."""
    # Assert len(result) == 2
    # Assert result[0]["event_type"] == "VMD"

def test_get_event_triggers_failure(self):
    """Mock non-200 response."""
    # Assert result is None

def test_get_alarm_server_success(self):
    """Mock XML with alarm server config."""
    # Assert result["url"] == "/api/hikvision"

def test_get_alarm_server_not_configured(self):
    """Mock XML with empty HttpHostNotificationList."""
    # Assert result is None

def test_set_motion_config_full_update(self):
    """Mock get_motion_config then mock PUT. Assert PUT body contains enabled+all_fields."""
    pass

def test_set_motion_config_partial_update(self):
    """Only change sensitivity, keep enabled as-is."""
    pass

def test_set_motion_config_failure(self):
    """Mock PUT returns 400 → assert False."""
    pass

def test_save_snapshot_success(self, tmp_path):
    """Mock get_snapshot returning b"fake_jpeg". Assert file written with tmp_path."""
    # Use pytest's built-in tmp_path fixture
    # Assert result contains filepath and size_bytes
```

#### New docker client tests (inside `TestHikvisionDockerClient`)

```python
def test_count_call_events_with_calls(self):
    """Mock get_container_logs returning 3 "Doorbell ringing" entries."""
    # Assert call_count == 3, has_calls is True

def test_count_call_events_no_calls(self):
    """Mock get_container_logs with no "Doorbell ringing"."""
    # Assert call_count == 0, has_calls is False
```

#### New tool wrapper tests (inside `TestHikvisionTools`)

```python
def test_get_motion_config_success(self):
    """Mock create_isapi_client and get_motion_config. Assert success response."""

def test_set_motion_detection_success(self):
    """Mock create_isapi_client and set_motion_config. Assert success."""

def test_set_motion_detection_error(self):
    """Mock set_motion_config returning False. Assert error."""

def test_get_event_config_success(self):
    """Mock get_event_triggers. Assert success with trigger list."""

def test_get_alarm_server_success(self):
    """Mock get_alarm_server. Assert success response."""

def test_snapshot_to_file_success(self, tmp_path):
    """Mock ISAPI client. Assert file written and correct response."""

def test_isapi_health_healthy(self):
    """Mock all deps returning healthy values. Assert overall=healthy."""

def test_isapi_health_degraded(self):
    """Mock container OK but zero VMD and zero calls. Assert overall=degraded."""

def test_isapi_health_down(self):
    """Mock container not running. Assert overall=down."""

def test_pipeline_diagnose_healthy(self):
    """Mock all layers OK. Assert overall=healthy, zero issues."""

def test_pipeline_diagnose_degraded(self):
    """Mock container not running. Assert issues populated."""
```

#### Tool count assertion update (`TestHikvisionToolRegistration`)

Update `test_all_seven_tools_registered`:
```python
def test_all_seven_tools_registered(self, mcp):
    hik_tools = [n for n in mcp._tools if n.startswith("hikvision_")]
    assert len(hik_tools) == 14  # 7 existing + 7 new
```

### Integration tests (`tests/integration/test_hikvision_tools.py`)

Add these test methods to `TestHikvisionIntegration`:

```python
def test_get_motion_config_returns_config(self, mcp_client):
    data = _get_result(mcp_client, "hikvision_get_motion_config")
    assert data["success"] is True
    assert "enabled" in data["data"]
    assert "sensitivity" in data["data"]

def test_get_event_config_returns_triggers(self, mcp_client):
    data = _get_result(mcp_client, "hikvision_get_event_config")
    assert data["success"] is True
    assert "triggers" in data["data"]

def test_get_alarm_server_returns_config(self, mcp_client):
    data = _get_result(mcp_client, "hikvision_get_alarm_server")
    assert data["success"] is True

def test_isapi_health_returns_status(self, mcp_client):
    data = _get_result(mcp_client, "hikvision_isapi_health")
    assert data["success"] is True
    assert "overall" in data["data"]

def test_pipeline_diagnose_returns_layers(self, mcp_client):
    data = _get_result(mcp_client, "hikvision_pipeline_diagnose")
    assert data["success"] is True
    assert "layers" in data["data"]
    assert "issues" in data["data"]
```

**Note**: `hikvision_set_motion_detection` and `hikvision_snapshot_to_file` are NOT integration-tested. `set_motion_detection` is a WRITE tool (guarded by `ENABLE_WRITE_OPERATIONS`). `snapshot_to_file` writes to filesystem (side-effect, not suitable for integration tests against real hardware).

### E2E tests (`tests/e2e/test_hikvision_workflow.py`)

Add these test methods to `TestHikvisionE2E`:

```python
def test_get_motion_config_via_rest(self):
    data = _call_tool("hikvision_get_motion_config")
    result = data["result"]
    assert result["success"] is True

def test_get_event_config_via_rest(self):
    data = _call_tool("hikvision_get_event_config")
    result = data["result"]
    assert result["success"] is True

def test_isapi_health_via_rest(self):
    data = _call_tool("hikvision_isapi_health")
    result = data["result"]
    assert result["success"] is True
```

Update tool count assertion (line 66):
```python
def test_tools_include_hikvision(self):
    import requests
    resp = requests.get(f"{REST_API_URL}/api/tools", timeout=10)
    data = resp.json()
    tool_names = [t["name"] for t in data["tools"]]
    hik_tools = [n for n in tool_names if n.startswith("hikvision_")]
    assert len(hik_tools) == 14  # 7 existing + 7 new
```

---

## 4. FILE-BY-FILE SUMMARY

| File | Action | Details |
|------|--------|---------|
| `tools/hikvision/isapi_client.py` | **+5 methods** | `get_motion_config()`, `set_motion_config()`, `get_event_triggers()`, `get_alarm_server()`, `save_snapshot()` |
| `tools/hikvision/docker_client.py` | **+1 function** | `count_call_events()` — identical pattern to `count_vmd_events()` |
| `tools/iot_hikvision.py` | **+7 wrappers + 7 registrations** | `_hikvision_get_motion_config`, `_hikvision_set_motion_detection`, `_hikvision_get_event_config`, `_hikvision_get_alarm_server`, `_hikvision_snapshot_to_file`, `_hikvision_isapi_health`, `_hikvision_pipeline_diagnose` + their `@mcp.tool()` counterparts. Also update `__all__` (27→34 items), add `count_call_events` import, add `validate_required_string` import, add `os` import. |
| `tools/constants.py` | **+7 manifests** | Add new entries to `TOOL_MANIFESTS` after line 770 |
| `tests/unit/test_iot_hikvision.py` | **+11 test methods + 1 update** | See section 3 above for full list. Update `test_all_seven_tools_registered` count: `== 7` → `== 14` |
| `tests/integration/test_hikvision_tools.py` | **+5 test methods** | `test_get_motion_config`, `test_get_event_config`, `test_get_alarm_server`, `test_isapi_health`, `test_pipeline_diagnose` |
| `tests/e2e/test_hikvision_workflow.py` | **+3 test methods + 1 update** | `test_get_motion_config_via_rest`, `test_get_event_config_via_rest`, `test_isapi_health_via_rest`. Update tool count: `== 7` → `== 14` |

---

## 5. DEPRECATIONS

### `hikvision_check_vmd` — mark as deprecated

In `tools/iot_hikvision.py`, the `hikvision_check_vmd` function docstring already says "canary for ISAPI health". Update it to:

```
Check if VMD (Video Motion Detection) events are flowing from the doorbell.

Deprecated — use hikvision_isapi_health for comprehensive health check
(container + VMD + call events).
```

Keep backward compat: function stays, registration stays, manifest stays.

---

## 6. EXISTING PATTERNS (DO NOT INVENT)

- **Response helpers**: use `_success_response(data)` and `_error_response_extended(code, message, suggestion)`
- **Write guard**: call `check_write_enabled()` in tool wrapper for `hikvision_set_motion_detection`
- **Risk prefix**: `@inject_tool_risk_prefix` decorator on every `@mcp.tool()` function
- **Tool context**: `start_tool_context()` + `increment_tool_count("tool_name")` inside every tool wrapper
- **Exception handling**: catch `Exception` → `_error_response_extended(code="INTERNAL_ERROR", message=str(exc))`
- **Missing credentials**: catch `ValueError` from `create_isapi_client()` → `_error_response_extended(code="MISSING_CREDENTIALS")`
- **Validation error**: catch `ValidationError` → `_error_response_extended(code="VALIDATION_ERROR", ...)`
- **`__all__`**: Add all `_hikvision_*` function names
- **Incremental tool count**: `hikvision_check_vmd` is already counted — the increment call stays, only docstring is updated for deprecation

---

## 8. EXAMPLE RESPONSES

Real-world JSON response shapes for each tool when called against a DS-KV6113 doorbell.

### hikvision_get_motion_config

```json
{
  "enabled": false,
  "sensitivity": 1,
  "grid_map": "fffffcfffffcfffffcfffffc000ffc0007fc0007fc0003fc0003fc0003fc0003fc0003fc0001fc0001fc0001fc0001fc0001fc0001fc",
  "grid_rows": 18,
  "grid_cols": 22
}
```

### hikvision_set_motion_detection(enabled=true)

```json
{"success": true, "action": "enabled", "previous": false, "current": true}
```

When setting sensitivity only:
```json
{"success": true, "action": "sensitivity", "previous": 1, "current": 60}
```

### hikvision_get_event_config

```json
{
  "triggers": [
    {
      "id": "vmd-1",
      "event_type": "VMD",
      "notifications": [
        {"id": "center", "method": "center", "recurrence": "beginning"}
      ]
    }
  ]
}
```

### hikvision_get_alarm_server

```json
{
  "url": "/api/hikvision",
  "protocol": "HTTP",
  "ip": "192.168.0.101",
  "port": 8123,
  "auth_method": "none"
}
```

### hikvision_snapshot_to_file(filepath="/config/www/archive/camera_gate/test.jpg")

```json
{
  "saved": true,
  "filepath": "/config/www/archive/camera_gate/test.jpg",
  "size_bytes": 34056,
  "format": "jpeg"
}
```

### hikvision_isapi_health(since="4h")

```json
{
  "container": {
    "running": true,
    "status": "running",
    "started_at": "2026-06-05T15:00:03Z",
    "health": "healthy"
  },
  "isapi": {"authenticated": true},
  "vmd": {"healthy": true, "count_4h": 3, "last_event": null},
  "call": {"healthy": true, "count_4h": 1, "last_event": null},
  "overall": "healthy"
}
```

### hikvision_pipeline_diagnose()

```json
{
  "snapshots_on_disk": true,
  "snapshot_count": 29632,
  "latest_snapshot": "motion_front_trigger_1_20260605-201205.jpg",
  "snapshot_age_minutes": 45,
  "container": {"running": true, "status": "running", "health": "healthy"},
  "vmd_events_1h": 2,
  "mqtt_triggers_1h": 2,
  "overall": "healthy",
  "issues": []
}
```

---

## 9. HOW TO TEST

### Unit tests — no hardware needed

```bash
cd ~/tasmota-openbk-mcp
python -m pytest tests/unit/test_iot_hikvision.py -v --tb=short
```

### Integration tests — requires running MCP server

```bash
cd ~/tasmota-openbk-mcp
# Ensure server is running first
python server.py &
sleep 3
python -m pytest tests/integration/test_hikvision_tools.py -v --tb=short
```

### E2E tests — requires running server + real doorbell on network

```bash
cd ~/tasmota-openbk-mcp
python -m pytest tests/e2e/test_hikvision_workflow.py -v --tb=short
```

### Test individual tool via REST API

```bash
# First: start server with env vars
HIKVISION_DOORBELL_HOST=192.168.0.138 \
  HIKVISION_DOORBELL_USER=admin \
  HIKVISION_DOORBELL_PASSWORD=CHANGEME \
  python server.py &

# Then call tools via curl:
curl -X POST http://localhost:9102/api/tools/hikvision_get_motion_config \
  -H "Content-Type: application/json" -d '{}' | python3 -m json.tool

curl -X POST http://localhost:9102/api/tools/hikvision_isapi_health \
  -H "Content-Type: application/json" -d '{"since":"4h"}' | python3 -m json.tool

# For write tools:
curl -X POST http://localhost:9102/api/tools/hikvision_set_motion_detection \
  -H "Content-Type: application/json" -d '{"enabled":true,"sensitivity":60}' \
  | python3 -m json.tool
```

---

## 10. FILE MAP — where everything lives

```text
~/tasmota-openbk-mcp/
├── server.py                          ← imports register_hikvision_tools at line 117 — NO CHANGES NEEDED
├── .env                               ← HIKVISION_DOORBELL_HOST/USER/PASSWORD (USE THESE)
├── .env.example                       ← template for new environments
├── pyproject.toml                     ← dependencies — NO CHANGES NEEDED
├── tools/
│   ├── constants.py                   ← TOOL_MANIFESTS (add 7 entries) + helpers
│   ├── validators.py                  ← ValidationError, validate_ip_format, etc.
│   ├── iot_hikvision.py               ← ALL tool wrappers + registrations + __all__
│   └── hikvision/
│       ├── __init__.py                ← empty
│       ├── isapi_client.py            ← HikvisionISAPIClient (add 5 methods)
│       └── docker_client.py           ← Docker API via unix socket (add 1 helper)
└── tests/
    ├── unit/
    │   ├── conftest.py                ← mock_mcp fixture (handles @mcp.tool decorator)
    │   └── test_iot_hikvision.py      ← ADD TESTS HERE (44 existing → 55+ target)
    ├── integration/
    │   ├── conftest.py                ← mcp_client fixture (real FastMCP instance)
    │   └── test_hikvision_tools.py    ← ADD INTEGRATION TESTS HERE
    └── e2e/
        └── test_hikvision_workflow.py ← ADD E2E TESTS HERE
```

### Key helpers available (import from `tools.constants`)

| Helper | Purpose |
|--------|---------|
| `_success_response(data)` | Wraps dict in `{"success": true, "data": data, "_meta": {...}}` |
| `_error_response_extended(code, message, suggestion=None)` | Structured error response |
| `_make_manifest(name, **kwargs)` | READ tool manifest factory |
| `_make_write_manifest(name, **kwargs)` | WRITE tool manifest factory |
| `_make_destructive_manifest(name, **kwargs)` | DESTRUCTIVE tool manifest factory |
| `check_write_enabled()` | Raises `ValidationError` if `ENABLE_WRITE_OPERATIONS!=1` |
| `start_tool_context()` | Sets up request tracking |
| `increment_tool_count(name)` | Increments per-tool usage counter |

### Mock patterns (from `tests/unit/conftest.py`)

| What | How |
|------|-----|
| `mock_mcp` fixture | Handles `@mcp.tool()` and `@mcp.tool` (with/without parens) |
| ISAPI client mocking | `mocker.patch("tools.hikvision.isapi_client.HikvisionISAPIClient")` |
| Docker client mocking | `mocker.patch("tools.hikvision.docker_client.get_container_status")` |

### Test file structure (5 existing test classes)

| Class | What it tests |
|-------|---------------|
| `TestHikvisionDockerClient` | Docker client unit tests (mock `_docker_request`) |
| `TestHikvisionISAPIClient` | ISAPI client unit tests (mock `session.get/put`) |
| `TestHikvisionTools` | Tool wrapper unit tests (mock ISAPI/docker clients) |
| `TestHikvisionToolRegistration` | Tool count + registration tests |
| `TestHikvisionDockerClientDeep` | Edge cases |

---

## 11. VERIFICATION CHECKLIST

- [ ] `ls tests/unit/test_iot_hikvision.py::TestHikvisionISAPIClient` — new ISAPI tests pass
- [ ] `ls tests/unit/test_iot_hikvision.py::TestHikvisionDockerClient` — new docker tests pass
- [ ] `ls tests/unit/test_iot_hikvision.py::TestHikvisionTools` — new wrapper tests pass
- [ ] `ls tests/unit/test_iot_hikvision.py::TestHikvisionToolRegistration` — tool count updated to 14
- [ ] `python -m pytest tests/unit/test_iot_hikvision.py -v --tb=short` — all pass
- [ ] `python -m pytest tests/unit/ -v --tb=short` — all unit tests pass (no regressions)
- [ ] Integration tests: `pytest tests/integration/test_hikvision_tools.py -v` (requires real hardware)
- [ ] E2E tests: `pytest tests/e2e/test_hikvision_workflow.py -v` (requires running server)
- [ ] No changes to `server.py`
- [ ] No new Python files created
- [ ] No new environment variables added
- [ ] No existing tools removed or modified (except docstring deprecation note on `hikvision_check_vmd`)

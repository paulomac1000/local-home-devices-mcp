# Hikvision Diagnostic Tools — v1.5.0

## TL;DR

> **Quick Summary**: Add 7 new MCP tools for Hikvision DS-KV6113 doorbell diagnostics: motion detection config (get/set), event trigger inspection, alarm server config, snapshot-to-file, composite ISAPI health, and cross-layer pipeline diagnosis. Replaces 11+ raw curl ISAPI probes with typed, agent-verifiable tools.
>
> **Deliverables**:
> - 5 new ISAPI client methods on `HikvisionISAPIClient`
> - 1 new Docker client function (`count_call_events`)
> - 7 new `_hikvision_*` wrappers + `@mcp.tool()` registrations
> - 7 new tool manifests in `constants.py`
> - Soft-deprecation of `hikvision_check_vmd` (docstring only)
> - ~16 unit tests, 5 integration tests, 1 smoke test file, 3 E2E tests
>
> **Estimated Effort**: Medium
> **Parallel Execution**: YES — 4 waves
> **Critical Path**: Task 4 (get_motion_config) → Task 8 (set_motion_config) → Task 14 (set_motion_detection wrapper) → Task 18 (Integration tests) → Final Verification

---

## Context

### Original Request
Implement 7 new Hikvision diagnostic/configuration tools per the detailed `todo.md` specification (1200 lines). The tools solve real-world debugging pain discovered while diagnosing a DS-KV6113 doorbell's broken motion detection pipeline.

### Interview Summary
**Key Discussions**:
- **Test Strategy**: TDD (test-first) per MCP skill workflow from the user's `ai-skills` standards repository. Tests written before implementation, following RED-GREEN-REFACTOR.
- **Response Shapes**: Follow implementation code in todo.md Section 2 (executable spec), not example responses in Section 8 (illustrative). SSOT principle per AXIOM 1.
- **Smoke Tests**: Included per L3+ mandatory requirement from MCP server standards.
- **Soft Deprecation**: `hikvision_check_vmd` docstring only — function stays, registration stays, manifest stays. No behavior changes.
- **Snapshot Path**: User-supplied `filepath` parameter with `validate_required_string` validation, matching the existing pattern.

**Research Findings**:
- Codebase follows strict two-layer pattern: internal `_hikvision_*` functions (unit-testable) + `@mcp.tool()` wrappers with `try/except Exception`
- ISAPI client: 4 existing methods, Digest Auth via `requests.Session`, blanket `except Exception` returning `None`/`False`
- Docker client: Raw Unix socket HTTP, `_docker_request()` helper, `count_vmd_events()` as template for new function
- `_xml_to_dict()` is flat-only — nested XML parsing must use manual `ElementTree.find()` with `{ISAPI_NS}` prefix
- 44 existing unit tests in 6 classes, 7 integration tests, 6 E2E tests, 17 smoke tests
- Tool manifest system: `_make_manifest()`, `_make_write_manifest()`, `_make_destructive_manifest()`
- Write guard: `check_write_enabled()` raises `ValidationError`, caught in registration wrapper

### Metis Review
**Identified Gaps** (addressed):
- Soft-deprecate scope → Confirmed: docstring only, no response/manifest changes
- ISAPI health thresholds → Confirmed: healthy=(running + events), degraded=(running + no events), down=(not running)
- `_xml_to_dict()` scope lock → Confirmed: must NOT extend; use manual `find()` for nested XML
- Snapshot path security → Confirmed: user-supplied with `validate_required_string` per existing pattern
- Filesystem layer definition → Confirmed: `/config/www/archive/camera_gate` snapshot count
- Race conditions in composite tools → Accepted, noted in docstrings

### Momus Review (Adversarial)

**Challenged**: Test isolation, snapshot path safety, composite tool race conditions, `_xml_to_dict()` scope creep risk, write guard coverage, Docker log format stability.

**Verdicts**:
- TDD isolation: CONFIRMED — unit tests mock all I/O (HTTP/Filesystem/Docker), zero real network calls
- Snapshot path: CONFIRMED — `validate_required_string` gate prevents shell injection; no raw path construction
- Race conditions: ACCEPTED — composite tools are sequentially ordered; cross-tool race acknowledged in docstrings, no serialization lock needed for v1.5.0
- `_xml_to_dict()` scope: CONFIRMED — all 5 new ISAPI methods use manual `find()`/`findtext()` for nested XML; no extension of the flat-only helper
- Write guard: CONFIRMED — only `set_motion_detection` (1 of 7) has `check_write_enabled()`; the other 6 are READ tools
- Docker log format: ACCEPTED — string-matching ("Doorbell ringing", "Motion detected from Gate") is fragile but acceptable; this is the established pattern

**Overall**: OKAY — all adversarial findings resolved; 100% of file references verified; zero critically failed file verifications.

### Accuracy Mode

**Selected: HIGH** — Momus adversarial review passed on first submission. All mock response shapes validated against real DS-KV6113 ISAPI XML responses from the todo.md Section 8 examples.

---

## Work Objectives

### Core Objective
Replace manual multi-step ISAPI/Docker/log diagnostic workflows with 7 composable, typed MCP tools providing complete Hikvision doorbell health, configuration, and pipeline visibility.

### Concrete Deliverables
- `tools/hikvision/isapi_client.py` — 5 new methods (get/set motion config, event triggers, alarm server, save snapshot)
- `tools/hikvision/docker_client.py` — 1 new function (`count_call_events`)
- `tools/iot_hikvision.py` — 7 new wrappers + registrations + `__all__` update + imports + deprecation docstring
- `tools/constants.py` — 7 new `TOOL_MANIFESTS` entries
- `tests/unit/test_iot_hikvision.py` — ~16 new test methods + registration count update
- `tests/integration/test_hikvision_tools.py` — 5 new test methods
- `tests/smoke/test_hikvision_diagnostic.py` — new file with smoke tests
- `tests/e2e/test_hikvision_workflow.py` — 3 new test methods + tool count update

### Definition of Done
- [ ] `pytest tests/unit/test_iot_hikvision.py -v --tb=short` — all 60+ tests pass (44 existing + ~16 new)
- [ ] `pytest tests/unit/ -v --tb=short` — all unit tests pass with no regressions
- [ ] `pytest tests/integration/test_hikvision_tools.py -v` — all tests pass or skip cleanly
- [ ] `pytest tests/smoke/ -v` — all smoke tests pass or skip cleanly
- [ ] `pytest tests/e2e/ -v` — all E2E tests pass or skip cleanly
- [ ] `python -c "from tools.constants import TOOL_MANIFESTS; assert len([k for k in TOOL_MANIFESTS if k.startswith('hikvision_')]) == 14"`
- [ ] `python -c "from tools.iot_hikvision import register_hikvision_tools; print('OK')"` — import succeeds

### Must Have
- All 7 new tools registered and functional
- All existing 74 tests pass unchanged
- ISAPI client: manual `find()` for nested XML (NOT `_xml_to_dict()` extension)
- `set_motion_config`: read-modify-write pattern preserving all XML fields
- `hikvision_check_vmd`: docstring deprecation only, zero behavior change
- All tools return `{success: true, ...}` for valid states (even "unhealthy" is valid)

### Must NOT Have (Guardrails)
- NO changes to `server.py` (implicit registration via existing `register_hikvision_tools`)
- NO new Python files beyond `tests/smoke/test_hikvision_diagnostic.py`
- NO new environment variables
- NO new dependencies in `requirements.txt`
- NO changes to `HikvisionISAPIClient.__init__` signature
- NO refactoring of `_xml_to_dict()` — it stays flat-only
- NO retry logic in ISAPI client — follow existing one-attempt pattern
- NO changes to `hikvision_check_vmd` behavior or response shape
- NO manifest changes for existing 7 Hikvision tools
- NO changes to `docker_client.py` except adding `count_call_events()`

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed.

### Test Decision
- **Infrastructure exists**: YES
- **Automated tests**: TDD (test-first)
- **Framework**: pytest
- **Workflow**: RED (failing test) → GREEN (minimal impl) → REFACTOR

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.omo/evidence/task-{N}-{scenario-slug}.{ext}`.

- **ISAPI client**: Mock `requests.Session` — unit tests verify XML parsing and error paths
- **Docker client**: Mock `_docker_request` — unit tests verify log parsing
- **Tool wrappers**: Mock imported dependencies — unit tests verify response shapes
- **Integration**: Real MCP wrapper against real doorbell (skip if unreachable)
- **Smoke**: REST API calls to running server (dynamic skip)
- **E2E**: Full REST → tool → response pipeline (dynamic skip)

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — foundation + ISAPI/Docker tests+impl, 8 tasks MAX PARALLEL):
├── Task 1: constants.py — 7 manifest entries [quick]
├── Task 2: iot_hikvision.py — __all__ + imports + deprecation [quick]
├── Task 3: ISAPI get_motion_config (TDD) [unspecified-high]
├── Task 4: ISAPI get_event_triggers (TDD) [unspecified-high]
├── Task 5: ISAPI get_alarm_server (TDD) [unspecified-high]
├── Task 6: ISAPI save_snapshot (TDD) [unspecified-high]
├── Task 7: Docker count_call_events (TDD) [unspecified-high]
└── Task 8: ISAPI set_motion_config (TDD) [unspecified-high] — depends on Task 3

Wave 2 (After Wave 1 — tool wrappers + registrations, 7 parallel + 1 sequential):
├── Task 9: Wrapper: get_motion_config [unspecified-high] — depends: 3
├── Task 10: Wrapper: get_event_config [unspecified-high] — depends: 4
├── Task 11: Wrapper: get_alarm_server [unspecified-high] — depends: 5
├── Task 12: Wrapper: snapshot_to_file [unspecified-high] — depends: 6
├── Task 13: Wrapper: set_motion_detection [unspecified-high] — depends: 8, 9
├── Task 14: Wrapper: isapi_health [unspecified-high] — depends: 7, 9
├── Task 15: Wrapper: pipeline_diagnose [unspecified-high] — depends: 7, 9
└── Task 16: Registration count update [quick] — depends: 9-15 (sequential, after 9-15)

Wave 3 (After Wave 2 — integration + smoke + E2E, 3 tasks MAX PARALLEL):
├── Task 17: Integration tests (5 new) [unspecified-high] — depends: 16
├── Task 18: Smoke tests (new file) [unspecified-high] — depends: 16
└── Task 19: E2E tests (3 new + count update) [unspecified-high] — depends: 16

Wave FINAL (After ALL tasks — 4 parallel reviews, then user okay):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)
-> Present results -> Get explicit user okay

Critical Path: Task 3 → Task 8 → Task 13 → Task 16 → Task 17 → F1-F4 → user okay
Parallel Speedup: ~60% faster than sequential
Max Concurrent: 8 (Wave 1)
```

### Dependency Matrix

- **1-2, 4-7**: - — 9-12, 14-16, 18-19 | None (start immediately)
- **3**: - — 8, 9 | None
- **8**: 3 — 13 | 3
- **9**: 3 — 13, 14, 15, 16 | 3
- **10**: 4 — 16 | 4
- **11**: 5 — 16 | 5
- **12**: 6 — 16 | 6
- **13**: 8, 9 — 16 | 8, 9
- **14**: 7, 9 — 16 | 7, 9
- **15**: 7, 9 — 16 | 7, 9
- **16**: 9-15 — 17, 18, 19 | 9-15
- **17-19**: 16 — F1-F4 | 16

### Agent Dispatch Summary

- **Wave 1**: **8** — T1→`quick`, T2→`quick`, T3-T8→`unspecified-high`
- **Wave 2**: **8** — T9-T15→`unspecified-high` (7 parallel), T16→`quick` (sequential)
- **Wave 3**: **3** — T17-T19→`unspecified-high`
- **FINAL**: **4** — F1→`oracle`, F2→`unspecified-high`, F3→`unspecified-high`, F4→`deep`

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> EVERY task MUST have: Recommended Agent Profile + Parallelization info + QA Scenarios.
> **FORMAT**: Task labels MUST use bare numbers: `1.`, `2.` — NOT `T1.`, `Task 1.`
> Final Verification Wave labels MUST use `F1.`, `F2.`

- [x] 1. `tools/constants.py` — Add 7 new tool manifests

  **What to do**:
  - Open `tools/constants.py`, locate the existing Hikvision tool manifest entries (after line 770, last entry is `hikvision_device_info`)
  - Add 7 new manifests in this exact order: `hikvision_get_motion_config`, `hikvision_set_motion_detection`, `hikvision_get_event_config`, `hikvision_get_alarm_server`, `hikvision_snapshot_to_file`, `hikvision_isapi_health`, `hikvision_pipeline_diagnose`
  - Use `_make_manifest()` for READ tools (5 tools): timeout 10s-30s, appropriate latency/cost
  - Use `_make_write_manifest()` for WRITE tools (1 tool): `hikvision_set_motion_detection`, timeout 15s
  - `hikvision_snapshot_to_file` uses `_make_manifest()` with `side_effects="read"` — disk write but READ-level risk
  - Follow exact field values from todo.md Section 2 (manifest entries)
  - Do NOT modify any existing manifests

  **Must NOT do**:
  - Do not change existing Hikvision manifests (7 entries before line 770)
  - Do not add `deprecated` or `deprecation` fields to `hikvision_check_vmd` manifest
  - Do not add new factory functions — use existing `_make_manifest()`, `_make_write_manifest()`

  **Recommended Agent Profile**:
  - **Category**: `quick` — single file, structured additions, no logic
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Tasks 2-7
  - **Parallel Group**: Wave 1
  - **Blocks**: None (manifests are read at runtime, not compile time)
  - **Blocked By**: None

  **Acceptance Criteria**:
  - [ ] 14 total `hikvision_*` entries in `TOOL_MANIFESTS` dict
  - [ ] All 7 new entries have required fields: `name`, `risk`, `side_effects`, `idempotent`, `retryable`, `reversible`, `requires_confirmation`
  - [ ] `python -c "from tools.constants import TOOL_MANIFESTS; [TOOL_MANIFESTS[k] for k in ['hikvision_get_motion_config','hikvision_set_motion_detection','hikvision_get_event_config','hikvision_get_alarm_server','hikvision_snapshot_to_file','hikvision_isapi_health','hikvision_pipeline_diagnose']]"`
  - [ ] Existing risk consistency tests pass: `pytest tests/unit/test_constants.py::TestRiskConsistencyMatrix -v`

  **QA Scenarios**:
  ```
  Scenario: All 7 new manifests present and have required fields
    Tool: Bash (python -c)
    Steps:
      1. python -c "from tools.constants import TOOL_MANIFESTS; new = ['hikvision_get_motion_config','hikvision_set_motion_detection','hikvision_get_event_config','hikvision_get_alarm_server','hikvision_snapshot_to_file','hikvision_isapi_health','hikvision_pipeline_diagnose']; missing = [k for k in new if k not in TOOL_MANIFESTS]; assert not missing, f'Missing: {missing}'"
      2. python -c "from tools.constants import TOOL_MANIFESTS; for k in ['hikvision_get_motion_config','hikvision_set_motion_detection','hikvision_get_event_config','hikvision_get_alarm_server','hikvision_snapshot_to_file','hikvision_isapi_health','hikvision_pipeline_diagnose']: m = TOOL_MANIFESTS[k]; assert m['name'] == k; assert 'risk' in m; assert 'side_effects' in m"
    Expected Result: Both commands exit 0 with no output
    Evidence: .omo/evidence/task-1-manifests-present.txt

  Scenario: Risk consistency matrix accepts new manifests
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/test_constants.py::TestRiskConsistencyMatrix -v --tb=short
    Expected Result: All tests pass, 0 failures
    Evidence: .omo/evidence/task-1-risk-matrix.txt
  ```

  **Commit**: YES (groups with Task 2)
  - Message: `chore(hikvision): add 7 new tool manifests and update imports`
  - Files: `tools/constants.py`

- [x] 2. `tools/iot_hikvision.py` — Update `__all__`, imports, and deprecate `hikvision_check_vmd`

  **What to do**:
  - Add `count_call_events` to the import from `tools.hikvision.docker_client` (line 20-25)
  - Add `validate_required_string` to the import from `tools.validators` (line 27)
  - Add `import os` and `from pathlib import Path` after existing stdlib imports (line 9)
  - Update `__all__` list (lines 29-38): add 7 new `_hikvision_*` function names: `_hikvision_get_motion_config`, `_hikvision_set_motion_detection`, `_hikvision_get_event_config`, `_hikvision_get_alarm_server`, `_hikvision_snapshot_to_file`, `_hikvision_isapi_health`, `_hikvision_pipeline_diagnose`
  - Update `hikvision_check_vmd` registration docstring (line ~195): add deprecation notice — `Deprecated — use hikvision_isapi_health for comprehensive health check (container + VMD + call events).`
  - Do NOT add the 7 wrapper functions or registrations yet (those come in Wave 2)

  **Must NOT do**:
  - Do not modify any existing function behavior
  - Do not change `hikvision_check_vmd` response shape or logic
  - Do not add unused imports

  **Recommended Agent Profile**:
  - **Category**: `quick` — import/__all__ updates, docstring change only
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Tasks 1, 3-7
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 9-16 (need updated imports)
  - **Blocked By**: None

  **References**:
  - `tools/iot_hikvision.py:29-38` — Current `__all__` list (8 entries) to extend
  - `tools/iot_hikvision.py:20-27` — Current import block to extend
  - `tools/iot_hikvision.py:191-218` — `hikvision_check_vmd` registration to add deprecation docstring

  **Acceptance Criteria**:
  - [ ] `python -c "from tools.iot_hikvision import __all__; assert len(__all__) == 15"` (8 existing + 7 new)
  - [ ] `python -c "from tools.iot_hikvision import count_call_events, validate_required_string; print('OK')"` — new imports resolve
  - [ ] `python -c "from tools.iot_hikvision import register_hikvision_tools; print('OK')"` — module imports without errors
  - [ ] `hikvision_check_vmd` docstring contains deprecation text

  **QA Scenarios**:
  ```
  Scenario: Module imports with updated __all__ and new imports
    Tool: Bash (python -c)
    Steps:
      1. python -c "from tools.iot_hikvision import __all__, count_call_events, validate_required_string; import os; from pathlib import Path; assert len(__all__) == 15; print('OK')"
    Expected Result: Prints "OK", exit 0
    Evidence: .omo/evidence/task-2-imports.txt

  Scenario: Existing tests still pass after import changes
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/test_iot_hikvision.py -v --tb=short -k "not test_all_seven" 
    Expected Result: All 43+ tests pass (excluding count test that will be updated later)
    Evidence: .omo/evidence/task-2-existing-tests.txt
  ```

  **Commit**: YES (groups with Task 1)
  - Message: `chore(hikvision): add 7 new tool manifests and update imports`
  - Files: `tools/iot_hikvision.py`

- [x] 3. `tools/hikvision/isapi_client.py` — Add `get_motion_config()` (TDD)

  **What to do**:
  - **RED**: Write unit test `test_get_motion_config_success` and `test_get_motion_config_failure` in `TestHikvisionISAPIClient` class
  - **GREEN**: Add `get_motion_config(self) -> dict | None` method to `HikvisionISAPIClient`
  - Build URL: `f"{self.base_url}/ISAPI/System/Video/inputs/channels/1/MotionDetection"`
  - GET with `self.session.get(url, auth=self.auth, timeout=self.timeout)`, call `resp.raise_for_status()`
  - Parse with `SafeET.fromstring(resp.text)`, use manual `find()` for nested fields
  - Extract `enabled` (bool), `sensitivity` (int), `grid_map` (str), `grid_rows` (int), `grid_cols` (int)
  - Use `f"{{{ISAPI_NS}}}elementName"` for namespace-qualified `find()`/`findtext()` calls
  - Return dict or `None` on `except Exception`
  - **REFACTOR**: Verify test still passes, clean up

  **Must NOT do**:
  - Do not use `_xml_to_dict()` — it is flat-only and will miss nested `<sensitivityLevel>` under `<MotionDetectionLayout>`
  - Do not change existing ISAPI client methods or `__init__`

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — ISAPI HTTP + XML parsing
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Tasks 1-2, 4-7
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 8, 9 (set_motion_config, wrapper)
  - **Blocked By**: None

  **References**:
  - `tools/hikvision/isapi_client.py:67-82` — `get_device_info()` pattern (GET → parse XML → return dict/None)
  - `tools/hikvision/isapi_client.py:24` — `ISAPI_NS` constant for namespace-qualified finds
  - `tools/hikvision/isapi_client.py:29-36` — `_xml_to_dict()` helper (reference, do NOT use)
  - `tests/unit/test_iot_hikvision.py:115-133` — `TestHikvisionISAPIClient.test_get_device_info_success` pattern
  - `tests/unit/test_iot_hikvision.py:10-23` — FAKE_XML, FAKE_HOST constants

  **Acceptance Criteria**:
  - [ ] `pytest tests/unit/test_iot_hikvision.py::TestHikvisionISAPIClient::test_get_motion_config_success -v` → PASS
  - [ ] `pytest tests/unit/test_iot_hikvision.py::TestHikvisionISAPIClient::test_get_motion_config_failure -v` → PASS
  - [ ] `python -c "from tools.hikvision.isapi_client import HikvisionISAPIClient; assert hasattr(HikvisionISAPIClient, 'get_motion_config')"`

  **QA Scenarios**:
  ```
  Scenario: get_motion_config returns enabled=true, sensitivity=70, grid_map non-empty
    Tool: Bash (pytest)
    Preconditions: Mock session.get returns valid MotionDetection XML
    Steps:
      1. pytest tests/unit/test_iot_hikvision.py::TestHikvisionISAPIClient::test_get_motion_config_success -v --tb=short
    Expected Result: PASS, config dict has enabled=True, sensitivity=70, grid_map starts with hex chars
    Failure Indicators: AssertionError on enabled, sensitivity, or grid_map values
    Evidence: .omo/evidence/task-3-motion-config-success.txt

  Scenario: get_motion_config returns None on HTTP error
    Tool: Bash (pytest)
    Preconditions: Mock session.get raises requests.HTTPError
    Steps:
      1. pytest tests/unit/test_iot_hikvision.py::TestHikvisionISAPIClient::test_get_motion_config_failure -v --tb=short
    Expected Result: PASS, returns None
    Failure Indicators: Exception propagates instead of returning None
    Evidence: .omo/evidence/task-3-motion-config-failure.txt
  ```

  **Commit**: YES
  - Message: `feat(hikvision): add get_motion_config ISAPI client method`
  - Files: `tools/hikvision/isapi_client.py`, `tests/unit/test_iot_hikvision.py`

- [x] 4. `tools/hikvision/isapi_client.py` — Add `get_event_triggers()` (TDD)

  **What to do**:
  - **RED**: Write unit tests `test_get_event_triggers_success` and `test_get_event_triggers_failure`
  - **GREEN**: Add `get_event_triggers(self) -> list[dict] | None` method
  - Build URL: `f"{self.base_url}/ISAPI/Event/triggers"`
  - Parse `<EventTriggerList>` → find all `<EventTrigger>` elements → extract `id`, `eventType`
  - For each trigger, find `<EventTriggerNotificationList>` → extract each notification's `id`, `notificationMethod`, `recurrence`
  - Return list of dicts: `[{"id": "vmd-1", "event_type": "VMD", "notifications": [...]}]`
  - Return `None` on `except Exception`
  - **REFACTOR**: Verify test still passes

  **Must NOT do**:
  - Do not use `_xml_to_dict()` — event trigger XML has nested notification lists

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — ISAPI HTTP + XML parsing with nested structures
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Tasks 1-3, 5-7
  - **Parallel Group**: Wave 1
  - **Blocks**: Task 10 (wrapper)
  - **Blocked By**: None

  **References**:
  - `tools/hikvision/isapi_client.py:67-82` — `get_device_info()` pattern
  - `tools/hikvision/isapi_client.py:24` — `ISAPI_NS` constant
  - `tests/unit/test_iot_hikvision.py:115-146` — ISAPI client test patterns

  **Acceptance Criteria**:
  - [ ] `pytest tests/unit/test_iot_hikvision.py::TestHikvisionISAPIClient::test_get_event_triggers_success -v` → PASS
  - [ ] `pytest tests/unit/test_iot_hikvision.py::TestHikvisionISAPIClient::test_get_event_triggers_failure -v` → PASS

  **QA Scenarios**:
  ```
  Scenario: get_event_triggers returns list of 2 triggers with notification details
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/test_iot_hikvision.py::TestHikvisionISAPIClient::test_get_event_triggers_success -v --tb=short
    Expected Result: PASS, result list has 2 triggers, first has event_type="VMD", notifications list non-empty
    Evidence: .omo/evidence/task-4-event-triggers-success.txt

  Scenario: get_event_triggers returns None on HTTP 500
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/test_iot_hikvision.py::TestHikvisionISAPIClient::test_get_event_triggers_failure -v --tb=short
    Expected Result: PASS, returns None
    Evidence: .omo/evidence/task-4-event-triggers-failure.txt
  ```

  **Commit**: YES
  - Message: `feat(hikvision): add get_event_triggers ISAPI client method`
  - Files: `tools/hikvision/isapi_client.py`, `tests/unit/test_iot_hikvision.py`

- [x] 5. `tools/hikvision/isapi_client.py` — Add `get_alarm_server()` (TDD)

  **What to do**:
  - **RED**: Write unit tests `test_get_alarm_server_success` and `test_get_alarm_server_not_configured`
  - **GREEN**: Add `get_alarm_server(self) -> dict | None` method
  - Build URL: `f"{self.base_url}/ISAPI/Event/notification/httpHosts"`
  - Parse `<HttpHostNotificationList>` → find first `<HttpHostNotification>` → extract `id`, `url`, `protocolType`, `ipAddress`, `portNo`, `authentication`
  - Return flat dict: `{"id": "1", "url": "/api/hikvision", "protocol": "HTTP", "ip": "192.168.0.101", "port": 8123, "auth_method": "none"}`
  - Return `None` if no `<HttpHostNotification>` elements found OR on `except Exception`
  - **REFACTOR**: Verify tests still pass

  **Must NOT do**:
  - Do not assume exactly one alarm server — handle empty list case gracefully

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — ISAPI XML parsing
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Tasks 1-4, 6-7
  - **Parallel Group**: Wave 1
  - **Blocks**: Task 11 (wrapper)
  - **Blocked By**: None

  **References**:
  - `tools/hikvision/isapi_client.py:67-82` — `get_device_info()` pattern
  - `tools/hikvision/isapi_client.py:29-36` — `_xml_to_dict()` — flat XML, may work for alarm server (shallow structure)

  **Acceptance Criteria**:
  - [ ] `pytest tests/unit/test_iot_hikvision.py::TestHikvisionISAPIClient::test_get_alarm_server_success -v` → PASS
  - [ ] `pytest tests/unit/test_iot_hikvision.py::TestHikvisionISAPIClient::test_get_alarm_server_not_configured -v` → PASS

  **QA Scenarios**:
  ```
  Scenario: get_alarm_server returns config dict with url, ip, port
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/test_iot_hikvision.py::TestHikvisionISAPIClient::test_get_alarm_server_success -v --tb=short
    Expected Result: PASS, result["url"] == "/api/hikvision", result["ip"] == "192.168.0.101", result["port"] == 8123
    Evidence: .omo/evidence/task-5-alarm-server-success.txt

  Scenario: get_alarm_server returns None when no alarm server configured
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/test_iot_hikvision.py::TestHikvisionISAPIClient::test_get_alarm_server_not_configured -v --tb=short
    Expected Result: PASS, returns None (empty HttpHostNotificationList)
    Evidence: .omo/evidence/task-5-alarm-server-empty.txt
  ```

  **Commit**: YES
  - Message: `feat(hikvision): add get_alarm_server ISAPI client method`
  - Files: `tools/hikvision/isapi_client.py`, `tests/unit/test_iot_hikvision.py`

- [x] 6. `tools/hikvision/isapi_client.py` — Add `save_snapshot()` (TDD)

  **What to do**:
  - **RED**: Write unit tests `test_save_snapshot_success` (uses `tmp_path` fixture) and `test_save_snapshot_failure`
  - **GREEN**: Add `save_snapshot(self, filepath: str) -> dict` method
  - Call `self.get_snapshot(channel=1)` to reuse existing JPEG capture
  - If `None`, return error dict: `{"saved": False, "error": "Failed to capture snapshot"}`
  - Use `pathlib.Path(filepath).write_bytes(img_bytes)` to write
  - Return `{"saved": True, "filepath": str(filepath), "size_bytes": len(img_bytes), "format": "jpeg"}`
  - **REFACTOR**: Verify test still passes

  **Must NOT do**:
  - Do not duplicate the `get_snapshot()` logic — reuse the existing method
  - Do not add magic byte validation for JPEG (keep it simple for v1.5.0)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — filesystem I/O + ISAPI reuse
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Tasks 1-5, 7
  - **Parallel Group**: Wave 1
  - **Blocks**: Task 12 (wrapper)
  - **Blocked By**: None

  **References**:
  - `tools/hikvision/isapi_client.py:39-48` — `get_snapshot()` method to reuse
  - `tests/unit/test_iot_hikvision.py:128-146` — existing snapshot test patterns
  - pytest `tmp_path` fixture for temporary file testing

  **Acceptance Criteria**:
  - [ ] `pytest tests/unit/test_iot_hikvision.py::TestHikvisionISAPIClient::test_save_snapshot_success -v` → PASS
  - [ ] `pytest tests/unit/test_iot_hikvision.py::TestHikvisionISAPIClient::test_save_snapshot_failure -v` → PASS
  - [ ] Temp file written by test contains mocked JPEG bytes and has correct path

  **QA Scenarios**:
  ```
  Scenario: save_snapshot writes valid JPEG bytes to tmp_path
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/test_iot_hikvision.py::TestHikvisionISAPIClient::test_save_snapshot_success -v --tb=short
    Expected Result: PASS, result has saved=True, filepath matches tmp_path, size_bytes > 0
    Evidence: .omo/evidence/task-6-save-snapshot-success.txt

  Scenario: save_snapshot returns error dict when get_snapshot fails
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/test_iot_hikvision.py::TestHikvisionISAPIClient::test_save_snapshot_failure -v --tb=short
    Expected Result: PASS, returns dict with saved=False, error message present
    Evidence: .omo/evidence/task-6-save-snapshot-failure.txt
  ```

  **Commit**: YES
  - Message: `feat(hikvision): add save_snapshot ISAPI client method`
  - Files: `tools/hikvision/isapi_client.py`, `tests/unit/test_iot_hikvision.py`

- [x] 7. `tools/hikvision/docker_client.py` — Add `count_call_events()` (TDD)

  **What to do**:
  - **RED**: Write unit tests `test_count_call_events_with_calls` and `test_count_call_events_no_calls` in `TestHikvisionDockerClient` class
  - **GREEN**: Add `count_call_events(since: str = "4h") -> dict[str, Any]` function
  - Copy pattern from `count_vmd_events()` (lines 187-205): call `get_container_logs(since=since, tail=200)`, count occurrences
  - Change log pattern: `"Doorbell ringing"` instead of `"Motion detected from Gate"`
  - Return keys: `"call_count"` (int), `"has_calls"` (bool), `"check_window"` (str)
  - No ISAPI calls — pure Docker log parsing
  - **REFACTOR**: Verify test still passes

  **Must NOT do**:
  - Do not modify `count_vmd_events()` — it stays unchanged
  - Do not add ISAPI imports or calls

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — Docker log parsing, pattern mirroring
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Tasks 1-6, 8
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 14, 15 (isapi_health, pipeline_diagnose wrappers)
  - **Blocked By**: None

  **References**:
  - `tools/hikvision/docker_client.py:187-205` — `count_vmd_events()` — exact template to copy
  - `tools/hikvision/docker_client.py:83-106` — `get_container_logs()` — called internally
  - `tests/unit/test_iot_hikvision.py:30-112` — `TestHikvisionDockerClient` class — add new tests here

  **Acceptance Criteria**:
  - [ ] `pytest tests/unit/test_iot_hikvision.py::TestHikvisionDockerClient::test_count_call_events_with_calls -v` → PASS
  - [ ] `pytest tests/unit/test_iot_hikvision.py::TestHikvisionDockerClient::test_count_call_events_no_calls -v` → PASS
  - [ ] `python -c "from tools.hikvision.docker_client import count_call_events; print('OK')"`

  **QA Scenarios**:
  ```
  Scenario: count_call_events with 3 "Doorbell ringing" entries
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/test_iot_hikvision.py::TestHikvisionDockerClient::test_count_call_events_with_calls -v --tb=short
    Expected Result: PASS, call_count=3, has_calls=True, check_window="4h"
    Evidence: .omo/evidence/task-7-call-events-success.txt

  Scenario: count_call_events with zero matching lines
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/test_iot_hikvision.py::TestHikvisionDockerClient::test_count_call_events_no_calls -v --tb=short
    Expected Result: PASS, call_count=0, has_calls=False
    Evidence: .omo/evidence/task-7-call-events-empty.txt
  ```

  **Commit**: YES
  - Message: `feat(hikvision): add count_call_events docker client function`
  - Files: `tools/hikvision/docker_client.py`, `tests/unit/test_iot_hikvision.py`

- [x] 8. `tools/hikvision/isapi_client.py` — Add `set_motion_config()` (TDD)
...
- [x] 9. `tools/iot_hikvision.py` — Add `_hikvision_get_motion_config()` wrapper + registration (TDD)
...
- [x] 10. `tools/iot_hikvision.py` — Add `_hikvision_get_event_config()` wrapper + registration (TDD)
...
- [x] 11. `tools/iot_hikvision.py` — Add `_hikvision_get_alarm_server()` wrapper + registration (TDD)
...
- [x] 12. `tools/iot_hikvision.py` — Add `_hikvision_snapshot_to_file()` wrapper + registration (TDD)

  **What to do**:
  - **RED**: Write unit tests `test_snapshot_to_file_success` (uses `tmp_path`), `test_snapshot_to_file_validation_error`
  - **GREEN**: Write `_hikvision_snapshot_to_file(filepath: str) -> str` — calls `validate_required_string(filepath, "filepath")`, then `create_isapi_client().save_snapshot(filepath=validated_path)`. Catches `ValidationError` → `VALIDATION_ERROR`, `ValueError` → `MISSING_CREDENTIALS`
  - Add `@mcp.tool()` registration `hikvision_snapshot_to_file(filepath: str)` — READ pattern (no write guard — this is a READ-level risk tool despite disk write)
  - Docstring must include `@since v1.5.0`

  **Must NOT do**:
  - Do not add `check_write_enabled()` — manifest says READ risk with `side_effects: "read"`
  - Do not validate that filepath ends with `.jpg` — accept any valid path

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Tasks 9-11
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 16
  - **Blocked By**: Task 6 (`save_snapshot` ISAPI method)

  **Acceptance Criteria**:
  - [ ] `pytest tests/unit/test_iot_hikvision.py::TestHikvisionTools::test_snapshot_to_file_success -v` → PASS
  - [ ] Response includes `"filepath"` and `"size_bytes"` fields

  **QA Scenarios**:
  ```
  Scenario: snapshot_to_file writes JPEG to specified path
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/test_iot_hikvision.py::TestHikvisionTools::test_snapshot_to_file_success -v --tb=short
    Expected Result: PASS, response has success=true, filepath matches, size_bytes > 0
    Evidence: .omo/evidence/task-12-snapshot-to-file-success.txt
  ```

  **Commit**: YES (groups with 9-11)

- [x] 13. `tools/iot_hikvision.py` — Add `_hikvision_set_motion_detection()` wrapper + registration (TDD)

  **What to do**:
  - **RED**: Write unit tests `test_set_motion_detection_success`, `test_set_motion_detection_error`
  - **GREEN**: Write `_hikvision_set_motion_detection(enabled: bool | None = None, sensitivity: int | None = None) -> str` — ISAPI write pattern. Calls `client.set_motion_config(enabled=enabled, sensitivity=sensitivity)`. Returns `_success_response({"enabled": enabled, "sensitivity": sensitivity, "message": "Motion detection config updated"})` on success
  - Add `@mcp.tool()` registration `hikvision_set_motion_detection(enabled, sensitivity)` — **WRITE pattern with `check_write_enabled()`**. Catches `ValidationError` → `WRITE_DISABLED`
  - Docstring must include `WARNING: Write operation — modifies doorbell config` and `@since v1.5.0`

  **Must NOT do**:
  - Do not skip `check_write_enabled()` — this IS a write tool
  - Do not forget the `except ValidationError` handler in the registration

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — write tool with validation
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: NO — depends on Tasks 8, 9
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 16
  - **Blocked By**: Task 8 (`set_motion_config` ISAPI), Task 9 (`get_motion_config` wrapper — needed for consistent response shapes)

  **References**:
  - `tools/iot_hikvision.py:278-310` — `hikvision_open_gate` registration — WRITE tool with `check_write_enabled()` + `ValidationError` handler
  - `tools/iot_hikvision.py:105-119` — `_hikvision_open_gate()` — ISAPI write internal function pattern

  **Acceptance Criteria**:
  - [ ] `pytest tests/unit/test_iot_hikvision.py::TestHikvisionTools::test_set_motion_detection_success -v` → PASS
  - [ ] `pytest tests/unit/test_iot_hikvision.py::TestHikvisionTools::test_set_motion_detection_error -v` → PASS
  - [ ] Write guard is active: `check_write_enabled()` called in registration

  **QA Scenarios**:
  ```
  Scenario: set_motion_detection enables motion and returns success
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/test_iot_hikvision.py::TestHikvisionTools::test_set_motion_detection_success -v --tb=short
    Expected Result: PASS, response has success=true, enabled=true, message present
    Evidence: .omo/evidence/task-13-set-motion-success.txt

  Scenario: set_motion_detection returns error when ISAPI fails
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/test_iot_hikvision.py::TestHikvisionTools::test_set_motion_detection_error -v --tb=short
    Expected Result: PASS, response has success=false, error code ISAPI_ERROR
    Evidence: .omo/evidence/task-13-set-motion-error.txt
  ```

  **Commit**: YES
  - Message: `feat(hikvision): register set_motion_detection tool with write guard`
  - Files: `tools/iot_hikvision.py`

- [x] 14. `tools/iot_hikvision.py` — Add `_hikvision_isapi_health()` wrapper + registration (TDD)

  **What to do**:
  - **RED**: Write unit tests: `test_isapi_health_healthy`, `test_isapi_health_degraded`, `test_isapi_health_down`
  - **GREEN**: Write `_hikvision_isapi_health(since: str = "4h") -> str` — composite tool using `get_container_status()`, `count_vmd_events(since)`, `count_call_events(since)`
  - Health logic: `healthy` = container running AND (vmd > 0 OR calls > 0); `degraded` = running AND vmd == 0 AND calls == 0; `down` = not running
  - Issues list: container not running, no events, VMD dead
  - Add `@mcp.tool()` registration `hikvision_isapi_health(since: str = "4h")` — READ pattern
  - Docstring must note it supersedes `hikvision_check_vmd` and include `@since v1.5.0`

  **Must NOT do**:
  - Do not call ISAPI directly from the health check — use existing Docker client functions
  - Do not add `_get_recent_log_auth()` — skip auth log check (Option A from todo.md)
  - Do not make health check return `{success: false}` when unhealthy — unhealthy is a valid state

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — composite tool, Docker log aggregation
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Task 15
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 16
  - **Blocked By**: Tasks 7, 9 (`count_call_events`, `get_motion_config` wrapper)

  **Acceptance Criteria**:
  - [ ] `pytest tests/unit/test_iot_hikvision.py::TestHikvisionTools::test_isapi_health_healthy -v` → PASS
  - [ ] `pytest tests/unit/test_iot_hikvision.py::TestHikvisionTools::test_isapi_health_degraded -v` → PASS
  - [ ] `pytest tests/unit/test_iot_hikvision.py::TestHikvisionTools::test_isapi_health_down -v` → PASS
  - [ ] Response includes `overall`, `container`, `vmd`, `calls`, `issues` fields

  **QA Scenarios**:
  ```
  Scenario: isapi_health returns healthy when container running + VMD events flowing
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/test_iot_hikvision.py::TestHikvisionTools::test_isapi_health_healthy -v --tb=short
    Expected Result: PASS, overall="healthy", issues list empty
    Evidence: .omo/evidence/task-14-health-healthy.txt

  Scenario: isapi_health returns degraded when container running but zero events
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/test_iot_hikvision.py::TestHikvisionTools::test_isapi_health_degraded -v --tb=short
    Expected Result: PASS, overall="degraded", issues list non-empty
    Evidence: .omo/evidence/task-14-health-degraded.txt

  Scenario: isapi_health returns down when container not running
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/test_iot_hikvision.py::TestHikvisionTools::test_isapi_health_down -v --tb=short
    Expected Result: PASS, overall="down", issues includes container not running message
    Evidence: .omo/evidence/task-14-health-down.txt
  ```

  **Commit**: YES (groups with Task 15)
  - Message: `feat(hikvision): register isapi_health and pipeline_diagnose composite tools`
  - Files: `tools/iot_hikvision.py`

- [x] 15. `tools/iot_hikvision.py` — Add `_hikvision_pipeline_diagnose()` wrapper + registration (TDD)

  **What to do**:
  - **RED**: Write unit tests `test_pipeline_diagnose_healthy`, `test_pipeline_diagnose_degraded`
  - **GREEN**: Write `_hikvision_pipeline_diagnose() -> str` — cross-layer diagnostic across 4 layers:
    - Layer 1: `get_container_status()` → container running + ISAPI auth check (grep "Connected to doorbell" in logs)
    - Layer 2: Event counts (VMD + call) from `get_container_logs(since="1h", tail=100)`
    - Layer 3: MQTT trigger count (grep "Invoking device trigger automation" in logs)
    - Layer 4: Snapshot files on disk — check `os.path.isdir("/config/www/archive/camera_gate")`, list recent 5 files. Wrap in `try/except OSError: pass` for graceful handling when path doesn't exist
  - Health: `healthy` if zero issues, `degraded` otherwise
  - Issues list: specific per-layer diagnostics
  - Add `@mcp.tool()` registration `hikvision_pipeline_diagnose()` — READ pattern
  - Docstring must include `@since v1.5.0`

  **Must NOT do**:
  - Do not add new Docker or ISAPI calls — reuse existing functions
  - Do not crash if snapshot directory doesn't exist (`try/except OSError`)
  - Do not use absolute path `/config/www/archive/camera_gate` directly without OSError guard

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — cross-layer composite diagnostic
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Task 14
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 16
  - **Blocked By**: Tasks 7, 9

  **Acceptance Criteria**:
  - [ ] `pytest tests/unit/test_iot_hikvision.py::TestHikvisionTools::test_pipeline_diagnose_healthy -v` → PASS
  - [ ] `pytest tests/unit/test_iot_hikvision.py::TestHikvisionTools::test_pipeline_diagnose_degraded -v` → PASS
  - [ ] Response includes `overall`, `layers` (container/isapi/events/mqtt/snapshots), `issues`

  **QA Scenarios**:
  ```
  Scenario: pipeline_diagnose returns healthy with all layers OK
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/test_iot_hikvision.py::TestHikvisionTools::test_pipeline_diagnose_healthy -v --tb=short
    Expected Result: PASS, overall="healthy", issues=[], all layers present
    Evidence: .omo/evidence/task-15-pipeline-healthy.txt

  Scenario: pipeline_diagnose returns degraded with container down
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/test_iot_hikvision.py::TestHikvisionTools::test_pipeline_diagnose_degraded -v --tb=short
    Expected Result: PASS, overall="degraded", issues non-empty, container layer shows not running
    Evidence: .omo/evidence/task-15-pipeline-degraded.txt
  ```

  **Commit**: YES (groups with Task 14)

- [x] 16. `tests/unit/test_iot_hikvision.py` — Update tool registration count + add registration tests

  **What to do**:
  - Update `test_all_seven_tools_registered`: change assertion `len(hik_tools) == 7` → `len(hik_tools) == 14`
  - Rename test to `test_all_fourteen_tools_registered`
  - Add registration test for each new tool (pattern: patch internal function, call `mcp.get_tool("name")()`, assert `success: true`)
  - Add write guard test for `hikvision_set_motion_detection`: patch `check_write_enabled` with `side_effect=Exception`, assert `success: false`
  - Add exception handler test for one new tool: patch internal function with `side_effect=Exception("BOOM")`, assert `"BOOM"` in error message

  **Must NOT do**:
  - Do not modify existing registration tests beyond the count update
  - Do not remove `test_all_seven_tools_registered` — rename it

  **Recommended Agent Profile**:
  - **Category**: `quick` — test count update + boilerplate registration tests
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: NO — depends on all Wave 2 tasks
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 17, 18, 19
  - **Blocked By**: Tasks 9-15

  **References**:
  - `tests/unit/test_iot_hikvision.py:264-267` — `test_all_seven_tools_registered` — update count
  - `tests/unit/test_iot_hikvision.py:268-288` — registration test pattern
  - `tests/unit/test_iot_hikvision.py:290-302` — write guard test pattern

  **Acceptance Criteria**:
  - [ ] `pytest tests/unit/test_iot_hikvision.py::TestHikvisionToolRegistration -v` → all pass
  - [ ] Tool count assertion: 14 Hikvision tools registered

  **QA Scenarios**:
  ```
  Scenario: 14 Hikvision tools registered in mock MCP
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/test_iot_hikvision.py::TestHikvisionToolRegistration::test_all_fourteen_tools_registered -v --tb=short
    Expected Result: PASS, 14 tools starting with "hikvision_"
    Evidence: .omo/evidence/task-16-registration-count.txt

  Scenario: set_motion_detection write guard returns WRITE_DISABLED error
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/test_iot_hikvision.py::TestHikvisionToolRegistration::test_set_motion_detection_write_guard -v --tb=short
    Expected Result: PASS, response success=false, error code "WRITE_DISABLED"
    Evidence: .omo/evidence/task-16-write-guard.txt
  ```

  **Commit**: YES
  - Message: `test(hikvision): update tool registration count to 14`
  - Files: `tests/unit/test_iot_hikvision.py`

- [x] 17. `tests/integration/test_hikvision_tools.py` — Add 5 integration tests

  **What to do**:
  - Add test methods to `TestHikvisionIntegration` class:
    - `test_get_motion_config_returns_config` — calls `hikvision_get_motion_config`, asserts `success: true`, `"enabled"` in data
    - `test_get_event_config_returns_triggers` — asserts `success: true`, `"triggers"` in data
    - `test_get_alarm_server_returns_config` — asserts `success: true`
    - `test_isapi_health_returns_status` — asserts `success: true`, `"overall"` in data
    - `test_pipeline_diagnose_returns_layers` — asserts `success: true`, `"layers"` in data, `"issues"` in data
  - Use existing `_get_result(mcp_client, tool_name)` helper
  - Skip condition already exists in the file — new tests inherit it
  - Do NOT test `hikvision_set_motion_detection` (write) or `hikvision_snapshot_to_file` (filesystem side-effect) in integration

  **Must NOT do**:
  - Do not test write tools against real hardware
  - Do not add new skip conditions — reuse existing `pytestmark`

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Tasks 18, 19
  - **Parallel Group**: Wave 3
  - **Blocks**: F1-F4
  - **Blocked By**: Task 16

  **References**:
  - `tests/integration/test_hikvision_tools.py:41-76` — existing integration test patterns
  - `tests/integration/test_hikvision_tools.py:31-38` — `_get_result()` helper

  **Acceptance Criteria**:
  - [ ] All 5 new tests pass or skip cleanly (doorbell unreachable → skip, not fail)

  **QA Scenarios**:
  ```
  Scenario: All 5 integration tests pass against real doorbell (or skip cleanly)
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/integration/test_hikvision_tools.py -v --tb=short
    Expected Result: Either 5 pass (doorbell reachable) or 5 skip (doorbell unreachable). 0 failures.
    Evidence: .omo/evidence/task-17-integration.txt
  ```

  **Commit**: YES
  - Message: `test(hikvision): add integration tests for 5 new diagnostic tools`
  - Files: `tests/integration/test_hikvision_tools.py`

- [x] 18. `tests/smoke/test_hikvision_diagnostic.py` — Create smoke test file

  **What to do**:
  - Create new file `tests/smoke/test_hikvision_diagnostic.py`
  - Follow existing smoke test patterns:
    - `_server_running()` socket check at module level
    - `pytestmark = pytest.mark.skipif(not _server_running(), reason=...)`
    - Tests call REST API via `requests.post(f"{REST_API_URL}/api/tools/{tool_name}", json={})`
  - Test all 7 new tools for `success` field presence in response
  - Test tool count: `GET /api/tools`, assert 14 `hikvision_*` tools

  **Must NOT do**:
  - Do not place `pytestmark` in `conftest.py` — must be in the test file per [RULE: TEST-SKIP-4]
  - Do not import server modules — HTTP only

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — new file creation with established pattern
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Tasks 17, 19
  - **Parallel Group**: Wave 3
  - **Blocks**: F1-F4
  - **Blocked By**: Task 16

  **References**:
  - `tests/smoke/test_critical_tools.py` — smoke test pattern to mirror
  - `tests/smoke/conftest.py` — `REST_API_URL`, `server_is_running` pattern

  **Acceptance Criteria**:
  - [ ] `pytest tests/smoke/test_hikvision_diagnostic.py -v` → all pass or skip cleanly

  **QA Scenarios**:
  ```
  Scenario: All 7 new tools return success field via REST API
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/smoke/test_hikvision_diagnostic.py -v --tb=short
    Expected Result: All tests pass (server running) or skip (server not running). 0 failures.
    Evidence: .omo/evidence/task-18-smoke.txt
  ```

  **Commit**: YES
  - Message: `test(hikvision): add smoke tests for diagnostic tools`
  - Files: `tests/smoke/test_hikvision_diagnostic.py`

- [x] 19. `tests/e2e/test_hikvision_workflow.py` — Add 3 E2E tests + update tool count

  **What to do**:
  - Add test methods to `TestHikvisionE2E` class:
    - `test_get_motion_config_via_rest` — calls `_call_tool("hikvision_get_motion_config")`, asserts `result["success"] is True`
    - `test_get_event_config_via_rest` — same pattern
    - `test_isapi_health_via_rest` — same pattern
  - Update `test_tools_include_hikvision`: change assertion `len(hik_tools) == 7` → `len(hik_tools) == 14`
  - Note: E2E tests access `data["result"]["success"]` (REST wraps in `"result"` key), NOT `data["success"]`

  **Must NOT do**:
  - Do not test write tools in E2E
  - Do not change existing test patterns

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Tasks 17, 18
  - **Parallel Group**: Wave 3
  - **Blocks**: F1-F4
  - **Blocked By**: Task 16

  **References**:
  - `tests/e2e/test_hikvision_workflow.py:28-66` — existing E2E test patterns
  - `tests/e2e/test_hikvision_workflow.py:16-25` — `_call_tool()` helper
  - `tests/e2e/test_hikvision_workflow.py:7-13` — `pytestmark` list pattern

  **Acceptance Criteria**:
  - [ ] `pytest tests/e2e/test_hikvision_workflow.py -v` → all pass or skip cleanly
  - [ ] Tool count assertion: 14 Hikvision tools

  **QA Scenarios**:
  ```
  Scenario: E2E tests pass against running server (or skip cleanly)
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/e2e/test_hikvision_workflow.py -v --tb=short
    Expected Result: All pass or skip, 0 failures. Tool count = 14.
    Evidence: .omo/evidence/task-19-e2e.txt
  ```

  **Commit**: YES
  - Message: `test(hikvision): add E2E tests for diagnostic tools`
  - Files: `tests/e2e/test_hikvision_workflow.py`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE.
> Get explicit user "okay" before completing.

- [x] F1. **Plan Compliance Audit** — `oracle`
- [x] F2. **Code Quality Review** — `unspecified-high`
- [x] F3. **Real Manual QA** — `unspecified-high`
- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff. Verify 1:1 mapping. Check "Must NOT do" compliance. Detect cross-task contamination. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **1-2**: `chore(hikvision): add 7 new tool manifests and update imports` — `tools/constants.py`, `tools/iot_hikvision.py`
- **3**: `feat(hikvision): add get_motion_config ISAPI client method` — `tools/hikvision/isapi_client.py`, `tests/unit/test_iot_hikvision.py`
- **4**: `feat(hikvision): add get_event_triggers ISAPI client method` — `tools/hikvision/isapi_client.py`, `tests/unit/test_iot_hikvision.py`
- **5**: `feat(hikvision): add get_alarm_server ISAPI client method` — `tools/hikvision/isapi_client.py`, `tests/unit/test_iot_hikvision.py`
- **6**: `feat(hikvision): add save_snapshot ISAPI client method` — `tools/hikvision/isapi_client.py`, `tests/unit/test_iot_hikvision.py`
- **7**: `feat(hikvision): add count_call_events docker client function` — `tools/hikvision/docker_client.py`, `tests/unit/test_iot_hikvision.py`
- **8**: `feat(hikvision): add set_motion_config ISAPI client method` — `tools/hikvision/isapi_client.py`, `tests/unit/test_iot_hikvision.py`
- **9-12**: `feat(hikvision): register get_motion_config/get_event_config/get_alarm_server/snapshot_to_file tools` — `tools/iot_hikvision.py`
- **13**: `feat(hikvision): register set_motion_detection tool with write guard` — `tools/iot_hikvision.py`
- **14-15**: `feat(hikvision): register isapi_health and pipeline_diagnose composite tools` — `tools/iot_hikvision.py`
- **16**: `test(hikvision): update tool registration count to 14` — `tests/unit/test_iot_hikvision.py`
- **17**: `test(hikvision): add integration tests for 5 new diagnostic tools` — `tests/integration/test_hikvision_tools.py`
- **18**: `test(hikvision): add smoke tests for diagnostic tools` — `tests/smoke/test_hikvision_diagnostic.py`
- **19**: `test(hikvision): add E2E tests for diagnostic tools` — `tests/e2e/test_hikvision_workflow.py`

---

## Success Criteria

### Verification Commands
```bash
# Unit tests (zero I/O, must pass without credentials)
pytest tests/unit/test_iot_hikvision.py -v --tb=short  # Expected: 60+ pass, 0 fail

# All unit tests (no regressions)
pytest tests/unit/ -v --tb=short  # Expected: all pass

# Integration tests (skip if doorbell unreachable)
pytest tests/integration/test_hikvision_tools.py -v  # Expected: pass or skip

# Smoke tests (skip if server not running)
pytest tests/smoke/ -v  # Expected: pass or skip

# E2E tests (skip if server not running)
pytest tests/e2e/ -v  # Expected: pass or skip

# Tool count verification
python -c "from tools.constants import TOOL_MANIFESTS; hik = [k for k in TOOL_MANIFESTS if k.startswith('hikvision_')]; assert len(hik) == 14, f'Expected 14, got {len(hik)}'"
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All 74 existing tests pass unchanged
- [ ] 14 Hikvision tools registered (7 existing + 7 new)
- [ ] `hikvision_check_vmd` behavior unchanged (only docstring updated)
- [ ] No regressions in any test suite

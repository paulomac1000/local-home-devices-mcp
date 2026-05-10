"""Unit tests for constants module — response helpers, logging, manifests."""

import json

import pytest

from tools.constants import (
    _build_meta,
    _error_response,
    _error_response_extended,
    _success_response,
    get_logger,
    get_tool_manifest,
    setup_logging,
)

pytestmark = pytest.mark.unit


class TestResponseHelpers:
    """Tests for response helper functions."""

    def test_success_response_returns_valid_json(self):
        result = _success_response({"key": "value"})
        data = json.loads(result)
        assert data["success"] is True
        assert data["data"] == {"key": "value"}
        assert "_meta" in data
        assert "request_id" in data["_meta"]
        assert data["_meta"]["tool_version"] == "1.2.0"

    def test_success_response_with_list(self):
        result = _success_response([1, 2, 3])
        data = json.loads(result)
        assert data["success"] is True
        assert data["data"] == [1, 2, 3]

    def test_error_response_returns_valid_json(self):
        result = _error_response("Something went wrong")
        data = json.loads(result)
        assert data["success"] is False
        assert data["error"] == "Something went wrong"
        assert "_meta" in data

    def test_error_response_extended_full(self):
        result = _error_response_extended(
            code="TIMEOUT",
            message="Device did not respond",
            retryable=True,
            suggestion="Check power and retry",
            available_names=["Device_A", "Device_B"],
        )
        data = json.loads(result)
        assert data["success"] is False
        err = data["error"]
        assert err["code"] == "TIMEOUT"
        assert err["message"] == "Device did not respond"
        assert err["retryable"] is True
        assert err["suggestion"] == "Check power and retry"
        assert err["available_names"] == ["Device_A", "Device_B"]

    def test_error_response_extended_minimal(self):
        result = _error_response_extended(code="INVALID_PARAM", message="Bad input")
        data = json.loads(result)
        assert data["success"] is False
        err = data["error"]
        assert err["code"] == "INVALID_PARAM"
        assert err["message"] == "Bad input"
        assert err["retryable"] is False
        assert "suggestion" not in err

    def test_build_meta_has_uuid_and_version(self):
        meta = _build_meta()
        assert "request_id" in meta
        assert len(meta["request_id"]) == 36  # UUID length
        assert meta["tool_version"] == "1.2.0"

    def test_build_meta_with_extra(self):
        meta = _build_meta(cached=True, duration_ms=42)
        assert meta["cached"] is True
        assert meta["duration_ms"] == 42


class TestLogging:
    """Tests for logging setup."""

    def test_setup_logging_creates_logger(self):
        setup_logging()
        logger = get_logger("test")
        assert logger.name == "iot_mcp.test"

    def test_setup_logging_idempotent(self):
        setup_logging()
        setup_logging()
        logger = get_logger("idempotent")
        assert logger.name == "iot_mcp.idempotent"

    def test_get_logger_returns_named_logger(self):
        log = get_logger("server")
        assert log.name == "iot_mcp.server"


class TestToolManifest:
    """Tests for tool manifest accessor."""

    def test_get_tool_manifest_found(self):
        manifest = get_tool_manifest("iot_discover_devices")
        assert manifest is not None
        assert manifest["risk"] == "READ"
        assert manifest["timeout_ms"] == 120000
        assert manifest["determinism"] == "env-dependent"

    def test_get_tool_manifest_missing(self):
        manifest = get_tool_manifest("nonexistent_tool")
        assert manifest is None

    def test_all_manifests_have_required_fields(self):
        required = {
            "name",
            "version",
            "risk",
            "side_effects",
            "idempotent",
            "retryable",
            "concurrent_safe",
            "timeout_ms",
            "requires_confirmation",
            "determinism",
            "latency",
            "cost",
        }
        from tools.constants import TOOL_MANIFESTS

        for tool_name, manifest in TOOL_MANIFESTS.items():
            missing = required - set(manifest.keys())
            assert not missing, f"Tool '{tool_name}' missing fields: {missing}"

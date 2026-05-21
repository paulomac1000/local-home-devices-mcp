"""Unit tests for IoT capability introspection tool."""

import json
from unittest.mock import patch

import pytest

from tools.iot_meta import _describe_capabilities, register_iot_meta_tools

pytestmark = pytest.mark.unit


class TestDescribeCapabilities:
    """Tests for the capability introspection function."""

    def test_returns_valid_json(self):
        result = _describe_capabilities()
        data = json.loads(result)
        assert data["success"] is True
        assert data["data"]["server"] == "IoT-Observer"
        assert "schema_version" in data["data"]
        assert "transports" in data["data"]
        assert "tool_count" in data["data"]
        assert "tools" in data["data"]
        assert isinstance(data["data"]["tools"], list)
        assert len(data["data"]["tools"]) == data["data"]["tool_count"]

    def test_every_tool_has_required_manifest_fields(self):
        result = _describe_capabilities()
        data = json.loads(result)
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
            "impact",
            "privacy",
            "reversible",
        }
        for tool in data["data"]["tools"]:
            missing = required - set(tool.keys())
            assert not missing, f"Tool '{tool['name']}' missing: {missing}"

    def test_tools_are_sorted_by_name(self):
        result = _describe_capabilities()
        data = json.loads(result)
        names = [t["name"] for t in data["data"]["tools"]]
        assert names == sorted(names)


class TestRegistrationWrappers:
    """Tests for MCP tool registration wrappers."""

    def test_registration_creates_one_tool(self, mock_mcp):
        register_iot_meta_tools(mock_mcp)
        assert "describe_iot_capabilities" in mock_mcp._tools

    def test_describe_iot_capabilities_wrapper(self, mock_mcp):
        register_iot_meta_tools(mock_mcp)
        fn = mock_mcp.get_tool("describe_iot_capabilities")
        result = fn()
        data = json.loads(result)
        assert data["success"] is True

    def test_describe_iot_capabilities_exception_handler(self, mock_mcp):
        register_iot_meta_tools(mock_mcp)
        fn = mock_mcp.get_tool("describe_iot_capabilities")
        with patch("tools.iot_meta._describe_capabilities", side_effect=RuntimeError("boom")):
            result = fn()
            data = json.loads(result)
            assert data["success"] is False
            assert "boom" in data["error"]["message"]

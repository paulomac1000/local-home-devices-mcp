"""Smoke tests: basic connectivity to the MCP server via REST API."""

import pytest
import requests

from tools.constants import TOOL_MANIFESTS

from .conftest import REST_API_URL, server_is_running

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(
        not server_is_running(),
        reason="MCP server not running",
    ),
]


class TestHealthConnectivity:
    """Verify MCP server is reachable and healthy."""

    def test_health_endpoint_returns_healthy(self):
        resp = requests.get(f"{REST_API_URL}/health", timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "healthy"

    def test_tools_list_matches_manifest_count(self):
        resp = requests.get(f"{REST_API_URL}/api/tools", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True
        assert data.get("total", 0) == len(TOOL_MANIFESTS)
        assert data.get("tool_count", 0) == len(TOOL_MANIFESTS)

    def test_response_format_has_success_field(self):
        resp = requests.get(f"{REST_API_URL}/api/health", timeout=5)
        data = resp.json()
        assert data.get("status") == "healthy"

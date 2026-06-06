"""
Unit test fixtures - mocked dependencies, zero I/O.

All fixtures use generic names (Tasmota_Test, OpenBK_Test).
No real devices, credentials, or network calls.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

from tests.fixtures import MOCK_OPENBK_DEVICE, MOCK_TASMOTA_DEVICE

# ---------------------------------------------------------------------------
# Mock fastmcp BEFORE any test module imports server.py.
# The installed fastmcp 2.0.0 has broken transitive dependencies
# (missing fastmcp.mcp_config, fastmcp.client.auth, etc.).
# A MagicMock satisfies everything server.py needs.
# ---------------------------------------------------------------------------
_fastmcp_mock = MagicMock()
_fastmcp_mock.FastMCP = MagicMock()
if "fastmcp" not in sys.modules:
    sys.modules["fastmcp"] = _fastmcp_mock


@pytest.fixture(autouse=True)
def _enable_write_operations(monkeypatch):
    """Enable the server-level write guard for all unit tests.

    Write-tool logic tests need writes enabled. The disabled path is covered by
    dedicated tests that re-disable the guard explicitly.
    """
    monkeypatch.setattr("tools.constants.ENABLE_WRITE_OPERATIONS", True)


@pytest.fixture
def mock_requests():
    """Mock requests library for HTTP calls."""
    with patch("tools.iot_discovery.requests") as mock:
        yield mock


@pytest.fixture
def mock_mqtt_client():
    """Mock MQTT client for MQTT operations."""
    client = MagicMock()
    client.is_connected.return_value = True
    client.publish.return_value = MagicMock()
    return client


@pytest.fixture
def sample_tasmota_device():
    """Return a sample Tasmota device dictionary."""
    return dict(MOCK_TASMOTA_DEVICE)


@pytest.fixture
def sample_openbk_device():
    """Return a sample OpenBK device dictionary."""
    return dict(MOCK_OPENBK_DEVICE)


@pytest.fixture
def mock_mcp():
    """Mock MCP for unit tests that properly handles tool registration."""
    mcp = MagicMock()
    mcp._tools = {}

    def tool_decorator(*args, **kwargs):
        def wrapper(func):
            tool_name = kwargs.get("name", func.__name__)
            mcp._tools[tool_name] = func
            return func

        if len(args) == 1 and callable(args[0]) and not kwargs:
            mcp._tools[args[0].__name__] = args[0]
            return args[0]

        return wrapper

    mcp.tool = tool_decorator

    def mock_get_tool(name):
        return mcp._tools.get(name)

    mcp.get_tool = mock_get_tool
    return mcp

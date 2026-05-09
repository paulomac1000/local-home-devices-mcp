"""Integration test conftest — real MQTT broker + devices, skip if not configured."""

import asyncio
import inspect
import os
from pathlib import Path

import pytest

env_paths = [Path("/app/.env"), Path(".env")]
for env_path in env_paths:
    if env_path.exists():
        try:
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        except Exception:
            pass

MQTT_BROKER = os.getenv("MQTT_BROKER", "")

_PLACEHOLDER_VALUES = {"", "your_broker_here", "192.168.0.101"}

iot_configured = bool(MQTT_BROKER) and MQTT_BROKER not in _PLACEHOLDER_VALUES


def _run_async(func, *args, **kwargs):
    """Run an async function from sync context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is None:
        return asyncio.run(func(*args, **kwargs))
    else:
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as ex:
            return ex.submit(asyncio.run, func(*args, **kwargs)).result()


class MCPWrapper:
    """Simple wrapper to call tools on a FastMCP instance."""

    def __init__(self, mcp):
        self._mcp = mcp

    def call_tool(self, tool_name, **kwargs):
        """Look up and execute a registered tool by name."""
        tools = (
            self._mcp._tool_manager._tools
            if hasattr(self._mcp, "_tool_manager")
            else getattr(self._mcp, "_tools", {})
        )
        tool = tools.get(tool_name)
        if tool is None:
            available = list(tools.keys())
            raise ValueError(f"Tool '{tool_name}' not found among {available}")
        fn = getattr(tool, "fn", tool)
        if inspect.iscoroutinefunction(fn):
            return _run_async(fn, **kwargs)
        return fn(**kwargs)


@pytest.fixture(scope="session")
def mcp_client():
    """Create real MCP server and return a call_tool wrapper."""
    from fastmcp import FastMCP

    from tools.iot_control import register_iot_control_tools
    from tools.iot_devices import register_iot_device_tools
    from tools.iot_discovery import register_iot_discovery_tools
    from tools.iot_mqtt import register_iot_mqtt_tools

    mcp = FastMCP("IoT-Integration-Test")

    register_iot_device_tools(mcp)
    register_iot_discovery_tools(mcp)
    register_iot_control_tools(mcp)
    register_iot_mqtt_tools(mcp)

    return MCPWrapper(mcp)


@pytest.fixture(scope="module")
def iot_configured_flag():
    """Returns True if MQTT broker is configured."""
    return iot_configured

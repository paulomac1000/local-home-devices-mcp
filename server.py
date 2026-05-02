#!/usr/bin/env python3
"""
IoT MCP Server

Model Context Protocol server for IoT device management.
Supports OpenBK (OpenBeken) and Tasmota devices.

Architecture:
- Port 9100: Health check (lightweight HTTP server)
- Port 9101: MCP SSE transport - /sse, /messages
- Port 9102: REST API (Starlette) - /api/*
"""

import inspect
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional

from fastmcp import FastMCP

from tools.iot_control import register_iot_control_tools
from tools.iot_devices import register_iot_device_tools
from tools.iot_discovery import register_iot_discovery_tools
from tools.iot_mqtt import register_iot_mqtt_tools

# =============================================================================
# HEALTH CHECK SERVER (port 9100)
# =============================================================================

HEALTH_STATE = {"status": "starting", "last_heartbeat": time.time()}


class HealthHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler for health check endpoint."""

    def do_GET(self) -> None:
        """Handle GET requests."""
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(HEALTH_STATE).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress request logging."""
        pass


def start_health_server(port: int = 9100) -> HTTPServer:
    """Start lightweight HTTP server for health checks.

    Args:
        port: Port number to listen on.

    Returns:
        The HTTP server instance.
    """
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    threading.Thread(
        target=server.serve_forever, daemon=True, name="HealthServer"
    ).start()
    print(f"[health] HTTP health endpoint started on port {port}")
    return server


# =============================================================================
# CONFIGURATION
# =============================================================================

MQTT_BROKER = os.getenv("MQTT_BROKER", "192.168.0.101")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MCP_SSE_PORT = int(os.getenv("MCP_SSE_PORT", "9101"))
REST_API_PORT = int(os.getenv("REST_API_PORT", "9102"))
START_IP = os.getenv("START_IP", "192.168.0.1")
END_IP = os.getenv("END_IP", "192.168.0.254")

# Build default network range for discovery
_default_octets = START_IP.rsplit(".", 1)[0]
DEFAULT_NETWORK_RANGE = os.getenv("NETWORK_RANGE", f"{_default_octets}.0/24")

# =============================================================================
# INITIALIZE MCP SERVER
# =============================================================================

mcp = FastMCP("IoT-Observer")

# =============================================================================
# REGISTER ALL TOOLS
# =============================================================================

register_iot_device_tools(mcp)
register_iot_discovery_tools(mcp)
register_iot_control_tools(mcp)
register_iot_mqtt_tools(mcp)


# =============================================================================
# TOOL HELPERS
# =============================================================================


def get_all_tools() -> Dict[str, Any]:
    """Return a dictionary of all registered tools."""
    if hasattr(mcp, "_tool_manager") and hasattr(mcp._tool_manager, "_tools"):
        return mcp._tool_manager._tools  # type: ignore[union-attr]
    if hasattr(mcp, "_tools"):
        return mcp._tools  # type: ignore[return-value]
    return {}


def get_tool(name: str) -> Optional[Any]:
    """Return tool by name if available."""
    return get_all_tools().get(name)


def get_tool_count() -> int:
    """Return the number of registered tools."""
    return len(get_all_tools())


tool_count = get_tool_count()


# =============================================================================
# REST API (Starlette on separate port 9102)
# =============================================================================


def create_rest_app():
    """Create REST API application for tools (alternative access, not MCP)."""
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def health(request):
        return JSONResponse(
            {
                "status": "healthy",
                "server": "IoT-Observer",
                "version": "1.1.0",
                "tools_registered": get_tool_count(),
                "endpoints": {
                    "mcp_sse": f"http://0.0.0.0:{MCP_SSE_PORT}/sse",
                    "mcp_messages": f"http://0.0.0.0:{MCP_SSE_PORT}/messages",
                    "rest_api": f"http://0.0.0.0:{REST_API_PORT}/api/",
                },
            }
        )

    async def list_tools_endpoint(request):
        tools = get_all_tools()
        tool_list = []
        for name, tool in tools.items():
            desc = None
            if hasattr(tool, "description") and tool.description:
                desc = tool.description
            elif (
                hasattr(tool, "fn")
                and hasattr(tool.fn, "__doc__")
                and tool.fn.__doc__
            ):
                desc = tool.fn.__doc__.strip().split("\n")[0]
            tool_list.append({"name": name, "description": desc})
        return JSONResponse(
            {
                "success": True,
                "total": len(tool_list),
                "tools": sorted(tool_list, key=lambda x: x["name"]),
            }
        )

    async def call_tool_endpoint(request):
        tool_name = request.path_params.get("tool_name", "")

        try:
            body = await request.body()
            args = json.loads(body) if body else {}
        except json.JSONDecodeError:
            args = {}
        except Exception:
            args = {}

        tool = get_tool(tool_name)

        if tool is None:
            all_tool_names = list(get_all_tools().keys())
            return JSONResponse(
                {
                    "success": False,
                    "error": f"Tool '{tool_name}' not found",
                    "available_tools": sorted(all_tool_names)[:30],
                    "total_tools": len(all_tool_names),
                },
                status_code=404,
            )

        try:
            if hasattr(tool, "fn") and callable(tool.fn):
                fn = tool.fn
            elif callable(tool):
                fn = tool
            else:
                return JSONResponse(
                    {
                        "success": False,
                        "error": f"Tool '{tool_name}' is not callable",
                    },
                    status_code=500,
                )

            if inspect.iscoroutinefunction(fn):
                result = await fn(**args)
            else:
                result = fn(**args)

            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    pass

            return JSONResponse(
                {"success": True, "tool": tool_name, "result": result}
            )

        except TypeError as exc:
            return JSONResponse(
                {
                    "success": False,
                    "error": f"Invalid arguments: {exc}",
                    "tool": tool_name,
                },
                status_code=400,
            )
        except Exception as exc:
            return JSONResponse(
                {
                    "success": False,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "tool": tool_name,
                },
                status_code=500,
            )

    routes = [
        Route("/health", endpoint=health, methods=["GET"]),
        Route("/api/health", endpoint=health, methods=["GET"]),
        Route("/api/tools", endpoint=list_tools_endpoint, methods=["GET"]),
        Route(
            "/api/tools/{tool_name}",
            endpoint=call_tool_endpoint,
            methods=["POST"],
        ),
    ]

    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
    ]

    return Starlette(routes=routes, middleware=middleware)


def run_rest_api() -> None:
    """Start REST API in a separate thread."""
    import uvicorn

    app = create_rest_app()
    print(f"[rest] REST API started on port {REST_API_PORT}")
    uvicorn.run(
        app, host="0.0.0.0", port=REST_API_PORT, log_level="warning"
    )


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    # 1. Start health check server (port 9100)
    start_health_server(port=9100)
    HEALTH_STATE["status"] = "healthy"
    HEALTH_STATE["last_heartbeat"] = time.time()

    print("[server] " + "=" * 50)
    print("[server] IoT-Observer MCP Server")
    print("[server] " + "=" * 50)
    print(f"[server] MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"[server] Network Range: {START_IP} - {END_IP}")
    print(f"[server] Scan CIDR: {DEFAULT_NETWORK_RANGE}")
    print("[server] Device Cache: /app/data/discovered_devices.json")
    print(f"[server] Registered tools: {tool_count}")
    print("[server] " + "-" * 50)

    # 2. Start REST API in a separate thread (port 9102)
    rest_thread = threading.Thread(
        target=run_rest_api, daemon=True, name="RestAPI"
    )
    rest_thread.start()

    print("[server] Endpoints:")
    print("[server]   Health:      http://0.0.0.0:9100/health")
    print(f"[server]   MCP SSE:     http://0.0.0.0:{MCP_SSE_PORT}/sse")
    print(f"[server]   MCP MSG:     http://0.0.0.0:{MCP_SSE_PORT}/messages")
    print(f"[server]   REST API:    http://0.0.0.0:{REST_API_PORT}/api/")
    print("[server] " + "=" * 50)

    # 3. Start MCP SSE server (port 9101) - BLOCKING!
    print(f"[server] Starting MCP SSE transport on port {MCP_SSE_PORT}...")
    mcp.run(transport="sse", host="0.0.0.0", port=MCP_SSE_PORT)

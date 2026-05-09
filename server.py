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
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from fastmcp import FastMCP

from tools.constants import (
    ALLOW_PUBLIC_BIND,
    BIND_HOST,
    DEFAULT_NETWORK_RANGE,
    END_IP,
    HEALTH_CHECK_PORT,
    MCP_SSE_PORT,
    MQTT_BROKER,
    MQTT_PORT,
    REST_API_PORT,
    START_IP,
    TOOL_MANIFESTS,
    TOOLS_VERSION,
)
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
    server = HTTPServer((BIND_HOST, port), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True, name="HealthServer").start()
    print(f"[health] HTTP health endpoint started on port {port}", file=sys.stderr)
    return server


# =============================================================================
# CONFIGURATION
# =============================================================================

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


def get_all_tools() -> dict[str, Any]:
    """Return a dictionary of all registered tools."""
    if hasattr(mcp, "_tool_manager") and hasattr(mcp._tool_manager, "_tools"):
        return mcp._tool_manager._tools  # type: ignore[union-attr]
    if hasattr(mcp, "_tools"):
        return mcp._tools  # type: ignore[return-value]
    return {}


def get_tool(name: str) -> Any | None:
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
                "version": TOOLS_VERSION,
                "tools_registered": get_tool_count(),
                "endpoints": {
                    "mcp_sse": f"http://{BIND_HOST}:{MCP_SSE_PORT}/sse",
                    "mcp_messages": f"http://{BIND_HOST}:{MCP_SSE_PORT}/messages",
                    "rest_api": f"http://{BIND_HOST}:{REST_API_PORT}/api/",
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
            elif hasattr(tool, "fn") and hasattr(tool.fn, "__doc__") and tool.fn.__doc__:
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

            return JSONResponse({"success": True, "tool": tool_name, "result": result})

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

    async def tool_manifest_endpoint(request):
        tool_name = request.path_params.get("tool_name", "")
        manifest = TOOL_MANIFESTS.get(tool_name)
        if manifest is None:
            return JSONResponse(
                {"success": False, "error": f"Tool '{tool_name}' not found"},
                status_code=404,
            )
        return JSONResponse({"success": True, "data": manifest})

    routes = [
        Route("/health", endpoint=health, methods=["GET"]),
        Route("/api/health", endpoint=health, methods=["GET"]),
        Route("/api/tools", endpoint=list_tools_endpoint, methods=["GET"]),
        Route(
            "/api/tools/{tool_name}",
            endpoint=call_tool_endpoint,
            methods=["POST"],
        ),
        Route(
            "/api/tools/{tool_name}/manifest",
            endpoint=tool_manifest_endpoint,
            methods=["GET"],
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
    print(f"[rest] REST API started on port {REST_API_PORT}", file=sys.stderr)
    uvicorn.run(app, host=BIND_HOST, port=REST_API_PORT, log_level="warning")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    # Guard: public binding requires explicit confirmation
    if BIND_HOST == "0.0.0.0" and not ALLOW_PUBLIC_BIND:
        print(
            "[CRITICAL] Binding to 0.0.0.0 without ALLOW_PUBLIC_BIND=1. "
            "Set ALLOW_PUBLIC_BIND=1 to confirm.",
            file=sys.stderr,
        )
        sys.exit(1)
    if BIND_HOST == "0.0.0.0":
        print(
            "[CRITICAL] Server bound to 0.0.0.0 — tools are exposed to the network.",
            file=sys.stderr,
        )

    # 1. Start health check server (port 9100)
    start_health_server(port=HEALTH_CHECK_PORT)
    HEALTH_STATE["status"] = "healthy"
    HEALTH_STATE["last_heartbeat"] = time.time()

    print("[server] " + "=" * 50, file=sys.stderr)
    print("[server] IoT-Observer MCP Server", file=sys.stderr)
    print("[server] " + "=" * 50, file=sys.stderr)
    print(f"[server] MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}", file=sys.stderr)
    print(f"[server] Network Range: {START_IP} - {END_IP}", file=sys.stderr)
    print(f"[server] Scan CIDR: {DEFAULT_NETWORK_RANGE}", file=sys.stderr)
    print("[server] Device Cache: /app/data/discovered_devices.json", file=sys.stderr)
    print(f"[server] Registered tools: {tool_count}", file=sys.stderr)
    print("[server] " + "-" * 50, file=sys.stderr)

    # 2. Start REST API in a separate thread (port 9102)
    rest_thread = threading.Thread(target=run_rest_api, daemon=True, name="RestAPI")
    rest_thread.start()

    print("[server] Endpoints:", file=sys.stderr)
    print(f"[server]   Health:      http://{BIND_HOST}:{HEALTH_CHECK_PORT}/health", file=sys.stderr)
    print(f"[server]   MCP SSE:     http://{BIND_HOST}:{MCP_SSE_PORT}/sse", file=sys.stderr)
    print(f"[server]   MCP MSG:     http://{BIND_HOST}:{MCP_SSE_PORT}/messages", file=sys.stderr)
    print(f"[server]   REST API:    http://{BIND_HOST}:{REST_API_PORT}/api/", file=sys.stderr)
    print("[server] " + "=" * 50, file=sys.stderr)

    # 3. Start MCP SSE server (port 9101) - BLOCKING!
    print(f"[server] Starting MCP SSE transport on port {MCP_SSE_PORT}...", file=sys.stderr)
    mcp.run(transport="sse", host=BIND_HOST, port=MCP_SSE_PORT)

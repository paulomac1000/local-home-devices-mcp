# mypy: disable-error-code="untyped-decorator"
"""
IoT Capability Introspection Tool

Exposes the tool catalog and manifests over the MCP transport itself, so that
agents connected over pure SSE can inspect capability metadata without invoking
each tool. The REST /api/tools/{name}/manifest endpoint is unreachable for such
agents — this tool closes that gap.
"""

from typing import Any

from tools.constants import (
    TOOL_MANIFESTS,
    TOOLS_VERSION,
    _error_response_extended,
    _success_response,
    increment_tool_count,
    inject_tool_risk_prefix,
    start_tool_context,
)

__all__ = ["register_iot_meta_tools", "_describe_capabilities"]


def _describe_capabilities() -> str:
    """Return the full tool catalog with manifests and supported transports.

    Returns:
        JSON string with schema version, transports and per-tool manifests.
    """
    return _success_response(
        {
            "server": "IoT-Observer",
            "schema_version": TOOLS_VERSION,
            "transports": ["sse", "rest"],
            "tool_count": len(TOOL_MANIFESTS),
            "tools": [TOOL_MANIFESTS[name] for name in sorted(TOOL_MANIFESTS)],
        }
    )


def register_iot_meta_tools(mcp: Any) -> None:
    """Register IoT capability introspection tools with the MCP server."""

    @mcp.tool()
    @inject_tool_risk_prefix
    def describe_iot_capabilities() -> str:
        """Describe all IoT tools, their manifests and supported transports.

        Use this to inspect tool capability metadata (risk, side effects,
        timeouts, confirmation requirements) without invoking any tool.

        Returns:
            JSON with the full tool catalog and manifests.

        @since v1.2.0
        """
        try:
            start_tool_context()
            increment_tool_count("describe_iot_capabilities")
            return _describe_capabilities()
        except Exception as exc:
            return _error_response_extended(code="INTERNAL_ERROR", message=str(exc))

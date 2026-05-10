import collections
import json
import logging
import os
import sys
import threading
import uuid
from typing import Any

# =============================================================================
# ENVIRONMENT CONFIGURATION
# =============================================================================

MQTT_BROKER = os.getenv("MQTT_BROKER", "192.168.0.101")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
START_IP = os.getenv("START_IP", "192.168.0.1")
END_IP = os.getenv("END_IP", "192.168.0.254")
NETWORK_RANGE = os.getenv("NETWORK_RANGE")
MCP_SSE_PORT = int(os.getenv("MCP_SSE_PORT", "9101"))
REST_API_PORT = int(os.getenv("REST_API_PORT", "9102"))

HEALTH_CHECK_PORT = int(os.getenv("HEALTH_CHECK_PORT", "9100"))

BIND_HOST = os.getenv("BIND_HOST", "127.0.0.1")
ALLOW_PUBLIC_BIND = os.getenv("MCP_UNSAFE_PUBLIC_ACCESS_CONFIRMED", "0") == "1"

# Build default network range for discovery (CIDR notation)
_DEFAULT_OCTETS = START_IP.rsplit(".", 1)[0]
DEFAULT_NETWORK_RANGE = NETWORK_RANGE or f"{_DEFAULT_OCTETS}.0/24"

TOOLS_VERSION = "1.2.0"

# =============================================================================
# TOOL INVOCATION COUNTERS
# =============================================================================

_tool_invocation_counts: dict[str, int] = collections.defaultdict(int)


def increment_tool_count(tool_name: str) -> None:
    """Increment invocation counter for a tool.

    Args:
        tool_name: Name of the registered tool.
    """
    _tool_invocation_counts[tool_name] += 1


def get_tool_counts() -> dict[str, int]:
    """Return invocation counts for all tools.

    Returns:
        Dict mapping tool names to invocation counts.
    """
    return dict(_tool_invocation_counts)


# =============================================================================
# LOGGING
# =============================================================================

_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
_LOGGER_INITIALIZED = False

_SENSITIVE_PATTERNS = [
    (r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", "Bearer <REDACTED>"),
    (r"Authorization:\s*[^\s]+", "Authorization: <REDACTED>"),
    (r"password[=:]\s*[^\s&]+", "password=<REDACTED>"),
    (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "<IP_REDACTED>"),
]


def sanitize_log_line(line: str) -> str:
    """Remove sensitive data from a log line.

    Args:
        line: Raw log line that may contain credentials or tokens.

    Returns:
        Sanitized line with sensitive patterns replaced by REDACTED markers.
    """
    import re

    for pattern, replacement in _SENSITIVE_PATTERNS:
        line = re.sub(pattern, replacement, line, flags=re.IGNORECASE)
    return line


_request_id_context = threading.local()


class RequestIdFilter(logging.Filter):
    """Logging filter that injects request_id from thread-local context."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = getattr(_request_id_context, "value", "-")
        return True


def set_request_id(request_id: str) -> None:
    """Set request_id for the current thread's log context.

    Args:
        request_id: UUID string identifying the current tool invocation.
    """
    _request_id_context.value = request_id


def get_request_id() -> str:
    """Get request_id for the current thread, or '-' if not set.

    Returns:
        UUID string or '-'.
    """
    return getattr(_request_id_context, "value", "-")


def start_tool_context() -> str:
    """Initialize request_id for a tool invocation.

    Should be called at the start of every tool wrapper before any
    I/O or logging. Returns the generated UUID.

    Returns:
        UUID string for the current invocation.
    """
    rid = str(uuid.uuid4())
    set_request_id(rid)
    return rid


def setup_logging() -> None:
    """Initialize logging once at startup.

    All log output targets stderr to avoid corrupting MCP stdio transport.
    """
    global _LOGGER_INITIALIZED
    if _LOGGER_INITIALIZED:
        return
    logger = logging.getLogger("iot_mcp")
    logger.setLevel(getattr(logging, _LOG_LEVEL, logging.INFO))
    handler = logging.StreamHandler(sys.stderr)

    class SanitizingFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            return sanitize_log_line(super().format(record))

    handler.setFormatter(
        SanitizingFormatter(
            "%(asctime)s [%(levelname)s] [%(request_id)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    handler.addFilter(RequestIdFilter())
    logger.addHandler(handler)
    logger.propagate = False
    _LOGGER_INITIALIZED = True


def get_logger(name: str) -> logging.Logger:
    """Get a named logger under the iot_mcp hierarchy.

    Args:
        name: Component name (e.g. "server", "discovery").

    Returns:
        Configured logger instance.
    """
    return logging.getLogger(f"iot_mcp.{name}")


# =============================================================================
# RESPONSE HELPERS
# =============================================================================


def _build_meta(
    duration_ms: int | None = None,
    cached: bool | None = None,
    retry_safe: bool | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Build _meta envelope for responses.

    Args:
        duration_ms: Optional elapsed time in milliseconds.
        cached: Optional whether the response came from cache.
        retry_safe: Optional whether the operation can be safely retried.
        extra: Additional metadata fields to include.

    Returns:
        Dictionary with request_id, tool_version and extra fields.
    """
    meta: dict[str, Any] = {
        "request_id": str(uuid.uuid4()),
        "tool_version": TOOLS_VERSION,
    }
    if duration_ms is not None:
        meta["duration_ms"] = duration_ms
    if cached is not None:
        meta["cached"] = cached
    if retry_safe is not None:
        meta["retry_safe"] = retry_safe
    meta.update(extra)
    return meta


def _success_response(
    data: Any,
    duration_ms: int | None = None,
    cached: bool | None = None,
    retry_safe: bool | None = None,
    **meta_extra: Any,
) -> str:
    """Build consistent success response as JSON string.

    Args:
        data: Data payload to include in the response.
        duration_ms: Optional elapsed time in milliseconds.
        cached: Optional whether the response came from cache.
        retry_safe: Optional whether the operation can be safely retried.
        meta_extra: Additional _meta fields.

    Returns:
        JSON string with success response and _meta envelope.
    """
    return json.dumps(
        {
            "success": True,
            "data": data,
            "_meta": _build_meta(
                duration_ms=duration_ms, cached=cached, retry_safe=retry_safe, **meta_extra
            ),
        }
    )


def _error_response(
    error: str,
    duration_ms: int | None = None,
    cached: bool | None = None,
    retry_safe: bool | None = None,
    **meta_extra: Any,
) -> str:
    """Build consistent error response as JSON string.

    Args:
        error: Error message string.
        duration_ms: Optional elapsed time in milliseconds.
        cached: Optional whether the response came from cache.
        retry_safe: Optional whether the operation can be safely retried.
        meta_extra: Additional _meta fields.

    Returns:
        JSON string with error response and _meta envelope.
    """
    return json.dumps(
        {
            "success": False,
            "error": error,
            "_meta": _build_meta(
                duration_ms=duration_ms, cached=cached, retry_safe=retry_safe, **meta_extra
            ),
        }
    )


def _error_response_extended(
    code: str,
    message: str,
    retryable: bool = False,
    suggestion: str | None = None,
    available_names: list[str] | None = None,
    duration_ms: int | None = None,
    cached: bool | None = None,
    retry_safe: bool | None = None,
    **meta_extra: Any,
) -> str:
    """Build structured error response with machine-readable fields.

    Args:
        code: Machine-readable error code (UPPER_SNAKE_CASE).
        message: Human-readable error description.
        retryable: Whether the operation can be retried safely.
        suggestion: Actionable next step for the user.
        available_names: List of valid alternatives when relevant.
        duration_ms: Optional elapsed time in milliseconds.
        cached: Optional whether the response came from cache.
        retry_safe: Optional whether the operation can be safely retried.
        meta_extra: Additional _meta fields.

    Returns:
        JSON string with structured error response and _meta envelope.
    """
    err: dict[str, Any] = {"code": code, "message": message, "retryable": retryable}
    if suggestion:
        err["suggestion"] = suggestion
    if available_names:
        err["available_names"] = available_names
    return json.dumps(
        {
            "success": False,
            "error": err,
            "_meta": _build_meta(
                duration_ms=duration_ms, cached=cached, retry_safe=retry_safe, **meta_extra
            ),
        }
    )


# =============================================================================
# TOOL MANIFESTS
# =============================================================================

TOOL_MANIFESTS: dict[str, dict[str, Any]] = {
    "iot_discover_devices": {
        "name": "iot_discover_devices",
        "version": "1.2.0",
        "risk": "READ",
        "side_effects": "read",
        "idempotent": True,
        "retryable": True,
        "concurrent_safe": True,
        "timeout_ms": 120000,
        "requires_confirmation": False,
        "determinism": "env-dependent",
        "latency": "slow",
        "cost": "expensive",
    },
    "iot_list_devices": {
        "name": "iot_list_devices",
        "version": "1.2.0",
        "risk": "READ",
        "side_effects": "read",
        "idempotent": True,
        "retryable": True,
        "concurrent_safe": True,
        "timeout_ms": 1000,
        "requires_confirmation": False,
        "determinism": "eventually-consistent",
        "latency": "instant",
        "cost": "cheap",
    },
    "iot_check_device": {
        "name": "iot_check_device",
        "version": "1.2.0",
        "risk": "READ",
        "side_effects": "read",
        "idempotent": True,
        "retryable": True,
        "concurrent_safe": True,
        "timeout_ms": 10000,
        "requires_confirmation": False,
        "determinism": "env-dependent",
        "latency": "moderate",
        "cost": "moderate",
    },
    "iot_find_device_by_name": {
        "name": "iot_find_device_by_name",
        "version": "1.2.0",
        "risk": "READ",
        "side_effects": "read",
        "idempotent": True,
        "retryable": True,
        "concurrent_safe": True,
        "timeout_ms": 1000,
        "requires_confirmation": False,
        "determinism": "deterministic",
        "latency": "instant",
        "cost": "cheap",
    },
    "iot_get_device_info": {
        "name": "iot_get_device_info",
        "version": "1.2.0",
        "risk": "READ",
        "side_effects": "read",
        "idempotent": True,
        "retryable": True,
        "concurrent_safe": True,
        "timeout_ms": 10000,
        "requires_confirmation": False,
        "determinism": "env-dependent",
        "latency": "moderate",
        "cost": "moderate",
    },
    "iot_get_device_power": {
        "name": "iot_get_device_power",
        "version": "1.2.0",
        "risk": "READ",
        "side_effects": "read",
        "idempotent": True,
        "retryable": True,
        "concurrent_safe": True,
        "timeout_ms": 10000,
        "requires_confirmation": False,
        "determinism": "env-dependent",
        "latency": "moderate",
        "cost": "moderate",
    },
    "iot_set_power": {
        "name": "iot_set_power",
        "version": "1.2.0",
        "risk": "WRITE",
        "side_effects": "write",
        "idempotent": False,
        "retryable": False,
        "concurrent_safe": False,
        "timeout_ms": 10000,
        "requires_confirmation": True,
        "determinism": "env-dependent",
        "latency": "moderate",
        "cost": "moderate",
    },
    "iot_set_brightness": {
        "name": "iot_set_brightness",
        "version": "1.2.0",
        "risk": "WRITE",
        "side_effects": "write",
        "idempotent": False,
        "retryable": False,
        "concurrent_safe": False,
        "timeout_ms": 10000,
        "requires_confirmation": True,
        "determinism": "env-dependent",
        "latency": "moderate",
        "cost": "moderate",
    },
    "iot_restart_device": {
        "name": "iot_restart_device",
        "version": "1.2.0",
        "risk": "DANGEROUS",
        "side_effects": "destructive",
        "idempotent": False,
        "retryable": False,
        "concurrent_safe": False,
        "timeout_ms": 10000,
        "requires_confirmation": True,
        "determinism": "env-dependent",
        "latency": "slow",
        "cost": "expensive",
    },
    "iot_get_wifi_config": {
        "name": "iot_get_wifi_config",
        "version": "1.2.0",
        "risk": "READ",
        "side_effects": "read",
        "idempotent": True,
        "retryable": True,
        "concurrent_safe": True,
        "timeout_ms": 10000,
        "requires_confirmation": False,
        "determinism": "env-dependent",
        "latency": "moderate",
        "cost": "moderate",
    },
    "iot_mqtt_publish": {
        "name": "iot_mqtt_publish",
        "version": "1.2.0",
        "risk": "WRITE",
        "side_effects": "write",
        "idempotent": False,
        "retryable": False,
        "concurrent_safe": False,
        "timeout_ms": 5000,
        "requires_confirmation": True,
        "determinism": "env-dependent",
        "latency": "moderate",
        "cost": "moderate",
    },
    "iot_mqtt_get_state": {
        "name": "iot_mqtt_get_state",
        "version": "1.2.0",
        "risk": "READ",
        "side_effects": "read",
        "idempotent": True,
        "retryable": True,
        "concurrent_safe": True,
        "timeout_ms": 10000,
        "requires_confirmation": False,
        "determinism": "env-dependent",
        "latency": "moderate",
        "cost": "moderate",
    },
    "iot_mqtt_build_command_topic": {
        "name": "iot_mqtt_build_command_topic",
        "version": "1.2.0",
        "risk": "READ",
        "side_effects": "none",
        "idempotent": True,
        "retryable": True,
        "concurrent_safe": True,
        "timeout_ms": 100,
        "requires_confirmation": False,
        "determinism": "deterministic",
        "latency": "instant",
        "cost": "cheap",
    },
}


def get_tool_manifest(tool_name: str) -> dict[str, Any] | None:
    """Get the manifest for a specific tool.

    Args:
        tool_name: Name of the registered tool.

    Returns:
        Manifest dict or None if tool not found.
    """
    return TOOL_MANIFESTS.get(tool_name)


def inject_tool_risk_prefix(func: Any) -> Any:
    """Inject [READ]/[WRITE]/[DANGEROUS] risk prefix from TOOL_MANIFESTS into func.__doc__.

    The prefix is prepended only if the docstring does not already start with '['.

    Args:
        func: The tool function being decorated.

    Returns:
        The same function with an updated __doc__.
    """
    manifest = TOOL_MANIFESTS.get(func.__name__)
    if manifest:
        doc = (func.__doc__ or "").strip()
        if doc and not doc.startswith("["):
            func.__doc__ = f"[{manifest['risk']}] {doc}"
    return func

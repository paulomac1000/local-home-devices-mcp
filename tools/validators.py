"""Input validation for MCP IoT tools."""

import re


class ValidationError(Exception):
    """Raised when input fails validation."""


def validate_required_string(value: str | None, name: str) -> str:
    """Validate that a required string parameter is non-empty.

    Args:
        value: The string value to validate.
        name: Parameter name for error messages.

    Returns:
        The stripped string.

    Raises:
        ValidationError: If value is None, empty, or whitespace-only.
    """
    if not value or not value.strip():
        raise ValidationError(f"{name} is required and must not be empty")
    return value.strip()


def validate_power_state(state: str) -> str:
    """Validate that a power state is ON, OFF, or TOGGLE.

    Args:
        state: Power state string to validate.

    Returns:
        Uppercase, trimmed state string.

    Raises:
        ValidationError: If state is not a valid power state.
    """
    s = state.upper().strip()
    if s not in ("ON", "OFF", "TOGGLE"):
        raise ValidationError(f"Invalid state '{state}'. Must be ON, OFF, or TOGGLE")
    return s


def validate_brightness(value: int) -> int:
    """Validate that a brightness value is within 0-100 range.

    Args:
        value: Brightness value to validate.

    Returns:
        The validated brightness value.

    Raises:
        ValidationError: If value is outside 0-100.
    """
    if not 0 <= value <= 100:
        raise ValidationError(f"Brightness must be 0-100, got {value}")
    return value


def validate_channel(channel: int) -> int:
    """Validate that a channel number is 1 or higher.

    Args:
        channel: Channel number to validate.

    Returns:
        The validated channel number.

    Raises:
        ValidationError: If channel is less than 1.
    """
    if channel < 1:
        raise ValidationError(f"Channel must be >= 1, got {channel}")
    return channel


def validate_ip_format(ip: str) -> str:
    """Validate that a string is a valid IPv4 address format.

    Args:
        ip: IP address string to validate.

    Returns:
        The trimmed IP address string.

    Raises:
        ValidationError: If the string does not match IPv4 format.
    """
    if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip.strip()):
        raise ValidationError(f"Invalid IP address format: {ip}")
    return ip.strip()

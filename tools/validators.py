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


_CIDR_RE = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/(\d{1,2})$")


def validate_cidr(cidr: str | None) -> str:
    """Validate a CIDR notation network range.

    Args:
        cidr: CIDR string (e.g. "192.168.0.0/24") or None.

    Returns:
        The trimmed CIDR string.

    Raises:
        ValidationError: If CIDR is None, empty, or does not match valid format.
    """
    if not cidr or not cidr.strip():
        raise ValidationError("Network range is required")
    cidr = cidr.strip()
    m = _CIDR_RE.match(cidr)
    if not m:
        raise ValidationError(f"Invalid CIDR notation: {cidr!r}. Expected format: 192.168.0.0/24")
    prefix = int(m.group(1))
    if not 0 <= prefix <= 32:
        raise ValidationError(f"Invalid CIDR prefix length: {prefix}. Must be 0-32")
    octets = cidr.split("/")[0].split(".")
    for octet in octets:
        if not 0 <= int(octet) <= 255:
            raise ValidationError(f"Invalid IP octet in CIDR: {cidr!r}. Each octet must be 0-255")
    return cidr

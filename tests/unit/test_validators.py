"""Unit tests for input validation module (zero I/O)."""

import pytest

from tools.validators import (
    ValidationError,
    validate_brightness,
    validate_channel,
    validate_ip_format,
    validate_power_state,
    validate_required_string,
)

pytestmark = pytest.mark.unit


class TestValidateRequiredString:
    """Tests for validate_required_string."""

    def test_accepts_valid_string(self):
        assert validate_required_string("hello", "name") == "hello"

    def test_rejects_empty_string(self):
        with pytest.raises(ValidationError, match="name is required"):
            validate_required_string("", "name")

    def test_rejects_none(self):
        with pytest.raises(ValidationError, match="name is required"):
            validate_required_string(None, "name")

    def test_rejects_whitespace_only(self):
        with pytest.raises(ValidationError):
            validate_required_string("   ", "name")

    def test_strips_whitespace(self):
        assert validate_required_string("  hello  ", "name") == "hello"


class TestValidatePowerState:
    """Tests for validate_power_state."""

    @pytest.mark.parametrize("state", ["ON", "OFF", "TOGGLE", "on", "off", "toggle", " On "])
    def test_valid_states(self, state):
        result = validate_power_state(state)
        assert result in ("ON", "OFF", "TOGGLE")

    @pytest.mark.parametrize("state", ["", "FOO", "ONN", "123", "ON OFF"])
    def test_invalid_states(self, state):
        with pytest.raises(ValidationError, match="Invalid state"):
            validate_power_state(state)


class TestValidateBrightness:
    """Tests for validate_brightness."""

    @pytest.mark.parametrize("value", [0, 1, 50, 100])
    def test_valid_values(self, value):
        assert validate_brightness(value) == value

    @pytest.mark.parametrize("value", [-1, -100, 101, 200])
    def test_invalid_values(self, value):
        with pytest.raises(ValidationError, match="Brightness must be 0-100"):
            validate_brightness(value)


class TestValidateChannel:
    """Tests for validate_channel."""

    @pytest.mark.parametrize("channel", [1, 2, 10])
    def test_valid_channels(self, channel):
        assert validate_channel(channel) == channel

    @pytest.mark.parametrize("channel", [0, -1, -100])
    def test_invalid_channels(self, channel):
        with pytest.raises(ValidationError, match="Channel must be >= 1"):
            validate_channel(channel)


class TestValidateIpFormat:
    """Tests for validate_ip_format."""

    @pytest.mark.parametrize("ip", ["192.168.1.1", "10.0.0.1", "0.0.0.0", "255.255.255.255"])
    def test_valid_ips(self, ip):
        assert validate_ip_format(ip) == ip

    @pytest.mark.parametrize("ip", ["", "notanip", "1.2.3", "abc.def.ghi.jkl", "1.2.3.4.5"])
    def test_invalid_ips(self, ip):
        with pytest.raises(ValidationError, match="Invalid IP address format"):
            validate_ip_format(ip)

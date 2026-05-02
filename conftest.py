"""
Test fixtures for Tasmota-OpenBK-MCP unit tests.
"""

import pytest
from unittest.mock import MagicMock, patch


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
    return {
        "ip": "192.168.1.100",
        "type": "tasmota",
        "name": "Tasmota_Light",
        "chip": "ESP8266",
        "version": "13.0.0",
    }


@pytest.fixture
def sample_openbk_device():
    """Return a sample OpenBK device dictionary."""
    return {
        "ip": "192.168.1.101",
        "type": "openbk",
        "name": "OpenBK_Switch",
        "chip": "BK7231N",
        "version": "1.17.0",
    }

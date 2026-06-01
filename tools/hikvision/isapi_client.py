"""
Hikvision ISAPI HTTP Client

Provides authenticated HTTP access to Hikvision doorbell ISAPI endpoints
using HTTP Digest Authentication (RFC 2617).

IMPORTANT: The Hikvision ISAPI API returns XML responses, not JSON.
All response parsing uses defusedxml ElementTree helpers.
"""

import xml.etree.ElementTree as ET

import requests
from defusedxml import ElementTree as SafeET  # type: ignore[import-untyped]
from requests.auth import HTTPDigestAuth

from tools.constants import (
    HIKVISION_DOORBELL_HOST,
    HIKVISION_DOORBELL_PASSWORD,
    HIKVISION_DOORBELL_USER,
)

# ISAPI XML namespace
ISAPI_NS = "http://www.isapi.org/ver20/XMLSchema"


def _xml_to_dict(element: ET.Element) -> dict[str, str]:
    """Convert an XML Element to a flat dict (first-level children only).

    Strips the ISAPI namespace from tag names. Nested elements are
    converted to their text value. Suitable for flat ISAPI responses
    like deviceInfo.
    """
    result: dict[str, str] = {}
    for child in element:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        text = child.text.strip() if child.text else ""
        result[tag] = text
    return result


class HikvisionISAPIClient:
    """HTTP client for Hikvision ISAPI API with digest auth."""

    def __init__(self, host: str, username: str, password: str, timeout: int = 10):
        self.base_url = f"http://{host}"
        self.auth = HTTPDigestAuth(username, password)
        self.timeout = timeout
        self.session = requests.Session()

    def get_snapshot(self, channel: int = 1) -> bytes | None:
        """Capture a JPEG snapshot from the doorbell camera.

        Endpoint: GET /ISAPI/Streaming/channels/{channel}01/picture
        Response: binary JPEG image

        Args:
            channel: Camera channel (1 = main doorbell camera).

        Returns:
            JPEG image bytes, or None on failure.
        """
        url = f"{self.base_url}/ISAPI/Streaming/channels/{channel}01/picture"
        try:
            resp = self.session.get(url, auth=self.auth, timeout=self.timeout)
            resp.raise_for_status()
            return resp.content
        except Exception:
            return None

    def get_device_info(self) -> dict[str, str] | None:
        """Fetch device information from ISAPI.

        Endpoint: GET /ISAPI/System/deviceInfo
        Response: XML (application/xml) - parsed to dict via ElementTree

        Returns:
            Dict with keys: deviceName, model, serialNumber, macAddress,
            firmwareVersion, firmwareReleasedDate, etc. None on failure.
        """
        url = f"{self.base_url}/ISAPI/System/deviceInfo"
        try:
            resp = self.session.get(url, auth=self.auth, timeout=self.timeout)
            resp.raise_for_status()
            root = SafeET.fromstring(resp.text)
            return _xml_to_dict(root)
        except Exception:
            return None

    def open_door(self, door_id: int = 1) -> bool:
        """Trigger the electric lock relay (open gate).

        Endpoint: PUT /ISAPI/AccessControl/RemoteControl/door/{door_id}
        Body: XML <RemoteControlDoor><cmd>open</cmd></RemoteControlDoor>
        Content-Type: application/xml

        Args:
            door_id: Door output number (1 = main gate relay).

        Returns:
            True if successful, False otherwise.
        """
        url = f"{self.base_url}/ISAPI/AccessControl/RemoteControl/door/{door_id}"
        headers = {"Content-Type": "application/xml"}
        body = "<RemoteControlDoor><cmd>open</cmd></RemoteControlDoor>"
        try:
            resp = self.session.put(
                url, auth=self.auth, data=body, headers=headers, timeout=self.timeout
            )
            resp.raise_for_status()
            return True
        except Exception:
            return False

    def ping(self) -> bool:
        """Check if the doorbell is reachable via HTTP.

        Endpoint: GET / (root page, returns 302 redirect)

        Returns:
            True if doorbell responds (any status < 500), False otherwise.
        """
        try:
            resp = self.session.get(self.base_url, timeout=self.timeout)
            return resp.status_code < 500
        except Exception:
            return False


def create_isapi_client() -> HikvisionISAPIClient:
    """Factory: create ISAPI client from environment variables.

    Reads:
        HIKVISION_DOORBELL_HOST
        HIKVISION_DOORBELL_USER (required)
        HIKVISION_DOORBELL_PASSWORD (required)

    Returns:
        Configured HikvisionISAPIClient instance.
    """
    host = HIKVISION_DOORBELL_HOST
    user = HIKVISION_DOORBELL_USER
    password = HIKVISION_DOORBELL_PASSWORD
    if not user or not password:
        raise ValueError(
            "HIKVISION_DOORBELL_USER and HIKVISION_DOORBELL_PASSWORD must be set. "
            "Configure them in the server environment."
        )
    return HikvisionISAPIClient(host, user, password)

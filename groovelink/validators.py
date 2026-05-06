"""URL and input validation utilities with SSRF protection."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

from groovelink.exceptions import ValidationError

# Private/internal IP ranges and hostnames blocked by default
_BLOCKED_SCHEMES = {"file", "ftp", "gopher", "telnet", "ldap", "dict"}
_BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def validate_url(url: str, allow_private: bool = False) -> str:
    """Validate a URL for safe fetching.

    Args:
        url: The URL to validate.
        allow_private: Whether to allow private/internal IP addresses.

    Returns:
        The original URL if valid.

    Raises:
        ValidationError: If the URL is unsafe or malformed.
    """
    if not url or not isinstance(url, str):
        raise ValidationError("URL must be a non-empty string.")

    parsed = urlparse(url)
    scheme = (parsed.scheme or "https").lower()

    if scheme not in {"http", "https"}:
        raise ValidationError(f"URL scheme '{scheme}' is not allowed.")

    host = (parsed.hostname or "").lower()
    if not host:
        raise ValidationError("URL must contain a valid host.")

    if not allow_private:
        if host in _BLOCKED_HOSTS:
            raise ValidationError(f"Host '{host}' is not allowed.")

        try:
            addr = ipaddress.ip_address(host)
            if addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_multicast:
                raise ValidationError(f"IP address '{host}' is not allowed.")
        except ValueError:
            pass  # Not an IP, likely a hostname

    if parsed.port and (parsed.port < 1 or parsed.port > 65535):
        raise ValidationError(f"Invalid port number: {parsed.port}")

    return url


def sanitize_path(path: str) -> str:
    """Sanitize a URL path segment to prevent path traversal."""
    if not path:
        return "/"
    cleaned = path.replace("\\", "/")
    parts = [p for p in cleaned.split("/") if p and p != ".." and p != "."]
    return "/" + "/".join(parts)

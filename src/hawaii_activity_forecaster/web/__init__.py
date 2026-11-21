"""Optional loopback-only web interface over the existing workflow (M2 WEB-A)."""

from .server import WebApp, create_server

__all__ = ["WebApp", "create_server"]

"""mDNS advertisement, so the sign is reachable by name.

The README used to tell users to find their Pi's IP address and paste it into
.env and into browser URLs. Advertising over mDNS makes that "open
http://blinkysign.local:5000".

Registered in-process rather than by changing the Pi's hostname: renaming the
host is invasive and breaks whatever SSH habits the user already has.
"""
from __future__ import annotations

import logging
import socket
from typing import Optional

logger = logging.getLogger(__name__)


class MdnsRegistration:
    """Keeps a Zeroconf service registration alive for the process lifetime."""

    def __init__(self, name: str, port: int):
        self._name = name
        self._port = port
        self._zeroconf = None
        self._info = None

    def start(self) -> None:
        from zeroconf import ServiceInfo, Zeroconf

        address = _primary_address()
        hostname = f"{self._name}.local."
        self._zeroconf = Zeroconf()
        self._info = ServiceInfo(
            "_http._tcp.local.",
            f"{self._name}._http._tcp.local.",
            addresses=[socket.inet_aton(address)] if address else [],
            port=self._port,
            properties={"path": "/"},
            server=hostname,
        )
        self._zeroconf.register_service(self._info)

        # Avahi silently appends -2 on a name collision, so report what was
        # actually registered rather than what we asked for.
        registered = getattr(self._info, "server", hostname)
        logger.info(
            "Advertised over mDNS as http://%s:%d",
            registered.rstrip("."), self._port,
        )

    def stop(self) -> None:
        if self._zeroconf is None:
            return
        try:
            if self._info is not None:
                self._zeroconf.unregister_service(self._info)
            self._zeroconf.close()
        except Exception:
            logger.exception("error unregistering the mDNS service")
        self._zeroconf = None
        self._info = None


def _primary_address() -> Optional[str]:
    """Best-effort local address. No traffic is actually sent."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("192.0.2.1", 9))  # TEST-NET-1, never routed
        return sock.getsockname()[0]
    except Exception:
        return None
    finally:
        sock.close()


def register_mdns(config) -> Optional[MdnsRegistration]:
    """Return a live registration, or None when disabled or unavailable."""
    if not config.mdns_enabled:
        return None

    registration = MdnsRegistration(config.mdns_name, config.port)
    try:
        registration.start()
    except Exception:
        # Never fatal -- the sign is still reachable by IP address.
        logger.exception(
            "could not advertise over mDNS; the sign is still reachable by IP"
        )
        return None
    return registration

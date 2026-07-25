#!/usr/bin/env python3
"""Composition root for the single BlinkySign process.

Everything the sign does -- the HTTP API, the control panel, the LED worker,
the MQTT bridge, the physical button, mDNS -- runs here in one process under
one systemd unit. This replaces the three separate processes (app.py,
iot_client.py and a bare `python -m http.server 8000`) the project used to
require.

This is currently a thin wrapper around the Flask app; the worker, MQTT bridge,
button and signal handling land in later phases.
"""
import logging
import os

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def main():
    load_dotenv()

    from blinkysign.server import app

    port = int(os.getenv('PORT', 5000))
    host = os.getenv('BLINKYSIGN_HOST', '0.0.0.0')
    logger.info("BlinkySign listening on http://%s:%d", host, port)
    app.run(host=host, port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Composition root for the single BlinkySign process.

Everything the sign does -- the HTTP API, the control panel, the LED worker,
the MQTT bridge, the physical button, mDNS -- runs here in one process under
one systemd unit. This replaces the three separate processes (app.py,
iot_client.py, and a bare `python -m http.server 8000`) the project used to
require, and with them the two hand-written systemd units and two wrapper
scripts the README asked users to compose themselves.
"""
from __future__ import annotations

import logging
import signal
import threading

from dotenv import load_dotenv
from werkzeug.serving import make_server

from blinkysign import __version__
from blinkysign.button import build_button
from blinkysign.config import Config
from blinkysign.discovery import register_mdns
from blinkysign.leds import get_controller
from blinkysign.mqtt import build_bridge
from blinkysign.server import create_app
from blinkysign.sign import build_sign

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def main() -> int:
    load_dotenv()
    _configure_logging()

    config = Config.from_env()

    controller = get_controller()
    if not controller.available:
        logger.warning(
            "LEDs are running on the '%s' backend -- nothing will light up. "
            "On a Pi this usually means SPI is not enabled yet (a reboot is "
            "required after enabling it). /health will report 'degraded'.",
            controller.backend_name,
        )

    sign = build_sign(config, controller)
    sign.refresh()  # paint the startup state

    bridge = build_bridge(config.mqtt, sign)
    button = build_button(config.button_pin, sign)
    mdns = register_mdns(config)

    shutdown = threading.Event()

    def handle_signal(signum, _frame):
        logger.info("Received signal %s, shutting down", signum)
        shutdown.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    app = create_app(config, sign)

    # make_server rather than app.run(): app.run() blocks forever with no way
    # to ask it to stop, so a signal handler could only set a flag nothing ever
    # read -- the process would ignore SIGTERM entirely and systemd would have
    # to SIGKILL it after the stop timeout, leaving the sign lit.
    server = make_server(config.host, config.port, app, threaded=True)
    server_thread = threading.Thread(
        target=server.serve_forever, name="http", daemon=True
    )
    server_thread.start()

    logger.info(
        "BlinkySign %s listening on http://%s:%d",
        __version__,
        config.host,
        config.port,
    )

    try:
        shutdown.wait()
    finally:
        logger.info("Shutting down: turning the LEDs off")
        server.shutdown()
        for component in (mdns, button, bridge):
            if component is not None:
                try:
                    component.stop()
                except Exception:
                    logger.exception("error stopping %r", component)
        try:
            sign.turn_off()
            sign.wait_idle(timeout=2.0)
        except Exception:
            logger.exception("failed to turn the LEDs off during shutdown")
        sign.stop()
        server_thread.join(timeout=5)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

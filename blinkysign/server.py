#!/usr/bin/env python3
"""The HTTP API and the control panel.

Flask serves the control panel itself now. The project used to require a second
process -- `python -m http.server 8000` -- purely to serve two static HTML
files, which is also the only reason the panel needed CORS at all.

Every route drives the SignController; nothing here touches the LED strip.
Effects return 202 because they are genuinely asynchronous now: the worker
renders them and a later command can interrupt them.
"""
from __future__ import annotations

import hmac
import logging
from functools import wraps
from typing import Optional

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from blinkysign import __version__
from blinkysign.colors import NAMED_COLORS
from blinkysign.config import Config
from blinkysign.sign import BadEffectParams, SignController
from blinkysign.worker import UnknownEffect

logger = logging.getLogger(__name__)

STATIC_DIR = "static"


def _envelope(snapshot, message: str, status: str = "success") -> dict:
    """The response shape the API has always returned.

    status/message/state are load-bearing for the Stream Deck buttons and the
    web button; the state object gains fields but never loses the original
    muted and led_on.
    """
    return {
        "status": status,
        "message": message,
        "state": snapshot.to_dict(),
    }


def create_app(config: Config, sign: SignController) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["BLINKYSIGN"] = config

    # Same-origin by default. It used to be origins:"*" with no authentication
    # of any kind, so any page the user happened to visit could drive the sign.
    # Now that Flask serves the panel itself there is nothing to widen this for
    # unless the operator explicitly asks.
    if config.cors_origins:
        CORS(
            app,
            resources={r"/*": {
                "origins": config.cors_origins,
                "methods": ["GET", "PUT", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization", "X-Api-Key"],
            }},
        )

    def require_token(view):
        """Enforce BLINKYSIGN_API_TOKEN on mutating routes, when it is set.

        Unset means open on the LAN, which keeps existing installs and Stream
        Deck buttons working untouched.
        """

        @wraps(view)
        def wrapper(*args, **kwargs):
            token = config.api_token
            if not token:
                return view(*args, **kwargs)

            presented = request.headers.get("X-Api-Key")
            if not presented:
                auth = request.headers.get("Authorization", "")
                if auth.lower().startswith("bearer "):
                    presented = auth[7:].strip()

            if not presented or not hmac.compare_digest(presented, token):
                return jsonify({
                    "status": "error",
                    "message": "Missing or invalid API token.",
                }), 401
            return view(*args, **kwargs)

        return wrapper

    # -- the control panel ----------------------------------------------
    #
    # Explicit routes rather than mounting a static folder at "/", which would
    # let a file called status shadow the /status endpoint.

    @app.route("/", methods=["GET"])
    def control_panel():
        return send_from_directory(STATIC_DIR, "control_panel.html")

    @app.route("/button", methods=["GET"])
    def web_button():
        return send_from_directory(STATIC_DIR, "web_button.html")

    @app.route("/api/config", methods=["GET"])
    def api_config():
        """Runtime configuration for the panel.

        This replaces the deploy scripts' in-place rewriting of
        control_panel.html, which stamped a live API key into a git-tracked
        file. An empty default_endpoint means "same origin", so a fresh
        checkout talks to the device that served it.
        """
        return jsonify({
            "version": __version__,
            "default_endpoint": "",
            "remote_endpoint": config.remote_endpoint,
            "requires_api_key": bool(config.api_token),
            "effects": sign.effects,
            "colors": sorted(NAMED_COLORS),
            "led_count": config.led_count,
        })

    # -- state ----------------------------------------------------------

    @app.route("/status", methods=["GET"])
    def get_status():
        return jsonify(sign.snapshot().to_dict())

    @app.route("/toggle", methods=["PUT"])
    @require_token
    def toggle_mute():
        snapshot = sign.toggle()
        return jsonify(_envelope(
            snapshot,
            f"Mute toggled to {'muted' if snapshot.muted else 'unmuted'}",
        ))

    @app.route("/set", methods=["PUT"])
    @require_token
    def set_status():
        data = request.get_json(silent=True)
        if not data or "muted" not in data:
            return jsonify({
                "status": "error",
                "message": "Invalid request. Expected JSON with 'muted' field.",
            }), 400
        snapshot = sign.set_muted(bool(data["muted"]))
        return jsonify(_envelope(
            snapshot,
            f"Status set to {'muted' if snapshot.muted else 'unmuted'}",
        ))

    @app.route("/off", methods=["PUT"])
    @require_token
    def turn_off():
        snapshot = sign.turn_off()
        return jsonify(_envelope(snapshot, "LEDs turned off"))

    @app.route("/health", methods=["GET"])
    def health_check():
        snapshot = sign.snapshot()
        # Deliberately still 200 when degraded, so systemd and uptime probes
        # do not flap over a detached strip. The panel surfaces the degradation.
        return jsonify({
            "status": "healthy" if snapshot.available else "degraded",
            "version": __version__,
            "leds": {
                "available": snapshot.available,
                "backend": snapshot.backend,
                "count": config.led_count,
            },
        })

    # -- effects --------------------------------------------------------

    def _run(name: str, body: Optional[dict]):
        params = dict(body or {})
        params.pop("muted", None)
        try:
            snapshot = sign.run_effect(name, **params)
        except UnknownEffect:
            return jsonify({
                "status": "error",
                "message": f"Unknown effect {name!r}.",
            }), 404
        except BadEffectParams as e:
            return jsonify({"status": "error", "message": str(e)}), 400

        payload = _envelope(snapshot, f"{name} effect started", status="accepted")
        payload["effect"] = name
        # 202: the worker renders this, and a later command can interrupt it.
        return jsonify(payload), 202

    @app.route("/effects/rainbow", methods=["PUT"])
    @require_token
    def rainbow_effect():
        return _run("rainbow", request.get_json(silent=True))

    @app.route("/effects/pulse", methods=["PUT"])
    @require_token
    def pulse_effect():
        return _run("pulse", request.get_json(silent=True))

    @app.route("/effects/theater", methods=["PUT"])
    @require_token
    def theater_effect():
        return _run("theater", request.get_json(silent=True))

    @app.route("/effects/wipe", methods=["PUT"])
    @require_token
    def wipe_effect():
        return _run("wipe", request.get_json(silent=True))

    return app

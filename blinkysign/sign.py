"""The one object every input drives the sign through.

The HTTP routes, the MQTT callbacks and the physical button all call this and
nothing else. That is deliberate: the previous design let each of them reach
into the LED controller directly with its own copy of the state-update logic,
which is how the local API and the MQTT client ended up disagreeing about
whether the sign was muted, and how MQTT ended up supporting only three of the
four effects the HTTP API exposed.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from blinkysign.colors import OFF, RGB, BadColor, parse_color
from blinkysign.config import Config
from blinkysign.state import SignState, Snapshot
from blinkysign.worker import EFFECT, EFFECT_NAMES, SOLID, Command, LedWorker, UnknownEffect

logger = logging.getLogger(__name__)


class BadEffectParams(ValueError):
    """Raised when an effect's parameters cannot be used."""


class SignController:
    """Facade over the state object and the LED worker."""

    def __init__(self, config: Config, state: SignState, worker: LedWorker):
        self._config = config
        self._state = state
        self._worker = worker

    # -- reads ----------------------------------------------------------

    def snapshot(self) -> Snapshot:
        return self._state.snapshot()

    @property
    def effects(self):
        return list(EFFECT_NAMES)

    # -- state changes --------------------------------------------------

    def toggle(self) -> Snapshot:
        return self._render(self._state.toggle())

    def set_muted(self, muted: bool) -> Snapshot:
        return self._render(self._state.set_muted(muted))

    def turn_off(self) -> Snapshot:
        snapshot = self._state.set_led_on(False)
        self._worker.submit(Command(kind=SOLID, color=OFF))
        return snapshot

    def refresh(self) -> Snapshot:
        """Repaint the current state, e.g. at startup."""
        return self._render(self._state.snapshot())

    def _render(self, snapshot: Snapshot) -> Snapshot:
        color = (
            self._config.muted_color if snapshot.muted else self._config.unmuted_color
        )
        self._worker.submit(Command(kind=SOLID, color=color))
        return snapshot

    # -- effects --------------------------------------------------------

    def run_effect(self, name: str, **params: Any) -> Snapshot:
        """Start an effect. Returns immediately; the worker renders it.

        Raises UnknownEffect for an unrecognised name and BadEffectParams for
        unusable parameters, so callers can map those onto 404/400 themselves.
        """
        if name not in EFFECT_NAMES:
            raise UnknownEffect(name)

        resolved = self._resolve_params(name, params)
        self._worker.submit(Command(kind=EFFECT, effect=name, params=resolved))
        return self._state.snapshot()

    def _resolve_params(self, name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        resolved: Dict[str, Any] = {}

        if name != "rainbow":
            default = parse_color(
                {"pulse": "blue", "theater": "white", "wipe": "blue"}[name]
            )
            requested = params.get("color")
            # Colours stay lenient: the original API did color_map.get(color,
            # BLUE), so an unrecognised colour has always fallen back rather
            # than failed, and a Stream Deck button configured with a typo
            # still works. Say so in the log instead of failing silently.
            resolved["color"] = parse_color(requested, default=default)
            if requested is not None and resolved["color"] == default:
                try:
                    parse_color(requested)
                except BadColor:
                    logger.warning(
                        "unrecognised colour %r for effect %s; using %s",
                        requested, name, default,
                    )

        for key, caster, lo, hi in (
            ("cycles", int, 1, 20),
            ("iterations", int, 1, 100),
            ("duration", float, 0.05, 30.0),
            ("wait", float, 0.0, 1.0),
        ):
            if key in params and params[key] is not None:
                try:
                    value = caster(params[key])
                except (TypeError, ValueError):
                    raise BadEffectParams(f"{key} must be a number")
                if not (lo <= value <= hi):
                    raise BadEffectParams(f"{key} must be between {lo} and {hi}")
                resolved[key] = value

        return resolved

    # -- hardware -------------------------------------------------------

    def set_hardware_status(self, available: bool, backend: str) -> None:
        self._state.set_hardware(available, backend)

    # -- lifecycle ------------------------------------------------------

    def add_listener(self, listener):
        """Observe state changes. Used by the MQTT bridge to publish."""
        return self._state.add_listener(listener)

    def wait_idle(self, timeout: Optional[float] = None) -> bool:
        """Block until the LED worker has finished its queued work."""
        return self._worker.wait_idle(timeout=timeout)

    def stop(self, timeout: float = 2.0) -> None:
        self._worker.stop(timeout=timeout)


def build_sign(config: Config, controller) -> "SignController":
    """Wire a controller, state object, worker and facade together."""
    state = SignState(
        available=controller.available,
        backend=controller.backend_name,
    )
    worker = LedWorker(controller, on_effect_change=state.set_effect)
    worker.start()
    return SignController(config, state, worker)

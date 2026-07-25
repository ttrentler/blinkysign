"""The single thread that owns the LED strip.

Every write to the strip happens here. Nothing else touches the hardware, which
is what makes the strip safe to drive from HTTP handlers, MQTT callbacks and a
GPIO interrupt at the same time.

Effects are cancellable within one frame. The worker drives an effect generator
and waits on a threading.Event between frames, so submitting a new command both
stores it and wakes the worker immediately -- Event.wait(delay) returns True the
moment it is set. Polling with time.sleep() would make preemption latency the
length of the frame budget rather than the time to the next frame.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from blinkysign.colors import OFF, RGB

logger = logging.getLogger(__name__)

SOLID = "solid"
EFFECT = "effect"


@dataclass(frozen=True)
class Command:
    """A unit of work for the LED worker."""

    kind: str  # SOLID | EFFECT
    color: Optional[RGB] = None
    effect: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_effect(self) -> bool:
        return self.kind == EFFECT


class UnknownEffect(ValueError):
    """Raised for an effect name the controller does not implement."""


EFFECT_BUILDERS = {
    "rainbow": lambda c, p: c.rainbow_frames(wait=p.get("wait", 0.01)),
    "pulse": lambda c, p: c.pulse_frames(
        p["color"], cycles=p.get("cycles", 3), duration=p.get("duration", 1.0)
    ),
    "theater": lambda c, p: c.theater_chase_frames(
        p["color"], wait=p.get("wait", 0.05), iterations=p.get("iterations", 10)
    ),
    "wipe": lambda c, p: c.color_wipe_frames(p["color"], wait=p.get("wait", 0.05)),
}

EFFECT_NAMES = tuple(EFFECT_BUILDERS)


class LedWorker(threading.Thread):
    """Serialises all LED writes onto one thread."""

    def __init__(self, controller, on_effect_change=None, name="led-worker"):
        super().__init__(name=name, daemon=True)
        self._controller = controller
        self._on_effect_change = on_effect_change

        self._cv = threading.Condition()
        self._pending: Optional[Command] = None
        self._stopping = False

        # The persistent render -- the muted/unmuted/off colour the sign
        # returns to when an effect finishes or is interrupted.
        self._base: Optional[Command] = None
        self._running_effect = False
        self._cancel = threading.Event()
        self._idle = threading.Event()
        self._idle.set()

    # -- public API -----------------------------------------------------

    def submit(self, command: Command) -> None:
        """Queue a command, cancelling anything currently running.

        There is no backlog: a newer command replaces an older pending one.
        The sign only ever wants to show the most recent instruction.
        """
        with self._cv:
            self._pending = command
            self._idle.clear()
            self._cancel.set()
            self._cv.notify_all()

    def stop(self, timeout: float = 2.0) -> None:
        with self._cv:
            self._stopping = True
            self._cancel.set()
            self._cv.notify_all()
        self.join(timeout=timeout)

    def wait_idle(self, timeout: Optional[float] = None) -> bool:
        """Block until the worker has nothing left to do. For tests."""
        return self._idle.wait(timeout=timeout)

    def has_effect(self) -> bool:
        """True when an effect is running or queued to run next."""
        with self._cv:
            if self._pending is not None:
                return self._pending.is_effect
            return self._running_effect

    def set_base(self, command: Command) -> None:
        """Change the resting render without interrupting a running effect.

        submit() would cancel the effect; this only changes what the sign
        returns to once the effect finishes. If nothing is running, it renders
        immediately.
        """
        with self._cv:
            self._base = command
            idle = self._pending is None and not self._running_effect
        if idle:
            self.submit(command)

    # -- thread body ----------------------------------------------------

    def run(self) -> None:
        while True:
            with self._cv:
                while self._pending is None and not self._stopping:
                    self._idle.set()
                    self._cv.wait()
                if self._stopping:
                    return
                command = self._pending
                self._pending = None
                self._cancel.clear()

            try:
                self._execute(command)
            except Exception:
                logger.exception("LED command failed: %r", command)

    def _execute(self, command: Command) -> None:
        if command.is_effect:
            self._run_effect(command)
        else:
            self._base = command
            self._render_solid(command)

    def _render_solid(self, command: Command) -> None:
        self._controller.set_all_strips(command.color or OFF)

    def _run_effect(self, command: Command) -> None:
        builder = EFFECT_BUILDERS.get(command.effect or "")
        if builder is None:
            raise UnknownEffect(command.effect)

        self._running_effect = True
        self._notify_effect(command.effect)
        frames = builder(self._controller, command.params)
        try:
            for delay in frames:
                # Sleeps and detects cancellation in one call, so a new command
                # preempts within a single frame rather than at the end of the
                # animation.
                if self._cancel.wait(delay or 0):
                    logger.debug("effect %s cancelled", command.effect)
                    break
        finally:
            frames.close()
            self._running_effect = False
            self._notify_effect(None)
            self._restore_base()

    def _restore_base(self) -> None:
        """Repaint the persistent state after an effect ends.

        Skipped when the command that interrupted us is itself a solid render:
        that command is about to run and would only be overwritten.
        """
        with self._cv:
            superseded_by_solid = (
                self._pending is not None and not self._pending.is_effect
            )
        if superseded_by_solid:
            return
        if self._base is not None:
            self._render_solid(self._base)

    def _notify_effect(self, name: Optional[str]) -> None:
        if self._on_effect_change is None:
            return
        try:
            self._on_effect_change(name)
        except Exception:
            logger.exception("effect-change callback failed")

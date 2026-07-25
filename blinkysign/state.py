"""The sign's state, shared by every input.

There used to be two of these: one dict in app.py and an identical one in
iot_client.py, in two separate processes, each with its own copy of
update_led_state(). Toggling over HTTP left the MQTT client's idea of the state
untouched and vice versa. There is now one object, guarded by one lock, and
every input -- HTTP, MQTT, the physical button -- goes through it.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import asdict, dataclass
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Snapshot:
    """An immutable view of the sign at one instant."""

    muted: bool
    led_on: bool
    effect: Optional[str]
    available: bool
    backend: str
    revision: int
    updated_at: float

    def to_dict(self) -> dict:
        return asdict(self)

    def to_legacy_dict(self) -> dict:
        """The two keys the original /status response carried.

        Existing Stream Deck buttons and the web button read these; they are
        never removed, only added to.
        """
        return {"muted": self.muted, "led_on": self.led_on}


Listener = Callable[[Snapshot], None]


class SignState:
    """Thread-safe mute/LED state with change notification."""

    def __init__(self, muted: bool = False, led_on: bool = False,
                 available: bool = False, backend: str = "unknown"):
        self._lock = threading.RLock()
        self._muted = muted
        self._led_on = led_on
        self._effect: Optional[str] = None
        self._available = available
        self._backend = backend
        self._revision = 0
        self._updated_at = time.time()
        self._listeners: List[Listener] = []

    # -- reads ----------------------------------------------------------

    def snapshot(self) -> Snapshot:
        with self._lock:
            return self._snapshot_locked()

    def _snapshot_locked(self) -> Snapshot:
        return Snapshot(
            muted=self._muted,
            led_on=self._led_on,
            effect=self._effect,
            available=self._available,
            backend=self._backend,
            revision=self._revision,
            updated_at=self._updated_at,
        )

    # -- writes ---------------------------------------------------------

    def _commit(self, snapshot: Snapshot) -> Snapshot:
        """Notify listeners. MUST be called with the lock released.

        Listeners publish to MQTT, and an MQTT listener that calls snapshot()
        would deadlock if we notified while holding the lock. Listeners are
        collected under the lock and invoked outside it.
        """
        for listener in self._listeners_copy():
            try:
                listener(snapshot)
            except Exception:
                logger.exception("state listener failed")
        return snapshot

    def _listeners_copy(self) -> List[Listener]:
        with self._lock:
            return list(self._listeners)

    def set_muted(self, muted: bool) -> Snapshot:
        with self._lock:
            muted = bool(muted)
            if muted != self._muted:
                self._muted = muted
                self._bump_locked()
            self._led_on = True
            snapshot = self._snapshot_locked()
        return self._commit(snapshot)

    def toggle(self) -> Snapshot:
        """Flip the mute state as one atomic read-modify-write.

        This is the operation that used to race: two processes each did
        `not current_state["muted"]` against their own dict.
        """
        with self._lock:
            self._muted = not self._muted
            self._led_on = True
            self._bump_locked()
            snapshot = self._snapshot_locked()
        return self._commit(snapshot)

    def set_led_on(self, on: bool) -> Snapshot:
        with self._lock:
            on = bool(on)
            if on != self._led_on:
                self._led_on = on
                self._bump_locked()
            snapshot = self._snapshot_locked()
        return self._commit(snapshot)

    def set_effect(self, name: Optional[str]) -> Snapshot:
        with self._lock:
            if name != self._effect:
                self._effect = name
                self._bump_locked()
            snapshot = self._snapshot_locked()
        return self._commit(snapshot)

    def set_hardware(self, available: bool, backend: str) -> Snapshot:
        with self._lock:
            self._available = bool(available)
            self._backend = backend
            snapshot = self._snapshot_locked()
        return self._commit(snapshot)

    def _bump_locked(self) -> None:
        self._revision += 1
        self._updated_at = time.time()

    # -- listeners ------------------------------------------------------

    def add_listener(self, listener: Listener) -> Callable[[], None]:
        """Register a change listener. Returns a callable that removes it."""
        with self._lock:
            self._listeners.append(listener)

        def remove() -> None:
            with self._lock:
                if listener in self._listeners:
                    self._listeners.remove(listener)

        return remove

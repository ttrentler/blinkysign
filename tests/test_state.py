"""SignState replaces the two independent current_state dicts that app.py and
iot_client.py each kept in separate processes.
"""
import threading

from blinkysign.state import SignState


def test_toggle_is_atomic_under_concurrency():
    """16 threads toggling 100 times each must land back where they started.

    The old code did `not current_state["muted"]` as a read-modify-write with
    no lock, in two processes at once.
    """
    state = SignState(muted=False)
    threads = [
        threading.Thread(target=lambda: [state.toggle() for _ in range(100)])
        for _ in range(16)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # 16 * 100 = 1600 flips, an even number, so we end where we began.
    assert state.snapshot().muted is False
    assert state.snapshot().revision == 1600


def test_set_muted_only_bumps_revision_on_change():
    state = SignState(muted=False)
    first = state.set_muted(True)
    second = state.set_muted(True)
    assert first.revision == second.revision


def test_listeners_fire_with_the_new_snapshot():
    state = SignState()
    seen = []
    state.add_listener(seen.append)
    state.set_muted(True)
    assert seen and seen[-1].muted is True


def test_listener_can_read_state_without_deadlocking():
    """A listener calling back into snapshot() must not deadlock.

    MQTT publishing does exactly this, so listeners are invoked with the lock
    released.
    """
    state = SignState()
    result = {}

    def listener(snapshot):
        result["muted"] = state.snapshot().muted

    state.add_listener(listener)
    done = threading.Event()

    def go():
        state.set_muted(True)
        done.set()

    threading.Thread(target=go, daemon=True).start()
    assert done.wait(timeout=5), "listener deadlocked against the state lock"
    assert result["muted"] is True


def test_failing_listener_does_not_break_the_write():
    state = SignState()

    def bad(snapshot):
        raise RuntimeError("boom")

    state.add_listener(bad)
    assert state.set_muted(True).muted is True


def test_remove_listener():
    state = SignState()
    seen = []
    remove = state.add_listener(seen.append)
    state.set_muted(True)
    remove()
    state.set_muted(False)
    assert len(seen) == 1


def test_legacy_dict_keeps_its_two_keys():
    snapshot = SignState(muted=True, led_on=True).snapshot()
    assert snapshot.to_legacy_dict() == {"muted": True, "led_on": True}

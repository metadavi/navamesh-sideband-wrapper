"""
dev_diagnostics.py — developer-only diagnostics helpers.

These functions back the optional Debug tab (see screens/debug.py), which is shown
ONLY when developer mode is enabled (env var ``NAVAMESH_DEV`` or the ``dev_mode``
setting). They are NOT part of the farmer-facing production UI, but are kept as
engineering tools so on-device diagnostics can be re-enabled for future field tests
without re-implementing them.

Each function takes the running FarmApp instance and is read-only against the public
SidebandCore API (plus the send_test_message action, which routes through the same
CoreDispatcher path the rest of the app uses). Nothing here touches Reticulum/RNS,
LXMF, or any Sideband backend file — it only observes state the backend already
exposes via getstate()/get_service_log() and the public send path.

Production connectivity logic (``_radio_is_up`` / ``_connectivity_state`` and the
``local_address`` accessor used by the Announce screen) deliberately stays on FarmApp
— it drives the always-visible status chip and is not debug-only.
"""
from __future__ import annotations

import threading

from kivy.clock import Clock

from .widgets import StatusChip


def heartbeat_age(app) -> float | None:
    """Seconds since the last service heartbeat, or None if never seen."""
    if not app.sideband:
        return None
    try:
        hb = app.sideband.getstate("service.heartbeat")
        return (app._now() - float(hb)) if hb else None
    except Exception:
        return None


def service_status_text(app) -> str:
    if app._service_launch_error is not None:
        return f"launch failed: {app._service_launch_error}"
    state = app._connectivity_state()
    return {
        StatusChip.CONNECTED:  "running (heartbeat fresh)",
        StatusChip.CONNECTING: "starting…",
        StatusChip.NO_SERVICE: "not running",
    }.get(state, state)


def interfaces_text(app) -> str:
    """Best-available interface detail. On Android only the service's
    connectivity_status string is visible to the UI; on desktop we can read
    RNS.Transport.interfaces directly."""
    if not app.sideband:
        return "(no core)"
    try:
        import RNS
        if RNS.vendor.platformutils.is_android():
            return str(app.sideband.getstate("service.connectivity_status") or "(no data yet)")
        lines = []
        for iface in RNS.Transport.interfaces:
            online = getattr(iface, "online", False)
            lines.append(f"{'● ' if online else '○ '}{iface}")
        return "\n".join(lines) if lines else "(no interfaces)"
    except Exception as exc:
        return f"(unavailable: {exc})"


def service_log_text(app) -> str:
    if not app.sideband:
        return "(no core)"
    try:
        log = app.sideband.get_service_log()
        return str(log) if log else "(no log yet)"
    except Exception as exc:
        return f"(unavailable: {exc})"


def send_test_message(app, dest_hash_hex: str, content: str, on_done=None):
    """Send a free-text LXMF message to a manually entered peer address.

    Routed through CoreDispatcher.send_text (correct send_message arg order
    + hex→bytes). Runs on a worker thread; on_done(ok, detail) on the UI thread.
    """
    dest_hash_hex = (dest_hash_hex or "").strip()
    content = content or ""
    if not app.sideband or app._dispatcher is None:
        if on_done:
            Clock.schedule_once(lambda _: on_done(False, "no core"), 0)
        return

    def _worker():
        try:
            bytes.fromhex(dest_hash_hex)  # validate hex early
            reply = app._dispatcher.send_text(dest_hash_hex, content)
            from .dispatch import FAILED
            ok = reply.state != FAILED
            detail = "sent" if ok else (reply.error or "failed")
        except Exception as exc:
            ok, detail = False, str(exc)
        if on_done:
            Clock.schedule_once(lambda _: on_done(ok, detail), 0)

    threading.Thread(target=_worker, daemon=True).start()

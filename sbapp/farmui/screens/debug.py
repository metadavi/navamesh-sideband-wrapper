"""
screens/debug.py — TEMPORARY / DEV-ONLY diagnostics tab.

Purpose: on-device verification of the backend service and end-to-end
Reticulum/LXMF networking (two-phone field test). NOT intended for farmers —
remove this screen (and its tab in app.py) before a production release.

Everything here is read-only against the public SidebandCore API plus the two
send actions (Send Announce / Send Test Message), which route through the same
paths the rest of the app uses. No Reticulum/LXMF/Sideband backend files are
touched.
"""
from __future__ import annotations

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.metrics import dp, sp
from kivy.utils import get_color_from_hex

from ..theme import (
    COLOR_ON_SURFACE, COLOR_SURFACE, COLOR_PRIMARY,
    FONT_HEADING, FONT_BODY, FONT_LABEL, FONT_ADDRESS, SCREEN_PADDING,
)
from ..widgets import BigButton
from .. import dev_diagnostics


def _field(title: str) -> Label:
    return Label(
        text=title,
        markup=True,
        font_size=sp(FONT_LABEL),
        color=get_color_from_hex(COLOR_ON_SURFACE),
        halign="left",
        valign="top",
        size_hint_y=None,
    )


class DebugScreen(BoxLayout):
    """Dev diagnostics: address, service/heartbeat/interfaces, send controls, logs."""

    name = "debug"

    def __init__(self, app, **kwargs):
        super().__init__(orientation="vertical", padding=dp(SCREEN_PADDING),
                         spacing=dp(8), **kwargs)
        self._app = app

        self.add_widget(Label(
            text="[font=emoji]🛠[/font] Debug (dev only)",
            markup=True, bold=True,
            font_size=sp(FONT_HEADING),
            color=get_color_from_hex(COLOR_ON_SURFACE),
            size_hint_y=None, height=dp(40),
        ))

        # Scrollable body so it fits on small phone screens.
        scroll = ScrollView(size_hint=(1, 1))
        body = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8),
                         padding=[0, 0, 0, dp(8)])
        body.bind(minimum_height=body.setter("height"))
        scroll.add_widget(body)

        # ── Live status fields (refreshed by app._poll → self.refresh) ─────────
        self._addr = _field("")
        self._svc = _field("")
        self._hb = _field("")
        self._ifaces = _field("")
        for w in (self._addr, self._svc, self._hb, self._ifaces):
            w.bind(width=lambda inst, v: setattr(inst, "text_size", (v, None)))
            w.bind(texture_size=lambda inst, v: setattr(inst, "height", v[1]))
            body.add_widget(w)

        # ── Actions ────────────────────────────────────────────────────────────
        announce_btn = BigButton(icon="📢", label="Send Announce")
        announce_btn.bind(on_press=self._on_announce)
        body.add_widget(announce_btn)

        copy_btn = BigButton(icon="📋", label="Copy Address")
        copy_btn.bind(on_press=self._on_copy)
        body.add_widget(copy_btn)

        body.add_widget(_field("[b]Send test message[/b]"))
        self._peer_in = TextInput(
            hint_text="peer LXMF address (hex)",
            multiline=False, size_hint_y=None, height=dp(48),
            font_size=sp(FONT_ADDRESS),
        )
        self._msg_in = TextInput(
            text="test from Navamesh Farm",
            multiline=False, size_hint_y=None, height=dp(48),
            font_size=sp(FONT_BODY),
        )
        body.add_widget(self._peer_in)
        body.add_widget(self._msg_in)
        send_btn = BigButton(icon="✉", label="Send Test Message")
        send_btn.bind(on_press=self._on_send_test)
        body.add_widget(send_btn)

        self._send_status = _field("")
        body.add_widget(self._send_status)

        # ── Logs ────────────────────────────────────────────────────────────────
        body.add_widget(_field("[b]Service log[/b]"))
        self._log = _field("(no log yet)")
        self._log.font_size = sp(FONT_ADDRESS)
        self._log.bind(width=lambda inst, v: setattr(inst, "text_size", (v, None)))
        self._log.bind(texture_size=lambda inst, v: setattr(inst, "height", v[1]))
        body.add_widget(self._log)

        self.add_widget(scroll)
        self.refresh()

    # ── Live refresh (called from app._poll) ───────────────────────────────────

    def refresh(self):
        app = self._app
        try:
            self._addr.text = f"[b]Address:[/b] {app.local_address()}"
            self._svc.text = f"[b]Service:[/b] {dev_diagnostics.service_status_text(app)}"
            age = dev_diagnostics.heartbeat_age(app)
            self._hb.text = (
                "[b]Heartbeat:[/b] never" if age is None
                else f"[b]Heartbeat:[/b] {age:.0f}s ago"
            )
            self._ifaces.text = f"[b]Interfaces:[/b]\n{dev_diagnostics.interfaces_text(app)}"
            self._log.text = dev_diagnostics.service_log_text(app)
        except Exception as exc:
            self._svc.text = f"[b]Service:[/b] (debug refresh error: {exc})"

    # ── Connectivity chip hooks (no chip here, but keep the screen API uniform) ─

    def set_state(self, state: str, detail: str = ""):
        pass

    def set_connected(self, connected: bool, detail: str = ""):
        pass

    # ── Actions ─────────────────────────────────────────────────────────────────

    def _on_announce(self, *_):
        self._app.send_announce()
        self._send_status.text = "[b]Last action:[/b] announce sent"

    def _on_copy(self, *_):
        addr = self._app.local_address()
        try:
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(addr)
            self._send_status.text = "[b]Last action:[/b] address copied"
        except Exception as exc:
            self._send_status.text = f"[b]Last action:[/b] copy failed ({exc})"

    def _on_send_test(self, *_):
        peer = self._peer_in.text.strip()
        msg = self._msg_in.text
        self._send_status.text = "[b]Last action:[/b] sending…"

        def _done(ok, detail):
            self._send_status.text = f"[b]Last action:[/b] test message {detail}"

        dev_diagnostics.send_test_message(self._app, peer, msg, on_done=_done)

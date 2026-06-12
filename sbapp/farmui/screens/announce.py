"""screens/announce.py — Own LXMF address + Send Announce button."""
from __future__ import annotations

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.metrics import dp, sp
from kivy.utils import get_color_from_hex

from ..theme import (
    COLOR_PRIMARY, COLOR_ON_SURFACE, COLOR_SURFACE,
    FONT_HEADING, FONT_BODY, FONT_ADDRESS, SCREEN_PADDING,
)
from ..widgets import BigButton, StatusChip


class AnnounceScreen(BoxLayout):
    name = "announce"

    def __init__(self, app, **kwargs):
        super().__init__(orientation="vertical", padding=dp(SCREEN_PADDING), spacing=dp(16), **kwargs)
        self._app = app

        self.add_widget(Label(
            text="📢 Your Farm Address",
            font_size=sp(FONT_HEADING),
            color=get_color_from_hex(COLOR_ON_SURFACE),
            size_hint_y=None,
            height=dp(48),
            bold=True,
        ))

        self._address_label = Label(
            text="(initialising…)",
            font_size=sp(FONT_ADDRESS),
            color=get_color_from_hex(COLOR_ON_SURFACE),
            size_hint_y=None,
            height=dp(40),
        )
        self.add_widget(self._address_label)

        self._last_sent_label = Label(
            text="Last announce: never",
            font_size=sp(FONT_BODY),
            color=get_color_from_hex(COLOR_ON_SURFACE),
            size_hint_y=None,
            height=dp(32),
        )
        self.add_widget(self._last_sent_label)

        btn = BigButton(icon="📢", label="Send Announce")
        btn.bind(on_press=self._send_announce)
        self.add_widget(btn)

        self._chip = StatusChip()
        self.add_widget(self._chip)

        self.add_widget(BoxLayout())  # spacer

    def update_address(self, address_hex: str):
        self._address_label.text = address_hex

    def update_last_sent(self, ts_str: str):
        self._last_sent_label.text = f"Last announce: {ts_str}"

    def set_connected(self, connected: bool, detail: str = ""):
        self._chip.set_connected(connected, detail)

    def _send_announce(self, *_):
        self._app.send_announce()
        self._last_sent_label.text = "Last announce: just now"

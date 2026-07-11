"""screens/announce.py — Connect tab: own LXMF address + Connect (announce) button."""
from __future__ import annotations

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.metrics import dp, sp
from kivy.utils import get_color_from_hex

from .. import theme
from ..theme import (
    COLOR_ON_SURFACE, COLOR_MUTED,
    FONT_CAPTION, FONT_ADDRESS,
    SCREEN_PADDING, SPACE_MD,
    TOUCH_TARGET,
)
from ..widgets import BigButton, SectionHeading, Panel


def _mono_kw():
    fam = theme.family(theme.FONT_MONO)
    return {"font_name": fam} if fam else {}


class AnnounceScreen(BoxLayout):
    name = "announce"

    def __init__(self, app, **kwargs):
        super().__init__(orientation="vertical", padding=dp(SCREEN_PADDING),
                         spacing=dp(SPACE_MD), **kwargs)
        self._app = app

        self.add_widget(SectionHeading("[font=emoji]📡[/font]  Your Farm Address"))

        # ── Address panel (Field-Log card) ──────────────────────────────────
        card = Panel(size_hint_y=None)
        card.bind(minimum_height=card.setter("height"))

        addr_caption = Label(
            text="LXMF ADDRESS",
            font_size=sp(FONT_CAPTION),
            color=get_color_from_hex(COLOR_MUTED),
            halign="left", valign="middle",
            size_hint_y=None, height=dp(TOUCH_TARGET) / 2,
            **_mono_kw(),
        )
        addr_caption.bind(width=lambda i, w: setattr(i, "text_size", (w, None)))
        card.add_widget(addr_caption)
        self._address_label = Label(
            text="(initialising…)",
            font_size=sp(FONT_ADDRESS),
            color=get_color_from_hex(COLOR_ON_SURFACE),
            halign="left", valign="middle",
            size_hint_y=None, height=dp(TOUCH_TARGET),
            **_mono_kw(),
        )
        self._address_label.bind(
            width=lambda i, w: setattr(i, "text_size", (w, None)))
        card.add_widget(self._address_label)

        self._last_sent_label = Label(
            text="Last announce: never",
            font_size=sp(FONT_CAPTION),
            color=get_color_from_hex(COLOR_MUTED),
            halign="left", valign="middle",
            size_hint_y=None, height=dp(TOUCH_TARGET) / 2,
            **_mono_kw(),
        )
        self._last_sent_label.bind(
            width=lambda i, w: setattr(i, "text_size", (w, None)))
        card.add_widget(self._last_sent_label)
        self.add_widget(card)

        # ── The one primary action on this screen (Mesa Red CTA) ────────────
        # Broadcasts the device announce over the HaLow HT-HD01 network. The
        # action is unchanged from the former "Send Announce" button — only the
        # label is renamed to "Connect".
        btn = BigButton(icon="📡", label="Connect", variant="primary")
        btn.bind(on_press=self._send_announce)
        self.add_widget(btn)

        self.add_widget(BoxLayout())  # spacer

    def update_address(self, address_hex: str):
        self._address_label.text = address_hex

    def update_last_sent(self, ts_str: str):
        self._last_sent_label.text = f"Last announce: {ts_str}"

    def _send_announce(self, *_):
        self._app.send_announce()
        self._last_sent_label.text = "Last announce: just now"

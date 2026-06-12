"""screens/stream.py — Announce stream: heard gateways highlighted, tap to pin."""
from __future__ import annotations

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.metrics import dp, sp
from kivy.utils import get_color_from_hex
from kivy.graphics import Color, Rectangle

from ..theme import (
    COLOR_ON_SURFACE, COLOR_SURFACE, COLOR_GATEWAY_HIGHLIGHT,
    COLOR_PRIMARY, COLOR_ON_PRIMARY,
    FONT_HEADING, FONT_BODY, FONT_LABEL, SCREEN_PADDING,
)
from ..widgets import BigButton, StatusChip, EmptyState


GATEWAY_DISPLAY_NAME = "Navamesh Gateway"


def _is_gateway(display_name: str) -> bool:
    return display_name.strip() == GATEWAY_DISPLAY_NAME


class AnnounceRow(BoxLayout):
    """Single row in the announce stream list."""

    def __init__(self, display_name: str, short_hash: str, time_ago: str,
                 on_set_gateway=None, **kwargs):
        super().__init__(
            orientation="horizontal",
            size_hint_y=None, height=dp(72),
            padding=dp(8), spacing=dp(8),
            **kwargs
        )
        is_gw = _is_gateway(display_name)
        bg_color = get_color_from_hex(COLOR_GATEWAY_HIGHLIGHT if is_gw else "#FFFFFF")
        with self.canvas.before:
            Color(*bg_color)
            self._rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *_: setattr(self._rect, 'pos', self.pos),
                  size=lambda *_: setattr(self._rect, 'size', self.size))

        name_block = BoxLayout(orientation="vertical", spacing=dp(2))
        prefix = "🌾 " if is_gw else ""
        name_block.add_widget(Label(
            text=f"{prefix}{display_name}",
            font_size=sp(FONT_BODY),
            color=get_color_from_hex(COLOR_ON_SURFACE),
            halign="left", valign="middle",
            size_hint_y=None, height=dp(28),
            bold=is_gw,
        ))
        name_block.add_widget(Label(
            text=f"{short_hash}  ·  {time_ago}",
            font_size=sp(FONT_LABEL - 2),
            color=get_color_from_hex(COLOR_ON_SURFACE),
            halign="left", valign="middle",
            size_hint_y=None, height=dp(20),
        ))
        self.add_widget(name_block)

        if on_set_gateway:
            btn = Button(
                text="Set as\nfarm GW",
                font_size=sp(FONT_LABEL - 2),
                size_hint=(None, None),
                width=dp(80), height=dp(56),
                background_color=get_color_from_hex(COLOR_PRIMARY),
                color=get_color_from_hex(COLOR_ON_PRIMARY),
            )
            btn.bind(on_press=lambda *_: on_set_gateway(display_name, short_hash))
            self.add_widget(btn)


class StreamScreen(BoxLayout):
    name = "stream"

    def __init__(self, app, **kwargs):
        super().__init__(orientation="vertical", padding=dp(SCREEN_PADDING), spacing=dp(8), **kwargs)
        self._app = app
        self._rows = {}

        self.add_widget(Label(
            text="📡 Nearby Gateways",
            font_size=sp(FONT_HEADING),
            color=get_color_from_hex(COLOR_ON_SURFACE),
            size_hint_y=None, height=dp(48),
            bold=True,
        ))

        self._chip = StatusChip()
        self.add_widget(self._chip)

        scroll = ScrollView(size_hint=(1, 1))
        self._list = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(2))
        self._list.bind(minimum_height=self._list.setter("height"))
        scroll.add_widget(self._list)
        self.add_widget(scroll)

        self._empty = EmptyState(
            icon="📡",
            message="No announces heard yet.\nCheck your radio connection.",
        )
        self._list.add_widget(self._empty)

    def add_announce(self, display_name: str, short_hash: str, time_ago: str):
        if self._empty.parent:
            self._list.remove_widget(self._empty)
        row = AnnounceRow(
            display_name=display_name,
            short_hash=short_hash,
            time_ago=time_ago,
            on_set_gateway=self._app.set_gateway,
        )
        self._list.add_widget(row)
        self._rows[short_hash] = row

    def clear(self):
        self._list.clear_widgets()
        self._list.add_widget(self._empty)
        self._rows.clear()

    def set_connected(self, connected: bool, detail: str = ""):
        self._chip.set_connected(connected, detail)

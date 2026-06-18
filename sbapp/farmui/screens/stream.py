"""screens/stream.py — Announce stream: heard gateways highlighted, tap to pin."""
from __future__ import annotations

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.metrics import dp, sp
from kivy.utils import get_color_from_hex
from kivy.graphics import Color, RoundedRectangle, Line

from .. import theme
from ..theme import (
    COLOR_ON_SURFACE, COLOR_MUTED, COLOR_CARD, COLOR_HAIRLINE,
    COLOR_GATEWAY_HIGHLIGHT, COLOR_PRIMARY, COLOR_ON_PRIMARY,
    FONT_BODY, FONT_CAPTION, SCREEN_PADDING, SPACE_XS, SPACE_SM, SPACE_MD,
    ROW_HEIGHT, TAB_HEIGHT, CARD_RADIUS, HAIRLINE_WIDTH,
)
from ..widgets import StatusChip, EmptyState, SectionHeading


GATEWAY_DISPLAY_NAME = "Navamesh Gateway"
_MAX_STREAM_ROWS = 200


def _is_gateway(display_name: str) -> bool:
    return display_name.strip() == GATEWAY_DISPLAY_NAME


def _mono_kw():
    fam = theme.family(theme.FONT_MONO)
    return {"font_name": fam} if fam else {}


def _set_button(primary: bool, on_press) -> Button:
    """A compact 'Set as farm GW' control. Mesa Red (primary) marks the one
    most-important action — the gateway row — while other rows get a quiet
    outlined variant so Mesa Red stays rare (the Rarity Rule)."""
    btn = Button(
        text="Set as\nfarm GW",
        font_size=sp(FONT_CAPTION),
        size_hint=(None, None),
        width=dp(84), height=dp(TAB_HEIGHT),
        halign="center", valign="middle",
        bold=primary,
        background_normal="", background_down="",
        background_color=(0, 0, 0, 0),
    )
    if primary:
        fill = get_color_from_hex(COLOR_PRIMARY)
        fill_down = get_color_from_hex(theme.COLOR_MESA_RED)
        btn.color = get_color_from_hex(COLOR_ON_PRIMARY)
        border = None
    else:
        fill = get_color_from_hex(COLOR_CARD)
        fill_down = get_color_from_hex(COLOR_GATEWAY_HIGHLIGHT)
        btn.color = get_color_from_hex(COLOR_ON_SURFACE)
        border = get_color_from_hex(COLOR_HAIRLINE)
    radius = dp(TAB_HEIGHT) / 2
    with btn.canvas.before:
        bg = Color(*fill)
        rect = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[radius])
        if border is not None:
            Color(*border)
            line = Line(width=dp(HAIRLINE_WIDTH),
                        rounded_rectangle=(btn.x, btn.y, btn.width, btn.height, radius))
        else:
            line = None

    def _sync(*_):
        rect.pos, rect.size = btn.pos, btn.size
        if line is not None:
            line.rounded_rectangle = (btn.x, btn.y, btn.width, btn.height, radius)
    btn.bind(pos=_sync, size=_sync,
             state=lambda _i, s: setattr(bg, "rgba", fill_down if s == "down" else fill))
    btn.bind(on_press=lambda *_: on_press())
    return btn


class AnnounceRow(BoxLayout):
    """Single row in the announce stream list — a Field-Log tile."""

    def __init__(self, display_name: str, short_hash: str, time_ago: str,
                 on_set_gateway=None, **kwargs):
        super().__init__(
            orientation="horizontal",
            size_hint_y=None, height=dp(ROW_HEIGHT),
            padding=dp(SPACE_SM), spacing=dp(SPACE_SM),
            **kwargs
        )
        is_gw = _is_gateway(display_name)
        fill = get_color_from_hex(COLOR_GATEWAY_HIGHLIGHT if is_gw else COLOR_CARD)
        radius = dp(CARD_RADIUS)
        with self.canvas.before:
            Color(*fill)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
            Color(*get_color_from_hex(COLOR_HAIRLINE))
            self._line = Line(width=dp(HAIRLINE_WIDTH),
                              rounded_rectangle=(self.x, self.y, self.width, self.height, radius))
        self.bind(pos=self._sync, size=self._sync)

        name_block = BoxLayout(orientation="vertical", spacing=dp(SPACE_XS))
        prefix = "[font=emoji]🌾[/font] " if is_gw else ""
        name_block.add_widget(Label(
            text=f"{prefix}{display_name}",
            markup=True,
            font_size=sp(FONT_BODY),
            color=get_color_from_hex(COLOR_ON_SURFACE),
            halign="left", valign="middle",
            size_hint_y=None, height=dp(28),
            bold=is_gw,
        ))
        sub = Label(
            text=f"{short_hash}  ·  {time_ago}",
            font_size=sp(FONT_CAPTION),
            color=get_color_from_hex(COLOR_MUTED),
            halign="left", valign="middle",
            size_hint_y=None, height=dp(20),
            **_mono_kw(),
        )
        sub.bind(width=lambda i, w: setattr(i, "text_size", (w, None)))
        name_block.add_widget(sub)
        self.add_widget(name_block)

        if on_set_gateway:
            self.add_widget(_set_button(
                primary=is_gw,
                on_press=lambda: on_set_gateway(display_name, short_hash),
            ))

    def _sync(self, *_):
        radius = dp(CARD_RADIUS)
        self._rect.pos, self._rect.size = self.pos, self.size
        self._line.rounded_rectangle = (self.x, self.y, self.width, self.height, radius)


class StreamScreen(BoxLayout):
    name = "stream"

    def __init__(self, app, **kwargs):
        super().__init__(orientation="vertical", padding=dp(SCREEN_PADDING),
                         spacing=dp(SPACE_MD), **kwargs)
        self._app = app
        self._rows = {}

        self.add_widget(SectionHeading("[font=emoji]📡[/font]  Nearby Gateways"))

        self._chip = StatusChip()
        self.add_widget(self._chip)

        scroll = ScrollView(size_hint=(1, 1))
        self._list = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(SPACE_SM))
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
        if short_hash in self._rows:
            return
        while len(self._rows) >= _MAX_STREAM_ROWS:
            oldest_hash = next(iter(self._rows))
            self._list.remove_widget(self._rows.pop(oldest_hash))
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

    def set_state(self, state: str, detail: str = ""):
        self._chip.set_state(state, detail)

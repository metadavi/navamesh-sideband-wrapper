"""screens/stream.py — Talk tab: every heard device, tap a row to open its chat.

Rows are uniform and tappable — the gateway-vs-peer decision is made only when
the user taps a device (FarmApp.open_chat → is_gateway_device), so this screen
never pre-classifies devices.
"""
from __future__ import annotations

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.metrics import dp, sp
from kivy.utils import get_color_from_hex
from kivy.graphics import Color, RoundedRectangle, Line

from .. import theme
from ..theme import (
    COLOR_ON_SURFACE, COLOR_MUTED, COLOR_CARD, COLOR_HAIRLINE,
    FONT_BODY, FONT_CAPTION, FONT_HEADING,
    SCREEN_PADDING, SPACE_XS, SPACE_SM, SPACE_MD,
    ROW_HEIGHT, CARD_RADIUS, HAIRLINE_WIDTH,
)
from ..widgets import StatusChip, EmptyState, SectionHeading
# Re-exported for backward compatibility; the canonical helper now lives in
# farmui.devices so the gateway/peer rule has a single home.
from ..devices import is_gateway_device, GATEWAY_DISPLAY_NAME  # noqa: F401

_MAX_STREAM_ROWS = 200


def _mono_kw():
    fam = theme.family(theme.FONT_MONO)
    return {"font_name": fam} if fam else {}


class AnnounceRow(BoxLayout):
    """A single, uniform, tappable device row in the Talk list (Field-Log tile).

    A tap (press + release that barely moves) opens the device's chat; a drag is
    left to the enclosing ScrollView. Tap-vs-drag is measured in window coords
    (touch.x/y, stable across down/up) like ResultCard's inline-map handling.
    """

    def __init__(self, display_name: str, short_hash: str, time_ago: str,
                 on_open=None, **kwargs):
        super().__init__(
            orientation="horizontal",
            size_hint_y=None, height=dp(ROW_HEIGHT),
            padding=dp(SPACE_SM), spacing=dp(SPACE_SM),
            **kwargs
        )
        self._on_open = on_open
        self._display_name = display_name
        self._short_hash = short_hash
        # Per-instance touch key: every row in the list shares one touch.ud dict,
        # so a shared literal key would be popped by whichever row is dispatched
        # first on touch-up (regardless of collision), leaving only one row
        # tappable. Keying by id(self) isolates each row's own press.
        self._press_key = f"_row_press_{id(self)}"
        radius = dp(CARD_RADIUS)
        with self.canvas.before:
            Color(*get_color_from_hex(COLOR_CARD))
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
            Color(*get_color_from_hex(COLOR_HAIRLINE))
            self._line = Line(width=dp(HAIRLINE_WIDTH),
                              rounded_rectangle=(self.x, self.y, self.width, self.height, radius))
        self.bind(pos=self._sync, size=self._sync)

        name_block = BoxLayout(orientation="vertical", spacing=dp(SPACE_XS))
        name_block.add_widget(Label(
            text=display_name,
            font_size=sp(FONT_BODY),
            color=get_color_from_hex(COLOR_ON_SURFACE),
            halign="left", valign="middle",
            size_hint_y=None, height=dp(28),
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

        # Chevron affordance so the row reads as "tap to open".
        self.add_widget(Label(
            text="›",
            font_size=sp(FONT_HEADING),
            color=get_color_from_hex(COLOR_MUTED),
            size_hint_x=None, width=dp(24),
            halign="center", valign="middle",
        ))

    def _sync(self, *_):
        radius = dp(CARD_RADIUS)
        self._rect.pos, self._rect.size = self.pos, self.size
        self._line.rounded_rectangle = (self.x, self.y, self.width, self.height, radius)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.ud[self._press_key] = (touch.x, touch.y)
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        origin = touch.ud.pop(self._press_key, None)
        if origin is not None and self._on_open is not None:
            moved = (abs(touch.x - origin[0]) > dp(SPACE_MD) or
                     abs(touch.y - origin[1]) > dp(SPACE_MD))
            if not moved and self.collide_point(*touch.pos):
                self._on_open(self._display_name, self._short_hash)
                return True
        return super().on_touch_up(touch)


class StreamScreen(BoxLayout):
    name = "talk"

    def __init__(self, app, **kwargs):
        super().__init__(orientation="vertical", padding=dp(SCREEN_PADDING),
                         spacing=dp(SPACE_MD), **kwargs)
        self._app = app
        self._rows = {}

        self.add_widget(SectionHeading("[font=emoji]💬[/font]  Nearby devices"))

        self._chip = StatusChip()
        self.add_widget(self._chip)

        scroll = ScrollView(size_hint=(1, 1))
        self._list = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(SPACE_SM))
        self._list.bind(minimum_height=self._list.setter("height"))
        scroll.add_widget(self._list)
        self.add_widget(scroll)

        self._empty = EmptyState(
            icon="📡",
            message="No devices heard yet.\nTap Connect, then check your radio.",
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
            on_open=self._app.open_chat,
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

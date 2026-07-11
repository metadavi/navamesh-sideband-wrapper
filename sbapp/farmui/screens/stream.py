"""screens/stream.py — Talk tab: every heard device, tap a row to open its chat.

Rows are uniform and tappable — the gateway-vs-peer decision is made only when
the user taps a device (FarmApp.open_chat → is_gateway_device), so this screen
never pre-classifies devices.
"""
from __future__ import annotations

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.widget import Widget
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
from ..widgets import EmptyState, SectionHeading, BigButton
# Re-exported for backward compatibility; the canonical helper now lives in
# farmui.devices so the gateway/peer rule has a single home.
from ..devices import is_gateway_device, GATEWAY_DISPLAY_NAME  # noqa: F401

_MAX_STREAM_ROWS = 200

# Fixed width of the row's right-hand chevron. A left spacer of the same width
# balances it so the device name + hash sit dead-centre in the card.
_CHEVRON_W = 24


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
                 received=None, on_open=None, **kwargs):
        super().__init__(
            orientation="horizontal",
            size_hint_y=None, height=dp(ROW_HEIGHT),
            padding=dp(SPACE_SM), spacing=dp(SPACE_SM),
            **kwargs
        )
        self._on_open = on_open
        self._display_name = display_name
        self._short_hash = short_hash
        # Announce received-time (epoch). Kept so the "time ago" label can be
        # recomputed on every poll (it ticks up without a fresh announce).
        self.received = received
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

        # Left spacer mirrors the chevron on the right, so the centred
        # name/hash block lands in the true middle of the card.
        self.add_widget(Widget(size_hint_x=None, width=dp(_CHEVRON_W)))

        name_block = BoxLayout(orientation="vertical", spacing=dp(SPACE_XS))
        name_lbl = Label(
            text=display_name,
            font_size=sp(FONT_BODY),
            color=get_color_from_hex(COLOR_ON_SURFACE),
            halign="center", valign="middle",
            size_hint_y=None, height=dp(28),
        )
        name_lbl.bind(width=lambda i, w: setattr(i, "text_size", (w, None)))
        self._name_lbl = name_lbl
        name_block.add_widget(name_lbl)
        # The LXMF address is intentionally not shown here — name + "time ago" is
        # enough for the Talk list; the full address lives in the conversation view.
        sub = Label(
            text=f"{time_ago}",
            font_size=sp(FONT_CAPTION),
            color=get_color_from_hex(COLOR_MUTED),
            halign="center", valign="middle",
            size_hint_y=None, height=dp(20),
            **_mono_kw(),
        )
        sub.bind(width=lambda i, w: setattr(i, "text_size", (w, None)))
        self._sub = sub
        name_block.add_widget(sub)
        self.add_widget(name_block)

        # Chevron affordance so the row reads as "tap to open".
        self.add_widget(Label(
            text="›",
            font_size=sp(FONT_HEADING),
            color=get_color_from_hex(COLOR_MUTED),
            size_hint_x=None, width=dp(_CHEVRON_W),
            halign="center", valign="middle",
        ))

    def refresh_time_ago(self, time_ago: str):
        """Re-render the caption (called per poll) — just the 'time ago' now."""
        self._sub.text = f"{time_ago}"

    def set_display_name(self, display_name: str):
        """Update the shown name (e.g. the farmer saved a local alias)."""
        self._display_name = display_name
        self._name_lbl.text = display_name

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
        # Over-the-air update card (hidden until an update is found).
        self._update_btn = None
        self._update_cb = None

        self.add_widget(SectionHeading("[font=emoji]💬[/font]  Nearby devices"))

        scroll = ScrollView(size_hint=(1, 1))
        self._list = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(SPACE_SM))
        self._list.bind(minimum_height=self._list.setter("height"))
        scroll.add_widget(self._list)
        self.add_widget(scroll)

        self._empty = EmptyState(
            icon="📡",
            message="No devices heard yet.\nYour phone announces itself automatically.\nCheck the white radio box.",
        )
        self._list.add_widget(self._empty)

    def add_announce(self, display_name: str, short_hash: str, time_ago: str,
                     received=None):
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
            received=received,
            on_open=self._app.open_chat,
        )
        self._list.add_widget(row)
        self._rows[short_hash] = row

    def update_name(self, short_hash: str, display_name: str):
        """Rename a visible row in place (alias saved/cleared). No-op if absent."""
        row = self._rows.get(short_hash)
        if row is not None:
            row.set_display_name(display_name)

    def refresh_times(self, formatter):
        """Recompute every visible row's 'time ago' label using `formatter(epoch)`.

        Called on each poll so labels tick up ("1m ago" → "2m ago") without a
        fresh announce. Rows with no stored timestamp are left untouched.
        """
        for row in self._rows.values():
            if row.received is not None:
                row.refresh_time_ago(formatter(row.received))

    def clear(self):
        self._list.clear_widgets()
        self._list.add_widget(self._empty)
        self._rows.clear()

    # ── Over-the-air update card ─────────────────────────────────────────────

    def show_update(self, version: str, on_install):
        """Show (or refresh) the 'update available' card above the device list.

        Idempotent per poll — repeated calls just update the label/callback.
        The card is deliberately farmer-simple: one big tap target.
        """
        self._update_cb = on_install
        label = f"Update available (v{version}) — tap to install"
        if self._update_btn is None:
            btn = BigButton(icon="⬇", label=label, variant="primary")
            btn.size_hint_y = None
            btn.bind(on_release=lambda *_: self._fire_update())
            # Insert directly under the heading (widget index counts from the
            # bottom in Kivy, so len(children)-1 places it right below it).
            self.add_widget(btn, index=len(self.children) - 1)
            self._update_btn = btn
        else:
            self._update_btn.text = f"[font=emoji]⬇[/font]  {label}"

    def _fire_update(self):
        if self._update_cb is not None:
            self._update_cb()

    def set_update_status(self, text: str, enabled: bool = False):
        """Progress feedback on the card itself (e.g. 'Downloading update…')."""
        if self._update_btn is not None:
            self._update_btn.text = text
            self._update_btn.disabled = not enabled

    def hide_update(self):
        if self._update_btn is not None:
            self.remove_widget(self._update_btn)
            self._update_btn = None
            self._update_cb = None

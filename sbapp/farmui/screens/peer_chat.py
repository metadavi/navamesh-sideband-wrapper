"""screens/peer_chat.py — Peer messenger: normal free-text LXMF conversation.

Opened when the user taps a non-gateway device in the Talk tab. Unlike the
gateway command dashboard, this is an ordinary chat: scrollable history, a text
field, and a send button. It reuses the existing LXMF send path
(FarmApp.send_peer_text → CoreDispatcher.send_text) and the shared message DB —
no new backend behavior.
"""
from __future__ import annotations

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.metrics import dp, sp
from kivy.utils import get_color_from_hex
from kivy.graphics import Color, RoundedRectangle, Line

from .. import theme
from ..theme import (
    COLOR_ON_SURFACE, COLOR_MUTED, COLOR_CARD, COLOR_HAIRLINE,
    COLOR_GATEWAY_HIGHLIGHT, COLOR_PRIMARY, COLOR_ON_PRIMARY, COLOR_SURFACE,
    FONT_BODY, FONT_LABEL,
    SCREEN_PADDING, SPACE_SM, SPACE_MD, CARD_PADDING, CARD_RADIUS,
    HAIRLINE_WIDTH, INPUT_HEIGHT, TOUCH_TARGET,
)
from ..widgets import StatusChip, EmptyState, BackBar, _body


def _body_kw():
    return _body()


class _Bubble(BoxLayout):
    """One chat message — a rounded card aligned right (sent) or left (received)."""

    def __init__(self, text: str, outbound: bool, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None,
                         spacing=0, **kwargs)
        fill = COLOR_GATEWAY_HIGHLIGHT if outbound else COLOR_CARD
        card = BoxLayout(orientation="vertical", size_hint=(0.82, None),
                         padding=dp(CARD_PADDING))
        radius = dp(CARD_RADIUS)
        with card.canvas.before:
            Color(*get_color_from_hex(fill))
            rect = RoundedRectangle(pos=card.pos, size=card.size, radius=[radius])
            Color(*get_color_from_hex(COLOR_HAIRLINE))
            line = Line(width=dp(HAIRLINE_WIDTH),
                        rounded_rectangle=(card.x, card.y, card.width, card.height, radius))

        def _sync(*_):
            rect.pos, rect.size = card.pos, card.size
            line.rounded_rectangle = (card.x, card.y, card.width, card.height, radius)
        card.bind(pos=_sync, size=_sync)

        lbl = Label(
            text=text,
            font_size=sp(FONT_BODY),
            color=get_color_from_hex(COLOR_ON_SURFACE),
            halign="left", valign="top",
            size_hint_y=None,
            **_body_kw(),
        )

        def _on_texture(_i, size):
            lbl.height = size[1]
            card.height = lbl.height + 2 * dp(CARD_PADDING)
            self.height = card.height

        lbl.bind(width=lambda i, w: setattr(i, "text_size", (w, None)),
                 texture_size=_on_texture)
        card.add_widget(lbl)

        spacer = Widget(size_hint_x=0.18)
        if outbound:
            self.add_widget(spacer)
            self.add_widget(card)
        else:
            self.add_widget(card)
            self.add_widget(spacer)


class PeerChatScreen(BoxLayout):
    name = "peer_chat"

    def __init__(self, app, **kwargs):
        super().__init__(orientation="vertical", padding=dp(SCREEN_PADDING),
                         spacing=dp(SPACE_MD), **kwargs)
        self._app = app
        self._peer_hash = None  # hex string of the active peer

        self._backbar = BackBar(title="", on_back=app.go_home)
        self.add_widget(self._backbar)

        self._chip = StatusChip()
        self.add_widget(self._chip)

        scroll = ScrollView(size_hint=(1, 1))
        self._msgs = BoxLayout(orientation="vertical", size_hint_y=None,
                               spacing=dp(SPACE_SM))
        self._msgs.bind(minimum_height=self._msgs.setter("height"))
        self._empty = EmptyState(icon="💬",
                                 message="No messages yet.\nSay hello below.")
        self._msgs.add_widget(self._empty)
        scroll.add_widget(self._msgs)
        self._scroll = scroll
        self.add_widget(scroll)

        # ── Composer row: text field + send ─────────────────────────────────
        row = BoxLayout(orientation="horizontal", size_hint_y=None,
                        height=dp(INPUT_HEIGHT), spacing=dp(SPACE_SM))
        self._input = TextInput(
            hint_text="Message…",
            multiline=False,
            font_size=sp(FONT_BODY),
            background_color=get_color_from_hex(COLOR_SURFACE),
            foreground_color=get_color_from_hex(COLOR_ON_SURFACE),
            cursor_color=get_color_from_hex(COLOR_PRIMARY),
            padding=[dp(SPACE_SM), dp(SPACE_SM)],
            size_hint_x=1,
        )
        self._input.bind(on_text_validate=lambda *_: self._send())
        row.add_widget(self._input)

        send_btn = Button(
            text="Send",
            font_size=sp(FONT_LABEL), bold=True,
            size_hint_x=None, width=dp(88),
            background_normal="", background_down="",
            background_color=get_color_from_hex(COLOR_PRIMARY),
            color=get_color_from_hex(COLOR_ON_PRIMARY),
        )
        send_btn.bind(on_press=lambda *_: self._send())
        row.add_widget(send_btn)
        self.add_widget(row)

    # ── Public API (called by FarmApp) ──────────────────────────────────────

    def open_peer(self, display_name: str, dest_hex: str):
        """Reset the view for a freshly-tapped peer; history is filled by polling."""
        self._peer_hash = dest_hex
        muted = COLOR_MUTED.lstrip("#")
        self._backbar.set_title(
            f"[b]{display_name}[/b]  [color={muted}]{dest_hex[:16]}…[/color]")
        self._msgs.clear_widgets()
        self._msgs.add_widget(self._empty)
        self._input.text = ""

    def add_message(self, text: str, outbound: bool):
        if self._empty.parent:
            self._msgs.remove_widget(self._empty)
        self._msgs.add_widget(_Bubble(text=text, outbound=outbound))
        # Keep the latest message in view.
        self._scroll.scroll_y = 0

    def set_connected(self, connected: bool, detail: str = ""):
        self._chip.set_connected(connected, detail)

    def set_state(self, state: str, detail: str = ""):
        self._chip.set_state(state, detail)

    # ── Internal ─────────────────────────────────────────────────────────────

    def _send(self):
        text = (self._input.text or "").strip()
        if not text or not self._peer_hash:
            return
        self._app.send_peer_text(self._peer_hash, text)
        self._input.text = ""

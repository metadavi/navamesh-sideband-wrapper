"""screens/conversation.py — Pinned-gateway header + 9 command buttons + message list."""
from __future__ import annotations

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.metrics import dp, sp
from kivy.utils import get_color_from_hex

from ..theme import (
    COLOR_ON_SURFACE, COLOR_SURFACE, COLOR_CARD, COLOR_PRIMARY, COLOR_ON_PRIMARY,
    FONT_HEADING, FONT_BODY, FONT_LABEL, SCREEN_PADDING,
)
from ..widgets import BigButton, ResultCard, StatusChip, EmptyState
from ..command_registry import COMMANDS


class ConversationScreen(BoxLayout):
    name = "conversation"

    def __init__(self, app, **kwargs):
        super().__init__(orientation="vertical", padding=dp(SCREEN_PADDING), spacing=dp(8), **kwargs)
        self._app = app

        # ── Gateway header ─────────────────────────────────────────────────
        self._gw_label = Label(
            text="Gateway: (none pinned — tap stream to set)",
            font_size=sp(FONT_LABEL),
            color=get_color_from_hex(COLOR_ON_SURFACE),
            size_hint_y=None, height=dp(32),
            halign="left",
        )
        self.add_widget(self._gw_label)

        self._chip = StatusChip()
        self.add_widget(self._chip)

        # ── Command button grid (3×3) ──────────────────────────────────────
        grid = GridLayout(cols=3, size_hint_y=None, spacing=dp(8))
        grid.bind(minimum_height=grid.setter("height"))
        for cmd in COMMANDS:
            btn = BigButton(icon=cmd.icon, label=cmd.label)
            btn.bind(on_press=lambda _, c=cmd: self._on_command(c))
            grid.add_widget(btn)
        self.add_widget(grid)

        # ── Message scroll area ────────────────────────────────────────────
        self.add_widget(Label(
            text="Replies",
            font_size=sp(FONT_HEADING),
            color=get_color_from_hex(COLOR_ON_SURFACE),
            size_hint_y=None, height=dp(36),
            bold=True,
            halign="left",
        ))

        scroll = ScrollView(size_hint=(1, 1))
        self._msgs = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8))
        self._msgs.bind(minimum_height=self._msgs.setter("height"))
        self._empty = EmptyState(icon="💬", message="No replies yet.\nTap a command above.")
        self._msgs.add_widget(self._empty)
        scroll.add_widget(self._msgs)
        self.add_widget(scroll)

    def update_gateway(self, display_name: str, short_hash: str):
        self._gw_label.text = f"Gateway: {display_name} [{short_hash}]"

    def add_result(self, text: str, image_bytes: bytes | None = None):
        if self._empty.parent:
            self._msgs.remove_widget(self._empty)
        card = ResultCard(text=text)
        self._msgs.add_widget(card)

    def set_connected(self, connected: bool, detail: str = ""):
        self._chip.set_connected(connected, detail)

    def _on_command(self, cmd):
        if cmd.needs_node:
            self._app.open_node_picker(cmd)
        else:
            self._app.dispatch_command(cmd.key)

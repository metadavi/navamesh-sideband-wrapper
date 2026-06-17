"""screens/conversation.py — Pinned-gateway header + 9 command buttons + message list."""
from __future__ import annotations

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.metrics import dp, sp
from kivy.utils import get_color_from_hex

from ..theme import (
    COLOR_ON_SURFACE, FONT_LABEL, SCREEN_PADDING, SPACE_SM, SPACE_MD, TOUCH_TARGET,
)
from ..widgets import BigButton, ResultCard, StatusChip, EmptyState, SectionHeading
from ..command_registry import COMMANDS

_MAX_CARDS = 100


class ConversationScreen(BoxLayout):
    name = "conversation"

    def __init__(self, app, **kwargs):
        super().__init__(orientation="vertical", padding=dp(SCREEN_PADDING),
                         spacing=dp(SPACE_MD), **kwargs)
        self._app = app
        self._in_flight = False
        self._result_cards: list = []

        # ── Gateway header ─────────────────────────────────────────────────
        self._gw_label = Label(
            text="Gateway: (none pinned — tap stream to set)",
            font_size=sp(FONT_LABEL),
            color=get_color_from_hex(COLOR_ON_SURFACE),
            size_hint_y=None, height=dp(TOUCH_TARGET),
            halign="left",
        )
        self.add_widget(self._gw_label)

        self._chip = StatusChip()
        self.add_widget(self._chip)

        # ── Command button grid (3×3) ──────────────────────────────────────
        grid = GridLayout(cols=3, size_hint_y=None, spacing=dp(SPACE_MD))
        grid.bind(minimum_height=grid.setter("height"))
        self._cmd_buttons: list[BigButton] = []
        for cmd in COMMANDS:
            btn = BigButton(icon=cmd.icon, label=cmd.label)
            btn.bind(on_press=lambda _, c=cmd: self._on_command(c))
            grid.add_widget(btn)
            self._cmd_buttons.append(btn)
        self.add_widget(grid)

        # ── Message scroll area ────────────────────────────────────────────
        self.add_widget(SectionHeading("Replies"))

        scroll = ScrollView(size_hint=(1, 1))
        self._msgs = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(SPACE_SM))
        self._msgs.bind(minimum_height=self._msgs.setter("height"))
        self._empty = EmptyState(icon="💬", message="No replies yet.\nTap a command above.")
        self._onboarding = ResultCard(
            text="[font=emoji]👋[/font] Welcome!\nGo to the [font=emoji]📡[/font] Stream tab to find your farm gateway,\nthen tap 'Set as farm GW' to connect.",
            use_markup=True,
        )
        self._msgs.add_widget(self._onboarding)
        scroll.add_widget(self._msgs)
        self.add_widget(scroll)

    def update_gateway(self, display_name: str, short_hash: str):
        self._gw_label.text = f"Gateway: {display_name} [{short_hash}]"
        if self._onboarding.parent:
            self._msgs.remove_widget(self._onboarding)
        if not self._empty.parent and not self._result_cards:
            self._msgs.add_widget(self._empty)

    def add_result(self, text: str, image_bytes: bytes | None = None,
                   image_ext: str = "png"):
        if self._onboarding.parent:
            self._msgs.remove_widget(self._onboarding)
        if self._empty.parent:
            self._msgs.remove_widget(self._empty)
        while len(self._result_cards) >= _MAX_CARDS:
            oldest = self._result_cards.pop(0)
            self._msgs.remove_widget(oldest)
        card = ResultCard(text=text, image_bytes=image_bytes, image_ext=image_ext)
        self._result_cards.append(card)
        self._msgs.add_widget(card)

    def set_connected(self, connected: bool, detail: str = ""):
        self._chip.set_connected(connected, detail)

    def set_state(self, state: str, detail: str = ""):
        self._chip.set_state(state, detail)

    def _set_buttons_enabled(self, enabled: bool):
        for btn in self._cmd_buttons:
            btn.disabled = not enabled
            btn.opacity = 1.0 if enabled else 0.5

    def _on_command_done(self):
        self._in_flight = False
        self._set_buttons_enabled(True)

    def _on_command(self, cmd):
        if self._in_flight:
            return
        self._in_flight = True
        self._set_buttons_enabled(False)
        if cmd.needs_node:
            self._app.open_node_picker(cmd, on_complete=self._on_command_done)
        else:
            self._app.dispatch_command(cmd.key, on_complete=self._on_command_done)

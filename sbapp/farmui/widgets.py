"""
widgets.py — Shared farm-utility widgets.
All sizes from theme.py constants; no magic numbers in this file.
"""
from __future__ import annotations

from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle
from kivy.utils import get_color_from_hex
from kivy.metrics import dp, sp

from . import theme


class BigButton(Button):
    """
    Minimum 96dp height button with icon + plain-language label.
    Touch target ≥48dp (height alone already exceeds it).
    """

    def __init__(self, icon: str = "", label: str = "", **kwargs):
        super().__init__(**kwargs)
        self.text = f"{icon}  {label}" if icon else label
        self.font_size = sp(theme.FONT_BODY)
        self.size_hint_y = None
        self.height = dp(theme.BUTTON_HEIGHT)
        self.background_color = get_color_from_hex(theme.COLOR_PRIMARY)
        self.color = get_color_from_hex(theme.COLOR_ON_PRIMARY)
        self.halign = "center"
        self.bold = True


class ResultCard(BoxLayout):
    """Display a gateway reply as a readable card."""

    def __init__(self, text: str = "", **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.size_hint_y = None
        self.padding = dp(theme.CARD_PADDING)
        self.spacing = dp(8)
        self._bg_color = get_color_from_hex(theme.COLOR_CARD)
        with self.canvas.before:
            Color(*self._bg_color)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(8)])
        self.bind(pos=self._update_rect, size=self._update_rect)
        self._label = Label(
            text=text,
            font_size=sp(theme.FONT_BODY),
            color=get_color_from_hex(theme.COLOR_ON_CARD),
            halign="left",
            valign="top",
            size_hint_y=None,
        )
        self._label.bind(texture_size=self._on_texture_size)
        self.add_widget(self._label)
        self._update_height()

    def _update_rect(self, *_):
        self._rect.pos  = self.pos
        self._rect.size = self.size

    def _on_texture_size(self, inst, val):
        inst.height = val[1]
        self._update_height()

    def _update_height(self):
        self.height = self._label.height + 2 * dp(theme.CARD_PADDING)


class StatusChip(Label):
    """Small connectivity status indicator: 'Connected · 3s ago' or 'No radio'."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.font_size = sp(theme.FONT_LABEL)
        self.size_hint_y = None
        self.height = dp(32)
        self.set_connected(False)

    def set_connected(self, is_connected: bool, detail: str = ""):
        if is_connected:
            self.text = f"● Connected  {detail}".strip()
            self.color = get_color_from_hex(theme.COLOR_CONNECTED)
        else:
            self.text = "○ No radio connection"
            self.color = get_color_from_hex(theme.COLOR_DISCONNECTED)


class EmptyState(BoxLayout):
    """Placeholder shown when a list/area has no content yet."""

    def __init__(self, icon: str = "📭", message: str = "Nothing here yet", **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.padding = dp(32)
        self.spacing = dp(12)
        self.add_widget(Label(
            text=icon,
            font_size=sp(48),
            size_hint_y=None,
            height=dp(64),
        ))
        self.add_widget(Label(
            text=message,
            font_size=sp(theme.FONT_BODY),
            color=get_color_from_hex(theme.COLOR_ON_SURFACE),
            halign="center",
        ))

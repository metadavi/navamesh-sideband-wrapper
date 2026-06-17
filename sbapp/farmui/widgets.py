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


class SectionHeading(Label):
    """A left-aligned screen/section title with consistent type + auto height.

    Replaces the per-screen heading Labels that each hardcoded their own font
    size, color, and a fixed pixel height (which clipped in large-text mode).
    """

    def __init__(self, text: str = "", **kwargs):
        super().__init__(**kwargs)
        self.text = text
        self.markup = True
        self.bold = True
        self.font_size = sp(theme.FONT_HEADING)
        self.color = get_color_from_hex(theme.COLOR_ON_SURFACE)
        self.halign = "left"
        self.valign = "middle"
        self.size_hint_y = None
        # text_size width binding makes halign="left" actually left-align; height
        # follows the rendered texture (+ a little breathing room) so it never clips.
        self.bind(width=lambda inst, w: setattr(inst, "text_size", (w, None)))
        self.bind(texture_size=lambda inst, s: setattr(
            inst, "height", s[1] + dp(theme.SPACE_SM)))


class BigButton(Button):
    """
    Minimum 96dp height button with icon + plain-language label.
    Touch target ≥48dp (height alone already exceeds it).
    """

    def __init__(self, icon: str = "", label: str = "", **kwargs):
        super().__init__(**kwargs)
        if icon:
            self.markup = True
            self.text = f"[font=emoji]{icon}[/font]  {label}"
        else:
            self.text = label
        self.font_size = sp(theme.FONT_BODY)
        self.size_hint_y = None
        self.height = dp(theme.BUTTON_HEIGHT)
        self.background_color = get_color_from_hex(theme.COLOR_PRIMARY)
        self.color = get_color_from_hex(theme.COLOR_ON_PRIMARY)
        self.halign = "center"
        self.bold = True


class ResultCard(BoxLayout):
    """Display a gateway reply as a readable card with optional inline image."""

    def __init__(self, text: str = "", image_bytes: bytes | None = None,
                 use_markup: bool = False, image_ext: str = "png", **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self._image_ext = image_ext or "png"
        self.size_hint_y = None
        self.padding = dp(theme.CARD_PADDING)
        self.spacing = dp(theme.SPACE_SM)
        self._img_height = 0
        self._bg_color = get_color_from_hex(theme.COLOR_CARD)
        with self.canvas.before:
            Color(*self._bg_color)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size,
                                          radius=[dp(theme.CARD_RADIUS)])
        self.bind(pos=self._update_rect, size=self._update_rect)
        self._label = Label(
            text=text,
            markup=use_markup,
            font_size=sp(theme.FONT_BODY),
            color=get_color_from_hex(theme.COLOR_ON_CARD),
            halign="left",
            valign="top",
            size_hint_y=None,
        )
        self._label.bind(texture_size=self._on_texture_size)
        self.add_widget(self._label)
        if image_bytes:
            self._attach_image(image_bytes)
        self._update_height()

    def _attach_image(self, image_bytes: bytes):
        import io
        from kivy.uix.image import Image
        from kivy.core.image import Image as CoreImage
        try:
            try:
                core_img = CoreImage(io.BytesIO(image_bytes), ext=self._image_ext)
            except Exception:
                # Fall back to letting the provider sniff the format (gateway map
                # replies are JPEG under the 'halow' profile, not PNG).
                core_img = CoreImage(io.BytesIO(image_bytes), ext="png")
            if core_img.texture:
                self._img_height = dp(theme.IMAGE_PREVIEW_HEIGHT)
                self.add_widget(Image(
                    texture=core_img.texture,
                    size_hint=(1, None),
                    height=self._img_height,
                ))
                self._update_height()
        except Exception:
            pass

    def _update_rect(self, *_):
        self._rect.pos  = self.pos
        self._rect.size = self.size

    def _on_texture_size(self, inst, val):
        inst.height = val[1]
        self._update_height()

    def _update_height(self):
        extra = self._img_height + (dp(theme.SPACE_SM) if self._img_height > 0 else 0)
        self.height = self._label.height + extra + 2 * dp(theme.CARD_PADDING)


class StatusChip(Label):
    """Small connectivity status indicator with three states.

    States reflect the *backend service* status, not the HaLow hardware:
      - "connected"  : the Sideband service is alive (fresh heartbeat).
      - "connecting" : the service was launched and we're waiting for it.
      - "no_service" : the service is not running / failed to launch.

    The negative copy deliberately gives a recovery hint (restart the app) rather
    than blaming the Heltec "white box", since a missing heartbeat is a service/UI
    condition — the radio itself may be perfectly fine.
    """

    CONNECTED  = "connected"
    CONNECTING = "connecting"
    NO_SERVICE = "no_service"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.font_size = sp(theme.FONT_LABEL)
        self.size_hint_y = None
        self.height = dp(theme.CHIP_HEIGHT)
        self.markup = True
        self.set_state(self.CONNECTING)

    @classmethod
    def status_text(cls, state: str, detail: str = "") -> str:
        """Pure text mapping for a state (no widget needed — unit-testable)."""
        if state == cls.CONNECTED:
            return f"[font=emoji]📶[/font] Radio connected  {detail}".strip()
        if state == cls.CONNECTING:
            return f"[font=emoji]🔄[/font] Connecting to radio…  {detail}".strip()
        return "[font=emoji]📵[/font] Radio service not running — try restarting the app"

    @classmethod
    def status_color(cls, state: str) -> str:
        if state == cls.CONNECTED:
            return theme.COLOR_CONNECTED
        if state == cls.CONNECTING:
            return theme.COLOR_PENDING
        return theme.COLOR_DISCONNECTED

    def set_state(self, state: str, detail: str = ""):
        self.text = self.status_text(state, detail)
        self.color = get_color_from_hex(self.status_color(state))

    def set_connected(self, is_connected: bool, detail: str = ""):
        """Backward-compatible boolean entry point (True→connected, False→no_service)."""
        self.set_state(self.CONNECTED if is_connected else self.NO_SERVICE, detail)


class EmptyState(BoxLayout):
    """Placeholder shown when a list/area has no content yet."""

    def __init__(self, icon: str = "📭", message: str = "Nothing here yet", **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.padding = dp(theme.SPACE_XL)
        self.spacing = dp(theme.SPACE_MD)
        self.add_widget(Label(
            text=f"[font=emoji]{icon}[/font]" if icon else "",
            markup=True,
            font_size=sp(theme.FONT_ICON),
            size_hint_y=None,
            height=dp(theme.ICON_BOX),
        ))
        self.add_widget(Label(
            text=message,
            font_size=sp(theme.FONT_BODY),
            color=get_color_from_hex(theme.COLOR_ON_SURFACE),
            halign="center",
        ))

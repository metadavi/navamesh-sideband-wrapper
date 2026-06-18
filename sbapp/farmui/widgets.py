"""
widgets.py — Shared farm-utility widgets, styled in the Navamesh "Field Log"
language: parchment panels with hairline borders, a single Mesa Red CTA, and a
mono register for addresses / IDs / timestamps.

All sizes from theme.py constants; no magic numbers in this file.
"""
from __future__ import annotations

from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.utils import get_color_from_hex
from kivy.metrics import dp, sp

from . import theme


def paint_background(widget, hex_color: str):
    """Paint a solid fill behind a widget (canvas.before), tracking pos/size.

    Used to guarantee the parchment content surface behind each screen: Kivy's
    TabbedPanel draws its own (dark) content background that `background_color`
    alone does not override, so we paint the screens directly. Returns the
    Rectangle instruction.
    """
    from kivy.graphics import Rectangle
    with widget.canvas.before:
        Color(*get_color_from_hex(hex_color))
        rect = Rectangle(pos=widget.pos, size=widget.size)
    widget.bind(pos=lambda *_: setattr(rect, "pos", widget.pos),
                size=lambda *_: setattr(rect, "size", widget.size))
    return rect


def _mono(name: str = theme.FONT_MONO):
    """font_name kwarg dict for the mono family (empty if not registered)."""
    fam = theme.family(name)
    return {"font_name": fam} if fam else {}


def _display():
    fam = theme.family(theme.FONT_DISPLAY_FAMILY)
    return {"font_name": fam} if fam else {}


def _body():
    fam = theme.family(theme.FONT_BODY_FAMILY)
    return {"font_name": fam} if fam else {}


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
        for k, v in _display().items():
            setattr(self, k, v)
        self.halign = "left"
        self.valign = "middle"
        self.size_hint_y = None
        # text_size width binding makes halign="left" actually left-align; height
        # follows the rendered texture (+ a little breathing room) so it never clips.
        self.bind(width=lambda inst, w: setattr(inst, "text_size", (w, None)))
        self.bind(texture_size=lambda inst, s: setattr(
            inst, "height", s[1] + dp(theme.SPACE_SM)))


class Panel(BoxLayout):
    """Parchment Field-Log panel: warm-white fill, hairline border, 14dp radius.

    The contrast between the parchment canvas and this slightly lifted surface,
    plus the hairline border, provides separation without heavy shadows.
    """

    def __init__(self, fill: str = theme.COLOR_CARD, border: bool = True, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("padding", dp(theme.CARD_PADDING))
        kwargs.setdefault("spacing", dp(theme.SPACE_SM))
        super().__init__(**kwargs)
        self._fill = get_color_from_hex(fill)
        self._draw_border = border
        with self.canvas.before:
            self._bg_color = Color(*self._fill)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size,
                                          radius=[dp(theme.CARD_RADIUS)])
            if border:
                self._line_color = Color(*get_color_from_hex(theme.COLOR_HAIRLINE))
                self._border = Line(width=dp(theme.HAIRLINE_WIDTH),
                                    rounded_rectangle=self._rounded_args())
        self.bind(pos=self._update_canvas, size=self._update_canvas)

    def _rounded_args(self):
        return (self.x, self.y, self.width, self.height, dp(theme.CARD_RADIUS))

    def set_fill(self, fill: str):
        self._bg_color.rgba = get_color_from_hex(fill)

    def _update_canvas(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size
        if self._draw_border:
            self._border.rounded_rectangle = self._rounded_args()


class BigButton(Button):
    """
    Minimum 96dp height button with icon + plain-language label.
    Touch target ≥48dp (height alone already exceeds it).

    variant="primary"  → the single Mesa Red call-to-action (pill, light label).
    variant="command"  → parchment tile, hairline border, Umber label. Used for
                         the command grid: light and sunlight-legible, leaving
                         Mesa Red rare (the Rarity Rule).
    """

    def __init__(self, icon: str = "", label: str = "", variant: str = "primary",
                 **kwargs):
        super().__init__(**kwargs)
        self._variant = variant
        if icon:
            self.markup = True
            self.text = f"[font=emoji]{icon}[/font]  {label}"
        else:
            self.text = label
        self.font_size = sp(theme.FONT_BODY)
        self.size_hint_y = None
        self.height = dp(theme.BUTTON_HEIGHT)
        self.bold = True
        self.halign = "center"
        self.valign = "middle"
        # Wrap the label inside the tile so long command names ("Signal
        # strength", "Map — all nodes") never overflow into neighbouring tiles.
        self.bind(size=lambda inst, _s: setattr(
            inst, "text_size", (inst.width - dp(theme.SPACE_MD) * 2, inst.height)))
        for k, v in _body().items():
            setattr(self, k, v)
        # Flatten Kivy's stock button textures; we draw our own rounded surface.
        self.background_normal = ""
        self.background_down = ""
        self.background_disabled_normal = ""
        self.background_color = (0, 0, 0, 0)

        if variant == "command":
            self._fill = get_color_from_hex(theme.COLOR_CARD)
            self._fill_down = get_color_from_hex(theme.COLOR_GATEWAY_HIGHLIGHT)
            self.color = get_color_from_hex(theme.COLOR_ON_CARD)
            self._radius = dp(theme.CARD_RADIUS)
            self._border = get_color_from_hex(theme.COLOR_HAIRLINE)
        else:  # primary CTA
            self._fill = get_color_from_hex(theme.COLOR_PRIMARY)
            self._fill_down = get_color_from_hex(theme.COLOR_MESA_RED)
            self.color = get_color_from_hex(theme.COLOR_ON_PRIMARY)
            self._radius = dp(theme.BUTTON_HEIGHT) / 2  # pill
            self._border = None

        with self.canvas.before:
            self._bg_color = Color(*self._fill)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size,
                                          radius=[self._radius])
            if self._border is not None:
                self._line_color = Color(*self._border)
                self._line = Line(width=dp(theme.HAIRLINE_WIDTH),
                                  rounded_rectangle=self._rounded_args())
        self.bind(pos=self._update_canvas, size=self._update_canvas,
                  state=self._on_state)

    def _rounded_args(self):
        return (self.x, self.y, self.width, self.height, self._radius)

    def _update_canvas(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size
        if self._border is not None:
            self._line.rounded_rectangle = self._rounded_args()

    def _on_state(self, _inst, state):
        self._bg_color.rgba = (self._fill_down if state == "down" else self._fill)


class ResultCard(BoxLayout):
    """Display a gateway reply as a readable parchment card with optional image."""

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
            self._line_color = Color(*get_color_from_hex(theme.COLOR_HAIRLINE))
            self._border = Line(width=dp(theme.HAIRLINE_WIDTH),
                                rounded_rectangle=self._rounded_args())
        self.bind(pos=self._update_rect, size=self._update_rect)
        self._label = Label(
            text=text,
            markup=use_markup,
            font_size=sp(theme.FONT_BODY),
            color=get_color_from_hex(theme.COLOR_ON_CARD),
            halign="left",
            valign="top",
            size_hint_y=None,
            **_body(),
        )
        # Wrap text to the card width so long replies / the onboarding copy
        # don't overflow (and clip) horizontally.
        self._label.bind(
            width=lambda i, w: setattr(i, "text_size", (w, None)),
            texture_size=self._on_texture_size,
        )
        self.add_widget(self._label)
        if image_bytes:
            self._attach_image(image_bytes)
        self._update_height()

    def _rounded_args(self):
        return (self.x, self.y, self.width, self.height, dp(theme.CARD_RADIUS))

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
        self._border.rounded_rectangle = self._rounded_args()

    def _on_texture_size(self, inst, val):
        inst.height = val[1]
        self._update_height()

    def _update_height(self):
        extra = self._img_height + (dp(theme.SPACE_SM) if self._img_height > 0 else 0)
        self.height = self._label.height + extra + 2 * dp(theme.CARD_PADDING)


class StatusChip(Label):
    """Small connectivity status indicator with three states.

    Triple-coded: a colored status dot (color channel) + a plain word (always in
    legible Umber ink, so the message reads regardless of the hue). The dot uses
    Sage (connected), Sandstone Gold (connecting) or Mesa Red (no service).

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
        self.halign = "left"
        self.valign = "middle"
        self.bind(width=lambda inst, w: setattr(inst, "text_size", (w, None)))
        for k, v in _body().items():
            setattr(self, k, v)
        self.set_state(self.CONNECTING)

    @classmethod
    def status_text(cls, state: str, detail: str = "") -> str:
        """Pure text mapping for a state (no widget needed — unit-testable)."""
        if state == cls.CONNECTED:
            return f"Radio connected  {detail}".strip()
        if state == cls.CONNECTING:
            return f"Connecting to radio…  {detail}".strip()
        return "Radio service not running — try restarting the app"

    @classmethod
    def status_color(cls, state: str) -> str:
        if state == cls.CONNECTED:
            return theme.COLOR_CONNECTED
        if state == cls.CONNECTING:
            return theme.COLOR_PENDING
        return theme.COLOR_DISCONNECTED

    def set_state(self, state: str, detail: str = ""):
        dot = self.status_color(state).lstrip("#")
        word = self.status_text(state, detail)
        self.text = f"[color={dot}]●[/color]  {word}"
        # The word stays Umber so it is always legible on the parchment canvas;
        # the colored dot carries the state hue.
        self.color = get_color_from_hex(theme.COLOR_ON_SURFACE)

    def set_connected(self, is_connected: bool, detail: str = ""):
        """Backward-compatible boolean entry point (True→connected, False→no_service)."""
        self.set_state(self.CONNECTED if is_connected else self.NO_SERVICE, detail)


class BrandMark(Widget):
    """Tiny Navamesh wordmark glyph: a canyon arch over a 3-node mesh triangle.

    Drawn as vectors (no image asset) in Sandstone Gold on the dark top bar,
    echoing the cloud dashboard's logo motif.
    """

    def __init__(self, color: str = theme.COLOR_ACCENT, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, 1)
        self.width = dp(28)
        self._color = get_color_from_hex(color)
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *_):
        self.canvas.clear()
        s = min(self.width, self.height)
        if s <= 0:
            return
        ox = self.x + (self.width - s) / 2.0
        oy = self.y + (self.height - s) / 2.0
        def p(fx, fy):  # fractional → absolute, y measured from top
            return (ox + fx * s, oy + (1.0 - fy) * s)
        arch = [
            *p(0.10, 0.88), *p(0.10, 0.50),
            *p(0.50, 0.16), *p(0.90, 0.50), *p(0.90, 0.88),
        ]
        n_top = p(0.50, 0.34)
        n_left = p(0.28, 0.74)
        n_right = p(0.72, 0.74)
        r = dp(2.4)
        with self.canvas:
            Color(self._color[0], self._color[1], self._color[2], 0.45)
            Line(points=arch, width=dp(1.2), cap="round", joint="round")
            Color(*self._color)
            Line(points=[*n_left, *n_right], width=dp(1.0))
            Line(points=[*n_left, *n_top], width=dp(1.0))
            Line(points=[*n_right, *n_top], width=dp(1.0))
            for cx, cy in (n_top, n_left, n_right):
                from kivy.graphics import Ellipse
                Ellipse(pos=(cx - r, cy - r), size=(2 * r, 2 * r))


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
            color=get_color_from_hex(theme.COLOR_MUTED),
            halign="center",
            **_body(),
        ))

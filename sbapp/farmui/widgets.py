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
        # Command tiles are compact (≥48dp touch target) to leave the reply area
        # the focus of the screen; the single primary CTA stays full height.
        self.font_size = sp(theme.FONT_LABEL if variant == "command" else theme.FONT_BODY)
        self.size_hint_y = None
        self.height = dp(theme.COMMAND_TILE_HEIGHT if variant == "command"
                         else theme.BUTTON_HEIGHT)
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
                 use_markup: bool = False, image_ext: str = "png",
                 mono: bool = False, **kwargs):
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
        # Gateway replies are monospace-formatted (space-aligned columns + ─── rule
        # lines): render them in the mono family so the columns stay aligned and the
        # box-drawing glyphs render (instead of falling back to .notdef boxes). Prose
        # cards (onboarding) keep the friendly body font.
        _font_kw = _mono() if mono else _body()
        self._label = Label(
            text=text,
            markup=use_markup,
            # Mono replies use a smaller size so the gateway's terminal-width
            # tables (and ─── rule lines) fit on one line instead of wrapping.
            font_size=sp(theme.FONT_REPLY if mono else theme.FONT_BODY),
            color=get_color_from_hex(theme.COLOR_ON_CARD),
            halign="left",
            valign="top",
            size_hint_y=None,
            **_font_kw,
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
            if not core_img.texture:
                return
            tex = core_img.texture
            tw, th = tex.size
            aspect = (th / tw) if tw else 1.0  # height / width
            # Fill the full card width and scale height to preserve aspect ratio,
            # so the map is as large as the reply column allows (no fixed-height
            # squish, no downscaling below the available width). Cap portrait
            # images so they don't run off-screen; the ScrollView handles overflow.
            img = Image(
                texture=tex,
                size_hint=(1, None),
                fit_mode="contain",
            )
            self._image_aspect = aspect
            self._image_widget = img

            def _resize(_inst, w):
                h = min(w * self._image_aspect, w * 1.4)
                img.height = h
                self._img_height = h
                self._update_height()

            img.bind(width=_resize)
            _resize(img, img.width)
            # Tap (not drag) the inline map to open it full-screen for close
            # reading. We do NOT consume on_touch_down — that would swallow the
            # ScrollView's drag gesture when it starts on the map. Instead we
            # remember the press (keyed on the down-collision, which is reliable)
            # and open only on a touch-up that barely moved. Tap-vs-scroll is
            # measured in window coords (touch.x/y) — stable across down/up —
            # because collide_point() in on_touch_up is unreliable inside the
            # ScrollView's transformed coordinate space.
            img.bind(on_touch_down=self._on_image_down,
                     on_touch_up=self._on_image_up)
            self.add_widget(img)
            self._update_height()
        except Exception:
            pass

    def _on_image_down(self, img, touch):
        if img.collide_point(*touch.pos) and getattr(img, "texture", None):
            touch.ud["_map_press"] = (touch.x, touch.y)
        return False  # let the ScrollView handle scrolling

    def _on_image_up(self, img, touch):
        origin = touch.ud.pop("_map_press", None)
        if origin is None:
            return False
        if (abs(touch.x - origin[0]) > dp(theme.SPACE_MD) or
                abs(touch.y - origin[1]) > dp(theme.SPACE_MD)):
            return False  # it was a scroll drag, not a tap
        build_map_viewer(img.texture).open()
        return True

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


def build_map_viewer(texture):
    """Full-screen pinch-zoom/pan viewer for an inline map image.

    Returns an UNOPENED ModalView (the caller calls .open()) so the structure
    is testable without touch gestures. Layout: ModalView > FloatLayout >
    [ScatterLayout (pinch zoom 1x-8x, pan, do_rotation=False) > Image
    (contain-fit), close (×) button on top]. Double-tap resets the zoom.
    The backdrop is a translucent dim so the app stays visible behind the
    map. At 1x zoom a tap on the letterbox (outside the drawn image) closes
    the viewer; once zoomed in, every touch pans/zooms instead — taps on the
    image itself never dismiss. auto_dismiss=True also serves ESC / Android
    back.
    """
    from kivy.uix.modalview import ModalView
    from kivy.uix.floatlayout import FloatLayout
    from kivy.uix.scatterlayout import ScatterLayout
    from kivy.uix.image import Image

    modal = ModalView(size_hint=(1, 1),
                      background_color=(0, 0, 0, 0.45),
                      auto_dismiss=True)
    root = FloatLayout()

    scatter = ScatterLayout(do_rotation=False,
                            scale_min=1.0, scale_max=8.0)
    img = Image(texture=texture, fit_mode="contain", size_hint=(1, 1))
    scatter.add_widget(img)

    def _reset(*_):
        scatter.scale = 1.0
        scatter.pos = (0, 0)

    def _drawn_rect():
        # Rect of the contain-fit texture inside the (full-screen) image
        # widget, in scatter-local coords — the rest is letterbox.
        iw, ih = img.size
        tw, th = texture.size if texture is not None else (0, 0)
        if not tw or not th or not iw or not ih:
            return 0, 0, iw, ih
        s = min(iw / tw, ih / th)
        dw, dh = tw * s, th * s
        return (iw - dw) / 2, (ih - dh) / 2, dw, dh

    def _on_down(_w, touch):
        if touch.is_double_tap and scatter.collide_point(*touch.pos):
            _reset()
            return False
        # Not zoomed in: a tap outside the image frame exits the viewer.
        if scatter.scale <= 1.001:
            lx, ly = scatter.to_local(*touch.pos)
            x, y, w, h = _drawn_rect()
            if not (x <= lx <= x + w and y <= ly <= y + h):
                modal.dismiss()
                return True
        return False  # let the Scatter's own pinch/pan handling run
    scatter.bind(on_touch_down=_on_down)
    root.add_widget(scatter)

    # × is U+00D7 — present in the bundled fonts. U+2715 and U+25CF are not
    # (they render as boxes), so don't swap the glyph for a "nicer" one.
    close = Button(
        text="×",
        font_size=sp(theme.FONT_HEADING), bold=True,
        size_hint=(None, None),
        size=(dp(theme.TOUCH_TARGET), dp(theme.TOUCH_TARGET)),
        pos_hint={"right": 1, "top": 1},
        background_normal="", background_down="",
        background_color=(0, 0, 0, 0.35),
        color=(1, 1, 1, 1),
    )
    close.bind(on_release=lambda *_: modal.dismiss())
    # Sibling of the scatter, added after it → receives touches first, so
    # closing never zooms the map underneath.
    root.add_widget(close)
    modal.add_widget(root)
    return modal


class StatusChip(Label):
    """Small mesh-connectivity status indicator with four states.

    Triple-coded: a colored status dot (color channel) + a plain word (always in
    legible Umber ink, so the message reads regardless of the hue). The dot uses
    Sage (mesh active), Sandstone Gold (listening / quiet) or Mesa Red (service
    offline).

    The wording reflects *observed mesh traffic*, never a hardware link claim we
    cannot verify (the HT-HD01 is a config-defined UDP interface that exposes no
    clean link signal across the UI↔service process boundary). The states:
      - "connected" → "Mesh active"      : an announce was heard over the radio
                                            within the freshness window — proof the
                                            device is receiving live mesh traffic.
      - "connecting" → "Listening for mesh…" : the service is alive but no announce
                                            has been heard yet this session.
      - "mesh_quiet" → "Mesh quiet"      : the service is alive and announces were
                                            heard before, but none recently (the
                                            mesh went quiet or the link dropped).
      - "no_service" → "Service offline" : the background service isn't running.

    The "Service offline" copy gives a recovery hint (restart the app) since a
    missing heartbeat is a service/UI condition, not necessarily a radio fault.
    "Radio Connected" is intentionally never shown — we can only prove traffic,
    not a link.
    """

    CONNECTED  = "connected"
    CONNECTING = "connecting"
    MESH_QUIET = "mesh_quiet"
    NO_SERVICE = "no_service"

    # Status-dot glyph. The bundled text fonts have no glyph for ● (U+25CF) — it
    # rendered as a □ box — and EmojiScaled draws the 🟢/🟡/🔴 circles monochrome
    # (losing the state hue). The bullet • (U+2022) *is* in the body font, so a
    # [color]-markup bullet renders as a crisp colored dot that carries the hue.
    DOT_GLYPH = "•"

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
            return f"Mesh active  {detail}".strip()
        if state == cls.CONNECTING:
            return f"Listening for mesh…  {detail}".strip()
        if state == cls.MESH_QUIET:
            return f"Mesh quiet  {detail}".strip()
        return "Service offline — try restarting the app"

    @classmethod
    def status_color(cls, state: str) -> str:
        if state == cls.CONNECTED:
            return theme.COLOR_CONNECTED
        if state in (cls.CONNECTING, cls.MESH_QUIET):
            return theme.COLOR_PENDING
        return theme.COLOR_DISCONNECTED

    def set_state(self, state: str, detail: str = ""):
        dot = self.status_color(state).lstrip("#")
        word = self.status_text(state, detail)
        self.text = f"[color={dot}]{self.DOT_GLYPH}[/color]  {word}"
        # The word stays Umber so it is always legible on the parchment canvas;
        # the colored bullet carries the state hue.
        self.color = get_color_from_hex(theme.COLOR_ON_SURFACE)

    def set_connected(self, is_connected: bool, detail: str = ""):
        """Backward-compatible boolean entry point (True→connected, False→no_service)."""
        self.set_state(self.CONNECTED if is_connected else self.NO_SERVICE, detail)


class BackBar(BoxLayout):
    """A compact top bar for pushed chat screens: a '‹ Back' button + a title.

    Used by the gateway command screen and the peer messenger so a tapped device
    chat can return to the Talk tab. The back control is a flat, full-height
    touch target (≥48dp) with Umber ink on the parchment canvas.
    """

    def __init__(self, title: str = "", on_back=None, **kwargs):
        kwargs.setdefault("orientation", "horizontal")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(theme.TOUCH_TARGET))
        kwargs.setdefault("spacing", dp(theme.SPACE_SM))
        super().__init__(**kwargs)
        btn = Button(
            text="‹ Back",
            font_size=sp(theme.FONT_LABEL),
            bold=True,
            size_hint_x=None, width=dp(96),
            halign="center", valign="middle",
            background_normal="", background_down="",
            background_color=(0, 0, 0, 0),
            color=get_color_from_hex(theme.COLOR_ON_SURFACE),
        )
        for k, v in _body().items():
            setattr(btn, k, v)
        if on_back is not None:
            btn.bind(on_press=lambda *_: on_back())
        self.add_widget(btn)
        self._title = Label(
            text=title,
            markup=True,
            font_size=sp(theme.FONT_LABEL),
            color=get_color_from_hex(theme.COLOR_MUTED),
            halign="left", valign="middle",
        )
        self._title.bind(size=lambda i, _s: setattr(i, "text_size", i.size))
        for k, v in _body().items():
            setattr(self._title, k, v)
        self.add_widget(self._title)

    def set_title(self, title: str):
        self._title.text = title


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


class NodePickerDialog:
    """Selection-only "pick a node to map" dialog (Map — one node).

    Lists the node IDs the gateway reported via its "List nodes" reply. The
    farmer taps one node and the wrapper sends `map <id>` — no typing anywhere.
    If no nodes are cached yet it shows a friendly hint and only a Close button,
    and never picks/sends anything. Built on the same ModalView + Panel + BigButton
    language as the rest of the Field-Log UI.
    """

    def __init__(self, nodes, on_pick, heading="Pick a node to map",
                 include_broadcast=False):
        from kivy.uix.modalview import ModalView
        from kivy.uix.scrollview import ScrollView

        self._on_pick = on_pick
        self._modal = ModalView(
            size_hint=(0.9, 0.8),
            background_color=(0, 0, 0, 0.55),
            background="",
            auto_dismiss=True,
        )
        panel = Panel(padding=dp(theme.SPACE_MD), spacing=dp(theme.SPACE_MD))

        panel.add_widget(SectionHeading(heading))

        # Control commands can address the whole mesh at once, which also happens to be
        # the only way to reach a node that sits outside direct gateway range (sensor
        # nodes do not rebroadcast for each other). Offered only when the caller asks,
        # so "Map — one node" keeps its single-node meaning.
        if include_broadcast:
            all_btn = BigButton(icon="📡", label="ALL FIELD NODES", variant="command")
            all_btn.bind(on_release=lambda *_: self._choose("^all"))
            panel.add_widget(all_btn)

        if nodes:
            scroll = ScrollView(size_hint=(1, 1))
            col = BoxLayout(orientation="vertical", size_hint_y=None,
                            spacing=dp(theme.SPACE_SM))
            col.bind(minimum_height=col.setter("height"))
            for node_id in nodes:
                btn = BigButton(icon="🛰", label=node_id, variant="command")
                btn.bind(on_release=lambda _b, nid=node_id: self._choose(nid))
                col.add_widget(btn)
            scroll.add_widget(col)
            panel.add_widget(scroll)
        else:
            hint = Label(
                text="No nodes found yet.\nTap List Nodes first.",
                font_size=sp(theme.FONT_BODY),
                color=get_color_from_hex(theme.COLOR_MUTED),
                halign="center", valign="middle",
                **_body(),
            )
            hint.bind(size=lambda i, _s: setattr(i, "text_size", i.size))
            panel.add_widget(hint)

        close = BigButton(label="Close", variant="command")
        close.size_hint_y = None
        close.bind(on_release=lambda *_: self._modal.dismiss())
        panel.add_widget(close)

        self._modal.add_widget(panel)

    def _choose(self, node_id):
        # A command is sent only from here — i.e. only when a node is tapped.
        self._modal.dismiss()
        if self._on_pick is not None:
            self._on_pick(node_id)

    def open(self):
        self._modal.open()


def _coordinate_input_filter(box):
    """
    Bind location.coordinate_filter to a TextInput, in the shape Kivy's input_filter wants.

    The rule itself lives in location.py, which imports no Kivy and can therefore be tested
    without a display — this is only the adapter.
    """
    from .location import coordinate_filter
    return lambda substring, from_undo: coordinate_filter(box.text, substring)


class ConfirmCommandDialog:
    """Value picker + confirmation for a control command.

    Control commands change deployed field hardware over LoRa, unlike the nine read-only
    commands which just query the Pi's database. So this dialog exists to put a
    deliberate second step in front of them: nothing is sent until the farmer taps
    "Send".

    Values are offered as presets rather than a text field. That keeps the "no typing
    anywhere" rule the rest of this UI follows, and it makes an out-of-range value
    impossible to enter rather than merely rejected afterwards.

    "Change sensor location" is the exception, unavoidably: a live GPS position has nothing to
    preset. It gets its own first step that reads the phone's own fix, falling back to
    typed coordinates when there is no fix to read — the one place in this UI where a
    number is entered by hand, because the alternative is a command the farmer cannot
    complete at all indoors or with location switched off.

    Flow:
      needs_location → capture a position (GPS, or typed), then confirm
      needs_value    → pick a preset, then confirm
      otherwise      → confirm directly

    `on_confirm(value)` is invoked ONLY from _send(). Cancelling or dismissing sends
    nothing.
    """

    def __init__(self, cmd, node_id, on_confirm, node_label=None):
        from kivy.uix.modalview import ModalView
        from kivy.uix.scrollview import ScrollView

        self._cmd = cmd
        self._node_id = node_id
        self._on_confirm = on_confirm
        self._node_label = node_label or node_id
        self._value = None
        # The captured Fix, kept alongside _value so the confirm step can show accuracy
        # and warn on a coarse one. None for every command that is not needs_location.
        self._fix = None
        self._lat_input = None
        self._lon_input = None
        self._value_input = None
        # A GPS search outlives the dialog: the farmer can cancel while it is still
        # waiting, and the callback still fires seconds later. Without this it would
        # rebuild a dismissed dialog's contents.
        self._dismissed = False

        self._modal = ModalView(
            size_hint=(0.9, 0.8),
            background_color=(0, 0, 0, 0.55),
            background="",
            auto_dismiss=True,
        )
        self._scroll = ScrollView(size_hint=(1, 1))
        self._panel = Panel(padding=dp(theme.SPACE_MD), spacing=dp(theme.SPACE_MD))
        self._modal.add_widget(self._panel)
        # Bound rather than set in each Cancel handler so it also catches auto_dismiss
        # (a tap outside the dialog), which is the easy way to abandon a GPS search.
        self._modal.bind(on_dismiss=self._mark_dismissed)

        if getattr(cmd, "needs_location", False):
            self._build_locate_step()
        elif cmd.needs_value and cmd.value_presets:
            self._build_value_step()
        else:
            self._build_confirm_step()

    # ── steps ────────────────────────────────────────────────────────────────

    def _clear(self):
        self._panel.clear_widgets()

    def _is_broadcast(self):
        return self._node_id in ("^all", "all")

    def _target_text(self):
        return "ALL FIELD NODES" if self._is_broadcast() else self._node_label

    def _hint_label(self, text, color=None):
        lbl = Label(
            text=text,
            font_size=sp(theme.FONT_BODY),
            color=get_color_from_hex(color or theme.COLOR_MUTED),
            halign="center", valign="middle",
            **_body(),
        )
        lbl.bind(size=lambda i, _s: setattr(i, "text_size", i.size))
        return lbl

    def _build_value_step(self):
        self._clear()
        self._panel.add_widget(SectionHeading(f"{self._cmd.label} — choose"))
        self._panel.add_widget(self._hint_label(
            f"For {self._target_text()}\n{self._cmd.confirm_hint}"
        ))

        from kivy.uix.scrollview import ScrollView
        scroll = ScrollView(size_hint=(1, 1))
        col = BoxLayout(orientation="vertical", size_hint_y=None,
                        spacing=dp(theme.SPACE_SM))
        col.bind(minimum_height=col.setter("height"))
        for label, value in self._cmd.value_presets:
            btn = BigButton(icon=self._cmd.icon, label=label, variant="command")
            btn.bind(on_release=lambda _b, v=value: self._pick_value(v))
            col.add_widget(btn)
        # Last, not first: the presets are the answer nearly every time, and putting a
        # keyboard ahead of them would make the common case the harder one.
        if getattr(self._cmd, "allow_manual_value", False):
            manual = BigButton(icon="\u2328", label="Enter a time", variant="command")
            manual.bind(on_release=lambda *_: self._build_manual_value_step())
            col.add_widget(manual)
        scroll.add_widget(col)
        self._panel.add_widget(scroll)

        cancel = BigButton(label="Cancel", variant="command")
        cancel.size_hint_y = None
        cancel.bind(on_release=lambda *_: self._modal.dismiss())
        self._panel.add_widget(cancel)

    def _pick_value(self, value):
        # Choosing a value does NOT send; it advances to the confirmation step.
        self._value = value
        self._build_confirm_step()

    def _build_manual_value_step(self, error=None):
        """Type a number, tap a unit. Two taps and a number, no unit dropdown.

        The unit buttons carry the action rather than sitting beside a separate "OK":
        picking "Hours" IS the submit, so there is no state where a farmer has typed a
        number, chosen a unit and still not noticed the button that accepts it.
        """
        from kivy.uix.textinput import TextInput
        from .command_registry import VALUE_UNITS

        self._clear()
        self._panel.add_widget(SectionHeading(f"{self._cmd.label} — how often?"))
        self._panel.add_widget(self._hint_label(
            f"For {self._target_text()}\nType a number, then choose minutes or hours."
        ))
        if error:
            self._panel.add_widget(self._hint_label(error, color=theme.COLOR_MESA_RED))

        box = TextInput(
            hint_text="e.g. 45",
            multiline=False,
            input_filter="int",   # a cadence in whole minutes or hours; no sign, no decimal
            font_size=sp(theme.FONT_BODY),
            background_color=get_color_from_hex(theme.COLOR_SURFACE),
            foreground_color=get_color_from_hex(theme.COLOR_ON_SURFACE),
            cursor_color=get_color_from_hex(theme.COLOR_PRIMARY),
            padding=[dp(theme.SPACE_SM), dp(theme.SPACE_SM)],
            size_hint_y=None, height=dp(theme.INPUT_HEIGHT),
        )
        self._value_input = box
        self._panel.add_widget(box)

        for unit_label, unit_seconds in VALUE_UNITS:
            btn = BigButton(icon=self._cmd.icon, label=unit_label, variant="command")
            btn.size_hint_y = None
            btn.bind(on_release=lambda _b, u=unit_seconds: self._accept_manual_value(u))
            self._panel.add_widget(btn)

        back = BigButton(label="Back", variant="command")
        back.size_hint_y = None
        back.bind(on_release=lambda *_: self._build_value_step())
        self._panel.add_widget(back)

    def _accept_manual_value(self, unit_seconds):
        from .command_registry import validate_manual_value

        raw = self._value_input.text if self._value_input else ""
        seconds, error = validate_manual_value(self._cmd.key, raw, unit_seconds)
        if error:
            # Rebuild rather than only swapping the label, so the field is cleared and the
            # farmer retypes instead of editing a value that was already rejected once.
            self._build_manual_value_step(error=error)
            return
        self._pick_value(seconds)

    # ── location capture (needs_location commands only) ──────────────────────

    def _build_locate_step(self, error=None):
        self._clear()
        self._panel.add_widget(SectionHeading(f"{self._cmd.label} — where?"))
        self._panel.add_widget(self._hint_label(
            f"Node: {self._node_label}\n{self._cmd.confirm_hint}"
        ))
        if error:
            self._panel.add_widget(self._hint_label(error, color=theme.COLOR_MESA_RED))

        use_gps = BigButton(icon="📡", label="Use my current location", variant="command")
        use_gps.size_hint_y = None
        use_gps.bind(on_release=lambda *_: self._start_fix())
        self._panel.add_widget(use_gps)

        manual = BigButton(icon="⌨", label="Enter coordinates", variant="command")
        manual.size_hint_y = None
        manual.bind(on_release=lambda *_: self._build_manual_step())
        self._panel.add_widget(manual)

        cancel = BigButton(label="Cancel", variant="command")
        cancel.size_hint_y = None
        cancel.bind(on_release=lambda *_: self._modal.dismiss())
        self._panel.add_widget(cancel)

    def _start_fix(self):
        from kivy.clock import Clock
        from . import location

        self._clear()
        self._panel.add_widget(SectionHeading("Finding your position"))
        # Says "usually" first because that is now the common case: with the farm's
        # internet uplink up, Android answers from the network provider in about a
        # second. The old copy blamed the satellites for a delay that was really the
        # accuracy threshold, so a farmer standing in an open field was told to go
        # stand in an open field.
        self._panel.add_widget(self._hint_label(
            "Usually a few seconds. It can take up to a minute the first time, "
            "or if the farm has no internet — hold still in the open."
        ))
        cancel = BigButton(label="Cancel", variant="command")
        cancel.size_hint_y = None
        cancel.bind(on_release=lambda *_: self._modal.dismiss())
        self._panel.add_widget(cancel)

        # plyer delivers its callback on whatever thread Android picks, so hop back to the
        # Kivy thread before touching a single widget.
        location.get_fix_async(
            lambda fix, error: Clock.schedule_once(lambda _dt: self._on_fix(fix, error), 0)
        )

    def _mark_dismissed(self, *_args):
        self._dismissed = True

    def _on_fix(self, fix, error):
        # The search runs for up to 25 s; the farmer may well have given up and closed the
        # dialog by now. Rebuilding a dismissed dialog would leave an invisible one holding
        # a captured position, so drop the result on the floor instead.
        if self._dismissed:
            return
        if fix is None:
            self._build_locate_step(error=error or "Could not read your position.")
            return
        self._use_fix(fix)

    def _use_fix(self, fix):
        """Accept a captured position and advance to confirmation. Never sends."""
        self._fix = fix
        self._value = fix.as_wire_value()
        self._build_confirm_step()

    def _build_manual_step(self, error=None):
        from kivy.uix.textinput import TextInput

        self._clear()
        self._panel.add_widget(SectionHeading("Enter coordinates"))
        self._panel.add_widget(self._hint_label(
            "Decimal degrees. South and west are negative."
        ))
        if error:
            self._panel.add_widget(self._hint_label(error, color=theme.COLOR_MESA_RED))

        def field(hint):
            box = TextInput(
                hint_text=hint,
                multiline=False,
                font_size=sp(theme.FONT_BODY),
                background_color=get_color_from_hex(theme.COLOR_SURFACE),
                foreground_color=get_color_from_hex(theme.COLOR_ON_SURFACE),
                cursor_color=get_color_from_hex(theme.COLOR_PRIMARY),
                padding=[dp(theme.SPACE_SM), dp(theme.SPACE_SM)],
                size_hint_y=None, height=dp(theme.INPUT_HEIGHT),
            )
            # NOT input_filter="float": Kivy's built-in float filter strips everything
            # outside [0-9.], minus sign included, so it would silently make every
            # longitude in the Navajo region impossible to type. Hence a custom filter.
            box.input_filter = _coordinate_input_filter(box)
            self._panel.add_widget(box)
            return box

        self._lat_input = field("Latitude, e.g. 36.0721")
        self._lon_input = field("Longitude, e.g. -109.0450")

        use = BigButton(icon="📍", label="Use these coordinates", variant="command")
        use.size_hint_y = None
        use.bind(on_release=lambda *_: self._accept_manual())
        self._panel.add_widget(use)

        back = BigButton(label="Back", variant="command")
        back.size_hint_y = None
        back.bind(on_release=lambda *_: self._build_locate_step())
        self._panel.add_widget(back)

    def _accept_manual(self):
        from . import location
        fix, error = location.parse_manual(
            self._lat_input.text if self._lat_input else "",
            self._lon_input.text if self._lon_input else "",
        )
        if fix is None:
            self._build_manual_step(error=error)
            return
        self._use_fix(fix)

    def _summary(self):
        cmd = self._cmd
        if getattr(cmd, "needs_location", False) and self._fix is not None:
            where = f"{self._fix.latitude:.6f}, {self._fix.longitude:.6f}"
            if self._fix.accuracy_m is not None:
                return f"{cmd.label}: {where}  (±{self._fix.accuracy_m:.0f} m)"
            return f"{cmd.label}: {where}"
        if cmd.needs_value:
            if getattr(cmd, "allow_manual_value", False):
                # "Reporting interval: 2700 seconds" is the protocol talking. A farmer who
                # typed 45 minutes should be asked to confirm 45 minutes -- this is the last
                # screen before a deployed node is reconfigured, so it has to be readable in
                # the units they chose, whether they typed them or tapped a preset.
                from .command_registry import _friendly_seconds
                return f"{cmd.label}: every {_friendly_seconds(self._value)}"
            unit = cmd.value_label.lower()
            return f"{cmd.label}: {self._value} {unit}"
        return cmd.label

    def _build_confirm_step(self):
        self._clear()
        self._panel.add_widget(SectionHeading("Confirm"))

        # Broadcasts get starker wording: one tap would otherwise reconfigure every
        # deployed node at once.
        if self._is_broadcast():
            self._panel.add_widget(self._hint_label(
                f"{self._summary()}\n\nThis affects ALL FIELD NODES.",
                color=theme.COLOR_MESA_RED,
            ))
        else:
            self._panel.add_widget(self._hint_label(
                f"{self._summary()}\n\nNode: {self._node_label}"
            ))

        # A coarse fix is the failure mode that looks like success: the command goes
        # through, the node acks, and the pin lands in the wrong part of the field. The
        # farmer standing next to the node is the only one who can catch it, so say so
        # before they tap Send rather than after.
        if self._fix is not None and self._fix.is_poor:
            if self._fix.accuracy_m is None:
                warning = ("Your phone did not report how accurate this is. "
                           "Check the numbers against where you are standing.")
            else:
                warning = (f"This position is only accurate to about "
                           f"{self._fix.accuracy_m:.0f} m — the node may end up that far "
                           f"from where you are standing.")
            self._panel.add_widget(self._hint_label(warning, color=theme.COLOR_MESA_RED))

        if self._cmd.confirm_hint:
            self._panel.add_widget(self._hint_label(self._cmd.confirm_hint))

        send = BigButton(icon="📤", label="Send", variant="command")
        send.size_hint_y = None
        send.bind(on_release=lambda *_: self._send())
        self._panel.add_widget(send)

        cancel = BigButton(label="Cancel", variant="command")
        cancel.size_hint_y = None
        cancel.bind(on_release=lambda *_: self._modal.dismiss())
        self._panel.add_widget(cancel)

    def _send(self):
        # The ONLY path that dispatches a control command.
        self._modal.dismiss()
        if self._on_confirm is not None:
            self._on_confirm(self._value)

    def open(self):
        self._modal.open()

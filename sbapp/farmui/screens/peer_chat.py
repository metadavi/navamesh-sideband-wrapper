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
    FONT_BODY, FONT_LABEL, FONT_HEADING, FONT_ADDRESS,
    SCREEN_PADDING, SPACE_XS, SPACE_SM, SPACE_MD, CARD_PADDING, CARD_RADIUS,
    HAIRLINE_WIDTH, INPUT_HEIGHT, TOUCH_TARGET,
)
from ..widgets import (EmptyState, BackBar, Panel, SectionHeading, BigButton,
                       _body, _display, _mono)


def _body_kw():
    return _body()


# Width of the small Rename control in the header; a left spacer of the same
# width keeps the peer name dead-centre.
_RENAME_W = 88


class RenameDialog:
    """Small modal to set/clear the local alias for the open peer.

    Wrapper-only: Save hands the typed text to `on_save` (FarmApp.rename_peer),
    which persists it in FarmSettings JSON. Saving an empty field clears the
    alias so the announced name shows again. Nothing here touches LXMF/Sideband
    records. Built on the same ModalView + Panel language as NodePickerDialog.
    """

    def __init__(self, current: str = "", on_save=None):
        from kivy.uix.modalview import ModalView

        self._on_save = on_save
        self._modal = ModalView(
            size_hint=(0.9, None), height=dp(280),
            background_color=(0, 0, 0, 0.55),
            background="",
            auto_dismiss=True,
        )
        panel = Panel(padding=dp(CARD_PADDING), spacing=dp(SPACE_MD))
        panel.add_widget(SectionHeading("Rename device"))

        self._input = TextInput(
            text=current or "",
            hint_text="New name (leave blank to use announced name)",
            multiline=False,
            font_size=sp(FONT_BODY),
            background_color=get_color_from_hex(COLOR_SURFACE),
            foreground_color=get_color_from_hex(COLOR_ON_SURFACE),
            cursor_color=get_color_from_hex(COLOR_PRIMARY),
            padding=[dp(SPACE_SM), dp(SPACE_SM)],
            size_hint_y=None, height=dp(INPUT_HEIGHT),
        )
        self._input.bind(on_text_validate=lambda *_: self._save())
        panel.add_widget(self._input)

        save = BigButton(label="Save", variant="command")
        save.size_hint_y = None
        save.bind(on_release=lambda *_: self._save())
        panel.add_widget(save)

        cancel = BigButton(label="Cancel", variant="command")
        cancel.size_hint_y = None
        cancel.bind(on_release=lambda *_: self._modal.dismiss())
        panel.add_widget(cancel)

        self._modal.add_widget(panel)

    def _save(self):
        self._modal.dismiss()
        if self._on_save is not None:
            self._on_save(self._input.text or "")

    def open(self):
        self._modal.open()


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

        # ── Peer identity card: name front-and-centre, address secondary ─────
        self._header = Panel(size_hint_y=None, spacing=dp(SPACE_XS))
        self._header.bind(minimum_height=self._header.setter("height"))
        # Name row: a left spacer mirrors the Rename control so the peer name
        # stays dead-centre; Rename opens the local-alias dialog (wrapper-only).
        name_row = BoxLayout(orientation="horizontal", spacing=dp(SPACE_XS),
                             size_hint_y=None, height=dp(TOUCH_TARGET))
        name_row.add_widget(Widget(size_hint_x=None, width=dp(_RENAME_W)))
        self._name_label = Label(
            text="", bold=True,
            font_size=sp(FONT_HEADING),
            color=get_color_from_hex(COLOR_ON_SURFACE),
            halign="center", valign="middle",
            **_display(),
        )
        self._name_label.bind(width=lambda i, w: setattr(i, "text_size", (w, None)))
        name_row.add_widget(self._name_label)
        self._rename_btn = Button(
            text="Rename",
            font_size=sp(FONT_LABEL),
            color=get_color_from_hex(COLOR_MUTED),
            size_hint_x=None, width=dp(_RENAME_W),
            background_normal="", background_down="",
            background_color=(0, 0, 0, 0),
        )
        self._rename_btn.bind(on_release=lambda *_: self._open_rename())
        name_row.add_widget(self._rename_btn)
        self._header.add_widget(name_row)
        self._addr_label = Label(
            text="",
            font_size=sp(FONT_ADDRESS),
            color=get_color_from_hex(COLOR_MUTED),
            halign="center", valign="middle",
            size_hint_y=None, height=dp(TOUCH_TARGET) / 2,
            **_mono(),
        )
        self._addr_label.bind(width=lambda i, w: setattr(i, "text_size", (w, None)))
        self._header.add_widget(self._addr_label)
        self.add_widget(self._header)

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
        """Reset the view for a freshly-tapped peer (session view, starts blank).

        Old DB history is baselined by FarmApp and not rendered; only messages
        exchanged while this chat is open appear.
        """
        self._peer_hash = dest_hex
        self._name_label.text = display_name or "(unnamed device)"
        self._addr_label.text = dest_hex
        self._msgs.clear_widgets()
        self._msgs.add_widget(self._empty)
        self._input.text = ""

    def close_peer(self):
        """Clear the visible session on exit (nothing in the DB is touched)."""
        self._peer_hash = None
        self._msgs.clear_widgets()
        self._msgs.add_widget(self._empty)
        self._input.text = ""

    def set_display_name(self, display_name: str):
        """Update the header name in place (alias saved/cleared while open)."""
        self._name_label.text = display_name or "(unnamed device)"

    def add_message(self, text: str, outbound: bool):
        if self._empty.parent:
            self._msgs.remove_widget(self._empty)
        self._msgs.add_widget(_Bubble(text=text, outbound=outbound))
        # Keep the latest message in view.
        self._scroll.scroll_y = 0

    # ── Internal ─────────────────────────────────────────────────────────────

    def _open_rename(self):
        """Open the local-alias dialog for the current peer (wrapper-only)."""
        if not self._peer_hash:
            return
        current = ""
        try:
            current = self._app._settings.get_peer_alias(self._peer_hash) or ""
        except Exception:
            pass
        peer_hash = self._peer_hash
        RenameDialog(
            current=current,
            on_save=lambda text: self._app.rename_peer(peer_hash, text),
        ).open()

    def _send(self):
        text = (self._input.text or "").strip()
        if not text or not self._peer_hash:
            return
        self._app.send_peer_text(self._peer_hash, text)
        self._input.text = ""

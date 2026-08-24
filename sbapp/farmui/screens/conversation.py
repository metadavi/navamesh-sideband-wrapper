"""screens/conversation.py — Pinned-gateway header + 9 command buttons + message list."""
from __future__ import annotations

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.metrics import dp, sp
from kivy.utils import get_color_from_hex

from ..theme import (
    COLOR_ON_SURFACE, COLOR_MUTED,
    FONT_LABEL, SCREEN_PADDING, SPACE_SM, SPACE_MD,
    TOUCH_TARGET,
)
from ..widgets import (
    BigButton, ResultCard, EmptyState, SectionHeading, Panel, BackBar,
)
from ..command_registry import COMMANDS
from ..textfmt import render_reply

_MAX_CARDS = 100


class ConversationScreen(BoxLayout):
    name = "conversation"

    def __init__(self, app, **kwargs):
        super().__init__(orientation="vertical", padding=dp(SCREEN_PADDING),
                         spacing=dp(SPACE_MD), **kwargs)
        self._app = app
        self._in_flight = False
        self._result_cards: list = []
        self._waiting = None  # transient "Waiting for reply…" placeholder card

        # ── Back to Talk ────────────────────────────────────────────────────
        self.add_widget(BackBar(title="Gateway commands", on_back=app.go_home))

        # ── Everything below the back bar scrolls as one page ───────────────
        #
        # It used to be only the reply area that scrolled, sitting in a fixed column
        # beneath the gateway strip and a 14-tile command grid. Those took most of a
        # phone screen and the ScrollView got what was left -- roughly a third. A
        # `help` reply is 27 lines and landed in a viewport showing eight of them, so
        # a complete answer read as a truncated one.
        #
        # Now the grid scrolls away with everything else and a reply renders at its
        # natural height, which is what makes reading a long one a scroll rather than
        # a squint. ResultCard already sizes itself from its texture, so nothing here
        # needs to know how tall a reply is.
        self._page = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        content = BoxLayout(orientation="vertical", size_hint_y=None,
                            spacing=dp(SPACE_MD))
        content.bind(minimum_height=content.setter("height"))

        # ── Gateway header (compact Field-Log status strip) ─────────────────
        # A single short line — "GATEWAY" caption + name + truncated hash — so the
        # reply area below gets the vertical space, not the header.
        header = Panel(size_hint_y=None, height=dp(TOUCH_TARGET),
                       padding=dp(SPACE_SM), spacing=0)
        self._gw_label = Label(
            text=self._gw_markup(None, None),
            markup=True,
            font_size=sp(FONT_LABEL),
            color=get_color_from_hex(COLOR_ON_SURFACE),
            size_hint_y=1,
            halign="left", valign="middle",
            shorten=True, shorten_from="right",
        )
        self._gw_label.bind(size=lambda i, _s: setattr(i, "text_size", i.size))
        header.add_widget(self._gw_label)
        content.add_widget(header)

        # ── Command button grid (3×3, compact parchment command tiles) ──────
        grid = GridLayout(cols=3, size_hint_y=None, spacing=dp(SPACE_SM))
        grid.bind(minimum_height=grid.setter("height"))
        self._cmd_buttons: list[BigButton] = []
        for cmd in COMMANDS:
            btn = BigButton(icon=cmd.icon, label=cmd.label, variant="command")
            btn.bind(on_press=lambda _, c=cmd: self._on_command(c))
            grid.add_widget(btn)
            self._cmd_buttons.append(btn)
        content.add_widget(grid)

        # ── Replies ────────────────────────────────────────────────────────
        content.add_widget(SectionHeading("Replies"))

        self._msgs = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(SPACE_SM))
        self._msgs.bind(minimum_height=self._msgs.setter("height"))
        # Explicit height: EmptyState stretches by default, and a stretching child
        # contributes nothing to a minimum_height column, so it would collapse here.
        self._empty = EmptyState(icon="💬", message="No replies yet.\nTap a command above.",
                                 size_hint_y=None, height=dp(160))
        self._onboarding = ResultCard(
            text="[font=emoji]👋[/font] Welcome!\nGo to the [font=emoji]💬[/font] Talk tab and tap your farm gateway\nto open these commands.",
            use_markup=True,
        )
        self._msgs.add_widget(self._onboarding)
        content.add_widget(self._msgs)
        self._page.add_widget(content)
        self.add_widget(self._page)

    @staticmethod
    def _gw_markup(display_name: str | None, short_hash: str | None) -> str:
        muted = COLOR_MUTED.lstrip("#")
        if not display_name:
            return (f"[color={muted}]GATEWAY[/color]  "
                    "None selected — tap a gateway in the Talk tab")
        return (f"[color={muted}]GATEWAY[/color]  [b]{display_name}[/b]  "
                f"[color={muted}]{short_hash}[/color]")

    def update_gateway(self, display_name: str, short_hash: str):
        self._gw_label.text = self._gw_markup(display_name, short_hash)
        if self._onboarding.parent:
            self._msgs.remove_widget(self._onboarding)
        if not self._empty.parent and not self._result_cards:
            self._msgs.add_widget(self._empty)

    def _clear_results(self):
        """Drop every card so the screen reads like a live dashboard, not a log.

        Called when a new command is sent: the previous reply is removed so only
        the latest gateway response stays visible.
        """
        for card in self._result_cards:
            self._msgs.remove_widget(card)
        self._result_cards.clear()
        if self._waiting is not None and self._waiting.parent:
            self._msgs.remove_widget(self._waiting)
        self._waiting = None
        if self._onboarding.parent:
            self._msgs.remove_widget(self._onboarding)
        if self._empty.parent:
            self._msgs.remove_widget(self._empty)

    def reset_replies(self):
        """Start a fresh gateway session (called when entering the chat)."""
        self._clear_results()
        if not self._empty.parent:
            self._msgs.add_widget(self._empty)

    def _show_waiting(self):
        self._waiting = ResultCard(
            text="[font=emoji]⏳[/font] Waiting for reply…", use_markup=True)
        self._msgs.add_widget(self._waiting)
        self._reveal_replies()

    def add_result(self, text: str, image_bytes: bytes | None = None,
                   image_ext: str = "png"):
        # The waiting placeholder and any older reply are replaced — only the
        # most recent gateway reply remains (a clean dashboard, not a history).
        if self._waiting is not None and self._waiting.parent:
            self._msgs.remove_widget(self._waiting)
            self._waiting = None
        if self._onboarding.parent:
            self._msgs.remove_widget(self._onboarding)
        if self._empty.parent:
            self._msgs.remove_widget(self._empty)
        while len(self._result_cards) >= _MAX_CARDS:
            oldest = self._result_cards.pop(0)
            self._msgs.remove_widget(oldest)
        card = ResultCard(text=render_reply(text), image_bytes=image_bytes,
                          image_ext=image_ext, use_markup=True, mono=True)
        self._result_cards.append(card)
        self._msgs.add_widget(card)
        self._reveal_replies()

    def _reveal_replies(self):
        """Scroll the page down to the reply that just arrived.

        Now that the command grid scrolls with the page, a reply lands below the fold:
        without this the farmer taps a command and the screen appears not to change.

        Deferred a frame rather than run inline, because a ResultCard's height comes
        from its label texture and is still 0 at the moment it is added -- scrolling
        immediately targets where the card was while it was empty, which is the top of
        the page. 0.05 s is after the next layout pass on the deployed handsets.
        """
        from kivy.clock import Clock

        def _do(_dt):
            try:
                self._page.scroll_to(self._msgs, padding=dp(SPACE_MD), animate=True)
            except Exception:
                # Never let a scrolling convenience take down the reply itself.
                pass

        Clock.schedule_once(_do, 0.05)

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
        if cmd.needs_node:
            # The node picker may be cancelled, so don't lock the UI or show the
            # "Waiting…" card yet — only _run_command (fired when a node is
            # actually chosen) commits to a send. The modal blocks double-taps.
            #
            # Control commands get one more hop: picking a target opens the
            # value/confirm dialog rather than sending, because these reconfigure
            # deployed hardware instead of just querying the database.
            if getattr(cmd, "is_write", False):
                self._app.open_node_picker(cmd, on_pick=self._confirm_write)
            else:
                self._app.open_node_picker(cmd, on_pick=self._run_command)
            return
        self._run_command(cmd.key)

    def _confirm_write(self, cmd_key, node_id=None):
        """A target was chosen for a control command — confirm before anything is sent."""
        from ..command_registry import get_command
        if self._in_flight:
            return
        self._app.open_command_confirm(
            get_command(cmd_key), node_id, on_confirm=self._run_command
        )

    def _run_command(self, cmd_key, node_id=None, value=None):
        self._in_flight = True
        self._set_buttons_enabled(False)
        # Replace the previous reply the moment a new command is sent.
        self._clear_results()
        self._show_waiting()
        self._app.dispatch_command(
            cmd_key, node_id, on_complete=self._on_command_done, value=value
        )

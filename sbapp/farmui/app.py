"""
app.py — FarmApp: minimal UI layer over SidebandCore.

SidebandCore is instantiated exactly as upstream sbapp/main_upstream.py does:
  - Desktop: SidebandCore(app, config_path=..., is_client=False, verbose=...)
  - Android: SidebandCore(app, config_path=..., is_client=True, android_app_dir=..., verbose=...)

The FarmApp accesses core ONLY via its public methods:
  lxmf_announce(), list_announces(), send_message(), list_messages(),
  list_conversations(), getstate(), setstate()

See docs/ARCHITECTURE.md for the seam description.
"""
from __future__ import annotations

import os
import sys
import threading

import kivy
kivy.require("2.0.0")

from kivy.app import App
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelHeader
from kivy.uix.label import Label
from kivy.metrics import dp, sp
from kivy.utils import get_color_from_hex
from kivy.clock import Clock

from .screens.announce import AnnounceScreen
from .screens.stream import StreamScreen
from .screens.conversation import ConversationScreen
from .command_registry import COMMANDS, get_wire
from . import theme


class FarmApp(App):
    """
    Farm UI app shell.

    SidebandCore lifecycle mirrors main_upstream.py (lines 541-546):
      Android:  is_client=True
      Desktop:  is_client=False
    """

    title = "Navamesh Farm"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sideband = None
        self._gateway_hash = None
        self._gateway_name = "(none)"
        self._node_cache: list[str] = []

    # ── Kivy lifecycle ────────────────────────────────────────────────────────

    def build(self):
        Window.clearcolor = get_color_from_hex(theme.COLOR_BG)
        Window.size = (480, 854)

        root = BoxLayout(orientation="vertical")
        tabs = TabbedPanel(do_default_tab=False)
        tabs.tab_width = Window.width / 3

        self._ann_screen  = AnnounceScreen(app=self)
        self._str_screen  = StreamScreen(app=self)
        self._conv_screen = ConversationScreen(app=self)

        for screen, label, icon in [
            (self._ann_screen,  "Announce",     "📢"),
            (self._str_screen,  "Stream",       "📡"),
            (self._conv_screen, "Commands",     "💬"),
        ]:
            tab = TabbedPanelHeader(text=f"{icon}\n{label}")
            tab.content = screen
            tabs.add_widget(tab)

        root.add_widget(tabs)
        return root

    def on_start(self):
        self._init_sideband()
        Clock.schedule_interval(self._poll, 2.0)

    def _init_sideband(self):
        try:
            import RNS.vendor.platformutils as pu
            platform = pu.get_platform()
        except Exception:
            platform = "linux"

        config_path = None

        if platform == "android":
            from .sideband.core import SidebandCore
            self.sideband = SidebandCore(
                self,
                config_path=config_path,
                is_client=True,
                android_app_dir=self.user_data_dir,
                verbose=False,
            )
        else:
            try:
                sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
                from sideband.core import SidebandCore
                self.sideband = SidebandCore(
                    self,
                    config_path=config_path,
                    is_client=False,
                    verbose=False,
                )
            except Exception as exc:
                # Desktop dev mode: core unavailable, run in stub mode
                self.sideband = None

        if self.sideband:
            try:
                addr = self.sideband.lxmf_destination.hexhash if hasattr(
                    self.sideband, 'lxmf_destination') else "unavailable"
            except Exception:
                addr = "unavailable"
            self._ann_screen.update_address(addr)

    def _poll(self, dt):
        """Lightweight poll of core state — mirrors main_upstream.py getstate pattern."""
        if self.sideband is None:
            return
        try:
            # Update connectivity chip on all screens
            connected = bool(self.sideband.getstate("misc.connectivity"))
            for screen in (self._ann_screen, self._str_screen, self._conv_screen):
                if hasattr(screen, 'set_connected'):
                    screen.set_connected(connected)
        except Exception:
            pass

    # ── Public actions (called by screens) ────────────────────────────────────

    def send_announce(self):
        if self.sideband:
            try:
                self.sideband.lxmf_announce()
            except Exception:
                pass

    def set_gateway(self, display_name: str, short_hash: str):
        self._gateway_name = display_name
        self._gateway_hash = short_hash
        self._conv_screen.update_gateway(display_name, short_hash)

    def dispatch_command(self, cmd_key: str, node_id: str | None = None):
        wire = get_wire(cmd_key, node_id)
        if self.sideband and self._gateway_hash:
            threading.Thread(
                target=self._send_and_show,
                args=(self._gateway_hash, wire),
                daemon=True,
            ).start()
        else:
            self._conv_screen.add_result(
                f"[Gateway not pinned or radio unavailable]\nWould send: {wire!r}"
            )

    def _send_and_show(self, dest_hash: str, content: str):
        try:
            self.sideband.send_message(dest_hash, content)
        except Exception as exc:
            Clock.schedule_once(
                lambda _: self._conv_screen.add_result(f"Send failed: {exc}"), 0
            )

    def open_node_picker(self, cmd):
        if self._node_cache:
            node_id = self._node_cache[0]
            self.dispatch_command(cmd.key, node_id)
        else:
            self._conv_screen.add_result(
                "No node list yet — tap 'List nodes' first, then try 'Map — one node'."
            )


def run():
    FarmApp().run()


if __name__ == "__main__":
    run()

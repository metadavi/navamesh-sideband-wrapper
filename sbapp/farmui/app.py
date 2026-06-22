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
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.label import Label
from kivy.metrics import dp, sp
from kivy.utils import get_color_from_hex
from kivy.clock import Clock

from .screens.announce import AnnounceScreen
from .screens.stream import StreamScreen
from .screens.conversation import ConversationScreen
from .screens.peer_chat import PeerChatScreen
from .command_registry import COMMANDS, get_wire
from .devices import is_gateway_device
from .widgets import StatusChip
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
        self._dispatcher = None
        self._gateway_hash = None
        self._gateway_name = "(none)"
        self._node_cache: list[str] = []
        # Hashes of gateway replies already shown in the gateway command screen.
        self._shown_msgs: set[str] = set()
        # Active peer conversation (Talk → tap a non-gateway device) + its
        # already-rendered message hashes (reset each time a peer is opened).
        self._active_peer_hash: str | None = None
        self._shown_peer_msgs: set[str] = set()
        # True once we have ever read an announce row this session — lets the
        # status chip tell "listening (none yet)" from "mesh quiet (gone stale)".
        self._heard_any_announce = False
        # Backend-service launch tracking (Android). Set by _start_service().
        self._service_launch_error: str | None = None
        self._service_started_at: float | None = None

    # ── Kivy lifecycle ────────────────────────────────────────────────────────

    def build(self):
        from .settings import FarmSettings
        self._settings = FarmSettings(self.user_data_dir)
        # Developer mode: shows the optional Debug diagnostics tab. Off for farmers.
        # Enabled by the NAVAMESH_DEV env var (dev builds) or the dev_mode setting.
        self._dev_mode = bool(os.environ.get("NAVAMESH_DEV")) or self._settings.dev_mode

        # Register emoji font. EmojiScaled.ttf is bundled by upstream Sideband and
        # is a standard TrueType that SDL2_ttf/FreeType can load on Android.
        # NotoEmoji-Regular.ttf (the 299K Google subset) causes "Couldn't load font"
        # in SDL2_ttf on this p4a build, so we prefer EmojiScaled.ttf.
        # (os is imported at module top; no local re-import — a local `import os`
        # here would shadow it and make the os.environ use above an UnboundLocalError.)
        from kivy.core.text import LabelBase
        _app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        fonts_dir = os.path.join(_app_root, "assets", "fonts")
        for _emoji_candidate in ("EmojiScaled.ttf", "NotoEmoji-Regular.ttf"):
            _path = os.path.join(fonts_dir, _emoji_candidate)
            if os.path.exists(_path):
                LabelBase.register("emoji", fn_regular=_path)
                break

        # Navamesh type registers, from fonts already bundled by upstream — no
        # new assets. mono carries addresses/IDs/timestamps (the JetBrains Mono
        # role on the cloud dashboard); body/display approximate Inter Tight /
        # the serif reading weight with NotoSans. Registration is defensive:
        # theme.family() returns None for any family that failed to load, so a
        # missing TTF degrades to Kivy's default font instead of crashing.
        for _family, _file in (
            (theme.FONT_MONO,           "RobotoMonoNerdFont-Regular.ttf"),
            (theme.FONT_BODY_FAMILY,    "NotoSans-Regular.ttf"),
            (theme.FONT_DISPLAY_FAMILY, "NotoSans-Bold.ttf"),
        ):
            _fp = os.path.join(fonts_dir, _file)
            if os.path.exists(_fp):
                try:
                    LabelBase.register(_family, fn_regular=_fp)
                    theme.register_family(_family)
                except Exception:
                    pass

        Window.clearcolor = get_color_from_hex(theme.COLOR_BG)

        # Only force a fixed size on desktop dev; on Android use the full screen
        from kivy.utils import platform as kivy_platform
        if kivy_platform != "android":
            Window.size = (480, 854)

        root = BoxLayout(orientation="vertical")
        root.add_widget(self._build_topbar())

        # ── Navigation: a ScreenManager wraps the two-tab home and the pushed
        # chat screens. Tapping a device in Talk opens the right chat screen
        # (gateway dashboard or peer messenger); each has a Back control. ───────
        tabs = TabbedPanel(do_default_tab=False, size_hint=(1, 1),
                           tab_height=dp(theme.TAB_HEIGHT))
        # Content frame behind the screens reads as parchment, not Kivy gray.
        tabs.background_color = get_color_from_hex(theme.COLOR_BG)
        self._home_tabs = tabs

        self._ann_screen  = AnnounceScreen(app=self)
        self._str_screen  = StreamScreen(app=self)
        self._conv_screen = ConversationScreen(app=self)
        self._peer_screen = PeerChatScreen(app=self)

        # Paint the parchment content surface behind each screen. TabbedPanel /
        # ScreenManager draw their own dark content background that
        # background_color does not fully override, so we fill screens directly.
        from .widgets import paint_background
        for _scr in (self._ann_screen, self._str_screen,
                     self._conv_screen, self._peer_screen):
            paint_background(_scr, theme.COLOR_BG)

        # Restore the previously-pinned farm gateway (if any) so the selection
        # persists across app close / relaunch / phone restart / stable-key
        # updates. Read from farmui's own settings; no backend state involved.
        self._restore_gateway()

        # Exactly two farmer tabs: Connect (announce) and Talk (devices).
        tab_specs = [
            (self._ann_screen,  "Connect",  "📡"),
            (self._str_screen,  "Talk",     "💬"),
        ]
        # Optional dev-only diagnostics tab (hidden from farmers; see dev_diagnostics).
        if self._dev_mode:
            from .screens.debug import DebugScreen
            self._dbg_screen = DebugScreen(app=self)
            tab_specs.append((self._dbg_screen, "Debug", "🛠"))

        n_tabs = len(tab_specs)
        tabs.tab_width = Window.width / n_tabs
        Window.bind(width=lambda _, w: setattr(tabs, "tab_width", w / n_tabs))

        self._talk_tab = None
        for screen, label, icon in tab_specs:
            tab = TabbedPanelHeader(
                text=f"[font=emoji]{icon}[/font]\n{label}",
                markup=True,
            )
            self._style_tab_header(tab)
            tab.content = screen
            tabs.add_widget(tab)
            if label == "Talk":
                self._talk_tab = tab

        self._sm = ScreenManager()
        home = Screen(name="home")
        home.add_widget(tabs)
        gw_screen = Screen(name="gateway_chat")
        gw_screen.add_widget(self._conv_screen)
        peer_screen = Screen(name="peer_chat")
        peer_screen.add_widget(self._peer_screen)
        for s in (home, gw_screen, peer_screen):
            self._sm.add_widget(s)

        # Android hardware back button: navigate back within the app (a backward
        # slide) instead of the default forward feel / app exit, when in a chat.
        Window.bind(on_keyboard=self._on_keyboard)

        root.add_widget(self._sm)
        return root

    def _on_keyboard(self, _window, key, *args):
        """Handle the Android back key (27): leave a chat back to home; on home,
        fall through to the default (minimise/exit)."""
        if key == 27:
            sm = getattr(self, "_sm", None)
            if sm is not None and sm.current != "home":
                self.go_home()
                return True
        return False

    def _build_topbar(self):
        """Canyon Dark 'instrument frame' top bar: brand mark + wordmark.

        Branding only — it intentionally holds no live state, so the polling
        path (_poll → screen.set_state) is untouched. Per-screen status chips
        continue to carry connectivity.
        """
        from kivy.uix.label import Label as _Label
        from kivy.graphics import Color, Rectangle
        from .widgets import BrandMark
        from .widgets import _mono  # mono-family kwargs helper

        bar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None, height=dp(theme.TOPBAR_HEIGHT),
            padding=[dp(theme.SCREEN_PADDING), dp(theme.SPACE_XS)],
            spacing=dp(theme.SPACE_SM),
        )
        with bar.canvas.before:
            Color(*get_color_from_hex(theme.COLOR_CHROME))
            bar._bg = Rectangle(pos=bar.pos, size=bar.size)
        bar.bind(pos=lambda *_: setattr(bar._bg, "pos", bar.pos),
                 size=lambda *_: setattr(bar._bg, "size", bar.size))

        bar.add_widget(BrandMark())
        wordmark = _Label(
            text="NAVAMESH",
            markup=True, bold=True,
            font_size=sp(theme.FONT_LABEL),
            color=get_color_from_hex(theme.COLOR_ON_CHROME),
            halign="left", valign="middle",
            **_mono(),
        )
        wordmark.bind(size=lambda inst, _s: setattr(inst, "text_size", inst.size))
        bar.add_widget(wordmark)

        tagline = _Label(
            text="FIELD LINK",
            font_size=sp(theme.FONT_CAPTION),
            color=get_color_from_hex(theme.COLOR_ACCENT),
            halign="right", valign="middle",
            **_mono(),
        )
        tagline.bind(size=lambda inst, _s: setattr(inst, "text_size", inst.size))
        bar.add_widget(tagline)
        return bar

    @staticmethod
    def _style_tab_header(tab):
        """Dark instrument-frame tab: Sandstone Gold label when active,
        dimmed ghost-light when inactive. Background atlas is tinted Canyon
        Dark so the whole strip reads as the dark frame."""
        tab.background_color = get_color_from_hex(theme.COLOR_CHROME)
        tab.font_size = sp(theme.FONT_CAPTION)

        def _update(_inst, state):
            active = (state == "down")
            tab.color = get_color_from_hex(
                theme.COLOR_ACCENT if active else theme.COLOR_GHOST)
            tab.bold = active

        tab.bind(state=_update)
        _update(tab, tab.state)
        return tab

    def on_start(self):
        # Defer backend bring-up off on_start so the UI's SDL/graphics stack
        # finishes initialising and renders FIRST. This mirrors upstream
        # (main_upstream.on_start → Clock.schedule_once(self.start_core, 0.25)):
        # launching the foreground service makes a second process cold-start the
        # native Python/SDL stack, and doing that concurrently with the UI's own
        # cold start races the HWUI render thread (observed SIGABRT in hwuiTask0).
        # A short delay lets the activity come up alone, then we start the
        # service + client core.
        Clock.schedule_once(self._start_backend, 0.75)
        Clock.schedule_interval(self._poll, 2.0)

    def _start_backend(self, _dt):
        # Order matters: construct the client core first (loads Sideband config +
        # identity), ensure the HT-HD01 RNS config template is in place, THEN
        # launch the service — the service regenerates its RNS config from that
        # template on start, so the interface must be persisted beforehand.
        self._init_sideband()
        changed = self._ensure_hthd01_config()
        if changed:
            # If a service from a previous session is still running with the old
            # template, ask it to stop so the one we launch picks up the new one.
            try:
                self.sideband.setstate("wants.service_stop", True)
            except Exception:
                pass
        self._start_service()

    def _ensure_hthd01_config(self) -> bool:
        """Persist the HT-HD01 UDP interface into Sideband's RNS config template
        and enable transport. Returns True if anything changed.

        This only writes Sideband *config* (config_template + connect_transport)
        via save_configuration(); the identity, message DB, and other storage are
        untouched. The service regenerates app_storage/reticulum/config from this
        template on each (re)start, so editing the generated file would not
        persist — the template is the durable home for the interface.
        """
        if not self.sideband:
            return False
        try:
            from .rns_config_writer import build_config_template
            desired = build_config_template()
            cfg = self.sideband.config
            changed = False
            if cfg.get("config_template") != desired:
                cfg["config_template"] = desired
                changed = True
            if not cfg.get("connect_transport"):
                cfg["connect_transport"] = True
                changed = True
            if changed:
                self.sideband.save_configuration()
                import RNS
                RNS.log("Navamesh: applied HT-HD01 RNS config template; "
                        "service will use it on (re)start", RNS.LOG_NOTICE)
            return changed
        except Exception as exc:
            try:
                import RNS
                RNS.log(f"Navamesh: failed to apply HT-HD01 config: {exc}", RNS.LOG_ERROR)
            except Exception:
                pass
            return False

    # ── Android backend service launch ─────────────────────────────────────────

    # p4a generates the service Java class as "Service" + the capitalized
    # service name declared in buildozer.spec (services = sidebandservice:...).
    # The PACKAGE is resolved at runtime from the running activity so we never
    # hardcode upstream Sideband's own application package name.
    SERVICE_SUFFIX = "ServiceSidebandservice"

    @classmethod
    def _service_class_name(cls, package: str) -> str:
        """Fully-qualified Android service class for this build's package."""
        return f"{package}.{cls.SERVICE_SUFFIX}"

    def _start_service(self):
        """Launch the declared foreground Sideband service (Android only).

        UI-layer mirror of main_upstream.start_service(), but the service class
        package is derived from the live activity (not hardcoded). Any failure
        is logged AND recorded so the UI can surface a clear message instead of
        silently showing 'radio not responding'.
        """
        try:
            import RNS
            if not RNS.vendor.platformutils.is_android():
                return
            from jnius import autoclass
            mActivity = autoclass("org.kivy.android.PythonActivity").mActivity
            package = mActivity.getPackageName()
            service_class = self._service_class_name(package)
            service = autoclass(service_class)
            # Argument becomes PYTHON_SERVICE_ARGUMENT → the service's app_dir,
            # matching the client core's android_app_dir so both share one config.
            service.start(mActivity, self.user_data_dir)
            self._service_started_at = self._now()
            self._service_launch_error = None
            RNS.log(f"Navamesh: launched backend service {service_class}", RNS.LOG_NOTICE)
        except Exception as exc:
            self._service_launch_error = str(exc)
            try:
                import RNS
                RNS.log(f"Navamesh: failed to launch backend service: {exc}", RNS.LOG_ERROR)
            except Exception:
                pass

    @staticmethod
    def _now() -> float:
        import time
        return time.time()

    def _init_sideband(self):
        try:
            import RNS.vendor.platformutils as pu
            platform = pu.get_platform()
        except Exception:
            platform = "linux"

        config_path = None

        # `sideband` is a TOP-LEVEL package at the app root (sbapp/sideband),
        # not a submodule of farmui — so import it absolutely, like upstream.
        # (The previous relative `from .sideband.core` resolved to
        # farmui.sideband.core, which does not exist → ModuleNotFoundError that
        # killed the process when raised from the deferred startup callback.)
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        if platform == "android":
            try:
                from sideband.core import SidebandCore
                self.sideband = SidebandCore(
                    self,
                    config_path=config_path,
                    is_client=True,
                    android_app_dir=self.user_data_dir,
                    verbose=False,
                )
            except Exception as exc:
                self.sideband = None
                try:
                    import RNS
                    RNS.log(f"Navamesh: failed to init client core: {exc}", RNS.LOG_ERROR)
                except Exception:
                    pass
        else:
            try:
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
            from .dispatch import CoreDispatcher
            self._dispatcher = CoreDispatcher(self.sideband)
            self._ann_screen.update_address(self.local_address())

    # Max age (seconds) of the backend service heartbeat before we consider the
    # radio/backend unresponsive. The service refreshes it roughly every second
    # (sidebandservice.py), so 8s tolerates a few missed ticks without flapping.
    HEARTBEAT_MAX_AGE = 8.0

    # Grace period after launching the service before a missing heartbeat is
    # treated as "not running" (the service takes a few seconds to boot RNS).
    CONNECT_GRACE = 20.0

    # How recently an announce must have been *heard over the radio* for the chip
    # to read "Mesh active". The Pi/gateway announces roughly every 3 minutes, so
    # 5 min tolerates one missed announce without flapping. A heard announce is
    # direct proof the device is receiving live mesh traffic — far stronger than
    # the service heartbeat (which only proves the background process is alive).
    RADIO_LIVE_WINDOW = 300.0

    def _radio_is_up(self) -> bool:
        """Real, read-only connectivity signal for the status chip.

        On Android the SidebandCore runs in a separate service process, so the
        only thing the UI can observe is the RPC-readable `service.heartbeat`
        timestamp the service refreshes each loop — a fresh heartbeat means the
        backend (and thus its configured interfaces) is alive and responding.

        On desktop/dev the core runs in-process, so we can inspect live RNS
        interface state directly. Either way this only *reads* existing state;
        no backend behavior is touched.
        """
        if self.sideband is None:
            return False
        try:
            import time
            import RNS
            if RNS.vendor.platformutils.is_android():
                hb = self.sideband.getstate("service.heartbeat")
                return bool(hb) and (time.time() - float(hb)) < self.HEARTBEAT_MAX_AGE
            # Desktop/dev: core is in-process; inspect live interfaces.
            local = getattr(self.sideband, "interface_local", None)
            for iface in RNS.Transport.interfaces:
                if iface is local:
                    continue
                if getattr(iface, "online", False):
                    return True
            reticulum = getattr(self.sideband, "reticulum", None)
            return bool(reticulum and getattr(
                reticulum, "is_connected_to_shared_instance", False))
        except Exception:
            return False

    def _latest_announce_epoch(self):
        """Epoch (float) of the most recently *received* announce, or None.

        Reads the shared Sideband announce table read-only with a single
        max(received) query — cheap (no LXMF decode, unlike list_announces_safe).
        Announces only arrive over the radio, so this is direct evidence of live
        mesh RX.
        """
        if not self.sideband:
            return None
        db_path = getattr(self.sideband, "db_path", None)
        if not db_path or not os.path.isfile(db_path):
            return None
        try:
            import sqlite3
            con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5.0)
            try:
                row = con.execute("select max(received) from announce").fetchone()
            finally:
                con.close()
        except Exception:
            return None
        if not row or row[0] is None:
            return None
        try:
            return float(row[0])
        except Exception:
            return None

    def _radio_traffic_fresh(self) -> bool:
        """True if an announce was heard within RADIO_LIVE_WINDOW.

        Side effect: records that we have *ever* heard an announce this session
        (even a stale one), so the chip can distinguish "listening, none yet"
        from "mesh quiet (heard before, now gone)".
        """
        epoch = self._latest_announce_epoch()
        if epoch is None:
            return False
        self._heard_any_announce = True
        return (self._now() - epoch) < self.RADIO_LIVE_WINDOW

    def _connectivity_state(self) -> str:
        """Four-state mesh status for the chip.

        Layered, honest signals (the backend is byte-locked, so we only read):
          - no_service : the background service isn't running / failed to launch.
          - connected  ("Mesh active")       : the service is alive AND an announce
            was heard over the radio within RADIO_LIVE_WINDOW (proof of live RX).
          - mesh_quiet ("Mesh quiet")         : service alive, announces were heard
            before but none recently (mesh went quiet / link likely dropped).
          - connecting ("Listening for mesh…"): service alive, none heard yet.
        We never claim "Radio Connected" — we can prove traffic, not a link.
        """
        if self.sideband is None:
            return StatusChip.NO_SERVICE
        if self._radio_is_up():
            if self._radio_traffic_fresh():
                return StatusChip.CONNECTED
            if self._heard_any_announce:
                return StatusChip.MESH_QUIET
            return StatusChip.CONNECTING
        if self._service_launch_error is not None:
            return StatusChip.NO_SERVICE
        # No heartbeat yet: still connecting if we're within the grace window
        # after launching the service, otherwise the service isn't running.
        if self._service_started_at is not None:
            if (self._now() - self._service_started_at) < self.CONNECT_GRACE:
                return StatusChip.CONNECTING
            return StatusChip.NO_SERVICE
        # Desktop/dev (no service launched): treat as connecting until up.
        return StatusChip.CONNECTING

    def _poll(self, dt):
        """Lightweight poll of core state — mirrors main_upstream.py getstate pattern."""
        try:
            state = self._connectivity_state()
            for screen in (self._ann_screen, self._str_screen,
                           self._conv_screen, self._peer_screen):
                if hasattr(screen, "set_state"):
                    screen.set_state(state)
            if hasattr(self, "_dbg_screen") and hasattr(self._dbg_screen, "refresh"):
                self._dbg_screen.refresh()
            self._refresh_announces()
            self._poll_gateway_replies()
            self._poll_peer_messages()
        except Exception:
            pass

    def _poll_gateway_replies(self):
        """Show incoming replies from the pinned gateway in the Commands tab.

        Command replies arrive asynchronously and are stored by the service in
        the message DB; nothing displayed them before. list_messages() is
        client-safe (it unpacks via LXMF, no message_router), so we read the
        gateway conversation and render replies we haven't shown yet (text +
        optional image, e.g. the map JPEG)."""
        if not self.sideband or not self._gateway_hash:
            return
        try:
            import LXMF
            gw = bytes.fromhex(self._gateway_hash)
        except Exception:
            return
        try:
            msgs = self.sideband.list_messages(gw, limit=25)
        except Exception:
            return
        for m in msgs or []:
            try:
                if m.get("source") != gw:
                    continue  # only inbound replies from the gateway
                h = m.get("hash")
                key = h.hex() if isinstance(h, (bytes, bytearray)) else str(h)
                if key in self._shown_msgs:
                    continue
                self._shown_msgs.add(key)
                content = m.get("content")
                text = (content.decode("utf-8", "replace")
                        if isinstance(content, (bytes, bytearray)) else (content or ""))
                image_bytes, image_ext = None, "png"
                fields = getattr(m.get("lxm"), "fields", None) or {}
                img = fields.get(LXMF.FIELD_IMAGE)
                if img and isinstance(img, (list, tuple)) and len(img) >= 2:
                    t, data = img[0], img[1]
                    image_ext = (t.decode() if isinstance(t, (bytes, bytearray)) else str(t)) or "png"
                    image_bytes = data
                self._conv_screen.add_result(text, image_bytes=image_bytes, image_ext=image_ext)
            except Exception:
                continue

    def _poll_peer_messages(self):
        """Render the active peer conversation (both directions) in the messenger.

        list_messages() is client-safe and returns oldest→newest; we dedupe by
        message hash so polling re-adds nothing. A message whose source is the
        peer is inbound; anything else (our own address) is outbound."""
        if not self.sideband or not self._active_peer_hash:
            return
        try:
            peer = bytes.fromhex(self._active_peer_hash)
        except Exception:
            return
        try:
            msgs = self.sideband.list_messages(peer, limit=50)
        except Exception:
            return
        for m in msgs or []:
            try:
                h = m.get("hash")
                key = h.hex() if isinstance(h, (bytes, bytearray)) else str(h)
                if key in self._shown_peer_msgs:
                    continue
                self._shown_peer_msgs.add(key)
                content = m.get("content")
                text = (content.decode("utf-8", "replace")
                        if isinstance(content, (bytes, bytearray)) else (content or ""))
                outbound = m.get("source") != peer
                self._peer_screen.add_message(text, outbound)
            except Exception:
                continue

    @staticmethod
    def _time_ago(epoch) -> str:
        try:
            import time
            secs = max(0, int(time.time() - float(epoch)))
        except Exception:
            return ""
        if secs < 60:
            return f"{secs}s ago"
        if secs < 3600:
            return f"{secs // 60}m ago"
        if secs < 86400:
            return f"{secs // 3600}h ago"
        return f"{secs // 86400}d ago"

    def list_announces_safe(self):
        """Recent announces read directly from the shared Sideband DB.

        core.list_announces() resolves stamp costs via message_router, which only
        exists in the SERVICE process — on the UI client it raises per-entry and
        silently skips lxmf.delivery (peer) announces. We read the announce table
        read-only instead, deriving the display name from app_data via LXMF.
        Returns newest-first list of {dest_hex, name, type, time}.
        """
        out = []
        if not self.sideband:
            return out
        db_path = getattr(self.sideband, "db_path", None)
        if not db_path or not os.path.isfile(db_path):
            return out
        try:
            import sqlite3
            import LXMF
            con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5.0)
            try:
                rows = con.execute(
                    "select source, data, dest_type, received "
                    "from announce order by received desc"
                ).fetchall()
            finally:
                con.close()
        except Exception:
            return out
        seen = set()
        for source, data, dest_type, received in rows:
            try:
                dest_hex = source.hex() if isinstance(source, (bytes, bytearray)) else str(source)
                if dest_hex in seen:
                    continue
                seen.add(dest_hex)
                dt = dest_type.decode() if isinstance(dest_type, (bytes, bytearray)) else str(dest_type)
                try:
                    if dt == "lxmf.delivery":
                        name = LXMF.display_name_from_app_data(data)
                    else:
                        name = LXMF.pn_name_from_app_data(data)
                except Exception:
                    name = None
                out.append({"dest_hex": dest_hex, "name": name or "", "type": dt, "time": received})
            except Exception:
                continue
        return out

    def _refresh_announces(self):
        """Populate the Stream tab from received announces (idempotent: the
        Stream dedupes by hash, so re-adding heard announces is a no-op)."""
        if not self.sideband:
            return
        for ann in self.list_announces_safe():
            if ann["type"] != "lxmf.delivery":
                continue  # only show peer (messaging) announces in the farm stream
            name = ann["name"] or "(unnamed device)"
            self._str_screen.add_announce(name, ann["dest_hex"], self._time_ago(ann["time"]))

    # ── Read-only diagnostics accessors (used by the Debug tab) ────────────────

    def local_address(self) -> str:
        """Local LXMF address as hex, or 'unavailable'.

        The client core (is_client) never builds lxmf_destination — that lives in
        the service. But the client DOES load the shared identity, so we derive
        the same LXMF delivery destination hash the service announces.
        """
        if not self.sideband:
            return "unavailable"
        try:
            dest = getattr(self.sideband, "lxmf_destination", None)
            if dest is not None:
                return dest.hexhash
            identity = getattr(self.sideband, "identity", None)
            if identity is not None:
                import RNS
                d = RNS.Destination(
                    identity, RNS.Destination.OUT, RNS.Destination.SINGLE,
                    "lxmf", "delivery",
                )
                return d.hexhash
        except Exception:
            pass
        return "unavailable"

    # Developer-only diagnostics (heartbeat_age, service_status_text,
    # interfaces_text, service_log_text, send_test_message) now live in
    # farmui/dev_diagnostics.py and back the optional Debug tab only.

    # ── Public actions (called by screens) ────────────────────────────────────

    def send_announce(self):
        # Trigger an announce via the `wants.announce` flag, which the service's
        # job loop consumes and turns into a real announce (the same path as the
        # startup auto-announce). We must NOT call lxmf_announce() directly: on
        # the Android client its else-branch dereferences message_router /
        # lxmf_destination (both None on a client) and raises *before* it would
        # set the flag — so the button silently did nothing.
        if not self.sideband:
            return
        try:
            self.sideband.setstate("wants.announce", True)
        except Exception:
            pass

    def _restore_gateway(self):
        """Re-pin the saved farm gateway from farmui settings, if one exists.

        Called once during build() after the screens are created. Reads only
        FarmSettings (app-private JSON); does not touch Sideband/RNS/LXMF.
        """
        try:
            saved_hash = self._settings.gateway_hash
            if not saved_hash:
                return
            saved_name = self._settings.gateway_display_name or "Navamesh Gateway"
            self.set_gateway(saved_name, saved_hash)
        except Exception:
            pass

    def set_gateway(self, display_name: str, short_hash: str):
        self._gateway_name = display_name
        self._gateway_hash = short_hash
        self._conv_screen.update_gateway(display_name, short_hash)
        # Persist the pin so it survives app close, relaunch, phone restart, and
        # stable-key in-place updates. Stored in farmui's own JSON settings only
        # (FarmSettings, app-private storage) — never touches Sideband/RNS state.
        # Switching gateways later (tapping a different row in Stream) calls this
        # again and overwrites the stored pin.
        try:
            self._settings.set_gateway(display_name, short_hash)
        except Exception:
            pass

    # ── Navigation / device routing (called by the Talk tab) ───────────────────

    def open_chat(self, display_name: str, dest_hex: str):
        """Route a tapped device to the right chat.

        Gateways open the predefined command dashboard (and pin the gateway);
        regular peers open a normal free-text messenger. The gateway-vs-peer
        decision lives here (via is_gateway_device), never in the Talk list.
        """
        is_gw = is_gateway_device(display_name, dest_hex)
        try:
            import RNS
            RNS.log(
                f"Navamesh: open_chat name={display_name!r} dest={dest_hex} "
                f"gateway={is_gw} -> {'gateway_chat' if is_gw else 'peer_chat'}",
                RNS.LOG_NOTICE,
            )
        except Exception:
            pass
        if is_gw:
            self._active_peer_hash = None
            self.set_gateway(display_name, dest_hex)
            self._conv_screen.reset_replies()
            self._goto_screen("gateway_chat")
        else:
            self.open_peer(display_name, dest_hex)

    def open_peer(self, display_name: str, dest_hex: str):
        """Open the free-text messenger for a peer and load its history."""
        self._active_peer_hash = dest_hex
        self._shown_peer_msgs = set()
        self._peer_screen.open_peer(display_name, dest_hex)
        self._goto_screen("peer_chat")
        # Fill history immediately rather than waiting for the next 2s poll.
        self._poll_peer_messages()

    def go_home(self):
        """Return from a chat screen to the two-tab home (Talk selected)."""
        self._active_peer_hash = None
        # Leaving a chat slides backward (opposite of entering one).
        self._goto_screen("home", direction="right")
        try:
            if self._talk_tab is not None:
                self._home_tabs.switch_to(self._talk_tab)
        except Exception:
            pass

    def _goto_screen(self, name: str, direction: str = "left"):
        """Switch screens. direction 'left' = forward (entering), 'right' = back."""
        sm = getattr(self, "_sm", None)
        if sm is not None:
            try:
                sm.transition.direction = direction
            except Exception:
                pass
            sm.current = name

    def send_peer_text(self, dest_hex: str, content: str):
        """Send a free-text LXMF message to a peer (reuses the dispatcher path)."""
        if not self.sideband or not self._dispatcher:
            return
        try:
            self._dispatcher.send_text(dest_hex, content)
        except Exception:
            pass
        # Reflect the sent message promptly (it's saved to the shared DB).
        self._poll_peer_messages()

    def dispatch_command(self, cmd_key: str, node_id: str | None = None, on_complete=None):
        wire = get_wire(cmd_key, node_id)
        if self.sideband and self._gateway_hash:
            threading.Thread(
                target=self._send_and_show,
                args=(self._gateway_hash, wire, on_complete),
                daemon=True,
            ).start()
        else:
            self._conv_screen.add_result(
                f"[Gateway not pinned or radio unavailable]\nWould send: {wire!r}"
            )
            if on_complete:
                Clock.schedule_once(lambda _: on_complete(), 0)

    def _send_and_show(self, dest_hash: str, content: str, on_complete=None):
        # Route through CoreDispatcher.send_text so the correct send_message
        # argument order (content, destination_hash, propagation) and hex→bytes
        # conversion are guaranteed — never call core.send_message directly here.
        try:
            reply = self._dispatcher.send_text(dest_hash, content)
            from .dispatch import FAILED
            if reply.state == FAILED:
                Clock.schedule_once(
                    lambda _: self._conv_screen.add_result(f"Send failed: {reply.error}"), 0
                )
        except Exception as exc:
            Clock.schedule_once(
                lambda _: self._conv_screen.add_result(f"Send failed: {exc}"), 0
            )
        finally:
            if on_complete:
                Clock.schedule_once(lambda _: on_complete(), 0)

    def open_node_picker(self, cmd, on_complete=None):
        if self._node_cache:
            node_id = self._node_cache[0]
            self.dispatch_command(cmd.key, node_id, on_complete=on_complete)
        else:
            self._conv_screen.add_result(
                "No node list yet — tap 'List nodes' first, then try 'Map — one node'."
            )
            if on_complete:
                Clock.schedule_once(lambda _: on_complete(), 0)


def run():
    FarmApp().run()


if __name__ == "__main__":
    run()

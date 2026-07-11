"""
test_updater.py — wrapper-only over-the-air update client.

Pure-logic tests for farmui/updater.py (version compare, manifest polling,
download) plus source guards for the FarmApp wiring and the Talk-screen update
card. Android-only glue (PackageInstaller, jnius) is exercised only as source
guards — it cannot run off-device. No Sideband/RNS/LXMF involvement anywhere.
"""
from __future__ import annotations

import inspect
import json
import os
import tempfile

os.environ["KIVY_NO_ENV_CONFIG"] = "1"
os.environ["KIVY_WINDOW"] = "headless"
os.environ["DISPLAY"] = ""


# ── Version comparison ──────────────────────────────────────────────────────────

def test_parse_version():
    from sbapp.farmui.updater import parse_version
    assert parse_version("1.9.8") == (1, 9, 8)
    assert parse_version("1.9.10") == (1, 9, 10)
    assert parse_version("2.0") == (2, 0)
    assert parse_version("") == ()
    assert parse_version("garbage") == ()


def test_is_newer_strict():
    from sbapp.farmui.updater import is_newer
    assert is_newer("1.9.9", "1.9.8")
    assert is_newer("1.9.10", "1.9.9")     # numeric, not lexicographic
    assert is_newer("1.10.0", "1.9.99")
    assert not is_newer("1.9.8", "1.9.8")  # same → not newer
    assert not is_newer("1.9.7", "1.9.8")  # downgrade → never offered
    assert not is_newer("", "1.9.8")       # malformed remote → never offered
    assert not is_newer("junk", "1.9.8")


# ── check_for_update: manifest polling ──────────────────────────────────────────

def _fetcher(responses):
    """Map url → bytes | Exception; unlisted URLs raise (unreachable)."""
    def fetch(url, timeout):
        r = responses.get(url)
        if r is None:
            raise OSError(f"unreachable: {url}")
        if isinstance(r, Exception):
            raise r
        return r
    return fetch


def test_check_finds_newer_version():
    from sbapp.farmui.updater import check_for_update
    manifest = json.dumps({"version": "1.9.9", "apk": "farm-1.9.9.apk",
                           "notes": "fixes"}).encode()
    fetch = _fetcher({"http://pi:8080/version.json": manifest})
    info = check_for_update(["http://pi:8080"], "1.9.8", fetch=fetch)
    assert info == {"version": "1.9.9",
                    "apk_url": "http://pi:8080/farm-1.9.9.apk",
                    "notes": "fixes",
                    "base_url": "http://pi:8080"}


def test_check_ignores_same_or_older_version():
    from sbapp.farmui.updater import check_for_update
    same = json.dumps({"version": "1.9.8", "apk": "farm.apk"}).encode()
    fetch = _fetcher({"http://pi:8080/version.json": same})
    assert check_for_update(["http://pi:8080"], "1.9.8", fetch=fetch) is None


def test_check_skips_unreachable_hosts_and_uses_next():
    from sbapp.farmui.updater import check_for_update
    manifest = json.dumps({"version": "2.0.0", "apk": "farm.apk"}).encode()
    fetch = _fetcher({"http://backup:8080/version.json": manifest})
    info = check_for_update(["http://pi:8080", "http://backup:8080"],
                            "1.9.8", fetch=fetch)
    assert info is not None and info["base_url"] == "http://backup:8080"


def test_check_survives_malformed_manifest():
    from sbapp.farmui.updater import check_for_update
    fetch = _fetcher({"http://pi:8080/version.json": b"not json at all"})
    assert check_for_update(["http://pi:8080"], "1.9.8", fetch=fetch) is None


def test_check_requires_apk_field():
    from sbapp.farmui.updater import check_for_update
    manifest = json.dumps({"version": "9.9.9"}).encode()  # no "apk"
    fetch = _fetcher({"http://pi:8080/version.json": manifest})
    assert check_for_update(["http://pi:8080"], "1.9.8", fetch=fetch) is None


def test_check_empty_url_list_is_none():
    from sbapp.farmui.updater import check_for_update
    assert check_for_update([], "1.9.8", fetch=_fetcher({})) is None
    assert check_for_update(None, "1.9.8", fetch=_fetcher({})) is None


def test_download_apk_writes_file():
    from sbapp.farmui.updater import download_apk
    d = tempfile.mkdtemp()
    dest = os.path.join(d, "updates", "u.apk")
    fetch = _fetcher({"http://pi:8080/farm.apk": b"apk-bytes"})
    assert download_apk("http://pi:8080/farm.apk", dest, fetch=fetch) == dest
    with open(dest, "rb") as f:
        assert f.read() == b"apk-bytes"


# ── FarmSettings.update_urls ────────────────────────────────────────────────────

def test_update_urls_default_and_override():
    from sbapp.farmui.settings import FarmSettings
    from sbapp.farmui.updater import DEFAULT_UPDATE_URLS
    d = tempfile.mkdtemp()
    s = FarmSettings(d)
    assert s.update_urls == list(DEFAULT_UPDATE_URLS)   # built-in default
    s.update_urls = ["http://10.0.0.5:8080"]
    assert FarmSettings(d).update_urls == ["http://10.0.0.5:8080"]  # persisted
    s.update_urls = None                                 # reset → default again
    assert FarmSettings(d).update_urls == list(DEFAULT_UPDATE_URLS)


def test_default_update_url_matches_farm_subnet():
    """The baked default must sit on the HT-HD01 subnet the phones use."""
    from sbapp.farmui.updater import DEFAULT_UPDATE_URLS
    from sbapp.farmui.rns_config_writer import HTHD01_FORWARD_IP
    subnet = ".".join(HTHD01_FORWARD_IP.split(".")[:3])   # 192.168.100
    assert any(subnet in u for u in DEFAULT_UPDATE_URLS)


# ── FarmApp wiring + UI card (headless-safe source guards) ──────────────────────

def test_app_schedules_update_checks():
    from sbapp.farmui.app import FarmApp
    src = inspect.getsource(FarmApp._start_update_checker)
    assert "schedule_once" in src and "schedule_interval" in src
    backend = inspect.getsource(FarmApp._start_backend)
    assert "_start_update_checker" in backend
    # Checks and downloads must run off the UI thread.
    assert "threading.Thread" in inspect.getsource(FarmApp._update_check_tick)
    assert "threading.Thread" in inspect.getsource(FarmApp.apply_update)


def test_apply_update_handles_missing_install_permission():
    from sbapp.farmui.app import FarmApp
    src = inspect.getsource(FarmApp.apply_update)
    assert "can_request_installs" in src
    assert "open_install_permission_settings" in src


def test_stream_screen_has_update_card():
    from sbapp.farmui.screens.stream import StreamScreen
    for method in ("show_update", "set_update_status", "hide_update"):
        assert hasattr(StreamScreen, method)
    src = inspect.getsource(StreamScreen.show_update)
    assert "tap to install" in src


def test_installer_uses_package_installer_session():
    """Install path must be the PackageInstaller session API (no FileProvider)."""
    from sbapp.farmui import updater
    src = inspect.getsource(updater.install_apk)
    assert "PackageInstaller" in src
    assert "createSession" in src and "commit" in src


def test_installer_handles_pending_user_action():
    """The session callback MUST launch the system confirm dialog, or nothing
    ever appears (STATUS_PENDING_USER_ACTION carries the intent to start)."""
    from sbapp.farmui import updater
    src = inspect.getsource(updater._on_new_intent)
    assert "STATUS_PENDING_USER_ACTION" in src
    assert "startActivity" in src
    # install_apk must arm the handler before committing the session, and the
    # app must ALSO bind it on the main thread (jnius proxies cannot be
    # created on worker threads — ClassNotFoundException).
    install = inspect.getsource(updater.install_apk)
    assert "ensure_intent_binding" in install
    from sbapp.farmui.app import FarmApp as _FA
    assert "ensure_intent_binding" in inspect.getsource(_FA._start_update_checker)
    # And the app resets the card when the farmer cancels the dialog.
    from sbapp.farmui.app import FarmApp
    assert hasattr(FarmApp, "_on_install_status")
    worker = inspect.getsource(FarmApp._apply_update_worker)
    assert "on_status" in worker


def test_manifest_permission_declared():
    """REQUEST_INSTALL_PACKAGES must be in buildozer.spec for install_apk."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "sbapp", "buildozer.spec")) as f:
        spec = f.read()
    assert "REQUEST_INSTALL_PACKAGES" in spec

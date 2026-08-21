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


# ── Background download via DownloadManager ─────────────────────────────────────
#
# The transfer itself runs in an Android system process, so what is testable off
# device is the arithmetic, the status mapping, and the wiring that decides what
# the farmer sees. The jnius calls are covered as source guards, the same way the
# PackageInstaller glue above is.

def test_download_percent():
    from sbapp.farmui.updater import download_percent
    assert download_percent(0, 100) == 0
    assert download_percent(50, 100) == 50
    assert download_percent(95021308, 95021308) == 100
    # DownloadManager reports total = -1 until Content-Length arrives; a
    # percentage from that would render as "-0%" on the card.
    assert download_percent(1024, -1) is None
    assert download_percent(1024, 0) is None
    assert download_percent(None, None) is None
    assert download_percent("x", "y") is None
    # Never exceeds 100 even if the server lies about the total.
    assert download_percent(200, 100) == 100


def test_dm_status_mapping_covers_every_documented_status():
    """Android's five DownloadManager.STATUS_* values must all map to a state.

    An unmapped status would fall through to "unknown", which the app treats as
    a failure — silently discarding a download that was merely paused.
    """
    from sbapp.farmui.updater import _DM_STATUS
    assert _DM_STATUS[1] == "pending"
    assert _DM_STATUS[2] == "running"
    assert _DM_STATUS[4] == "paused"
    assert _DM_STATUS[8] == "success"
    assert _DM_STATUS[16] == "failed"


def test_uri_to_path():
    from sbapp.farmui.updater import _uri_to_path
    assert _uri_to_path("file:///storage/emulated/0/x/navamesh_update.apk") == \
        "/storage/emulated/0/x/navamesh_update.apk"
    # Percent-encoding is real: external files dirs contain the package name.
    assert _uri_to_path("file:///a/My%20Files/u.apk") == "/a/My Files/u.apk"
    assert _uri_to_path("content://downloads/42") is None
    assert _uri_to_path("") is None
    assert _uri_to_path(None) is None


def test_download_state_is_safe_off_android():
    """Off-device there is no DownloadManager; this must not raise."""
    from sbapp.farmui.updater import download_state, downloads_available
    assert downloads_available() is False
    state = download_state(1234)
    assert state["state"] == "unknown"
    assert state["path"] is None


def test_cancel_background_download_is_safe_off_android():
    from sbapp.farmui.updater import cancel_background_download
    cancel_background_download(1234)   # must not raise
    cancel_background_download(None)


def test_enqueue_restricts_to_wifi_and_survives_sleep():
    """Source guards on the DownloadManager request.

    Each of these is load-bearing for "downloads while the phone is asleep":
    Wi-Fi-only makes it wait for Wi-Fi instead of failing on cellular (the update
    host only exists on the farm LAN), and requiring neither idle nor charging
    keeps it from parking on a farmer's phone that is neither.
    """
    import inspect
    from sbapp.farmui import updater
    src = inspect.getsource(updater.enqueue_background_download)
    assert "NETWORK_WIFI" in src
    assert "setAllowedOverRoaming" in src
    assert "setRequiresDeviceIdle" in src
    assert "setRequiresCharging" in src
    # Progress in the notification shade is the only feedback once pocketed.
    assert "VISIBILITY_VISIBLE_NOTIFY_COMPLETED" in src
    # App-private external dir: no storage permission, readable by us.
    assert "setDestinationInExternalFilesDir" in src


def test_purge_previous_apk_is_called_before_enqueue():
    """DownloadManager silently renames rather than overwriting.

    Without the purge, every update leaves another ~91 MB behind and the file
    name drifts to navamesh_update-1.apk, -2.apk, ...
    """
    import inspect
    from sbapp.farmui import updater
    src = inspect.getsource(updater.enqueue_background_download)
    assert src.index("_purge_previous_apk") < src.index("setDestinationInExternalFilesDir")


# ── FarmApp wiring ──────────────────────────────────────────────────────────────

def test_app_prefers_downloadmanager_and_falls_back():
    import inspect
    from sbapp.farmui.app import FarmApp
    src = inspect.getsource(FarmApp.apply_update)
    assert "downloads_available" in src
    assert "enqueue_background_download" in src
    # The reassurance that makes the feature worth having.
    assert "lock the phone" in src
    # Desktop / refused-enqueue path must still work.
    assert "_apply_update_worker" in src


def test_app_persists_download_id_for_restart():
    """The id must be persisted, not held in memory.

    A download that finishes while the app is closed is the whole point; if the
    id only lived on the instance, the farmer would refetch 91 MB.
    """
    import inspect
    from sbapp.farmui.app import FarmApp
    assert "pending_download" in inspect.getsource(FarmApp.apply_update)
    assert "pending_download" in inspect.getsource(FarmApp._resume_pending_download)
    src = inspect.getsource(FarmApp._start_update_checker)
    assert "_resume_pending_download" in src


def test_resume_handles_completed_download_while_closed():
    import inspect
    from sbapp.farmui.app import FarmApp
    src = inspect.getsource(FarmApp._resume_pending_download)
    # In-flight → keep watching; finished → install; anything else → clear.
    for expected in ('"pending", "running", "paused"', '"success"',
                     "_clear_pending_download"):
        assert expected in src, expected


def test_paused_download_explains_itself():
    """A Wi-Fi-only download parks as PAUSED off Wi-Fi; say so, don't look stuck."""
    import inspect
    from sbapp.farmui.app import FarmApp
    src = inspect.getsource(FarmApp._download_poll_tick)
    assert "paused" in src
    assert "Wi-Fi" in src


def test_finish_download_verifies_file_exists():
    """COLUMN_LOCAL_URI can point at a file the user cleared from the shade."""
    import inspect
    from sbapp.farmui.app import FarmApp
    src = inspect.getsource(FarmApp._finish_download)
    assert "os.path.exists" in src
    assert "install_apk" in src


# ── FarmSettings.pending_download ───────────────────────────────────────────────

def test_pending_download_roundtrip_and_rejects_junk():
    from sbapp.farmui.settings import FarmSettings
    with tempfile.TemporaryDirectory() as d:
        s = FarmSettings(d)
        assert s.pending_download is None

        s.pending_download = {"id": 42, "version": "1.9.12"}
        assert s.pending_download == {"id": 42, "version": "1.9.12"}

        # Survives a reload — the case that matters (app was killed).
        assert FarmSettings(d).pending_download == {"id": 42, "version": "1.9.12"}

        s.pending_download = None
        assert s.pending_download is None
        assert FarmSettings(d).pending_download is None


def test_pending_download_tolerates_corrupt_state():
    """A hand-edited or truncated settings file must not crash startup."""
    from sbapp.farmui.settings import FarmSettings
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "farmui_settings.json")
        for junk in ('{"pending_download": "nonsense"}',
                     '{"pending_download": {"version": "1.9.12"}}',
                     '{"pending_download": {"id": "not-an-int"}}',
                     '{"pending_download": []}'):
            with open(path, "w") as f:
                f.write(junk)
            assert FarmSettings(d).pending_download is None, junk


def test_download_state_avoids_varargs_setfilterbyid():
    """Regression: setFilterById(long...) is a jnius binding we cannot verify
    off-device, and on-device it threw — turning a hard failure into "unknown"
    and hiding the real cause (cleartext blocked). We scan and match COLUMN_ID.
    """
    import inspect
    from sbapp.farmui import updater
    src = inspect.getsource(updater.download_state)
    # Comments deliberately mention setFilterById to explain the choice, so
    # assert against code only.
    code = "\n".join(l for l in src.splitlines()
                     if not l.lstrip().startswith("#"))
    assert ".setFilterById(" not in code
    assert "COLUMN_ID" in code
    # Failures must be logged, never silently swallowed.
    assert "_log(" in code


def test_download_state_distinguishes_gone_from_unknown():
    """"gone" (row pruned/cleared) and "unknown" (we failed to read) are
    different problems: one is routine, the other is a bug worth logging."""
    import inspect
    from sbapp.farmui import updater
    src = inspect.getsource(updater.download_state)
    assert '"gone"' in src
    assert "not found" in src or "if not found" in src


def test_cleartext_traffic_is_patched_into_manifest_template():
    """DownloadManager refuses http:// without usesCleartextTraffic.

    urllib never needed it (Python sockets bypass Android's network-security
    policy entirely), which is why the gap survived until the download moved
    into Android's own stack.

    Asserted against build_apk.sh rather than buildozer.spec on purpose:
    buildozer 1.5.0's android.extra_manifest_application_arguments is broken --
    it shell-escapes the value but passes argv as a list, so the attribute lands
    in the manifest as  "android:usesCleartextTraffic=\\"true\\" "  , quotes
    included, and aapt2 rejects it. We patch p4a's template instead.
    """
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script = open(os.path.join(root, "scripts", "build_apk.sh")).read()
    assert "usesCleartextTraffic" in script
    assert "AndroidManifest.tmpl.xml" in script
    # Must fail loudly rather than silently shipping a build that cannot download.
    assert "no p4a manifest template patched" in script
    # The broken buildozer route must not come back.
    spec = open(os.path.join(root, "sbapp", "buildozer.spec")).read()
    assert "extra_manifest_application_arguments" not in spec

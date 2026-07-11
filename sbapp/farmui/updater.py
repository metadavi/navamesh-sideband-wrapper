"""
updater.py — wrapper-only over-the-air update client.

The Pi gateway (or any HTTP host) serves a folder containing the released APK
and a small version.json:

    {"version": "1.9.9", "apk": "navameshfarm-1.9.9-arm64-v8a-debug.apk",
     "notes": "optional one-line description"}

The app polls <base_url>/version.json (FarmSettings.update_urls, first
reachable wins), compares against the installed versionName, and — when a
newer build is available — surfaces an "Update available" card. Tapping it
downloads the APK and hands it to Android's PackageInstaller, which shows the
standard system "Update app?" confirmation. Because every release is signed
with the repo's committed keystore, the update installs over the top and all
identities/messages/settings survive.

Pure wrapper code: no Sideband/RNS/LXMF involvement anywhere. All network I/O
is plain HTTP GET against the farmer-side LAN (or any URL the operator adds);
callers run it off the UI thread.
"""
from __future__ import annotations

import json
import os
import urllib.request

# Convention baked at ship time: the farm Pi gets this static IP on the
# HT-HD01 subnet (the phones already live on 192.168.100.x — their RNS UDP
# interface broadcasts to 192.168.100.255). Overridable per phone via the
# update_urls list in farmui_settings.json.
DEFAULT_UPDATE_URLS = ["http://192.168.100.10:8080"]

# Short timeouts: the check runs periodically in the background and must fail
# fast when the phone is off-farm / the Pi is down.
CHECK_TIMEOUT = 6.0
DOWNLOAD_TIMEOUT = 60.0


def parse_version(version: str) -> tuple:
    """Dotted version string → comparable int tuple ("1.9.10" → (1, 9, 10)).

    Non-numeric segments are ignored; an unparsable string sorts lowest so a
    malformed remote version can never look "newer" than the installed one.
    """
    parts = []
    for seg in str(version or "").strip().split("."):
        seg = seg.strip()
        if seg.isdigit():
            parts.append(int(seg))
        else:
            break
    return tuple(parts)


def is_newer(remote: str, installed: str) -> bool:
    """True only when the remote version is strictly newer than installed."""
    r, i = parse_version(remote), parse_version(installed)
    if not r:
        return False
    return r > i


def _http_get(url: str, timeout: float):
    """Tiny fetch wrapper (separated so tests can stub it)."""
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read()


def check_for_update(urls, installed_version: str, fetch=_http_get):
    """Poll each base URL's version.json; return update info or None.

    Returns {"version", "apk_url", "notes", "base_url"} for the first
    reachable host that advertises a strictly newer version. Unreachable
    hosts and malformed manifests are skipped silently — the check must
    never disturb the app.
    """
    for base in urls or []:
        base = str(base).rstrip("/")
        try:
            raw = fetch(f"{base}/version.json", CHECK_TIMEOUT)
            info = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
            remote = str(info.get("version", ""))
            apk = str(info.get("apk", ""))
            if not apk or not is_newer(remote, installed_version):
                continue
            return {
                "version": remote,
                "apk_url": f"{base}/{apk.lstrip('/')}",
                "notes": str(info.get("notes", "")),
                "base_url": base,
            }
        except Exception:
            continue
    return None


def download_apk(apk_url: str, dest_path: str, fetch=None) -> str:
    """Download the APK to dest_path (streamed); returns dest_path.

    Any failure raises — the caller shows a friendly retry message.
    """
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    if fetch is not None:  # test seam
        data = fetch(apk_url, DOWNLOAD_TIMEOUT)
        with open(dest_path, "wb") as f:
            f.write(data)
        return dest_path
    with urllib.request.urlopen(apk_url, timeout=DOWNLOAD_TIMEOUT) as resp:
        with open(dest_path, "wb") as f:
            while True:
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
    return dest_path


# ── Android-only glue (jnius) ────────────────────────────────────────────────

def installed_version(default: str = "0.0.0") -> str:
    """The installed APK's versionName (Android), or `default` on desktop."""
    try:
        from jnius import autoclass
        mActivity = autoclass("org.kivy.android.PythonActivity").mActivity
        ctx = mActivity.getApplicationContext()
        pm = ctx.getPackageManager()
        return str(pm.getPackageInfo(ctx.getPackageName(), 0).versionName)
    except Exception:
        return default


def can_request_installs() -> bool:
    """True when the app already holds the 'install unknown apps' toggle."""
    try:
        from jnius import autoclass
        mActivity = autoclass("org.kivy.android.PythonActivity").mActivity
        pm = mActivity.getApplicationContext().getPackageManager()
        return bool(pm.canRequestPackageInstalls())
    except Exception:
        return False


def open_install_permission_settings():
    """Send the farmer to the one-time 'allow updates from this app' screen."""
    try:
        from jnius import autoclass
        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")
        Settings = autoclass("android.provider.Settings")
        mActivity = autoclass("org.kivy.android.PythonActivity").mActivity
        intent = Intent(
            Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
            Uri.parse(f"package:{mActivity.getPackageName()}"),
        )
        mActivity.startActivity(intent)
    except Exception:
        pass


# PackageInstaller reports install progress by re-delivering our PendingIntent
# to PythonActivity with status extras. The crucial one is
# STATUS_PENDING_USER_ACTION: it carries the system's "Update this app?"
# confirmation intent, which WE must start — nothing appears otherwise.
_status_cb = None
_intent_bound = False


def _on_new_intent(intent):
    """PythonActivity.onNewIntent hook: drive the PackageInstaller handshake."""
    global _status_cb
    try:
        from jnius import autoclass, cast
        PI = autoclass("android.content.pm.PackageInstaller")
        status = intent.getIntExtra("android.content.pm.extra.STATUS", -999)
        if status == -999:
            return  # unrelated intent (normal app launches land here)
        if status == PI.STATUS_PENDING_USER_ACTION:
            confirm = intent.getParcelableExtra("android.intent.extra.INTENT")
            confirm = cast("android.content.Intent", confirm)
            Intent = autoclass("android.content.Intent")
            confirm.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            mActivity = autoclass("org.kivy.android.PythonActivity").mActivity
            mActivity.startActivity(confirm)
            return
        cb = _status_cb
        if cb is not None:
            cb(int(status))  # STATUS_SUCCESS == 0; anything else = failed/cancelled
    except Exception:
        pass


def ensure_intent_binding():
    """Bind the onNewIntent hook once per process (p4a android.activity).

    MUST be called from the main/UI thread: activity.bind creates a
    PythonJavaClass proxy, and constructing one on a worker thread fails with
    ClassNotFoundException: org.jnius.NativeInvocationHandler (the worker's
    class loader can't see jnius' Java side). FarmApp calls this when it
    starts the update checker; install_apk re-asserts it as a safety net.
    """
    global _intent_bound
    if _intent_bound:
        return
    from android import activity  # p4a runtime module (Android only)
    activity.bind(on_new_intent=_on_new_intent)
    _intent_bound = True


def install_apk(apk_path: str, on_status=None):
    """Hand a downloaded APK to Android's PackageInstaller (session API).

    Streams the file into an install session and commits it. The system then
    calls back with STATUS_PENDING_USER_ACTION (handled above — it launches
    the standard "Update this app?" confirmation), and finally with the
    outcome, forwarded to `on_status` (0 = success; nonzero = cancelled or
    failed). No FileProvider/manifest surgery needed. Requires the
    REQUEST_INSTALL_PACKAGES permission (declared in buildozer.spec) and the
    one-time per-app "install unknown apps" toggle (see can_request_installs).
    """
    global _status_cb
    from jnius import autoclass, cast

    _status_cb = on_status
    ensure_intent_binding()

    mActivity = autoclass("org.kivy.android.PythonActivity").mActivity
    ctx = mActivity.getApplicationContext()
    installer = ctx.getPackageManager().getPackageInstaller()

    SessionParams = autoclass("android.content.pm.PackageInstaller$SessionParams")
    params = SessionParams(SessionParams.MODE_FULL_INSTALL)
    session_id = installer.createSession(params)
    session = installer.openSession(session_id)

    size = os.path.getsize(apk_path)
    out = session.openWrite("navamesh_update.apk", 0, size)
    try:
        with open(apk_path, "rb") as f:
            while True:
                chunk = f.read(256 * 1024)
                if not chunk:
                    break
                out.write(chunk)
        session.fsync(out)
    finally:
        out.close()

    # The commit callback returns to our own activity; the system installer UI
    # takes over in between.
    Intent = autoclass("android.content.Intent")
    PendingIntent = autoclass("android.app.PendingIntent")
    intent = Intent(mActivity, mActivity.getClass())
    flags = PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_MUTABLE
    pending = PendingIntent.getActivity(mActivity, 0, intent, flags)
    session.commit(pending.getIntentSender())
    session.close()

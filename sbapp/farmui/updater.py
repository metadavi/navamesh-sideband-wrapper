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
# Port 8090 (not 8080): the Pi's farm Docker stack already serves map tiles on
# 8080 (the navamesh_tiles nginx container), so the OTA update server runs on
# 8090 to avoid the conflict.
DEFAULT_UPDATE_URLS = ["http://192.168.100.10:8090"]

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


# ── Background download via Android DownloadManager ──────────────────────────
#
# Why not just urllib on a worker thread (what download_apk above does): the APK
# is ~91 MB and takes minutes over the HaLow mesh, and a farmer is not going to
# stand there holding the screen awake. Once the screen sleeps, a plain worker
# thread loses on every front at once -- the CPU suspends it, Doze cuts the
# app's network, the Wi-Fi radio powers down, and because nothing here resumes,
# the next attempt restarts from byte 0. Field-observed: awake it finishes in a
# couple of minutes, asleep it never finishes at all.
#
# DownloadManager is the system service built for exactly this. The transfer runs
# in a system process, so it survives screen-off, Doze, and this app being killed
# outright; it retries across network drops on its own, and it shows the farmer
# real progress in the notification shade for free.
#
# The download id is the only thing we have to keep. It outlives our process, so
# FarmApp persists it (see FarmSettings.pending_download) and re-attaches to a
# download still in flight -- or one that finished while the app was closed -- the
# next time it starts.

DOWNLOAD_FILENAME = "navamesh_update.apk"

# DownloadManager.STATUS_* — mirrored here so the state mapping stays testable
# off-device (these are frozen platform constants, not values we choose).
_DM_STATUS = {
    1: "pending",
    2: "running",
    4: "paused",
    8: "success",
    16: "failed",
}


def _log(message: str):
    """Best-effort log. Silence here is what made the first failure unreadable."""
    try:
        import RNS
        RNS.log(f"Navamesh updater: {message}", RNS.LOG_ERROR)
    except Exception:
        pass


def _download_manager():
    """(DownloadManager service, DownloadManager class, app Context). Android only."""
    from jnius import autoclass, cast
    Context = autoclass("android.content.Context")
    DownloadManager = autoclass("android.app.DownloadManager")
    mActivity = autoclass("org.kivy.android.PythonActivity").mActivity
    ctx = mActivity.getApplicationContext()
    service = cast("android.app.DownloadManager",
                   ctx.getSystemService(Context.DOWNLOAD_SERVICE))
    return service, DownloadManager, ctx


def downloads_available() -> bool:
    """True when the DownloadManager path can be used (i.e. we are on Android)."""
    try:
        _download_manager()
        return True
    except Exception:
        return False


def _purge_previous_apk(ctx) -> None:
    """Delete a previously downloaded APK before enqueuing a new one.

    DownloadManager does not overwrite: handed a destination that already
    exists it silently writes navamesh_update-1.apk instead, so without this
    every update would leave another ~91 MB behind and the names would drift
    away from DOWNLOAD_FILENAME. (We still read the real path back out of
    COLUMN_LOCAL_URI rather than trusting the name.)
    """
    try:
        import os as _os
        d = ctx.getExternalFilesDir(None)
        if d is None:
            return
        base = d.getAbsolutePath()
        for name in _os.listdir(base):
            if name.startswith("navamesh_update") and name.endswith(".apk"):
                try:
                    _os.remove(_os.path.join(base, name))
                except OSError:
                    pass
    except Exception:
        pass


def enqueue_background_download(apk_url: str, version: str = "") -> int:
    """Hand `apk_url` to DownloadManager; return the download id.

    Raises on failure so the caller can fall back to the in-process download.

    Restricted to Wi-Fi on purpose: the update host only ever exists on the farm
    LAN/mesh, so a cellular attempt could not reach it anyway. Asking for Wi-Fi
    makes DownloadManager *wait* for Wi-Fi instead of failing, and removes any
    chance of a farmer paying for 91 MB of mobile data.
    """
    service, DownloadManager, ctx = _download_manager()
    from jnius import autoclass
    Uri = autoclass("android.net.Uri")
    Request = autoclass("android.app.DownloadManager$Request")

    _purge_previous_apk(ctx)

    req = Request(Uri.parse(apk_url))
    req.setTitle(f"Navamesh Farm update{f' v{version}' if version else ''}")
    req.setDescription("Downloading — you can lock the phone.")
    # Progress in the shade while it runs, and a tappable entry when it lands:
    # the farmer's only feedback once they pocket the phone.
    req.setNotificationVisibility(Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
    req.setAllowedNetworkTypes(Request.NETWORK_WIFI)
    req.setAllowedOverRoaming(False)
    # App-private external dir: readable by us with no storage permission, and
    # cleaned up by Android when the app is uninstalled.
    req.setDestinationInExternalFilesDir(ctx, None, DOWNLOAD_FILENAME)
    # Explicit: a farm phone is usually neither idle nor charging, and either
    # requirement would park the download indefinitely.
    for setter, value in (("setRequiresDeviceIdle", False),
                          ("setRequiresCharging", False)):
        try:
            getattr(req, setter)(value)
        except Exception:
            pass  # older/vendor Android without the setter — defaults are already False

    return int(service.enqueue(req))


def _uri_to_path(local_uri: str):
    """file:///a/b.apk → /a/b.apk. None for anything that is not a file URI."""
    if not local_uri:
        return None
    if local_uri.startswith("file://"):
        from urllib.parse import unquote
        return unquote(local_uri[len("file://"):])
    return None


def download_state(download_id: int) -> dict:
    """Current state of `download_id`.

    Always returns a dict with a "state" key, one of:
      pending | running | paused | success | failed | gone | unknown

    "gone" means DownloadManager has no such row — the user cleared it from the
    shade, or the system pruned it. "unknown" means we could not read the state
    at all, which is a bug on our side, so it is logged rather than swallowed:
    the first on-device run reported "unknown" for what was really a hard
    failure, and the silent except hid the cause.

    Also carries "downloaded"/"total"/"percent" (percent is None while the total
    is unknown, which DownloadManager reports as -1 early on), "path" on success,
    and "reason" on failure.
    """
    out = {"state": "unknown", "downloaded": 0, "total": 0,
           "percent": None, "path": None, "reason": None}
    try:
        service, DownloadManager, _ctx = _download_manager()
        from jnius import autoclass
        Query = autoclass("android.app.DownloadManager$Query")
        # Deliberately NOT Query().setFilterById(id): that is a Java long...
        # varargs method, and relying on jnius to map a Python list onto long[]
        # is the kind of binding that fails at runtime and only at runtime. The
        # download table holds a handful of rows, so scanning it and matching
        # COLUMN_ID ourselves is both cheaper to reason about and impossible to
        # get subtly wrong.
        cursor = service.query(Query())
    except Exception as exc:
        out["reason"] = f"query failed: {exc}"
        _log(f"download_state query failed: {exc}")
        return out

    try:
        want = int(download_id)
        idx_id = cursor.getColumnIndex(DownloadManager.COLUMN_ID)
        found = False
        while cursor.moveToNext():
            if int(cursor.getLong(idx_id)) != want:
                continue
            found = True
            status = cursor.getInt(
                cursor.getColumnIndex(DownloadManager.COLUMN_STATUS))
            out["state"] = _DM_STATUS.get(int(status), "unknown")
            if out["state"] == "unknown":
                _log(f"unmapped DownloadManager status {status}")
            out["downloaded"] = int(cursor.getLong(cursor.getColumnIndex(
                DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR)) or 0)
            out["total"] = int(cursor.getLong(cursor.getColumnIndex(
                DownloadManager.COLUMN_TOTAL_SIZE_BYTES)) or 0)
            out["percent"] = download_percent(out["downloaded"], out["total"])
            if out["state"] == "success":
                out["path"] = _uri_to_path(cursor.getString(
                    cursor.getColumnIndex(DownloadManager.COLUMN_LOCAL_URI)))
            elif out["state"] == "failed":
                out["reason"] = cursor.getInt(
                    cursor.getColumnIndex(DownloadManager.COLUMN_REASON))
                _log(f"download {want} failed, reason={out['reason']}")
            break
        if not found:
            out["state"] = "gone"
    except Exception as exc:
        out["reason"] = f"read failed: {exc}"
        _log(f"download_state read failed: {exc}")
    finally:
        try:
            cursor.close()
        except Exception:
            pass
    return out


def download_percent(downloaded, total):
    """0-100, or None when the total is not known yet.

    Split out from download_state so the arithmetic is testable off-device.
    DownloadManager reports total = -1 until the server's Content-Length lands,
    and a percentage computed from that would read as "-0%" on the card.
    """
    try:
        downloaded, total = int(downloaded or 0), int(total or 0)
    except (TypeError, ValueError):
        return None
    if total <= 0 or downloaded < 0:
        return None
    return max(0, min(100, int(downloaded * 100 / total)))


def cancel_background_download(download_id) -> None:
    """Remove a download (and its partial file). Safe to call on a stale id."""
    try:
        service, _DownloadManager, _ctx = _download_manager()
        service.remove(int(download_id))
    except Exception:
        pass

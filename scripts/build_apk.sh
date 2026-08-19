#!/usr/bin/env bash
# build_apk.sh — Build the Navamesh Farm debug APK in a Docker container.
#
# Uses a custom buildozer image (Python 3.12 + buildozer 1.5.0) built from
# Dockerfile.buildozer at the project root.  kivy/buildozer:latest ships
# Python 3.14 which breaks kivy 2.3.0's pre-Cythonized C extensions.
#
# IMPORTANT (macOS): Docker Desktop's bind mount (VirtioFS) throws
# "OSError: [Errno 35] Resource deadlock avoided" under python-for-android's
# file access — and even a plain `cp` off the bind mount fails the same way.
# So this script NEVER bind-mounts the source.  It uses `docker cp` (which
# streams through the Docker API, bypassing VirtioFS) to load the source into
# an ext4 Docker volume, runs the whole build on volumes, and `docker cp`s the
# finished APK back out.
#
# Usage:
#   bash scripts/build_apk.sh
#
# Output:
#   dist/navamesh-farm-<version>-arm64-v8a-debug.apk
#
# First build: ~30-60 min (SDK + NDK + p4a recipes download).
# Subsequent builds: ~5-10 min (cache warm).
#
# See docs/BUILD.md for the Linux-VM / CI alternative if Docker is unavailable.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SBAPP_DIR="$ROOT_DIR/sbapp"
RECIPES_DIR="$ROOT_DIR/recipes"
LIBS_DIR="$ROOT_DIR/libs"          # native libs referenced by recipes (e.g. able)
DIST_DIR="$ROOT_DIR/dist"
KEYSTORE_FILE="$ROOT_DIR/keystore/navamesh-debug.keystore"  # stable debug signer (committed)

IMAGE="navamesh-buildozer:py312"
CACHE_VOLUME="navamesh-buildozer-cache"   # SDK / NDK (global, ~/.buildozer)
BUILD_VOLUME="navamesh-build-dir"         # per-project build tree (.buildozer)
SRC_VOLUME="navamesh-src"                 # project source (loaded via docker cp)
ANDROID_VOLUME="navamesh-android-home"    # persistent ~/.android (holds debug.keystore)
HELPER="navamesh-src-helper"

cleanup() { docker rm -f "$HELPER" > /dev/null 2>&1 || true; }
trap cleanup EXIT

echo "=== Navamesh Farm APK build ==="
echo "Source: $SBAPP_DIR"
echo "Image:  $IMAGE  (Python 3.12 + buildozer 1.5.0)"
echo "Volumes: $SRC_VOLUME (source), $BUILD_VOLUME (build), $CACHE_VOLUME (SDK/NDK)"
echo ""

# Verify Docker is running
if ! docker info > /dev/null 2>&1; then
  echo "ERROR: Docker daemon is not running."
  echo "Start Docker Desktop and retry, or see docs/BUILD.md for alternatives."
  exit 1
fi

# Build custom image if not present (fast — just pip installs, ~2 min)
if ! docker image inspect "$IMAGE" > /dev/null 2>&1; then
  echo "--- Building custom buildozer image (Python 3.12) ---"
  docker build \
    --platform linux/amd64 \
    -f "$ROOT_DIR/Dockerfile.buildozer" \
    -t "$IMAGE" \
    "$ROOT_DIR"
  echo ""
fi

# Ensure volumes exist (created once; survive container restarts)
for V in "$CACHE_VOLUME" "$BUILD_VOLUME" "$SRC_VOLUME" "$ANDROID_VOLUME"; do
  docker volume inspect "$V" > /dev/null 2>&1 || docker volume create "$V"
done

mkdir -p "$DIST_DIR"

# --- Step 0: seed the stable debug keystore into the .android volume -----------
# Buildozer/p4a runs `buildozer android debug`, which has Gradle (AGP) sign the APK
# with the default Android debug key at <user.home>/.android/debug.keystore.
# CRITICAL: the container runs as root and the JVM derives user.home from
# /etc/passwd → "/root" (NOT $HOME=/home/user).  So AGP looks in /root/.android,
# and the build step below mounts this volume there (and at /home/user/.android too,
# for any $HOME-based tools).  Without intervention AGP auto-generates that keystore
# inside each --rm container — DIFFERENT every build — so Android refuses to install
# a new APK over an old one (signature mismatch), forcing an uninstall that wipes the
# device's Reticulum identity + pinned gateway.
#
# We commit ONE fixed debug keystore (keystore/navamesh-debug.keystore, the standard
# androiddebugkey/android credentials) and copy it onto a persistent volume so every
# build signs with the SAME key → APKs install as in-place updates and per-device app
# data survives.  Purely a signing/build concern; it does not touch Sideband, RNS,
# LXMF, or the per-install identity in app_storage.
if [ ! -f "$KEYSTORE_FILE" ]; then
  echo "ERROR: stable debug keystore not found at $KEYSTORE_FILE"
  echo "Generate it once with (any machine with a JDK / keytool):"
  echo "  keytool -genkeypair -v -keystore keystore/navamesh-debug.keystore \\"
  echo "    -alias androiddebugkey -keyalg RSA -keysize 2048 -validity 10000 \\"
  echo "    -storepass android -keypass android -dname 'CN=Android Debug,O=Android,C=US'"
  exit 1
fi
echo "--- Seeding stable debug keystore into '$ANDROID_VOLUME' (docker cp) ---"
cleanup
# The volume mounts at /home/user/.android, so that directory already exists and
# docker cp (streams through the Docker API, no VirtioFS) lands the file inside it.
docker create --name "$HELPER" -v "$ANDROID_VOLUME:/home/user/.android" "$IMAGE" > /dev/null
docker cp "$KEYSTORE_FILE" "$HELPER:/home/user/.android/debug.keystore"
docker rm "$HELPER" > /dev/null
echo "Seeded debug.keystore (stable signer)"
echo ""

# --- Step 1: load source into the src volume via docker cp ---------------------
# docker cp streams through the Docker API (no VirtioFS), so it sidesteps the
# macOS bind-mount EDEADLK bug.  Only sbapp/ + recipes/ are copied (not .venv).
echo "--- Loading source into '$SRC_VOLUME' (docker cp) ---"
cleanup
# Wipe the volume, then create a stopped helper that holds it.
docker run --rm -v "$SRC_VOLUME:/dst" --entrypoint bash "$IMAGE" \
  -c 'rm -rf /dst/* /dst/.[!.]* /dst/..?* 2>/dev/null; true'
docker create --name "$HELPER" -v "$SRC_VOLUME:/home/user/hostcwd" "$IMAGE" > /dev/null
docker cp "$SBAPP_DIR"   "$HELPER:/home/user/hostcwd/"
docker cp "$RECIPES_DIR" "$HELPER:/home/user/hostcwd/"
docker cp "$LIBS_DIR"    "$HELPER:/home/user/hostcwd/"
# Drop any stale build/output dirs that rode along inside sbapp/.
docker run --rm -v "$SRC_VOLUME:/dst" --entrypoint bash "$IMAGE" \
  -c 'rm -rf /dst/sbapp/.buildozer /dst/sbapp/bin 2>/dev/null; true'
docker rm "$HELPER" > /dev/null
echo ""

# --- Step 1.5: patch p4a TargetPythonRecipe for meson numpy compatibility ------
# Latest p4a numpy uses MesonRecipe which calls python_recipe.get_python_root().
# The vendored Python3Recipe (recipes/python3/) extends TargetPythonRecipe and
# has no get_python_root — it builds Python in-place (no make install) so
# _sysconfigdata lives in android-build/build/lib.linux-*/ not a standard prefix.
# This pre-step injects a get_python_root shim into p4a's TargetPythonRecipe if
# p4a is already cloned.  The Dockerfile wrapper handles the fresh-clone case.
echo "--- Patching p4a TargetPythonRecipe (get_python_root shim) ---"
docker run --rm \
  --platform linux/amd64 \
  -v "$BUILD_VOLUME:/home/user/hostcwd/sbapp/.buildozer" \
  --entrypoint python3 \
  "$IMAGE" /usr/local/bin/patch_p4a.py
echo ""

# --- Step 1.6: bootstrap pip for hostpython3 if missing -----------------------
# ensurepip only runs inside the hostpython3 recipe when build_configured=True
# (first configure).  On incremental builds hostpython3 is already cached and
# ensurepip is skipped; any recipe built for the first time in that session will
# fail with "No module named pip" when install_hostpython_prerequisites runs.
# This step mirrors what the recipe does: run ensurepip --root site_root if pip
# is not already importable from site_dir.
echo "--- Bootstrapping hostpython3 pip (if needed) ---"
docker run --rm \
  --platform linux/amd64 \
  -v "$BUILD_VOLUME:/home/user/hostcwd/sbapp/.buildozer" \
  --entrypoint sh \
  "$IMAGE" \
  -c '
PYTHON=/home/user/hostcwd/sbapp/.buildozer/android/platform/build-arm64-v8a/build/other_builds/hostpython3/desktop/hostpython3/native-build/python3
SITE_ROOT=/home/user/hostcwd/sbapp/.buildozer/android/platform/build-arm64-v8a/build/other_builds/hostpython3/desktop/hostpython3/native-build/root
SITE_DIR="$SITE_ROOT/usr/local/lib/python3.11/site-packages"
if [ ! -f "$PYTHON" ]; then
  echo "hostpython3 not yet built; skipping"
  exit 0
fi
if PYTHONPATH="$SITE_DIR" "$PYTHON" -c "import pip" 2>/dev/null; then
  echo "pip already present"
else
  echo "Running ensurepip for hostpython3..."
  HOME=/tmp "$PYTHON" -m ensurepip --root "$SITE_ROOT" -U
  echo "pip bootstrapped"
fi
# Install numpy to site_dir so CythonRecipes (e.g. pycodec2) can import it.
# get_recipe_env(arch) sets PYTHONPATH=site_dir, so packages in site_dir are
# found by setup.py without any extra env changes.
if PYTHONPATH="$SITE_DIR" "$PYTHON" -c "import numpy" 2>/dev/null; then
  echo "numpy already present in site_dir"
else
  echo "Installing numpy to site_dir for host Python 3.11..."
  PYTHONPATH="$SITE_DIR" "$PYTHON" -m pip install numpy --target "$SITE_DIR" -q
  echo "numpy installed"
fi
# pycodec2/setup.py also needs Cython importable on host Python 3.11.
if PYTHONPATH="$SITE_DIR" "$PYTHON" -c "import Cython" 2>/dev/null; then
  echo "Cython already present in site_dir"
else
  echo "Installing Cython to site_dir for host Python 3.11..."
  PYTHONPATH="$SITE_DIR" "$PYTHON" -m pip install Cython --target "$SITE_DIR" -q
  echo "Cython installed"
fi
'
echo ""

# --- Step 2.5: inject device_filter.xml into two persistent locations ---------
# p4a's build.py (bootstraps/common/build/build.py:338) uses a two-step pattern:
#   if src/res_initial exists → rmdir src/main/res; copytree res_initial → res
#   else                      → copytree res → res_initial   (first build only)
# So EVERY gradle invocation resets src/main/res from src/res_initial.
# We must inject device_filter.xml into BOTH:
#   1. src/res_initial  — used on every incremental build
#   2. _sdl_common bootstrap template — picked up on a fresh first build
#      (becomes src/res_initial on that first run)
_inject_bootstrap_device_filter() {
  docker run --rm \
    --platform linux/amd64 \
    -v "$SRC_VOLUME:/src" \
    -v "$BUILD_VOLUME:/home/user/hostcwd/sbapp/.buildozer" \
    --entrypoint sh \
    "$IMAGE" \
    -c '
# 1. _sdl_common bootstrap template (for fresh builds / first run)
TMPL="/home/user/hostcwd/sbapp/.buildozer/android/platform/python-for-android/pythonforandroid/bootstraps/_sdl_common/build/src/main/res"
if [ -d "$TMPL" ]; then
  mkdir -p "$TMPL/xml"
  cp /src/sbapp/patches/device_filter.xml "$TMPL/xml/device_filter.xml"
  echo "device_filter.xml -> _sdl_common bootstrap template"
else
  echo "Bootstrap not yet cloned; template injection skipped (retry will cover it)"
fi

# 2. src/res_initial in the dist (for incremental builds where res_initial exists)
RES_INIT="/home/user/hostcwd/sbapp/.buildozer/android/platform/build-arm64-v8a/dists/navameshfarm/src/res_initial"
if [ -d "$RES_INIT" ]; then
  mkdir -p "$RES_INIT/xml"
  cp /src/sbapp/patches/device_filter.xml "$RES_INIT/xml/device_filter.xml"
  echo "device_filter.xml -> src/res_initial"
else
  echo "src/res_initial not yet created; bootstrap template covers first build"
fi'
}

echo "--- Injecting device_filter.xml into res_initial + bootstrap template ---"
_inject_bootstrap_device_filter
echo ""

# --- Step 1.9: force the debug APK to be re-signed -----------------------------
# Gradle does NOT track the external debug.keystore as a task input, so on an
# incremental build it reuses the previously-signed APK and never re-signs with
# our stable key.  Remove the cached debug APK + packaging/signing intermediates
# so packageDebug re-runs and signs with the seeded keystore.  (Native libs, dex
# and merged resources are untouched, so this is a fast re-package, not a rebuild.)
echo "--- Clearing cached debug APK so it re-signs with the stable keystore ---"
docker run --rm \
  --platform linux/amd64 \
  -v "$BUILD_VOLUME:/home/user/hostcwd/sbapp/.buildozer" \
  --entrypoint sh "$IMAGE" -c '
B=/home/user/hostcwd/sbapp/.buildozer/android/platform/build-arm64-v8a/dists/navameshfarm/build
rm -rf "$B/outputs/apk" "$B/intermediates/apk" "$B/intermediates/signing_config_versions" 2>/dev/null
echo "cleared cached apk/signing outputs (if present)"'
echo ""

# --- Step 2: run the build entirely on volumes (no bind mount) -----------------
# On a first-ever build p4a is cloned during this step; the bootstrap template
# injection above was a no-op.  If gradle fails we inject into the now-present
# template and retry exactly once (all recipes are cached so the retry is fast).
echo "--- Building APK ---"
BUILD_STATUS=0
docker run --rm \
  --platform linux/amd64 \
  -v "$SRC_VOLUME:/home/user/hostcwd" \
  -v "$CACHE_VOLUME:/home/user/.buildozer" \
  -v "$BUILD_VOLUME:/home/user/hostcwd/sbapp/.buildozer" \
  -v "$ANDROID_VOLUME:/root/.android" \
  -v "$ANDROID_VOLUME:/home/user/.android" \
  -w /home/user/hostcwd/sbapp \
  "$IMAGE" \
  android debug || BUILD_STATUS=$?

if [ "$BUILD_STATUS" -ne 0 ]; then
  echo "--- First pass failed; injecting device_filter.xml into bootstrap template and retrying ---"
  _inject_bootstrap_device_filter
  echo ""
  echo "--- Building APK (retry) ---"
  docker run --rm \
    --platform linux/amd64 \
    -v "$SRC_VOLUME:/home/user/hostcwd" \
    -v "$CACHE_VOLUME:/home/user/.buildozer" \
    -v "$BUILD_VOLUME:/home/user/hostcwd/sbapp/.buildozer" \
    -v "$ANDROID_VOLUME:/root/.android" \
    -v "$ANDROID_VOLUME:/home/user/.android" \
    -w /home/user/hostcwd/sbapp \
    "$IMAGE" \
    android debug
fi

# --- Step 3: copy the finished APK back out via docker cp ---------------------
echo ""
echo "=== Build complete — copying APK to dist/ ==="
APK_IN_VOL=$(docker run --rm -v "$SRC_VOLUME:/v" --entrypoint bash "$IMAGE" \
  -c 'find /v/sbapp/bin -name "*.apk" 2>/dev/null | head -1')
if [ -z "$APK_IN_VOL" ]; then
  echo "ERROR: No APK found in sbapp/bin/ after build."
  exit 1
fi
APK_BASENAME=$(basename "$APK_IN_VOL")
APK_NAME=$(echo "$APK_BASENAME" | sed 's/^sideband/navamesh-farm/')
HELPER_PATH="/home/user/hostcwd/sbapp/bin/$APK_BASENAME"

docker create --name "$HELPER" -v "$SRC_VOLUME:/home/user/hostcwd" "$IMAGE" > /dev/null
docker cp "$HELPER:$HELPER_PATH" "$DIST_DIR/$APK_NAME"
docker rm "$HELPER" > /dev/null

echo "APK: $DIST_DIR/$APK_NAME"
ls -lh "$DIST_DIR/$APK_NAME"

# --- Step 4: verify no host-arch cryptography got bundled ----------------------
# A COLD build silently poisons the APK: `cryptography` is a transitive dep
# (lxst -> rns -> cryptography>=3.4.7), p4a's pip step runs under an x86_64
# hostpython3, so pip resolves the HOST wheel and p4a packages an x86_64
# _rust.abi3.so into an arm64 APK. The backend service dlopen()s it and dies
# before RNS initialises, while the UI process survives -- so the app looks
# perfectly healthy and the radio is completely dead. Warm-cache builds never
# pull the wheel, which is why this appears only after a prune.
#
# sbapp/blacklist.txt is supposed to keep it out. This gate proves it did.
# Checked here rather than trusted, because the failure is invisible on device
# without opening the Debug tab.
echo ""
echo "=== Verifying APK does not contain host-arch cryptography ==="
# NOTE: `set -e` is active, so this must not be a bare command -- a non-zero
# exit would abort the script before VERIFY_STATUS could be read.
VERIFY_STATUS=0
python3 - "$DIST_DIR/$APK_NAME" <<'PY' || VERIFY_STATUS=$?
import io, sys, tarfile, zipfile

apk = sys.argv[1]
member = "lib/arm64-v8a/libpybundle.so"
try:
    blob = zipfile.ZipFile(apk).read(member)
    names = tarfile.open(fileobj=io.BytesIO(blob)).getnames()
except Exception as exc:
    print(f"FAIL: could not read {member} from the APK: {type(exc).__name__}: {exc}")
    sys.exit(1)

# The site-packages live in libpybundle.so. Do NOT look in assets/private.tar --
# that holds app code only and has no RNS in it at all.
bundled = [n for n in names if "site-packages/cryptography" in n]
fallback = [n for n in names if "RNS/Cryptography" in n]

if bundled:
    print(f"FAIL: {len(bundled)} host-arch cryptography entries are bundled, e.g.:")
    for n in bundled[:3]:
        print(f"   {n}")
    print("\nThe backend service will die in dlopen() and the radio will be dead")
    print("while the UI still launches. Confirm on device via the Debug tab")
    print('(set "dev_mode": true in farmui_settings.json).')
    print("\nCheck that sbapp/buildozer.spec still has:")
    print("   android.blacklist_src = blacklist.txt")
    print("and that sbapp/blacklist.txt contains cryptography/* -- note it")
    print("REPLACES p4a's built-in blacklist, so p4a's defaults must be in it too.")
    sys.exit(1)

if not fallback:
    # This is a liveness check on the blacklist, not a check on current behaviour.
    # The pattern in sbapp/blacklist.txt is safe as written -- fnmatch is
    # case-sensitive, so "*/cryptography/*" cannot match RNS/Cryptography/.
    # But that file REPLACES p4a's built-in blacklist and has to be resynced
    # whenever p4a's defaults change, so it will get edited again. Broadening a
    # pattern (*crypto*, or adding a capital-C variant) would strip RNS's own
    # fallback and leave it with NO crypto provider -- which fails with the same
    # symptom as the bug above (UI launches, radio dead) for a different reason,
    # and would sail past the negative check. This catches that.
    print("FAIL: RNS/Cryptography/* is missing -- RNS has no crypto provider at all.")
    print("      A good build carries ~24 of these as the pure-python fallback.")
    print("      Most likely a pattern in sbapp/blacklist.txt was broadened and is")
    print("      now matching RNS/Cryptography/ as well. See the comment in that file.")
    sys.exit(1)

print(f"OK: no bundled cryptography; RNS pure-python fallback present "
      f"({len(fallback)} RNS/Cryptography entries).")
PY

if [ "$VERIFY_STATUS" -ne 0 ]; then
  # Rename so publish_update.sh cannot pick it up: that script globs
  # dist/navameshfarm-*-debug.apk and takes the newest match.
  mv "$DIST_DIR/$APK_NAME" "$DIST_DIR/$APK_NAME.BROKEN"
  echo ""
  echo "Quarantined the bad build as: $DIST_DIR/$APK_NAME.BROKEN"
  echo "(renamed so publish_update.sh cannot publish it)"
  exit 1
fi

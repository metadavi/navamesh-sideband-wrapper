#!/usr/bin/env bash
# publish_update.sh — push the newest built APK to the farm Pi's update server.
#
# Usage:
#   bash scripts/publish_update.sh pi@<pi-address> [remote-dir]
#
# Takes the newest APK in dist/, derives its version from the filename
# (navameshfarm-<version>-arm64-v8a-debug.apk), writes version.json, and
# copies both to the Pi's update folder (default /home/pi/navamesh-updates).
# The phones poll that folder and offer the update in-app.
#
# Build first: bash scripts/build_apk.sh
# See scripts/pi_update_server/README.md for the one-time Pi setup.

set -euo pipefail

REMOTE="${1:?usage: publish_update.sh pi@<pi-address> [remote-dir]}"
REMOTE_DIR="${2:-/home/pi/navamesh-updates}"

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APK="$(ls -t "$ROOT_DIR"/dist/navameshfarm-*-debug.apk 2>/dev/null | head -1 || true)"
if [ -z "$APK" ]; then
  echo "ERROR: no APK in dist/ — run: bash scripts/build_apk.sh" >&2
  exit 1
fi

BASENAME="$(basename "$APK")"
VERSION="$(echo "$BASENAME" | sed -E 's/^navameshfarm-([0-9.]+)-.*$/\1/')"
if [ -z "$VERSION" ] || [ "$VERSION" = "$BASENAME" ]; then
  echo "ERROR: could not parse version from $BASENAME" >&2
  exit 1
fi

NOTES="${NOTES:-}"
MANIFEST="$(mktemp)"
printf '{"version": "%s", "apk": "%s", "notes": "%s"}\n' \
  "$VERSION" "$BASENAME" "$NOTES" > "$MANIFEST"

echo "Publishing $BASENAME (version $VERSION) to $REMOTE:$REMOTE_DIR"
scp "$APK" "$REMOTE:$REMOTE_DIR/$BASENAME"
scp "$MANIFEST" "$REMOTE:$REMOTE_DIR/version.json"
rm -f "$MANIFEST"

echo "Done. Phones will offer the update on their next check (≤6h or app relaunch)."

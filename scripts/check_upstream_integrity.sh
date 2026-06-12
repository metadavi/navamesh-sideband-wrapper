#!/usr/bin/env bash
# check_upstream_integrity.sh — verify protected Sideband paths are byte-identical
# to the upstream-pin baseline and that rns/lxmf installed versions match the lock.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
LOCK="$ROOT/UPSTREAM.lock"
FAIL=0

_parse_lock_hash() {
  local key="$1"
  grep -E "^${key}[[:space:]]+=|^${key}=" "$LOCK" 2>/dev/null \
    | sed 's/.*=[[:space:]]*//' | head -1
}

echo "=== Navamesh Farm — Upstream Integrity Check ==="
echo "Lock: $LOCK"
echo ""

# ── Protected path tree hashes ──────────────────────────────────────────────
# Compare working tree + index against the upstream-pin COMMIT, not just HEAD.
# This catches both committed drift and uncommitted edits to protected paths.
echo "── Protected path tree hashes ──"

check_tree() {
  local key="$1" path="$2"
  local expected
  expected="$(_parse_lock_hash "$key")"
  if [ -z "$expected" ]; then
    echo "  SKIP  $path (no lock entry)"
    return
  fi
  # Check committed tree hash at upstream-pin
  pin_hash=$(git ls-tree upstream-pin "$path" 2>/dev/null | awk '{print $3}')
  # Check for uncommitted diff from upstream-pin in working tree
  wt_diff=$(git diff upstream-pin -- "$path" 2>/dev/null)
  if [ "$pin_hash" = "$expected" ] && [ -z "$wt_diff" ]; then
    echo "  OK    $path"
  elif [ "$pin_hash" != "$expected" ]; then
    echo "  FAIL  $path — tree drifted in commits (expected $expected got $pin_hash)"
    FAIL=1
  else
    echo "  FAIL  $path — uncommitted changes detected in working tree"
    FAIL=1
  fi
}

check_tree "sbapp/sideband"  "sbapp/sideband"
check_tree "sbapp/services"  "sbapp/services"
check_tree "sbapp/ui"        "sbapp/ui"
check_tree "sbapp/kivymd"    "sbapp/kivymd"
check_tree "sbapp/mapview"   "sbapp/mapview"
check_tree "sbapp/plyer"     "sbapp/plyer"
check_tree "sbapp/pmqtt"     "sbapp/pmqtt"
check_tree "sbapp/md"        "sbapp/md"
check_tree "sbapp/share"     "sbapp/share"
check_tree "sbapp/patches"   "sbapp/patches"
check_tree "libs"            "libs"
check_tree "recipes"         "recipes"

# ── main_upstream.py blob hash ───────────────────────────────────────────────
echo ""
echo "── main_upstream.py blob hash ──"
expected_mu="$(_parse_lock_hash "sbapp/main_upstream.py")"
if [ -f "$ROOT/sbapp/main_upstream.py" ]; then
  actual_mu=$(git hash-object "$ROOT/sbapp/main_upstream.py")
  if [ "$actual_mu" = "$expected_mu" ]; then
    echo "  OK    sbapp/main_upstream.py"
  else
    echo "  FAIL  sbapp/main_upstream.py — expected $expected_mu got $actual_mu"
    FAIL=1
  fi
else
  echo "  FAIL  sbapp/main_upstream.py — file missing"
  FAIL=1
fi

# ── pip version pins ─────────────────────────────────────────────────────────
echo ""
echo "── pip version pins ──"
VENV_PYTHON="${VENV_PYTHON:-$ROOT/.venv/bin/python}"
rns_req="$(_parse_lock_hash "rns")"
lxmf_req="$(_parse_lock_hash "lxmf")"

if [ -f "$VENV_PYTHON" ]; then
  rns_inst=$("$VENV_PYTHON" -c "import importlib.metadata; print(importlib.metadata.version('rns'))" 2>/dev/null || echo "MISSING")
  lxmf_inst=$("$VENV_PYTHON" -c "import importlib.metadata; print(importlib.metadata.version('lxmf'))" 2>/dev/null || echo "MISSING")
  if [ "$rns_inst" = "$rns_req" ]; then
    echo "  OK    rns==$rns_inst"
  else
    echo "  FAIL  rns — lock requires $rns_req, installed $rns_inst"
    FAIL=1
  fi
  if [ "$lxmf_inst" = "$lxmf_req" ]; then
    echo "  OK    lxmf==$lxmf_inst"
  else
    echo "  FAIL  lxmf — lock requires $lxmf_req, installed $lxmf_inst"
    FAIL=1
  fi
else
  echo "  SKIP  .venv not found at $VENV_PYTHON"
fi

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo "RESULT: PASS — all protected paths intact, pins verified"
  exit 0
else
  echo "RESULT: FAIL — integrity violations detected (see FAIL lines above)"
  exit 1
fi

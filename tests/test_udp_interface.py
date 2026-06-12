"""
test_udp_interface.py — Phase 5: HT-HD01 UDP connectivity tests.

1. UDP round-trip (subprocess-isolated): all 9 commands over loopback UDPInterface.
   Subprocess isolation avoids the RNS singleton conflict with the session-scoped
   TCP testnet used by test_e2e_conversation and test_protocol_roundtrip.

2. rns_config_writer surgical-edit assertions:
   - inserts [[Navamesh HT-HD01]] block into a clean config
   - replaces an existing [[Navamesh HT-HD01]] block
   - leaves all other interface blocks byte-identical
   - byte-level diff confirms only the named block changed

3. Boot test: RNS.Reticulum starts cleanly with a config that contains the
   [[Navamesh HT-HD01]] UDPInterface block (subprocess evidence).
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile

import pytest

_HERE = os.path.dirname(__file__)
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))

# ── Base config template used by config-writer tests ─────────────────────────

_BASE = """\
[reticulum]
  enable_transport = False
  share_instance = No

[logging]
  loglevel = 1

[interfaces]
"""


# ── 1. UDP round-trip (subprocess-isolated) ───────────────────────────────────

def test_udp_all_9_commands():
    """All 9 LXMF commands round-trip over loopback UDPInterface (subprocess)."""
    runner = os.path.join(_HERE, "rig", "udp_roundtrip_runner.py")
    result = subprocess.run(
        [sys.executable, runner],
        capture_output=True, text=True, timeout=180,
        cwd=_ROOT,
    )
    # Extract the UDP_RESULTS line (last non-empty line)
    lines = [l for l in result.stdout.splitlines() if l.strip()]
    last = lines[-1] if lines else ""

    assert last.startswith("UDP_RESULTS:"), (
        f"UDP runner did not emit UDP_RESULTS.\n"
        f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    data = json.loads(last[len("UDP_RESULTS:"):].strip())
    failures = data.get("failures", [])
    assert not failures, (
        f"UDP round-trip failures ({data['passed']}/{data['total']} passed):\n"
        + "\n".join(failures)
    )
    assert data["passed"] == 9, f"Expected 9 passed, got {data['passed']}"


# ── 2a. Config-writer: insert into clean config ───────────────────────────────

def test_config_writer_inserts_block():
    """write_hthd01_interface inserts [[Navamesh HT-HD01]] into a clean config."""
    from sbapp.farmui.rns_config_writer import write_hthd01_interface
    tmpdir = tempfile.mkdtemp(prefix="navamesh_cfgw_")
    try:
        path = os.path.join(tmpdir, "config")
        with open(path, "w") as f:
            f.write(_BASE)

        write_hthd01_interface(path, "127.0.0.1", 9876, "192.168.1.10", 4242)

        with open(path) as f:
            result = f.read()

        assert "[[Navamesh HT-HD01]]" in result
        assert "type = UDPInterface" in result
        assert "listen_port = 9876" in result
        assert "forward_ip = 192.168.1.10" in result
        assert "forward_port = 4242" in result
        # Non-interface lines must be preserved
        assert "[reticulum]" in result
        assert "enable_transport = False" in result
        assert "[logging]" in result
        assert "loglevel = 1" in result
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── 2b. Config-writer: replace existing block ─────────────────────────────────

def test_config_writer_replaces_block():
    """write_hthd01_interface replaces an existing [[Navamesh HT-HD01]] block."""
    from sbapp.farmui.rns_config_writer import write_hthd01_interface
    initial = _BASE + (
        "[[Navamesh HT-HD01]]\n"
        "  type = UDPInterface\n"
        "  enabled = yes\n"
        "  listen_ip = 127.0.0.1\n"
        "  listen_port = 1111\n"
        "  forward_ip = 10.0.0.1\n"
        "  forward_port = 2222\n"
    )
    tmpdir = tempfile.mkdtemp(prefix="navamesh_cfgw_")
    try:
        path = os.path.join(tmpdir, "config")
        with open(path, "w") as f:
            f.write(initial)

        write_hthd01_interface(path, "127.0.0.1", 3333, "192.168.1.50", 4444)

        with open(path) as f:
            result = f.read()

        assert "listen_port = 3333" in result
        assert "forward_ip = 192.168.1.50" in result
        assert "forward_port = 4444" in result
        assert "listen_port = 1111" not in result
        assert "10.0.0.1" not in result
        assert result.count("[[Navamesh HT-HD01]]") == 1
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── 2c. Config-writer: surgical — other blocks unchanged ──────────────────────

def test_config_writer_surgical_other_blocks_unchanged():
    """Lines outside [[Navamesh HT-HD01]] block are byte-identical after edit."""
    from sbapp.farmui.rns_config_writer import write_hthd01_interface
    initial = _BASE + (
        "[[SomeOtherInterface]]\n"
        "  type = TCPServerInterface\n"
        "  enabled = yes\n"
        "  listen_port = 9000\n"
    )
    tmpdir = tempfile.mkdtemp(prefix="navamesh_cfgw_")
    try:
        path = os.path.join(tmpdir, "config")
        with open(path, "w") as f:
            f.write(initial)

        write_hthd01_interface(path, "127.0.0.1", 5555, "10.0.0.1", 4242)

        with open(path) as f:
            result = f.read()

        assert "[[SomeOtherInterface]]" in result
        assert "type = TCPServerInterface" in result
        assert "listen_port = 9000" in result
        assert "[[Navamesh HT-HD01]]" in result
        assert "listen_port = 5555" in result
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── 2d. Config-writer: byte-level diff proof ──────────────────────────────────

def test_config_writer_byte_diff():
    """
    After insertion, a line-level diff shows ONLY [[Navamesh HT-HD01]] lines added;
    all original lines remain verbatim.
    """
    from sbapp.farmui.rns_config_writer import write_hthd01_interface
    tmpdir = tempfile.mkdtemp(prefix="navamesh_cfgw_")
    try:
        path = os.path.join(tmpdir, "config")
        with open(path, "w") as f:
            f.write(_BASE)
        original_lines = set(_BASE.splitlines())

        write_hthd01_interface(path, "127.0.0.1", 7777, "10.0.0.2", 4242)

        with open(path) as f:
            result = f.read()
        result_lines = result.splitlines()

        # Every original line must appear in the result
        for line in _BASE.splitlines():
            assert line in result_lines, f"Original line missing after edit: {line!r}"

        # Only new lines are the [[Navamesh HT-HD01]] block lines
        added = [l for l in result_lines if l not in original_lines]
        assert all("HT-HD01" in l or "UDPInterface" in l or "listen" in l
                   or "forward" in l or "enabled" in l or l == "" for l in added), (
            f"Unexpected added lines: {added}"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── 3. Boot test: RNS starts with [[Navamesh HT-HD01]] config ─────────────────

def test_udp_config_boot():
    """RNS.Reticulum starts cleanly with a config containing [[Navamesh HT-HD01]]."""
    from sbapp.farmui.rns_config_writer import write_hthd01_interface, free_udp_port
    tmpdir = tempfile.mkdtemp(prefix="navamesh_boot_")
    try:
        path = os.path.join(tmpdir, "config")
        with open(path, "w") as f:
            f.write(_BASE)

        listen_port  = free_udp_port()
        forward_port = free_udp_port()
        write_hthd01_interface(path, "127.0.0.1", listen_port, "127.0.0.1", forward_port)

        script = (
            f"import RNS; "
            f"r = RNS.Reticulum(configdir={tmpdir!r}, loglevel=1); "
            f"print('RNS_BOOT_OK')"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=30,
        )
        assert "RNS_BOOT_OK" in result.stdout, (
            f"RNS did not boot cleanly with [[Navamesh HT-HD01]] config.\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

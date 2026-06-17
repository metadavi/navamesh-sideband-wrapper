"""
test_stock_equivalence.py — Proves that farmui sends the same bytes as stock Sideband.

For representative commands the test does:
  stock_path:  create LXMessage(content=<command_text>) directly — the same
               bytes a user typing in stock Sideband would produce.
  farmui_path: LxmfDirectDispatcher.send_command(<cmd_key>) — farmui's button
               dispatch path.

Both messages are sent to the stub gateway which records the received
content string in its wirelog file.  The test asserts:
  1. stock_path wirelog entry == raw command text (gateway sees exact string)
  2. farmui_path wirelog entry == raw command text (same bytes, not modified)
  3. stock_path entry == farmui_path entry  (byte-identical on the wire)

Two separate LXMRouter instances are used so their delivery callbacks
never interfere.

This is the automated evidence for the behavior-preservation guarantee:
farmui buttons produce byte-identical LXMF content to typing the command
in stock Sideband.
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time

import pytest
import RNS
import LXMF

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sbapp"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "rig"))

from farmui.dispatch import LxmfDirectDispatcher
from farmui.command_registry import get_wire, COMMANDS
from rns_testnet import RnsTestnet


ANNOUNCE_WAIT  = 30.0
REPLY_TIMEOUT  = 40.0
WIRELOG_POLL   = 40.0

# Representative commands: one simple, one list, one map-all, one map-with-id
EQUIV_CASES = [
    ("status",  "status",      None),
    ("soil",    "soil",        None),
    ("nodes",   "nodes",       None),
    ("map_all", "map",         None),
    ("map_one", "map node42",  "node42"),
]


def _wait_wirelog(path: str, expect_n: int, timeout: float = WIRELOG_POLL) -> list[str]:
    """Poll wirelog until at least expect_n lines exist, then return all lines."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with open(path) as f:
                lines = [l.strip() for l in f if l.strip()]
            if len(lines) >= expect_n:
                return lines
        except FileNotFoundError:
            pass
        time.sleep(0.3)
    try:
        with open(path) as f:
            return [l.strip() for l in f if l.strip()]
    except FileNotFoundError:
        return []


class _StockClient:
    """
    Minimal direct LXMF sender — mirrors what a user typing in stock Sideband
    would produce: LXMessage(content=<command_text>, desired_method=OPPORTUNISTIC).
    Uses its own LXMRouter so its delivery callback never conflicts with the
    farmui dispatcher's callback.
    """

    def __init__(self, storagedir: str):
        os.makedirs(storagedir, exist_ok=True)
        identity = RNS.Identity()
        self._router = LXMF.LXMRouter(storagepath=storagedir, autopeer=False)
        self._source = self._router.register_delivery_identity(
            identity, display_name="StockClient"
        )
        self._source.announce()
        self._reply_event   = threading.Event()
        self._reply_content = []
        self._lock          = threading.Lock()
        self._router.register_delivery_callback(self._on_reply)

    def _on_reply(self, message):
        content = message.content.decode("utf-8") if message.content else ""
        with self._lock:
            self._reply_content.append(content)
        self._reply_event.set()

    def send(self, gateway_hash_hex: str, command_text: str,
             timeout: float = REPLY_TIMEOUT) -> str:
        """Send command_text as raw LXMessage content; return reply text."""
        gw_hash  = bytes.fromhex(gateway_hash_hex)
        identity = RNS.Identity.recall(gw_hash)
        if identity is None:
            raise RuntimeError("Stock client: gateway identity not resolved")

        dest = RNS.Destination(
            identity,
            RNS.Destination.OUT, RNS.Destination.SINGLE,
            "lxmf", "delivery",
        )
        self._reply_event.clear()
        msg = LXMF.LXMessage(
            destination    = dest,
            source         = self._source,
            content        = command_text,
            title          = "",
            desired_method = LXMF.LXMessage.OPPORTUNISTIC,
        )
        self._router.handle_outbound(msg)
        if not self._reply_event.wait(timeout=timeout):
            raise RuntimeError(
                f"Stock client: no reply within {timeout}s for {command_text!r}"
            )
        with self._lock:
            return self._reply_content[-1] if self._reply_content else ""


# ── Module-scoped fixture ─────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def equiv_session(shared_tcp_testnet):
    """
    Two LXMF clients on the shared testnet:
      - stock_client  (_StockClient)  → raw LXMessage sends
      - farmui_disp   (LxmfDirectDispatcher) → farmui button dispatch path
    """
    net    = shared_tcp_testnet
    tmpdir = tempfile.mkdtemp(prefix="navamesh_equiv_")
    try:
        # farmui router + source
        farmui_storage = os.path.join(tmpdir, "farmui_lxmf")
        os.makedirs(farmui_storage, exist_ok=True)
        farmui_id = RNS.Identity()
        farmui_router = LXMF.LXMRouter(storagepath=farmui_storage, autopeer=False)
        farmui_source = farmui_router.register_delivery_identity(
            farmui_id, display_name="FarmuiClient"
        )
        farmui_source.announce()
        farmui_disp = LxmfDirectDispatcher(farmui_router, farmui_source)

        # stock router + source
        stock_storage = os.path.join(tmpdir, "stock_lxmf")
        stock_client  = _StockClient(stock_storage)

        # Let both announces propagate
        time.sleep(5)

        yield {
            "net":         net,
            "farmui_disp": farmui_disp,
            "stock_client": stock_client,
        }
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── Parametrized equivalence tests ───────────────────────────────────────────

@pytest.mark.parametrize("cmd_key,expected_wire,node_id", EQUIV_CASES,
                         ids=[c[0] for c in EQUIV_CASES])
def test_farmui_wire_equals_stock(cmd_key, expected_wire, node_id, equiv_session):
    """
    farmui dispatch produces byte-identical LXMF content to typing the command
    in stock Sideband.  Gateway wirelog proves both paths sent the exact same
    string.
    """
    sess    = equiv_session
    gw_hash = sess["net"].gateway_hash
    wirelog = sess["net"].wirelog

    # ── Record wirelog baseline ──
    try:
        with open(wirelog) as f:
            baseline_count = sum(1 for l in f if l.strip())
    except FileNotFoundError:
        baseline_count = 0

    # ── stock path ──
    stock_reply = sess["stock_client"].send(gw_hash, expected_wire)
    assert stock_reply, f"stock send for {cmd_key!r} returned empty reply"

    time.sleep(1)  # let wirelog flush

    # ── farmui path ──
    farmui_wire = get_wire(cmd_key, node_id)
    assert farmui_wire == expected_wire, (
        f"get_wire({cmd_key!r}) = {farmui_wire!r}; expected {expected_wire!r}"
    )
    farmui_reply = sess["farmui_disp"].send_command(
        cmd_key, gw_hash, node_id=node_id, timeout=REPLY_TIMEOUT
    )
    assert farmui_reply.state != "failed", (
        f"farmui dispatch failed for {cmd_key!r}: {farmui_reply.error}"
    )

    time.sleep(1)  # let wirelog flush

    # ── Wirelog assertion ──
    lines = _wait_wirelog(wirelog, expect_n=baseline_count + 2)
    new_lines = lines[baseline_count:]

    assert len(new_lines) >= 2, (
        f"Expected 2 new wirelog entries for {cmd_key!r}; got {new_lines!r}"
    )

    # Both new entries must equal expected_wire
    for entry in new_lines[:2]:
        assert entry == expected_wire, (
            f"Wirelog entry {entry!r} != expected {expected_wire!r} for {cmd_key!r}"
        )

    # Entries are equal to each other (stock == farmui on the wire)
    assert new_lines[0] == new_lines[1], (
        f"Wire mismatch for {cmd_key!r}: stock={new_lines[0]!r} farmui={new_lines[1]!r}"
    )


def test_all_commands_wire_strings_are_plain_text():
    """
    Every command's wire string is plain lowercase printable text — exactly
    what a user would type.  No binary, no extra fields, no control chars.
    """
    for cmd in COMMANDS:
        wire = cmd.wire
        assert wire == wire.lower(), f"{cmd.key}: wire must be lowercase"
        assert wire == wire.strip(), f"{cmd.key}: wire must have no surrounding whitespace"
        assert wire.isprintable(), f"{cmd.key}: wire must be printable ASCII"
        if not cmd.needs_node:
            assert "{" not in wire, (
                f"{cmd.key}: static command must not contain format placeholders"
            )

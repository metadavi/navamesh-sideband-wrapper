"""
conftest.py — Session-scoped shared TCP testnet.

RNS.Reticulum raises OSError on a second init attempt in the same process.
All test modules that need RNS share ONE Reticulum instance, started here.

Modules that use this:
  test_protocol_roundtrip.py  — session fixture takes shared_tcp_testnet
  test_e2e_conversation.py    — e2e_session fixture takes shared_tcp_testnet
"""
from __future__ import annotations

import os
import sys
import time
import tempfile
import shutil

import pytest
import RNS

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "rig"))
from rns_testnet import RnsTestnet

ANNOUNCE_WAIT = 30.0


@pytest.fixture(scope="session")
def shared_tcp_testnet():
    """
    One TCP testnet + one RNS.Reticulum instance for the entire pytest session.
    Shared by test_protocol_roundtrip and test_e2e_conversation to avoid the
    OSError that RNS raises on a second Reticulum() call in the same process.
    """
    net = RnsTestnet(timeout=60)
    tmpdir = tempfile.mkdtemp(prefix="navamesh_session_")
    try:
        net.__enter__()
        RNS.Reticulum(configdir=net.client_configdir, loglevel=RNS.LOG_WARNING)

        gw_hash_bytes = bytes.fromhex(net.gateway_hash)
        deadline = time.time() + ANNOUNCE_WAIT
        while time.time() < deadline:
            if RNS.Identity.recall(gw_hash_bytes) is not None:
                break
            time.sleep(0.5)

        if RNS.Identity.recall(gw_hash_bytes) is None:
            net.__exit__(None, None, None)
            pytest.skip(f"Shared gateway not resolved within {ANNOUNCE_WAIT}s")

        yield net

    finally:
        try:
            net.__exit__(None, None, None)
        except Exception:
            pass
        shutil.rmtree(tmpdir, ignore_errors=True)

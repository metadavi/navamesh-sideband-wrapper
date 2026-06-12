#!/usr/bin/env python3
"""
udp_roundtrip_runner.py — Subprocess-isolated UDP round-trip runner.

Runs all 9 LXMF commands against the stub gateway over a loopback
UDPInterface.  Prints "UDP_RESULTS: <json>" on the last line and exits 0
on success, 1 on failure.

Run via: python tests/rig/udp_roundtrip_runner.py
Used by: tests/test_udp_interface.py (subprocess isolation avoids RNS singleton
conflict with the session-scoped TCP testnet used by other test modules).
"""
from __future__ import annotations

import json
import os
import sys
import time
import threading

# Ensure project root is on path
_HERE = os.path.dirname(__file__)
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import RNS
import LXMF

from udp_testnet import UdpRnsTestnet

ANNOUNCE_WAIT = 25.0
REPLY_WAIT    = 35.0

ALL_COMMANDS = [
    ("help",     "help"),
    ("status",   "status"),
    ("soil",     "soil"),
    ("battery",  "battery"),
    ("position", "position"),
    ("link",     "link"),
    ("nodes",    "nodes"),
    ("map",      "map"),
    ("map_one",  "map !drynode001"),
]


class _Client:
    def __init__(self, storagedir: str):
        os.makedirs(storagedir, exist_ok=True)
        id_path = os.path.join(storagedir, "identity")
        if os.path.exists(id_path):
            self._identity = RNS.Identity.from_file(id_path)
        else:
            self._identity = RNS.Identity()
            self._identity.to_file(id_path)
        self._router = LXMF.LXMRouter(storagepath=storagedir, autopeer=False)
        self._source = self._router.register_delivery_identity(
            self._identity, display_name="UDPTestClient"
        )
        self._received: list = []
        self._event = threading.Event()
        self._router.register_delivery_callback(self._on_reply)

    def _on_reply(self, msg):
        self._received.append(msg)
        self._event.set()

    def announce(self):
        self._source.announce()

    def send_and_wait(self, gw_hash_hex: str, content: str, timeout: float = REPLY_WAIT):
        gw_hash = bytes.fromhex(gw_hash_hex)
        identity = RNS.Identity.recall(gw_hash)
        if identity is None:
            return None
        dest = RNS.Destination(
            identity, RNS.Destination.OUT, RNS.Destination.SINGLE, "lxmf", "delivery"
        )
        msg = LXMF.LXMessage(
            destination=dest, source=self._source,
            content=content, title="",
            desired_method=LXMF.LXMessage.OPPORTUNISTIC,
        )
        self._router.handle_outbound(msg)
        self._event.wait(timeout=timeout)
        self._event.clear()
        return self._received.pop(0) if self._received else None


def _content(msg) -> str:
    if msg is None:
        return ""
    if hasattr(msg, "content") and msg.content:
        return msg.content.decode("utf-8")
    return ""

def _has_image(msg) -> bool:
    if msg is None:
        return False
    return hasattr(msg, "fields") and msg.fields and LXMF.FIELD_IMAGE in msg.fields


def main():
    import tempfile, shutil
    tmpdir = tempfile.mkdtemp(prefix="navamesh_udp_runner_")
    failures = []
    try:
        with UdpRnsTestnet(timeout=60) as net:
            RNS.Reticulum(configdir=net.client_configdir, loglevel=RNS.LOG_WARNING)
            client = _Client(storagedir=os.path.join(tmpdir, "lxmf"))
            client.announce()

            gw_hash_bytes = bytes.fromhex(net.gateway_hash)
            deadline = time.time() + ANNOUNCE_WAIT
            resolved = False
            while time.time() < deadline:
                if RNS.Identity.recall(gw_hash_bytes) is not None:
                    resolved = True
                    break
                time.sleep(0.5)

            if not resolved:
                print("UDP_RESULTS: " + json.dumps({"passed": 0, "failures": ["Gateway not resolved"]}))
                sys.exit(1)

            for name, wire in ALL_COMMANDS:
                timeout = 45.0 if "map" in name else REPLY_WAIT
                msg = client.send_and_wait(net.gateway_hash, wire, timeout=timeout)
                if msg is None:
                    failures.append(f"{name}: no reply")
                    continue
                txt = _content(msg)
                if name == "help" and "Navamesh Gateway" not in txt:
                    failures.append(f"{name}: missing 'Navamesh Gateway' in reply")
                elif name == "status" and "Navamesh Status" not in txt:
                    failures.append(f"{name}: missing 'Navamesh Status'")
                elif name == "soil" and "Soil Moisture" not in txt:
                    failures.append(f"{name}: missing 'Soil Moisture'")
                elif name == "battery" and "Battery" not in txt:
                    failures.append(f"{name}: missing 'Battery'")
                elif name == "position" and "Position" not in txt:
                    failures.append(f"{name}: missing 'Position'")
                elif name == "link" and "Link Quality" not in txt:
                    failures.append(f"{name}: missing 'Link Quality'")
                elif name == "nodes" and "Known field nodes" not in txt:
                    failures.append(f"{name}: missing 'Known field nodes'")
                elif name in ("map", "map_one") and not _has_image(msg):
                    failures.append(f"{name}: missing FIELD_IMAGE")

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    passed = len(ALL_COMMANDS) - len(failures)
    result = {"passed": passed, "total": len(ALL_COMMANDS), "failures": failures}
    print("UDP_RESULTS: " + json.dumps(result))
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()

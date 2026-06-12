"""
udp_testnet.py — UDP-variant two-node testnet for Phase 5 rig tests.

Identical to RnsTestnet but uses loopback UDPInterface instead of
TCPServerInterface/TCPClientInterface.  Two distinct ports on 127.0.0.1.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path


def _free_udp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def write_udp_rns_config(configdir: str, listen_port: int, forward_port: int) -> None:
    """Write a minimal standalone RNS config with a loopback UDPInterface."""
    os.makedirs(configdir, exist_ok=True)
    iface = textwrap.dedent(f"""\
        [[TestUDP]]
          type = UDPInterface
          enabled = yes
          listen_ip = 127.0.0.1
          listen_port = {listen_port}
          forward_ip = 127.0.0.1
          forward_port = {forward_port}
    """)
    cfg = textwrap.dedent(f"""\
        [reticulum]
          enable_transport = False
          share_instance = No

        [logging]
          loglevel = 1

        [interfaces]
        {iface}
    """)
    with open(os.path.join(configdir, "config"), "w") as f:
        f.write(cfg)


class UdpRnsTestnet:
    """
    Context manager: starts the stub gateway as a subprocess using a loopback
    UDPInterface, mirrors the RnsTestnet API so tests can swap transports.

    Usage:
        with UdpRnsTestnet() as net:
            # net.gateway_hash   — hex LXMF hash
            # net.client_configdir — UDP config for the in-process RNS client
            # net.wirelog        — path to wire-content log file
    """

    def __init__(self, timeout: float = 60.0):
        self._timeout = timeout
        self._tmpdir: str | None = None
        self._proc = None
        self.gw_udp_port: int = 0
        self.client_udp_port: int = 0
        self.gateway_hash: str = ""
        self.client_configdir: str = ""
        self.gw_configdir: str = ""
        self.gw_storagedir: str = ""
        self.wirelog: str = ""

    def __enter__(self) -> "UdpRnsTestnet":
        self._tmpdir = tempfile.mkdtemp(prefix="navamesh_udp_net_")
        self.gw_udp_port     = _free_udp_port()
        self.client_udp_port = _free_udp_port()
        self.gw_configdir    = os.path.join(self._tmpdir, "gw_rns")
        self.gw_storagedir   = os.path.join(self._tmpdir, "gw_lxmf")
        self.client_configdir = os.path.join(self._tmpdir, "client_rns")
        hashfile = os.path.join(self._tmpdir, "gateway.hash")
        self.wirelog = os.path.join(self._tmpdir, "wire.log")

        write_udp_rns_config(self.gw_configdir,     self.gw_udp_port,     self.client_udp_port)
        write_udp_rns_config(self.client_configdir, self.client_udp_port, self.gw_udp_port)

        stub_script = str(Path(__file__).parent / "stub_gateway.py")

        self._proc = subprocess.Popen(
            [
                sys.executable, stub_script,
                "--configdir",  self.gw_configdir,
                "--storagedir", self.gw_storagedir,
                "--port",       str(self.gw_udp_port),  # required by argparse; unused
                "--hashfile",   hashfile,
                "--wirelog",    self.wirelog,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        deadline = time.time() + self._timeout
        while time.time() < deadline:
            if os.path.exists(hashfile):
                with open(hashfile) as f:
                    h = f.read().strip()
                if h:
                    self.gateway_hash = h
                    break
            if self._proc.poll() is not None:
                out = self._proc.stdout.read() if self._proc.stdout else ""
                err = self._proc.stderr.read() if self._proc.stderr else ""
                raise RuntimeError(
                    f"UDP gateway process died. stdout={out!r} stderr={err!r}"
                )
            time.sleep(0.2)
        else:
            self._cleanup()
            raise TimeoutError(f"UDP gateway did not start within {self._timeout}s")

        return self

    def __exit__(self, *_):
        self._cleanup()

    def _cleanup(self):
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                self._proc.kill()
        if self._tmpdir and os.path.exists(self._tmpdir):
            import shutil
            shutil.rmtree(self._tmpdir, ignore_errors=True)

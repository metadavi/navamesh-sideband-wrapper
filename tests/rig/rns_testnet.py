"""
rns_testnet.py — Start an isolated two-node RNS loopback testnet for pytest.

Creates two temporary directories (gateway + client) with distinct RNS configs,
launches the stub gateway as a subprocess with a TCPServerInterface, and provides
the gateway hash to the test so a client RNS instance can resolve and message it.

The client RNS instance runs IN the test process (connected via TCPClientInterface
to the gateway's server port). The gateway runs in a subprocess because RNS is a
process-global singleton.
"""
from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _write_rns_config(configdir: str, role: str, tcp_port: int) -> None:
    """Write a minimal RNS config for the gateway (server) or client."""
    os.makedirs(configdir, exist_ok=True)
    if role == "server":
        iface = textwrap.dedent(f"""\
            [[TestServer]]
              type = TCPServerInterface
              enabled = yes
              listen_ip = 127.0.0.1
              listen_port = {tcp_port}
        """)
    else:
        iface = textwrap.dedent(f"""\
            [[TestClient]]
              type = TCPClientInterface
              enabled = yes
              target_host = 127.0.0.1
              target_port = {tcp_port}
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


class RnsTestnet:
    """
    Context manager that starts the stub gateway subprocess and provides
    the gateway LXMF hash for the test client.

    Usage:
        with RnsTestnet() as net:
            # net.port — TCP port of the gateway server
            # net.gateway_hash — hex LXMF hash of the gateway
            # net.client_configdir — RNS configdir for the test-process client
    """

    def __init__(self, timeout: float = 60.0):
        self._timeout = timeout
        self._tmpdir: str | None = None
        self._proc: subprocess.Popen | None = None
        self.port: int = 0
        self.gateway_hash: str = ""
        self.client_configdir: str = ""
        self.gw_configdir: str = ""
        self.gw_storagedir: str = ""
        self.wirelog: str = ""  # path to the wire-content log file

    def __enter__(self) -> "RnsTestnet":
        self._tmpdir = tempfile.mkdtemp(prefix="navamesh_testnet_")
        self.port         = _free_port()
        self.gw_configdir  = os.path.join(self._tmpdir, "gw_rns")
        self.gw_storagedir = os.path.join(self._tmpdir, "gw_lxmf")
        self.client_configdir = os.path.join(self._tmpdir, "client_rns")
        hashfile = os.path.join(self._tmpdir, "gateway.hash")
        self.wirelog = os.path.join(self._tmpdir, "wire.log")

        _write_rns_config(self.gw_configdir, "server", self.port)
        _write_rns_config(self.client_configdir, "client", self.port)

        stub_script = str(Path(__file__).parent / "stub_gateway.py")
        python = sys.executable

        self._proc = subprocess.Popen(
            [
                python, stub_script,
                "--configdir",  self.gw_configdir,
                "--storagedir", self.gw_storagedir,
                "--port",       str(self.port),
                "--hashfile",   hashfile,
                "--wirelog",    self.wirelog,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Wait for the gateway to write its hash
        deadline = time.time() + self._timeout
        while time.time() < deadline:
            if os.path.exists(hashfile):
                with open(hashfile) as f:
                    h = f.read().strip()
                if h:
                    self.gateway_hash = h
                    break
            if self._proc.poll() is not None:
                stdout = self._proc.stdout.read() if self._proc.stdout else ""
                stderr = self._proc.stderr.read() if self._proc.stderr else ""
                raise RuntimeError(
                    f"Gateway process died at startup. "
                    f"stdout={stdout!r} stderr={stderr!r}"
                )
            time.sleep(0.2)
        else:
            self._cleanup()
            raise TimeoutError(f"Gateway did not start within {self._timeout}s")

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

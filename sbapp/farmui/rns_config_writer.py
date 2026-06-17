"""
rns_config_writer.py — Surgical editor for the RNS config file.

Inserts or replaces the [[Navamesh HT-HD01]] UDPInterface block in the
[interfaces] section of an RNS config file.  Every line outside that named
block is preserved byte-identically.

The RNS config template is stored on disk at:
  <sideband_configdir>/rns/config   (desktop/Android)

Sideband generates it from the rns_config template string in sideband/core.py
and then leaves it editable.  The [interfaces] section at the end is the
designated place for custom interfaces.  We only touch the named block.
"""
from __future__ import annotations

import re
import socket
from typing import Optional


BLOCK_NAME = "Navamesh HT-HD01"

_BLOCK_PATTERN = re.compile(
    r'\[\[Navamesh HT-HD01\]\]\n(?:(?!\[)[^\n]*\n)*',
    re.DOTALL,
)


def _make_block(listen_ip: str, listen_port: int, forward_ip: str, forward_port: int) -> str:
    return (
        f"[[{BLOCK_NAME}]]\n"
        f"  type = UDPInterface\n"
        f"  enabled = yes\n"
        f"  listen_ip = {listen_ip}\n"
        f"  listen_port = {listen_port}\n"
        f"  forward_ip = {forward_ip}\n"
        f"  forward_port = {forward_port}\n"
    )


def _splice(content: str, listen_ip: str, listen_port: int,
            forward_ip: str, forward_port: int) -> str:
    """Return new config content with [[Navamesh HT-HD01]] inserted or replaced."""
    block = _make_block(listen_ip, listen_port, forward_ip, forward_port)
    if _BLOCK_PATTERN.search(content):
        return _BLOCK_PATTERN.sub(block, content)
    # Block not present — append after [interfaces] header
    if "\n[interfaces]\n" in content:
        return content.replace("\n[interfaces]\n", "\n[interfaces]\n" + block, 1)
    if content.rstrip("\n").endswith("[interfaces]"):
        return content.rstrip("\n") + "\n" + block
    # No [interfaces] section at all — append it
    return content.rstrip("\n") + "\n[interfaces]\n" + block


def write_hthd01_interface(
    config_path: str,
    listen_ip: str,
    listen_port: int,
    forward_ip: str,
    forward_port: int,
) -> None:
    """
    Surgically insert or replace [[Navamesh HT-HD01]] in the RNS config file at
    config_path.  All lines outside that block are preserved byte-identically.
    """
    with open(config_path) as f:
        content = f.read()
    new_content = _splice(content, listen_ip, listen_port, forward_ip, forward_port)
    with open(config_path, "w") as f:
        f.write(new_content)


def free_udp_port() -> int:
    """Return a free UDP port on 127.0.0.1."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ── Config-template builder (Android: Sideband regenerates the RNS config from
#    config["config_template"] on every service start, so the persistent place
#    for the HT-HD01 interface is the TEMPLATE, not the generated file) ────────

# HT-HD01 HaLow UDP broadcast defaults (the "working Docker/Pi" reference).
# The phone's Wi-Fi (wlan0) must be on the HT-HD01's subnet for forward_ip's
# broadcast address to reach the peer radio.
HTHD01_LISTEN_IP    = "0.0.0.0"
HTHD01_LISTEN_PORT  = 4242
HTHD01_FORWARD_IP   = "192.168.10.255"
HTHD01_FORWARD_PORT = 4242
HTHD01_IFAC_NAME    = "HTHD01_UDP"

# Mirrors Sideband's own default Android template (sideband/core.py: rns_config):
# the [reticulum] block is byte-for-byte Sideband's Android default — we do NOT
# substitute Linux/Docker-only pieces (e.g. an eth0 AutoInterface). The only
# addition is the HT-HD01 UDPInterface under [interfaces]. enable_transport is
# left as the TRANSPORT_IS_ENABLED placeholder that Sideband fills from the
# connect_transport setting (we set connect_transport=True alongside this).
_TEMPLATE = """\
# Navamesh Farm — Sideband-managed RNS config template.
# Mirrors Sideband's default Android template; only the HT-HD01 UDPInterface
# is added. If Reticulum aborts at startup, Sideband resets to its default.

[reticulum]
  enable_transport = TRANSPORT_IS_ENABLED
  share_instance = Yes
  shared_instance_port = 37428
  instance_control_port = 37429
  panic_on_interface_error = No

[logging]
  loglevel = 4

[interfaces]

  [[{name}]]
    type = UDPInterface
    enabled = true
    listen_ip = {listen_ip}
    listen_port = {listen_port}
    forward_ip = {forward_ip}
    forward_port = {forward_port}
    name = {ifac_name}
"""


def build_config_template(
    listen_ip: str = HTHD01_LISTEN_IP,
    listen_port: int = HTHD01_LISTEN_PORT,
    forward_ip: str = HTHD01_FORWARD_IP,
    forward_port: int = HTHD01_FORWARD_PORT,
    ifac_name: str = HTHD01_IFAC_NAME,
) -> str:
    """Full Sideband config-template string including the HT-HD01 UDP interface."""
    return _TEMPLATE.format(
        name=BLOCK_NAME,
        listen_ip=listen_ip,
        listen_port=listen_port,
        forward_ip=forward_ip,
        forward_port=forward_port,
        ifac_name=ifac_name,
    )

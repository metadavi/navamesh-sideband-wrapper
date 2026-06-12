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

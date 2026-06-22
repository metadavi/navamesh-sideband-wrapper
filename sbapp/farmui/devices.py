"""
devices.py — classify discovered LXMF devices for routing.

The Talk tab lists every heard device uniformly; the gateway-vs-peer decision is
made only when the user taps a device (FarmApp.open_chat). Detection is
name-based for now (case-insensitive "gateway" substring). dest_hex is accepted
so a future identity-based check (e.g. a known gateway hash set or an announce
flag) can replace the heuristic without touching any caller.
"""
from __future__ import annotations

from typing import Optional

# Canonical name the Navamesh gateway announces; kept for reference / fallbacks.
GATEWAY_DISPLAY_NAME = "Navamesh Gateway"


def is_gateway_device(display_name: str, dest_hex: Optional[str] = None) -> bool:
    """True if a discovered device should be treated as a Navamesh gateway.

    Current rule: the announced/displayed name contains "gateway"
    (case-insensitive). The dest_hex parameter is intentionally unused today but
    part of the signature so identification can move to an identity/hash basis
    later without changing callers.
    """
    return "gateway" in (display_name or "").lower()

"""
dispatch.py — Command dispatch and reply handling for the farm UI.

Abstracts over two send paths:
  CoreDispatcher   — wraps SidebandCore.send_message() (production)
  LxmfDirectDispatcher — pure rns+lxmf, no Sideband (tests / rig)

Wire content is ALWAYS the plain command string (e.g. "soil", "map !abc123").
This matches exactly what a user would type in stock Sideband — the gateway
receives `message.content.decode("utf-8").strip()` which equals the wire string.
"""
from __future__ import annotations

import io
import threading
import time
from typing import Optional, Callable

import LXMF
import RNS

from .command_registry import COMMANDS, get_wire


# ── Delivery states ───────────────────────────────────────────────────────────

SENDING   = "sending"
DELIVERED = "delivered"
FAILED    = "failed"


# ── Reply model ───────────────────────────────────────────────────────────────

class CommandReply:
    def __init__(
        self,
        cmd_key: str,
        text: str,
        image_bytes: Optional[bytes] = None,
        state: str = DELIVERED,
        error: Optional[str] = None,
    ):
        self.cmd_key     = cmd_key
        self.text        = text
        self.image_bytes = image_bytes
        self.state       = state
        self.error       = error

    @classmethod
    def failed(cls, cmd_key: str, reason: str) -> "CommandReply":
        return cls(
            cmd_key=cmd_key,
            text=f"Gateway not reachable — could not deliver '{cmd_key}'.\n\n{reason}",
            state=FAILED,
            error=reason,
        )


# ── Abstract dispatcher ───────────────────────────────────────────────────────

class AbstractDispatcher:
    def send_command(
        self,
        cmd_key: str,
        gateway_hash_hex: str,
        node_id: Optional[str] = None,
        on_reply: Optional[Callable[[CommandReply], None]] = None,
        timeout: float = 30.0,
    ) -> CommandReply:
        raise NotImplementedError


# ── Direct LXMF dispatcher (tests, no SidebandCore) ──────────────────────────

class LxmfDirectDispatcher(AbstractDispatcher):
    """
    Pure rns+lxmf dispatcher for tests/rig.
    Wire content = exactly the command string — no extra fields.
    """

    def __init__(self, router: LXMF.LXMRouter, source):
        self._router  = router
        self._source  = source
        self._replies: dict[str, CommandReply] = {}
        self._events:  dict[str, threading.Event] = {}
        self._lock = threading.Lock()
        self._router.register_delivery_callback(self._on_reply)

    def _on_reply(self, message):
        cmd_key = None
        with self._lock:
            for k, ev in list(self._events.items()):
                if not ev.is_set():
                    cmd_key = k
                    break
        if cmd_key is None:
            return
        content = message.content.decode("utf-8") if message.content else ""
        image_bytes = None
        if hasattr(message, "fields") and message.fields:
            img_field = message.fields.get(LXMF.FIELD_IMAGE)
            if img_field:
                _, image_bytes = img_field[0], img_field[1]
        reply = CommandReply(
            cmd_key=cmd_key,
            text=content,
            image_bytes=image_bytes,
            state=DELIVERED,
        )
        with self._lock:
            self._replies[cmd_key] = reply
            self._events[cmd_key].set()

    def send_command(
        self,
        cmd_key: str,
        gateway_hash_hex: str,
        node_id: Optional[str] = None,
        on_reply: Optional[Callable[[CommandReply], None]] = None,
        timeout: float = 30.0,
        value: Optional[int] = None,
    ) -> CommandReply:
        wire = get_wire(cmd_key, node_id, value)
        gw_hash = bytes.fromhex(gateway_hash_hex)
        identity = RNS.Identity.recall(gw_hash)
        if identity is None:
            r = CommandReply.failed(cmd_key, "Gateway identity not resolved")
            if on_reply:
                on_reply(r)
            return r

        dest = RNS.Destination(
            identity,
            RNS.Destination.OUT, RNS.Destination.SINGLE,
            "lxmf", "delivery",
        )
        event = threading.Event()
        with self._lock:
            self._events[cmd_key] = event

        msg = LXMF.LXMessage(
            destination=dest,
            source=self._source,
            content=wire,
            title="",
            desired_method=LXMF.LXMessage.OPPORTUNISTIC,
        )
        self._router.handle_outbound(msg)

        if not event.wait(timeout=timeout):
            r = CommandReply.failed(cmd_key, f"No reply within {timeout}s (gateway unreachable?)")
            if on_reply:
                on_reply(r)
            return r

        with self._lock:
            r = self._replies.pop(cmd_key, CommandReply.failed(cmd_key, "Reply missing"))
        if on_reply:
            on_reply(r)
        return r


# ── Core dispatcher (production — wraps SidebandCore) ─────────────────────────

class CoreDispatcher(AbstractDispatcher):
    """
    Wraps SidebandCore.send_message().
    Wire content = plain command string; propagation=False (DIRECT/OPPORTUNISTIC).
    """

    def __init__(self, core, on_new_message: Optional[Callable] = None):
        self._core = core
        self._on_new_message = on_new_message

    def send_command(
        self,
        cmd_key: str,
        gateway_hash_hex: str,
        node_id: Optional[str] = None,
        on_reply: Optional[Callable[[CommandReply], None]] = None,
        timeout: float = 30.0,
        value: Optional[int] = None,
    ) -> CommandReply:
        wire = get_wire(cmd_key, node_id, value)
        dest_hash = bytes.fromhex(gateway_hash_hex)
        try:
            self._core.send_message(
                content=wire,
                destination_hash=dest_hash,
                propagation=False,
                skip_fields=True,
            )
        except Exception as exc:
            r = CommandReply.failed(cmd_key, str(exc))
            if on_reply:
                on_reply(r)
            return r
        return CommandReply(cmd_key=cmd_key, text="", state=SENDING)

    def send_text(
        self,
        gateway_hash_hex: str,
        content: str,
        on_reply: Optional[Callable[[CommandReply], None]] = None,
    ) -> CommandReply:
        """Send a free-text LXMF message to a peer (used by the Debug tab).

        Uses the SAME correct call shape as send_command: hex→bytes for the
        destination, and the required positional/keyword args of
        SidebandCore.send_message(content, destination_hash, propagation, ...).
        """
        dest_hash = bytes.fromhex(gateway_hash_hex)
        try:
            self._core.send_message(
                content=content,
                destination_hash=dest_hash,
                propagation=False,
                skip_fields=True,
            )
        except Exception as exc:
            r = CommandReply.failed("message", str(exc))
            if on_reply:
                on_reply(r)
            return r
        return CommandReply(cmd_key="message", text="", state=SENDING)


# ── Reply parser ──────────────────────────────────────────────────────────────

def parse_nodes_reply(text: str) -> list[str]:
    """Extract node IDs from a 'nodes' command reply."""
    nodes = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("!") or (line and not line.startswith("Known")):
            nodes.append(line.lstrip("-").strip())
    return [n for n in nodes if n.startswith("!")]


def extract_image(message_fields: dict) -> Optional[bytes]:
    """Return JPEG bytes from LXMF FIELD_IMAGE if present, None otherwise."""
    if not message_fields:
        return None
    img = message_fields.get(LXMF.FIELD_IMAGE)
    if img and len(img) >= 2:
        return img[1]
    return None

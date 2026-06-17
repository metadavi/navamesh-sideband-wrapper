"""
test_gateway_replies.py — gateway command replies show in the Commands tab.

Replies arrive asynchronously and are stored in the message DB; the wrapper
must poll list_messages() for the pinned gateway and render inbound replies
(text + optional image). Outbound commands and already-shown replies are skipped.
"""
from __future__ import annotations

import os
import types

os.environ["KIVY_NO_ENV_CONFIG"] = "1"
os.environ["KIVY_WINDOW"] = "headless"
os.environ["DISPLAY"] = ""

import pytest

GW = bytes.fromhex("ab3e0adcaa3d62130c3ce6cdf99a48bf")   # the Pi gateway
ME = bytes.fromhex("1d1922b7f52519872fd6244d7c4ea034")   # Phone A


class FakeConv:
    def __init__(self):
        self.results = []  # (text, image_bytes, image_ext)
    def add_result(self, text, image_bytes=None, image_ext="png"):
        self.results.append((text, image_bytes, image_ext))


class FakeCore:
    def __init__(self, messages):
        self._messages = messages
    def list_messages(self, context_dest, after=None, before=None, limit=None):
        return self._messages


def _msg(source, content, h, image=None):
    fields = {}
    if image is not None:
        import LXMF
        fields[LXMF.FIELD_IMAGE] = image  # [type, bytes]
    lxm = types.SimpleNamespace(fields=fields)
    return {"source": source, "hash": h, "content": content, "lxm": lxm}


def _app(core, conv):
    from sbapp.farmui.app import FarmApp
    app = FarmApp.__new__(FarmApp)
    app.sideband = core
    app._gateway_hash = GW.hex()
    app._shown_msgs = set()
    app._conv_screen = conv
    return app


def test_inbound_reply_text_is_displayed():
    conv = FakeConv()
    core = FakeCore([_msg(GW, b"Soil: OK 42%", b"\x01\x02")])
    _app(core, conv)._poll_gateway_replies()
    assert conv.results == [("Soil: OK 42%", None, "png")]


def test_outbound_command_is_not_displayed():
    conv = FakeConv()
    core = FakeCore([_msg(ME, b"soil", b"\xaa\xbb")])  # our own outgoing command
    _app(core, conv)._poll_gateway_replies()
    assert conv.results == []


def test_reply_deduped_across_polls():
    conv = FakeConv()
    core = FakeCore([_msg(GW, b"status ok", b"\x09\x09")])
    app = _app(core, conv)
    app._poll_gateway_replies()
    app._poll_gateway_replies()   # same message again
    assert len(conv.results) == 1


def test_image_reply_passes_bytes_and_ext():
    conv = FakeConv()
    core = FakeCore([_msg(GW, b"map", b"\x07\x07", image=["jpg", b"\xff\xd8\xff\xe0JPEGDATA"])])
    _app(core, conv)._poll_gateway_replies()
    assert len(conv.results) == 1
    text, img, ext = conv.results[0]
    assert text == "map"
    assert img == b"\xff\xd8\xff\xe0JPEGDATA"
    assert ext == "jpg"


def test_no_gateway_or_core_is_safe():
    from sbapp.farmui.app import FarmApp
    a = FarmApp.__new__(FarmApp)
    a.sideband = None
    a._gateway_hash = None
    a._shown_msgs = set()
    a._conv_screen = FakeConv()
    a._poll_gateway_replies()  # must not raise
    assert a._conv_screen.results == []

"""
test_textfmt.py — Pure-logic tests for render_reply() (no Kivy window).

render_reply() prepares gateway reply text for a markup Label rendered in the
mono family: it strips control/replacement chars, escapes Kivy markup
metacharacters, and wraps emoji runs in [font=emoji] so they don't fall back to
the .notdef box (the □ bug).
"""
from __future__ import annotations

from sbapp.farmui.textfmt import render_reply


def test_empty_and_none():
    assert render_reply("") == ""
    assert render_reply(None) == ""


def test_plain_ascii_unchanged():
    assert render_reply("Node 1a2b: 85%  3.92V") == "Node 1a2b: 85%  3.92V"


def test_box_drawing_preserved():
    """The ─── rule lines survive (mono font renders them); not stripped."""
    rule = "─" * 30
    out = render_reply(rule)
    assert out == rule


def test_replacement_char_dropped():
    """U+FFFD from a lossy UTF-8 decode is removed, not shown as a box."""
    assert "�" not in render_reply("Battery� 85%")
    assert render_reply("Battery� 85%") == "Battery 85%"


def test_control_chars_stripped_newline_tab_kept():
    out = render_reply("a\x00b\x07c\nd\te")
    assert "\x00" not in out and "\x07" not in out
    assert "\n" in out and "\t" in out
    assert out == "abc\nd\te"


def test_markup_metacharacters_escaped():
    out = render_reply("[ node ] & co")
    assert "&bl;" in out and "&br;" in out and "&amp;" in out
    assert "[node" not in out  # raw '[' must not survive to the Label


def test_emoji_wrapped_in_emoji_font():
    out = render_reply("🔋 Battery")
    assert out.startswith("[font=emoji]🔋[/font]")
    assert "Battery" in out


def test_title_line_with_emoji_and_rules():
    """The exact battery-reply header shape: rules above/below an emoji title."""
    src = ("─" * 30) + "\n🌱 Navamesh Status\n" + ("─" * 30)
    out = render_reply(src)
    assert "[font=emoji]🌱[/font]" in out
    assert ("─" * 30) in out
    assert "Navamesh Status" in out


def test_idempotent_on_plain_text():
    txt = "RSSI=-92 dBm  SNR=6 dB"
    assert render_reply(render_reply(txt)) == render_reply(txt)


def test_adjacent_emoji_share_one_wrapper():
    out = render_reply("🌱🔋")
    assert out == "[font=emoji]🌱🔋[/font]"

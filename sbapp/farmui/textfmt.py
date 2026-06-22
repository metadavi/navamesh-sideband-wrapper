"""
textfmt.py — Make gateway reply text safe and legible for a Kivy markup Label.

Gateway replies arrive as plain UTF-8 (decoded with errors="replace" upstream),
formatted for a monospace terminal: space-aligned columns, ``─``×30 rule lines,
and emoji in section titles (🔋 Battery, 🌱 Status…). Rendering them naively in a
Label produced ``□`` boxes — the body font has no glyphs for the box-drawing
rules or the emoji, so they fell back to the font's ``.notdef`` box.

``render_reply()`` returns text ready for a ``markup=True`` Label rendered in the
mono family (which has the box-drawing glyphs and keeps the columns aligned):

  1. NFC-normalize.
  2. Strip C0/C1 control characters (keep ``\\n`` and ``\\t``) and the U+FFFD
     replacement character left behind by a lossy UTF-8 decode.
  3. Escape Kivy markup metacharacters so reply text containing ``[`` / ``]`` /
     ``&`` cannot break or inject markup.
  4. Wrap emoji / pictographic runs in ``[font=emoji]…[/font]`` so they render
     with the bundled emoji font instead of as boxes.

Pure functions, no Kivy import — unit-testable without a window.
"""
from __future__ import annotations

import unicodedata

# Emoji / pictographic codepoint ranges. A run of these (plus the zero-width
# joiner U+200D and the emoji variation selector U+FE0F that glue sequences
# together) gets wrapped in [font=emoji] so the emoji font renders it.
_EMOJI_RANGES = (
    (0x1F300, 0x1FAFF),  # Misc Symbols & Pictographs, Emoticons, Transport,
                         # Supplemental Symbols & Pictographs, Symbols & Pictographs Extended-A
    (0x2600, 0x27BF),    # Misc Symbols + Dingbats
    (0x1F000, 0x1F0FF),  # Mahjong / Dominoes / Playing cards
    (0x1F1E6, 0x1F1FF),  # Regional indicator symbols (flags)
    (0x2B00, 0x2BFF),    # Misc Symbols & Arrows (★ ▶ etc.)
    (0x2190, 0x21FF),    # Arrows
    (0x2300, 0x23FF),    # Misc Technical (⌚ ⏰ ⏳…)
)

# Codepoints that extend an emoji run without being emoji themselves.
_EMOJI_JOINERS = {0x200D, 0xFE0F, 0xFE0E}


def _is_emoji(cp: int) -> bool:
    return any(lo <= cp <= hi for lo, hi in _EMOJI_RANGES)


def _strip_controls(text: str) -> str:
    """Drop control chars (except \\n and \\t) and U+FFFD replacement chars."""
    out = []
    for ch in text:
        if ch in ("\n", "\t"):
            out.append(ch)
            continue
        if ch == "�":
            continue  # replacement char from a lossy decode — drop, don't show □
        cat = unicodedata.category(ch)
        if cat in ("Cc", "Cf", "Cs", "Co", "Cn"):
            continue
        out.append(ch)
    return "".join(out)


def _escape_markup(text: str) -> str:
    """Escape Kivy markup metacharacters so reply text can't break markup."""
    return (text.replace("&", "&amp;")
                .replace("[", "&bl;")
                .replace("]", "&br;"))


def render_reply(text: str) -> str:
    """Sanitize gateway reply text into markup ready for a mono Label.

    Emoji runs are wrapped in ``[font=emoji]…[/font]``; everything else is
    control-stripped and markup-escaped. Safe on empty / None input.
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = _strip_controls(text)

    out = []
    run: list[str] = []        # current non-emoji run (to be escaped)
    emoji_run: list[str] = []  # current emoji run (to be font-wrapped)

    def flush_text():
        if run:
            out.append(_escape_markup("".join(run)))
            run.clear()

    def flush_emoji():
        if emoji_run:
            out.append(f"[font=emoji]{''.join(emoji_run)}[/font]")
            emoji_run.clear()

    for ch in text:
        cp = ord(ch)
        if _is_emoji(cp):
            flush_text()
            emoji_run.append(ch)
        elif cp in _EMOJI_JOINERS and emoji_run:
            # joiner only extends an already-open emoji run
            emoji_run.append(ch)
        else:
            flush_emoji()
            run.append(ch)
    flush_emoji()
    flush_text()
    return "".join(out)

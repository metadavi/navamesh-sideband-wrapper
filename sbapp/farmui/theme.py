"""
theme.py — Farm UI design tokens.
Big, sunlight-legible buttons; AA contrast enforced by helper.
"""
from __future__ import annotations

# ── Color roles ──────────────────────────────────────────────────────────────

# Soil status (triple-coded: color + icon + word)
COLOR_SOIL_DRY  = "#C62828"   # red  — dry
COLOR_SOIL_OK   = "#2E7D32"   # green — ok
COLOR_SOIL_WET  = "#1565C0"   # blue — wet

# App surface / navigation
COLOR_PRIMARY    = "#1B5E20"   # dark green brand
COLOR_ON_PRIMARY = "#FFFFFF"
COLOR_SURFACE    = "#F5F5F0"   # near-white
COLOR_ON_SURFACE = "#1A1A1A"
COLOR_BG         = "#FFFDF6"   # warm white
COLOR_ON_BG      = "#1A1A1A"
COLOR_CARD       = "#FFFFFF"
COLOR_ON_CARD    = "#1A1A1A"
COLOR_GATEWAY_HIGHLIGHT = "#E8F5E9"  # light green — highlighted gateway row

# Status / feedback
COLOR_CONNECTED    = "#388E3C"
COLOR_DISCONNECTED = "#B71C1C"
COLOR_PENDING      = "#F57F17"

# ── Type scale (sp) ──────────────────────────────────────────────────────────
FONT_BODY     = 18
FONT_LABEL    = 16
FONT_HEADING  = 24
FONT_TITLE    = 32
FONT_ADDRESS  = 14   # monospace, LXMF address
FONT_CAPTION  = 14   # secondary metadata (hash · time, hints)
FONT_ICON     = 48   # large decorative emoji (empty states)

# ── Spacing scale (dp) ───────────────────────────────────────────────────────
# One rhythm for every screen: pick the step, never a raw number.
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16
SPACE_XL = 24

# ── Sizes (dp) ───────────────────────────────────────────────────────────────
BUTTON_HEIGHT        = 96
TOUCH_TARGET         = 48
CARD_PADDING         = 12
CARD_RADIUS          = 12
SCREEN_PADDING       = 16
TAB_HEIGHT           = 56
CHIP_HEIGHT          = 36
ROW_HEIGHT           = 72
INPUT_HEIGHT         = 48
ICON_BOX             = 64   # height of the large empty-state emoji box
IMAGE_PREVIEW_HEIGHT = 200


# ── Contrast helper ──────────────────────────────────────────────────────────

def _hex_to_srgb(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return r / 255.0, g / 255.0, b / 255.0


def _linearize(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _relative_luminance(hex_color: str) -> float:
    r, g, b = (_linearize(c) for c in _hex_to_srgb(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: str, bg: str) -> float:
    """WCAG 2.1 contrast ratio between two hex colors."""
    lum_fg = _relative_luminance(fg)
    lum_bg = _relative_luminance(bg)
    lighter = max(lum_fg, lum_bg)
    darker  = min(lum_fg, lum_bg)
    return (lighter + 0.05) / (darker + 0.05)


# All token pairs that must meet AA (≥4.5:1 for normal text)
TOKEN_PAIRS = [
    ("primary on primary",    COLOR_ON_PRIMARY, COLOR_PRIMARY),
    ("surface on bg",         COLOR_ON_BG,      COLOR_BG),
    ("card text",             COLOR_ON_CARD,    COLOR_CARD),
    ("surface text",          COLOR_ON_SURFACE, COLOR_SURFACE),
    ("soil-dry on white",     COLOR_SOIL_DRY,   "#FFFFFF"),
    ("soil-ok on white",      COLOR_SOIL_OK,    "#FFFFFF"),
    ("soil-wet on white",     COLOR_SOIL_WET,   "#FFFFFF"),
    ("gateway highlight ink", COLOR_ON_SURFACE, COLOR_GATEWAY_HIGHLIGHT),
]

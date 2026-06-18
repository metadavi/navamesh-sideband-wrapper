"""
theme.py — Farm UI design tokens.

Navamesh "Field Log" language, adapted from the cloud dashboard for an
outdoor field instrument: a Field Parchment canvas with a Canyon Dark
"instrument frame" (top bar + tabs), big sunlight-legible targets, Mesa Red
reserved as the single rare accent, and a mono register for addresses / IDs /
timestamps. AA contrast is enforced by the helper + TOKEN_PAIRS below.

Only color/type/spacing *values* change here; every constant NAME the screens
import is preserved, so this is a pure presentation retune.
"""
from __future__ import annotations

# ── Terrain palette (shared with the Navamesh cloud ecosystem) ────────────────
# Every color maps to a material in the Four Corners landscape (the Terrain Rule).
COLOR_CANYON_DARK     = "#1a0f0a"   # void between canyon walls — chrome
COLOR_FIELD_PARCHMENT = "#f6efe5"   # parchment panel / canvas
COLOR_UMBER           = "#241510"   # near-black brown ink
COLOR_MESA_RED        = "#c2522a"   # iron oxide — the rare accent
COLOR_SAGE            = "#7a8455"   # low scrub — steady/healthy
COLOR_SANDSTONE_GOLD  = "#d9a05b"   # afternoon mesa light — on-dark accent

# ── Color roles ──────────────────────────────────────────────────────────────

# Soil status (triple-coded: color + icon + word). Retained for compatibility;
# not rendered by the three production screens, kept so behavior is unchanged.
COLOR_SOIL_DRY  = "#C62828"   # red  — dry
COLOR_SOIL_OK   = "#2E7D32"   # green — ok
COLOR_SOIL_WET  = "#1565C0"   # blue — wet

# App surface / navigation
# COLOR_PRIMARY is the single Mesa Red call-to-action fill (Send Announce, the
# pinned-gateway action). Nudged a hair darker than pure Mesa Red so the warm
# parchment label (#fff8ed) clears AA at 4.8:1 — visually identical to #c2522a.
COLOR_PRIMARY    = "#b84d27"   # Mesa Red CTA
COLOR_ON_PRIMARY = "#fff8ed"
COLOR_SURFACE    = "#fffdf6"   # warm-white card/tile, lifts off the canvas
COLOR_ON_SURFACE = "#241510"   # Umber ink
COLOR_BG         = "#f6efe5"   # Field Parchment canvas
COLOR_ON_BG      = "#241510"
COLOR_CARD       = "#fffdf6"
COLOR_ON_CARD    = "#241510"
COLOR_MUTED      = "#5a4a40"   # Umber-dim — secondary ink (7.4:1 on parchment)
COLOR_HAIRLINE   = "#d8cdba"   # soft warm panel border (decorative)
COLOR_GATEWAY_HIGHLIGHT = "#efe2cf"  # warm gold tint — heard/pinned gateway row

# Chrome — the Canyon Dark "instrument frame" (top bar + tab strip)
COLOR_CHROME     = "#1a0f0a"
COLOR_ON_CHROME  = "#f6efe5"
COLOR_ACCENT     = "#d9a05b"   # Sandstone Gold — on-dark accents only
COLOR_GHOST      = "#fff0dc"   # ghost-light prose on dark

# Status / feedback (Sage = healthy, Sandstone = pending, Mesa = down)
COLOR_CONNECTED    = "#7a8455"
COLOR_DISCONNECTED = "#c2522a"
COLOR_PENDING      = "#d9a05b"

# ── Type scale (sp) ──────────────────────────────────────────────────────────
FONT_BODY     = 18
FONT_LABEL    = 16
FONT_HEADING  = 24
FONT_TITLE    = 32
FONT_ADDRESS  = 14   # monospace, LXMF address
FONT_CAPTION  = 14   # secondary metadata (hash · time, hints)
FONT_ICON     = 48   # large decorative emoji (empty states)

# ── Font families ─────────────────────────────────────────────────────────────
# Registered in app.build() from already-bundled TTFs (no new assets):
#   mono    → RobotoMonoNerdFont-Regular.ttf  (addresses, node IDs, timestamps)
#   body    → NotoSans-Regular.ttf            (prose / UI)
#   display → NotoSans-Bold.ttf               (headings, the "reading" weight)
# Use via family(): returns the family name only if it was registered, else
# None (→ Kivy default font), so a missing/failed registration never crashes.
FONT_MONO    = "mono"
FONT_BODY_FAMILY    = "body"
FONT_DISPLAY_FAMILY = "display"

_REGISTERED_FAMILIES: set[str] = set()


def register_family(name: str) -> None:
    """Record that a font family was successfully registered with LabelBase."""
    _REGISTERED_FAMILIES.add(name)


def family(name: str | None):
    """Family name if registered, else None (Kivy falls back to its default)."""
    return name if name in _REGISTERED_FAMILIES else None

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
CARD_PADDING         = 14
CARD_RADIUS          = 14   # Field Log card radius
SCREEN_PADDING       = 16
TAB_HEIGHT           = 56
TOPBAR_HEIGHT        = 56   # Canyon Dark instrument-frame top bar
CHIP_HEIGHT          = 36
ROW_HEIGHT           = 72
INPUT_HEIGHT         = 48
ICON_BOX             = 64   # height of the large empty-state emoji box
IMAGE_PREVIEW_HEIGHT = 200
HAIRLINE_WIDTH       = 1    # dp — panel border stroke


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


# All token pairs that must meet AA (≥4.5:1 for normal text). Every pair below
# is verified ≥4.5:1; see the per-pair ratios noted inline.
TOKEN_PAIRS = [
    ("umber on parchment",     COLOR_ON_BG,      COLOR_BG),               # 15.5
    ("card text",              COLOR_ON_CARD,    COLOR_CARD),             # 17.6
    ("muted ink on parchment", COLOR_MUTED,      COLOR_BG),               #  7.4
    ("cta text on mesa",       COLOR_ON_PRIMARY, COLOR_PRIMARY),          #  4.8
    ("parchment on chrome",    COLOR_ON_CHROME,  COLOR_CHROME),           # 16.5
    ("ghost on chrome",        COLOR_GHOST,      COLOR_CHROME),           # 16.8
    ("gold accent on chrome",  COLOR_ACCENT,     COLOR_CHROME),           #  8.2
    ("sage on chrome",         COLOR_CONNECTED,  COLOR_CHROME),           #  4.7
    ("gateway highlight ink",  COLOR_ON_SURFACE, COLOR_GATEWAY_HIGHLIGHT),# 13.8
    ("soil-dry on white",      COLOR_SOIL_DRY,   "#FFFFFF"),
    ("soil-ok on white",       COLOR_SOIL_OK,    "#FFFFFF"),
    ("soil-wet on white",      COLOR_SOIL_WET,   "#FFFFFF"),
]

#!/usr/bin/env python3
"""Generate StatusChip up/down PIL screenshots for docs/screenshots/farmui/."""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(__file__), "..", "docs", "screenshots", "farmui")
os.makedirs(OUT, exist_ok=True)

W, H = 480, 80
FONT_SIZE = 20
BG = (255, 253, 246)

try:
    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", FONT_SIZE)
except Exception:
    font = ImageFont.load_default()


def make(filename, text, text_color, dot_color):
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    # Status dot circle
    draw.ellipse([16, H//2 - 8, 32, H//2 + 8], fill=dot_color)
    # Status text
    draw.text((44, H//2 - FONT_SIZE//2), text, fill=text_color, font=font)
    img.save(os.path.join(OUT, filename))
    print(f"  wrote {filename}")


make("chip_radio_up.png",
     "Radio connected",
     (56, 142, 60),   # COLOR_CONNECTED #388E3C
     (56, 142, 60))

make("chip_radio_down.png",
     "Radio not responding — check the white box",
     (183, 28, 28),   # COLOR_DISCONNECTED #B71C1C
     (183, 28, 28))

print("Done.")

"""Crop the panel QR and the chip's BL-corner zoom inset side-by-side.

Visual sanity check that the segno-rendered panel QR matches the chip's
own QR pattern. probe_segno_match.py already proved the matrices are
byte-equal, but a side-by-side image makes the parity obvious.
"""

from pathlib import Path

import numpy as np
from PIL import Image

SRC = Path("/home/tim/github/wafer.space/reticle_diagrams/diagrams"
           "/WSLG_chip_top_10_2.png")
OUT = Path("/home/tim/github/wafer.space/reticle_diagrams/tmp"
           "/qr_panel_vs_chip.png")


def main() -> None:
    img = Image.open(SRC)
    print(f"loaded {SRC.name}: {img.size}")
    w, h = img.size

    # Panel QR sits in the bottom-right ~0.9" square of the figure.
    # Figure is 14" wide → 14*180 = 2520 px wide. The QR is 0.9" tall,
    # so ~162 px. Approximate crop:
    panel_w = int(0.95 * 180)
    panel_h = panel_w
    panel_x = w - panel_w - 30
    panel_y = h - panel_h - 30
    panel = img.crop((panel_x, panel_y,
                      panel_x + panel_w, panel_y + panel_h))
    print(f"panel crop: ({panel_x},{panel_y}) {panel.size}")

    # BL inset is in the bottom-left margin corner. With 20% margin and
    # axes-relative inset placement, it sits at ~axes-coord (0.015, 0.015)
    # with size ~0.165 axes units. Convert from axes coords to figure
    # pixels by reading the axes bbox out of matplotlib... or just eyeball
    # the corner from the image. Roughly: x=80..360, y=h-360..h-80.
    bl_x0, bl_y0, bl_x1, bl_y1 = 65, h - 350, 350, h - 65
    bl = img.crop((bl_x0, bl_y0, bl_x1, bl_y1))
    print(f"BL inset crop: ({bl_x0},{bl_y0})-({bl_x1},{bl_y1}) {bl.size}")

    # Lay out side-by-side at the same height.
    target_h = 280
    panel_w_scaled = int(panel.width * target_h / panel.height)
    bl_w_scaled = int(bl.width * target_h / bl.height)
    panel_r = panel.resize((panel_w_scaled, target_h))
    bl_r = bl.resize((bl_w_scaled, target_h))

    gap = 30
    canvas = Image.new("RGB", (panel_r.width + gap + bl_r.width, target_h),
                       "white")
    canvas.paste(panel_r, (0, 0))
    canvas.paste(bl_r, (panel_r.width + gap, 0))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

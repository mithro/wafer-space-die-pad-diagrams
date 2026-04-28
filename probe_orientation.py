"""Crop the four corners of the shipping/die_renders/WSLG.png to find
the QR cell and the logo cell positions.

The user says the chip should display with the QR in the top-right
corner, but our render has the QR in the bottom-left. Either the
shipping render is rotated relative to ours, or the GDS positions
are different. Cropping each corner of the reference at high
resolution lets us read which cell sits where.
"""

from pathlib import Path

from PIL import Image

REF = Path("/home/tim/github/wafer.space/shipping/die_renders/WSLG.png")
OUT = Path("/home/tim/github/wafer.space/reticle_diagrams/tmp")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    img = Image.open(REF)
    w, h = img.size
    print(f"reference image: {w}x{h}")
    crop_size = min(w, h) // 4
    crops = {
        "tl": img.crop((0, 0, crop_size, crop_size)),
        "tr": img.crop((w - crop_size, 0, w, crop_size)),
        "bl": img.crop((0, h - crop_size, crop_size, h)),
        "br": img.crop((w - crop_size, h - crop_size, w, h)),
    }
    for k, c in crops.items():
        out = OUT / f"shipping_WSLG_corner_{k}.png"
        c.save(out)
        print(f"  wrote {out}")


if __name__ == "__main__":
    main()

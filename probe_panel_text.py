"""Crop just the bottom-right info panel of a diagram to read the text.

The displayed thumbnail of TQVA looked like 'slot 8.5x8.5' which would
be wildly wrong — every public reticle slot is 0.5/1/2 units. Probably
a font-rendering artifact at small thumbnail sizes; this probe pulls
the panel out at native PNG resolution so we can read the digits.
"""

from pathlib import Path

from PIL import Image

OUT_DIR = Path(__file__).resolve().parent / "tmp"
DIAGRAMS = Path(__file__).resolve().parent / "diagrams"

TARGETS = ("TQVA_chip_top_14_8", "WSLG_chip_top_10_2", "TRID_TOP_14_2")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in TARGETS:
        src = DIAGRAMS / f"{name}.png"
        if not src.exists():
            print(f"skip {name}: no png")
            continue
        img = Image.open(src)
        w, h = img.size
        # Bottom-right panel is roughly 2.5" x 1.5" => 450x270 px at 180dpi.
        crop = img.crop((w - 480, h - 220, w - 10, h - 10))
        out = OUT_DIR / f"panel_{name}.png"
        crop.save(out)
        print(f"{name}: image {w}x{h}, panel saved to {out}")


if __name__ == "__main__":
    main()

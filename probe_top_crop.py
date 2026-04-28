"""Crop the top portion of each smoketest design to see if any pad
label rotated 90° at the top edge bleeds into the title area."""

from pathlib import Path

from PIL import Image

DIA = Path(__file__).resolve().parent / "diagrams"
OUT = Path(__file__).resolve().parent / "tmp"

TARGETS = [
    "WSLG_chip_top_10_2",
    "TRID_TOP_14_2",
    "TQVA_chip_top_14_8",
    "ISHI_ISHI-KAI_WS_RUN1_12_4",
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in TARGETS:
        src = DIA / f"{name}.png"
        if not src.exists():
            continue
        img = Image.open(src)
        w, h = img.size
        crop = img.crop((0, 0, w, int(h * 0.30)))
        out = OUT / f"top_{name}.png"
        crop.save(out)
        print(f"{name} {w}x{h} → {out}")


if __name__ == "__main__":
    main()

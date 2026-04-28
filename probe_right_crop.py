"""Crop the right edge to inspect for label overflow there."""

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
        crop = img.crop((int(w * 0.75), 0, w, int(h * 0.85)))
        out = OUT / f"right_{name}.png"
        crop.save(out)
        print(f"{name} → {out} ({crop.size})")


if __name__ == "__main__":
    main()

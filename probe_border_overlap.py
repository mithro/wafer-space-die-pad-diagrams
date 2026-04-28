"""Crop just the top-edge and bottom-edge regions of WSLG/TRID
including the chip outline so we can see whether pad labels actually
cross the black border."""

from pathlib import Path

from PIL import Image

DIA = Path(__file__).resolve().parent / "diagrams"
OUT = Path(__file__).resolve().parent / "tmp"

TARGETS = ["WSLG_chip_top_10_2", "TRID_TOP_14_2"]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in TARGETS:
        src = DIA / f"{name}.png"
        if not src.exists():
            continue
        img = Image.open(src)
        w, h = img.size
        # Top: a 30%-tall band at the top, full width
        top = img.crop((0, 0, w, int(h * 0.30)))
        top.save(OUT / f"border_top_{name}.png")
        # Bottom: 30% band above the panel strip
        bot = img.crop((0, int(h * 0.55), w, int(h * 0.85)))
        bot.save(OUT / f"border_bot_{name}.png")
        print(f"{name} top→border_top_{name}.png  bot→border_bot_{name}.png")


if __name__ == "__main__":
    main()

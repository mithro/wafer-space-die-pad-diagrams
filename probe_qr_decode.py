"""Decode the extracted 21x21 QR matrix to find the encoded payload.

probe_qr_matrix.py recovered a clean binary matrix from
gf180mcu_ws_ip__id.gds; we now render that matrix as a high-contrast
black-and-white PNG and feed it to cv2.QRCodeDetector. The KLayout
render included the wafer.space cell-frame dither, which confused the
decoder, but a flat black/white render of the raw module grid is the
simplest possible input for a QR detector.

This is purely diagnostic — we do not need the decoded string to render
the QR identically (the matrix alone is enough). But knowing the
payload lets us put it in a comment so future readers understand what
the chip QR actually advertises.
"""

from pathlib import Path

import numpy as np
from PIL import Image

# Matrix from probe_qr_matrix.py (top-down rows, "#" = on, "." = off).
QR = (
    "#######..##.#.#######",
    "#.....#...##..#.....#",
    "#.###.#....##.#.###.#",
    "#.###.#..#.##.#.###.#",
    "#.###.#.##....#.###.#",
    "#.....#..##.#.#.....#",
    "#######.#.#.#.#######",
    "........###..........",
    "..##..####.#.##.#....",
    "..##...####..#.#..#..",
    "########.#.#.#.###..#",
    ".##.#..###.####....#.",
    "#...###.##.##...#.#..",
    "........#.####.#.#..#",
    "#######.#####...#..#.",
    "#.....#.......#...#.#",
    "#.###.#..###..#..#..#",
    "#.###.#.#.#.#.#.#..#.",
    "#.###.#.#..#....#.#..",
    "#.....#..###.#..##.##",
    "#######.....#..#...#.",
)

OUT = Path(__file__).resolve().parent / "tmp" / "ws_ip_id_clean.png"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    n = len(QR)
    # 20 px per module, plus a 4-module quiet zone on every side
    # (the QR spec requires at least 4 modules of white border for
    # decoders to find the symbol reliably).
    px = 20
    quiet = 4
    side = (n + 2 * quiet) * px
    arr = np.full((side, side), 255, dtype=np.uint8)
    for r, row in enumerate(QR):
        for c, ch in enumerate(row):
            if ch == "#":
                y = (r + quiet) * px
                x = (c + quiet) * px
                arr[y:y + px, x:x + px] = 0
    Image.fromarray(arr, mode="L").save(OUT)
    print(f"wrote clean render to {OUT} ({side}x{side} px)")

    # Try decoders. opencv first (built in to opencv-python), then any
    # others that may have been installed.
    decoded = None
    try:
        import cv2  # type: ignore
        img = cv2.imread(str(OUT), cv2.IMREAD_GRAYSCALE)
        det = cv2.QRCodeDetector()
        data, _, _ = det.detectAndDecode(img)
        if data:
            decoded = ("cv2", data)
        else:
            print("cv2 returned empty — trying detect-then-decode")
            ok, points = det.detect(img)
            if ok:
                data, _ = det.decode(img, points)
                if data:
                    decoded = ("cv2.decode-after-detect", data)
    except ImportError:
        print("cv2 unavailable")

    if decoded is None:
        try:
            from pyzbar.pyzbar import decode  # type: ignore
            results = decode(Image.open(OUT))
            for r in results:
                if r.type == "QRCODE":
                    decoded = ("pyzbar", r.data.decode("utf-8", errors="replace"))
                    break
        except ImportError:
            print("pyzbar unavailable")

    if decoded:
        print(f"\nDECODED via {decoded[0]}: {decoded[1]!r}")
    else:
        print("\nNo decoder succeeded.")


if __name__ == "__main__":
    main()

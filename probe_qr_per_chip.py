"""Find each chip's actual QR cell in reticle.oas and extract its matrix.

The chip-template's QR encodes a placeholder ("00000000"); wafer.space
customises the QR per project before assembling reticle.oas. The user
told us this happens during the precheck, so each chip in
reticle.oas should contain a different QR.

Strategy: scan every cell in the layout database and find ones that
look like the ws-ip ID cell (142.8 µm Metal5 squares only). Group by
top-level chip ancestor and dump the matrix + decoded payload for
each. This is much faster than recursing through every chip's full
hierarchy because we lookup cells by name first.
"""

import hashlib
import time
from collections import Counter
from pathlib import Path

import klayout.db as kdb

OAS = Path("/home/tim/github/wafer.space/ws-run1/layout/reticle.oas")
TMP = Path(__file__).resolve().parent / "tmp"

WSIP_QR_INSET_UM = (40.0, 50.0)
WSIP_CELL_UM = 142.8  # exact cell extent from the LEF (143 was rounded)
METAL5_LAYER = (81, 0)


def render_clean_png(matrix: list[list[int]], out: Path,
                     px: int = 20, quiet: int = 4) -> None:
    """Render a binary matrix as a B/W PNG (for cv2 decoding)."""
    import numpy as np
    from PIL import Image

    n = len(matrix)
    side = (n + 2 * quiet) * px
    arr = np.full((side, side), 255, dtype=np.uint8)
    for r, row in enumerate(matrix):
        for c, bit in enumerate(row):
            if bit:
                y = (r + quiet) * px
                x = (c + quiet) * px
                arr[y:y + px, x:x + px] = 0
    Image.fromarray(arr, mode="L").save(out)


def matrix_to_str(matrix: list[list[int]]) -> str:
    return "\n".join("".join("#" if b else "." for b in row) for row in matrix)


def matrix_hash(matrix: list[list[int]]) -> str:
    return hashlib.sha1(matrix_to_str(matrix).encode()).hexdigest()[:10]


def decode_matrix(matrix: list[list[int]], scratch: Path) -> str | None:
    try:
        import cv2  # type: ignore
    except ImportError:
        return None
    render_clean_png(matrix, scratch)
    img = cv2.imread(str(scratch), cv2.IMREAD_GRAYSCALE)
    det = cv2.QRCodeDetector()
    data, _, _ = det.detectAndDecode(img)
    return data or None


def matrix_from_cell(cell: kdb.Cell, layout: kdb.Layout
                     ) -> tuple[list[list[int]], int] | None:
    """Build a matrix from a cell whose shapes ARE the QR modules.

    Walks the cell's Metal5 shapes recursively (so it picks up any
    sub-cell instances inside the QR cell), but the cell tree under
    the QR cell is small (just the modules themselves, plus maybe a
    finder-pattern sub-cell).
    """
    li = layout.layer(*METAL5_LAYER)
    rects: list[tuple[int, int, int, int]] = []
    it = cell.begin_shapes_rec(li)
    while not it.at_end():
        b = it.shape().bbox().transformed(it.trans())
        rects.append((b.left, b.bottom, b.right, b.top))
        it.next()
    if not rects:
        return None
    widths = sorted({r[2] - r[0] for r in rects})
    module = widths[0]
    if module <= 0:
        return None

    bb = cell.bbox()
    n = round(bb.width() / module)
    if n < 5:
        return None
    matrix = [[0] * n for _ in range(n)]
    for x0, y0, x1, y1 in rects:
        cx = (x0 + x1) // 2
        cy = (y0 + y1) // 2
        col = (cx - bb.left) // module
        row_from_bottom = (cy - bb.bottom) // module
        if 0 <= col < n and 0 <= row_from_bottom < n:
            matrix[n - 1 - row_from_bottom][col] = 1
    return matrix, module


def main() -> None:
    TMP.mkdir(parents=True, exist_ok=True)
    layout = kdb.Layout()
    print(f"Reading {OAS} ...", flush=True)
    t0 = time.time()
    layout.read(str(OAS))
    print(f"  loaded in {time.time() - t0:.1f}s — {layout.cells()} cells",
          flush=True)

    # Find every cell that looks like a QR cell: 142.8 µm square,
    # contains only Metal5 modules of a single small size. Print
    # the candidates so we know what to look for.
    print("\nLooking for QR-shaped cells (~142.8 µm Metal5 grid)...",
          flush=True)
    candidates: list[tuple[str, int, int, int]] = []
    target_dbu = round(WSIP_CELL_UM / layout.dbu)  # 142800
    li_m5 = layout.layer(*METAL5_LAYER)
    for cell in layout.each_cell():
        bb = cell.bbox()
        # Within ±2 dbu of the target square size.
        if abs(bb.width() - target_dbu) > 2 or abs(bb.height() - target_dbu) > 2:
            continue
        # Count Metal5 shapes — direct only, fast.
        n_m5 = sum(1 for _ in cell.shapes(li_m5).each())
        candidates.append((cell.name, bb.width(), bb.height(), n_m5))

    print(f"found {len(candidates)} candidate cells", flush=True)
    for name, w, h, n in sorted(candidates):
        print(f"  {name}  {w}x{h} dbu  {n} Metal5 shapes", flush=True)

    # Decode each candidate's matrix (recursive walk needed because the
    # cell may instantiate a finder-pattern sub-cell rather than draw
    # everything directly).
    print("\nDecoding candidate matrices:", flush=True)
    scratch = TMP / "probe_chip_qr.png"
    by_hash: dict[str, list[tuple[str, str | None]]] = {}
    for name, _, _, _ in sorted(candidates):
        cell = layout.cell(name)
        if cell is None:
            continue
        result = matrix_from_cell(cell, layout)
        if result is None:
            print(f"  {name}: NO MATRIX", flush=True)
            continue
        matrix, module = result
        h = matrix_hash(matrix)
        try:
            decoded = decode_matrix(matrix, scratch)
        except Exception as exc:
            decoded = f"<decode error: {exc}>"
        by_hash.setdefault(h, []).append((name, decoded))
        print(f"  {name:<40} {len(matrix)}x{len(matrix)}  "
              f"hash={h}  payload={decoded!r}", flush=True)

    print(f"\n{len(by_hash)} unique matrices across "
          f"{sum(len(v) for v in by_hash.values())} candidates",
          flush=True)
    for h, entries in by_hash.items():
        print(f"  hash {h}: {len(entries)}", flush=True)
        for name, decoded in entries:
            print(f"    {name}  payload={decoded!r}", flush=True)


if __name__ == "__main__":
    main()

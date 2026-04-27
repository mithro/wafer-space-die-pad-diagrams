"""Extract the QR-module matrix from gf180mcu_ws_ip__id.gds.

Metal5 rectangles in the cell each represent one QR module. By:
  1. enumerating every Metal5 shape,
  2. finding the smallest square (= one-module size),
  3. snapping each shape's centre to a module grid,

we recover the QR's binary matrix without needing an image decoder. The
matrix is what we actually need to render an identical QR with
matplotlib — we don't need to know what string it decodes to.

Print the matrix as a Python literal so it can be pasted into
make_diagrams.py as a constant.
"""

from pathlib import Path

import klayout.db as kdb

GDS = Path("/home/tim/github/mithro/gf180mcu-project-template"
           "/ip/gf180mcu_ws_ip__id/gds/gf180mcu_ws_ip__id.gds")

METAL5_LAYER = (81, 0)


def main() -> None:
    layout = kdb.Layout()
    layout.read(str(GDS))
    top = next(iter(layout.top_cells()))
    li = layout.layer(*METAL5_LAYER)

    # Collect every Metal5 rectangle's bbox in DBU (integer micrometres).
    rects: list[tuple[int, int, int, int]] = []
    it = top.begin_shapes_rec(li)
    while not it.at_end():
        bb = it.shape().bbox().transformed(it.trans())
        rects.append((bb.left, bb.bottom, bb.right, bb.top))
        it.next()

    if not rects:
        print("No Metal5 shapes found")
        return

    print(f"Metal5 rectangles: {len(rects)}")
    widths = sorted({r[2] - r[0] for r in rects})
    heights = sorted({r[3] - r[1] for r in rects})
    print(f"unique widths (DBU):  {widths[:8]}{' ...' if len(widths) > 8 else ''}")
    print(f"unique heights (DBU): {heights[:8]}{' ...' if len(heights) > 8 else ''}")

    # Module size = smallest rectangle width (the single 1x1 squares).
    # The finder patterns include 3x3 and 7x7 sub-rectangles too, but
    # the cell still emits each individual module as a separate shape,
    # so the smallest width is the module pitch in DBU.
    module = widths[0]
    dbu = layout.dbu
    print(f"module size: {module} DBU = {module * dbu:.3f} um")

    # Cell extent in DBU.
    bb = top.bbox()
    print(f"cell bbox (DBU): "
          f"({bb.left}, {bb.bottom}) -> ({bb.right}, {bb.top})  "
          f"size {bb.width()} x {bb.height()}")

    # Determine the module-grid origin and dimension. The finder patterns
    # are 7x7 modules; a Version-1 QR is 21x21 modules total. The cell is
    # 142.8 um → 1428 DBU → 21 modules at 68 DBU? Let's compute.
    n_w = round(bb.width() / module)
    n_h = round(bb.height() / module)
    print(f"grid: {n_w} x {n_h} modules")

    # Build a NxN matrix of 1/0. A grid cell is 'on' if any rectangle
    # covers its centre.
    matrix = [[0] * n_w for _ in range(n_h)]
    for x0, y0, x1, y1 in rects:
        # The cell origin is bb.left, bb.bottom. Convert to module index.
        for r in range(n_h):
            cy = bb.bottom + (r + 0.5) * module
            if not (y0 < cy < y1):
                continue
            for c in range(n_w):
                cx = bb.left + (c + 0.5) * module
                if x0 < cx < x1:
                    matrix[r][c] = 1

    # Print top-down (row 0 = top of QR). GDS y grows up, but a printed
    # QR reads top-to-bottom — so flip vertically when displaying.
    print("\nMatrix (row 0 is top of QR, '#' = on):")
    for r in reversed(range(n_h)):
        print("  " + "".join("#" if matrix[r][c] else "." for c in range(n_w)))

    # Sanity check: the three finder patterns should sit at top-left,
    # top-right, bottom-left, each a 7x7 with a 5x5 white ring inside a
    # 7x7 black border, centre 3x3 black. We just verify the corners are
    # filled where expected.
    def block(r0: int, c0: int) -> bool:
        return all(matrix[r0 + dr][c0 + dc]
                   for dr in range(7) for dc in range(7)
                   if dr in (0, 6) or dc in (0, 6))
    print(f"\nfinder TL (rows top): {block(n_h - 7, 0)}")
    print(f"finder TR (rows top): {block(n_h - 7, n_w - 7)}")
    print(f"finder BL (rows bot): {block(0, 0)}")

    # Output the matrix as a Python tuple-of-strings literal in TOP-DOWN
    # reading order (so the printed and stored representations match).
    print("\nPython literal (top-down rows, '#' = on, '.' = off):")
    print("WSIP_QR_MATRIX = (")
    for r in reversed(range(n_h)):
        s = "".join("#" if matrix[r][c] else "." for c in range(n_w))
        print(f'    "{s}",')
    print(")")


if __name__ == "__main__":
    main()

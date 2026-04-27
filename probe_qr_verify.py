"""Verify segno+the project-mask dict reproduces every chip's QR matrix.

Sanity check that runs after make_diagrams.py changes touch the QR
parameters. For each design in reticle.oas:
  1. extract the actual QR matrix from the chip's QR cell,
  2. compute the matrix segno would emit for our (data, mask, mode, ec),
  3. compare them.

Print PASS / FAIL per chip and an exit-style summary so this can be
wired into CI later.
"""

import sys
import time
from pathlib import Path

import klayout.db as kdb
import segno

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_diagrams import (  # noqa: E402
    WSIP_QR_DATA_PREFIX, WSIP_QR_ERROR, WSIP_QR_MODE,
    WSIP_QR_PROJECT_MASKS, OAS, _project_code,
)

# The actual ws-ip ID cell in the GDS is 142.8 µm square (see the LEF
# at gf180mcu_ws_ip__id.lef). make_diagrams uses a rounded 143.0 for
# its visual highlight frame; the verify probe needs the exact size to
# match cells by bbox.
WSIP_CELL_UM_EXACT = 142.8
METAL5_LAYER = (81, 0)


def matrix_from_cell(cell: kdb.Cell, layout: kdb.Layout
                     ) -> tuple[str, ...] | None:
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
    bb = cell.bbox()
    n = round(bb.width() / module)
    matrix = [[0] * n for _ in range(n)]
    for x0, y0, x1, y1 in rects:
        cx = (x0 + x1) // 2
        cy = (y0 + y1) // 2
        col = (cx - bb.left) // module
        rb = (cy - bb.bottom) // module
        if 0 <= col < n and 0 <= rb < n:
            matrix[n - 1 - rb][col] = 1
    return tuple("".join("#" if b else "." for b in r) for r in matrix)


def segno_matrix(data: str, mask: int | None) -> tuple[str, ...]:
    qr = segno.make(data, error=WSIP_QR_ERROR, mask=mask,
                    mode=WSIP_QR_MODE, version=1, boost_error=False)
    return tuple("".join("#" if b else "." for b in r) for r in qr.matrix)


def main() -> None:
    layout = kdb.Layout()
    print(f"Reading {OAS} ...", flush=True)
    t0 = time.time()
    layout.read(str(OAS))
    print(f"  loaded in {time.time() - t0:.1f}s", flush=True)

    target_dbu = round(WSIP_CELL_UM_EXACT / layout.dbu)
    li_m5 = layout.layer(*METAL5_LAYER)

    top = next(iter(layout.top_cells()))
    skip = {"RETICLE_FILL", "TEXT"}
    designs: list[str] = []
    for inst in top.each_inst():
        n = inst.cell.name
        if n in skip or n in designs:
            continue
        designs.append(n)

    # Map QR cell → project via caller-walking.
    qr_cells: list[kdb.Cell] = []
    for cell in layout.each_cell():
        bb = cell.bbox()
        if abs(bb.width() - target_dbu) > 2 or abs(bb.height() - target_dbu) > 2:
            continue
        if sum(1 for _ in cell.shapes(li_m5).each()) == 0:
            continue
        qr_cells.append(cell)

    design_indices = {layout.cell(d).cell_index(): _project_code(d)
                      for d in designs}
    proj_to_qr: dict[str, kdb.Cell] = {}
    for qr in qr_cells:
        seen: set[int] = set()
        stack: list[int] = [qr.cell_index()]
        while stack:
            idx = stack.pop()
            if idx in seen:
                continue
            seen.add(idx)
            if idx in design_indices:
                proj_to_qr.setdefault(design_indices[idx], qr)
                continue
            for caller in layout.cell(idx).caller_cells():
                stack.append(caller)

    fails: list[str] = []
    for proj in sorted(proj_to_qr):
        chip = matrix_from_cell(proj_to_qr[proj], layout)
        data = f"{WSIP_QR_DATA_PREFIX}{proj}"
        mask = WSIP_QR_PROJECT_MASKS.get(proj)
        ours = segno_matrix(data, mask)
        ok = chip == ours
        msg = (f"  {proj:<5} mask={mask!r:<5} data={data!r:<13} "
               f"{'PASS' if ok else 'FAIL'}")
        print(msg, flush=True)
        if not ok:
            fails.append(proj)

    print(f"\n{len(proj_to_qr) - len(fails)}/{len(proj_to_qr)} pass", flush=True)
    if fails:
        sys.exit(1)


if __name__ == "__main__":
    main()

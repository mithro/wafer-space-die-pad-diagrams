"""Find segno parameters matching the chip's per-project QR matrix.

probe_qr_per_chip.py confirmed each chip's QR encodes "G801" + the
4-char project code from the README (e.g. "G801BTAP", "G801WSLG").
We need to find a single (error, mask, mode) combo that segno can use
to reproduce *every* chip's pattern, so render() can derive the data
string from the cell name and let segno render it directly.

For each chip we re-extract the matrix from reticle.oas, then ask
segno to encode the corresponding payload at every (ec, mask, mode)
combination. A combo passes only if it matches every chip — so we
end up with one or more universal parameter sets.
"""

import time
from collections import defaultdict
from pathlib import Path

import klayout.db as kdb
import segno

OAS = Path("/home/tim/github/wafer.space/ws-run1/layout/reticle.oas")
WSIP_CELL_UM = 142.8
METAL5_LAYER = (81, 0)


def matrix_from_cell(cell: kdb.Cell, layout: kdb.Layout
                     ) -> list[list[int]] | None:
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
    return matrix


def matrix_str(matrix) -> tuple[str, ...]:
    """Accept either a 2D list/tuple of ints or a segno QRCode."""
    rows = matrix.matrix if hasattr(matrix, "matrix") else matrix
    return tuple("".join("#" if b else "." for b in row) for row in rows)


def main() -> None:
    layout = kdb.Layout()
    print(f"Reading {OAS} ...", flush=True)
    t0 = time.time()
    layout.read(str(OAS))
    print(f"  loaded in {time.time() - t0:.1f}s", flush=True)

    target_dbu = round(WSIP_CELL_UM / layout.dbu)
    li_m5 = layout.layer(*METAL5_LAYER)

    # Find every QR cell + decode its payload by name (using cv2 like
    # before would be cleaner but we have probe_qr_per_chip.py output
    # for that). For this probe we trust the previously-decoded
    # payload comes from G801<PROJ>: instead, derive it from the chip
    # ancestor's name. To map QR cell → project code, walk top-cell
    # instances and remember which QR cell each chip cell uses.

    top = next(iter(layout.top_cells()))
    # For each top-level chip instance, find its (only) QR cell
    # instance descendant and record the link.
    qr_to_proj: dict[str, str] = {}
    skip = {"RETICLE_FILL", "TEXT"}
    designs: list[str] = []
    for inst in top.each_inst():
        n = inst.cell.name
        if n in skip or n in designs:
            continue
        designs.append(n)
    print(f"{len(designs)} designs", flush=True)

    # Enumerate every QR-shaped cell and tie it back to its design via
    # the design's child-instance set.
    qr_cells: list[kdb.Cell] = []
    for cell in layout.each_cell():
        bb = cell.bbox()
        if abs(bb.width() - target_dbu) > 2 or abs(bb.height() - target_dbu) > 2:
            continue
        if sum(1 for _ in cell.shapes(li_m5).each()) == 0:
            continue
        qr_cells.append(cell)

    # For each design, find the QR cell index that appears as one of
    # its descendants. caller_cells walks UP from the QR cell, so for
    # each QR cell we list its callers; whichever caller leads to a
    # design top-cell gives us the project mapping.
    design_indices = {layout.cell(name).cell_index(): _project_code(name)
                      for name in designs}
    proj_to_qr: dict[str, kdb.Cell] = {}
    for qr in qr_cells:
        # called_cells doesn't help here; we need callers. Walk up
        # callers transitively until we hit a design cell.
        seen: set[int] = set()
        stack: list[int] = [qr.cell_index()]
        while stack:
            idx = stack.pop()
            if idx in seen:
                continue
            seen.add(idx)
            if idx in design_indices:
                proj = design_indices[idx]
                proj_to_qr.setdefault(proj, qr)
                continue
            for caller in layout.cell(idx).caller_cells():
                stack.append(caller)

    # Brute force: for each (ec, mask, mode), see if segno reproduces
    # every chip's matrix.
    print(f"\nProbing segno params across {len(proj_to_qr)} project QRs...",
          flush=True)
    targets: dict[str, tuple[str, ...]] = {}
    for proj, qr in sorted(proj_to_qr.items()):
        matrix = matrix_from_cell(qr, layout)
        if matrix is None:
            continue
        targets[proj] = matrix_str(matrix)
    print(f"  collected {len(targets)} target matrices", flush=True)

    candidates: list[tuple[str, int | None, str | None]] = []
    for ec in ("L", "M", "Q", "H"):
        for mask in (None, *range(8)):
            for mode in (None, "alphanumeric", "byte", "numeric"):
                ok = True
                for proj, target in targets.items():
                    payload = f"G801{proj}"
                    try:
                        qr = segno.make(payload, error=ec, mask=mask,
                                        mode=mode, version=1,
                                        boost_error=False)
                    except Exception:
                        ok = False
                        break
                    if matrix_str(qr) != target:
                        ok = False
                        break
                if ok:
                    candidates.append((ec, mask, mode))
                    print(f"  MATCH ec={ec} mask={mask} mode={mode!r}",
                          flush=True)

    if not candidates:
        print("\nNo single param set matches every chip — trying per-chip...",
              flush=True)
        any_per_chip: dict[str, list[tuple[str, int | None, str | None]]] = {}
        for proj, target in targets.items():
            matches = []
            for ec in ("L", "M", "Q", "H"):
                for mask in (None, *range(8)):
                    for mode in (None, "alphanumeric", "byte", "numeric"):
                        try:
                            qr = segno.make(
                                f"G801{proj}", error=ec, mask=mask,
                                mode=mode, version=1, boost_error=False)
                        except Exception:
                            continue
                        if matrix_str(qr) == target:
                            matches.append((ec, mask, mode))
            any_per_chip[proj] = matches
            if matches:
                print(f"  {proj}: matches {matches[:2]}"
                      f"{' ...' if len(matches) > 2 else ''}",
                      flush=True)
            else:
                print(f"  {proj}: no segno match", flush=True)
        # Surface common params across all chips.
        common = set(any_per_chip[next(iter(any_per_chip))])
        for s in any_per_chip.values():
            common &= set(s)
        print(f"\ncommon params across all: {sorted(common)}", flush=True)


def _project_code(cell_name: str) -> str:
    return cell_name.split("_", 1)[0]


if __name__ == "__main__":
    main()

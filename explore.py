"""Print the top-level cell hierarchy of the reticle using KLayout's db module."""

import time
from pathlib import Path

import klayout.db as kdb

OAS = Path(__file__).resolve().parent.parent / "ws-run1" / "layout" / "reticle.oas"


def main() -> None:
    layout = kdb.Layout()
    print(f"Reading {OAS} ...")
    t0 = time.time()
    layout.read(str(OAS))
    print(f"  loaded in {time.time() - t0:.1f}s — "
          f"{layout.cells()} cells, dbu={layout.dbu} um")

    tops = [layout.cell(i) for i in layout.each_top_cell()]
    print(f"\nTop-level cells ({len(tops)}):")
    for cell in tops:
        bb = cell.bbox()
        print(f"  {cell.name}: bbox=({bb.left * layout.dbu:.1f},{bb.bottom * layout.dbu:.1f}) "
              f".. ({bb.right * layout.dbu:.1f},{bb.top * layout.dbu:.1f})  "
              f"size={bb.width() * layout.dbu:.1f} x {bb.height() * layout.dbu:.1f} um")

    # For the first top cell, enumerate direct child instances by cell name
    top = tops[0]
    print(f"\nDirect instances inside {top.name!r}:")
    counts: dict[str, int] = {}
    first_origin: dict[str, tuple[float, float]] = {}
    for inst in top.each_inst():
        name = inst.cell.name
        counts[name] = counts.get(name, 0) + 1
        if name not in first_origin:
            t = inst.trans
            first_origin[name] = (t.disp.x * layout.dbu, t.disp.y * layout.dbu)
    for name in sorted(counts):
        x, y = first_origin[name]
        bb = layout.cell_by_name(name)
        bb = layout.cell(bb).bbox() if bb >= 0 else None
        size = (f"{bb.width() * layout.dbu:.0f} x {bb.height() * layout.dbu:.0f} um"
                if bb else "?")
        print(f"  {name}  x{counts[name]}  first-origin=({x:.1f},{y:.1f})  cell-size={size}")


if __name__ == "__main__":
    main()

"""Figure out which sub-cells (or layers) draw the QR code and the
wafer.space logo on each reticle slot.

Both elements are part of the standard tapeout template the reticle
applies to every project, so they should appear as named child cells of
the design top-cell — or at least as shapes on a specific layer that
only the template populates. Printing the child-cell names and bbox
positions lets us identify which ones to call out in render().
"""

from pathlib import Path

import klayout.db as kdb

from make_diagrams import OAS


def main() -> None:
    layout = kdb.Layout()
    print(f"Reading {OAS} ...")
    layout.read(str(OAS))

    target = "WSLG_chip_top_10_2"
    cell = layout.cell(target)
    bb = cell.bbox()
    x0 = bb.left * layout.dbu
    y0 = bb.bottom * layout.dbu
    x1 = bb.right * layout.dbu
    y1 = bb.top * layout.dbu
    print(f"\n{target}: {x0:.1f},{y0:.1f} -> {x1:.1f},{y1:.1f}  "
          f"({x1 - x0:.0f} x {y1 - y0:.0f} um)")

    print("\nTop-level child instances (grouped by cell name, count + largest bbox):")
    seen: dict[str, list[tuple[float, float, float, float]]] = {}
    for inst in cell.each_inst():
        ib = inst.bbox()
        key = inst.cell.name
        seen.setdefault(key, []).append(
            (ib.left * layout.dbu, ib.bottom * layout.dbu,
             ib.right * layout.dbu, ib.top * layout.dbu)
        )
    for name, bbs in sorted(seen.items()):
        w = max(b[2] - b[0] for b in bbs)
        h = max(b[3] - b[1] for b in bbs)
        print(f"  {name}   x{len(bbs)}   max bbox {w:.0f}x{h:.0f} um")

    # Any cell whose NAME hints at logo/qr/marker — look anywhere in the layout.
    print("\nCells whose name mentions logo / qr / ws / fill / frame / mark / align / rocket:")
    patterns = ("logo", "qr", "wafer", "ws_", "rocket",
                "frame", "mark", "align", "identif")
    matches = []
    for c in layout.each_cell():
        nm = c.name.lower()
        if any(p in nm for p in patterns):
            cb = c.bbox()
            matches.append((c.name, cb.width() * layout.dbu, cb.height() * layout.dbu))
    for name, w, h in sorted(matches):
        print(f"  {name}  {w:.0f}x{h:.0f} um")
    print(f"  ({len(matches)} matches)")


if __name__ == "__main__":
    main()

"""Render a single design cell headlessly via klayout.lay.LayoutView."""

from pathlib import Path

import klayout.db as kdb
import klayout.lay as klay

REPO = Path(__file__).resolve().parent.parent / "ws-run1"
OAS = REPO / "layout" / "reticle.oas"
LYP = REPO / "lyp" / "gf180mcu.lyp"

TARGET = "TQVA_chip_top_14_8"
OUT = Path(__file__).resolve().parent / "tmp" / f"{TARGET}.png"


def main() -> None:
    OUT.parent.mkdir(exist_ok=True)

    layout = kdb.Layout()
    print(f"Reading {OAS}")
    layout.read(str(OAS))
    print("  loaded")

    cell = layout.cell(TARGET)
    print(f"  bbox={cell.bbox()}")

    lv = klay.LayoutView()
    # show_layout adds our already-loaded kdb.Layout to the view.
    # Second arg: add_new_cellview (True so we start clean).
    lv.show_layout(layout, True)
    lv.load_layer_props(str(LYP))

    # Point the active cellview at the design cell.
    cv = lv.active_cellview()
    cv.cell_name = TARGET

    # Fit the design bbox exactly.
    bb = cell.bbox()
    lv.zoom_box(kdb.DBox(
        bb.left * layout.dbu, bb.bottom * layout.dbu,
        bb.right * layout.dbu, bb.top * layout.dbu,
    ))

    lv.max_hier()  # expand full hierarchy (otherwise deep cells may be hidden)
    lv.save_image(str(OUT), 1600, 2000)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()

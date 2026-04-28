"""Re-render WSLG with solid (non-dithered) fills for the visible layers.

The current bg render uses the .lyp's default dither patterns: I9 for
Metal5/MetalTop (an inverted-stripe pattern) and I5 for Pad. That's
where the horizontal-stripe artifacts come from. Switching these to
dither pattern 0 (solid fill) should produce a clean look closer to
shipping/die_renders/WSLG.png.

Probe just renders one design with `dither_pattern = 0` applied to
each kept layer, alongside the original render for comparison.
"""

import time
from pathlib import Path

import klayout.db as kdb
import klayout.lay as klay

REPO = Path("/home/tim/github/wafer.space/ws-run1")
OAS = REPO / "layout" / "reticle.oas"
LYP = REPO / "lyp" / "gf180mcu.lyp"
OUT_DIR = Path(__file__).resolve().parent / "tmp"

BG_VISIBLE = {(37, 0), (81, 0), (53, 0)}
TARGET = "WSLG_chip_top_10_2"


def render(lv: klay.LayoutView, layout: kdb.Layout, cell_name: str,
           out: Path, solid: bool) -> None:
    for it in lv.each_layer():
        keep = (it.source_layer, it.source_datatype) in BG_VISIBLE
        it.visible = keep
        if keep:
            it.dither_pattern = 0 if solid else it.dither_pattern
    lv.update_content()

    cell = layout.cell(cell_name)
    bb = cell.bbox()
    x0, y0 = bb.left * layout.dbu, bb.bottom * layout.dbu
    x1, y1 = bb.right * layout.dbu, bb.top * layout.dbu
    lv.active_cellview().cell_name = cell_name
    lv.zoom_box(kdb.DBox(x0, y0, x1, y1))
    lv.max_hier()

    w_um = x1 - x0
    h_um = y1 - y0
    max_px = 3200
    if w_um >= h_um:
        w_px = max_px
        h_px = max(int(max_px * h_um / w_um), 32)
    else:
        h_px = max_px
        w_px = max(int(max_px * w_um / h_um), 32)
    lv.save_image(str(out), w_px, h_px)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    layout = kdb.Layout()
    print(f"Reading {OAS} ...", flush=True)
    t0 = time.time()
    layout.read(str(OAS))
    print(f"  loaded in {time.time() - t0:.1f}s", flush=True)

    lv = klay.LayoutView()
    lv.show_layout(layout, True)
    lv.load_layer_props(str(LYP))
    lv.set_config("grid-visible", "false")
    lv.set_config("background-color", "#ffffff")
    lv.set_config("text-visible", "false")
    lv.set_config("draw-cell-frame", "false")

    out_dithered = OUT_DIR / "WSLG_dither.png"
    out_solid = OUT_DIR / "WSLG_solid.png"
    render(lv, layout, TARGET, out_dithered, solid=False)
    print(f"  wrote {out_dithered}", flush=True)
    render(lv, layout, TARGET, out_solid, solid=True)
    print(f"  wrote {out_solid}", flush=True)


if __name__ == "__main__":
    main()

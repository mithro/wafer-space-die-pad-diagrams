"""Probe which layers are visible=True in the loaded .lyp and check that the
visibility-overriding filter works on a LayoutView.

Prints: layer/datatype, name, color, dither, visibility — both before and
after applying a minimal-layer filter (Pad + Metal5 + MetalTop only).
"""

from pathlib import Path

import klayout.db as kdb
import klayout.lay as klay

from make_diagrams import LYP, OAS

KEEP = {(37, 0), (81, 0), (53, 0)}  # Pad, Metal5, MetalTop


def dump(lv: klay.LayoutView, label: str) -> None:
    vis_on = 0
    vis_off = 0
    print(f"\n== {label} ==")
    for it in lv.each_layer():
        ld, dt = it.source_layer, it.source_datatype
        name = it.name or ""
        if it.visible:
            vis_on += 1
            if (ld, dt) in KEEP or ld in {37, 81, 53}:
                print(f"  VIS {ld:>3}/{dt:<2}  {name!r}  fill=#{it.fill_color:06x}")
        else:
            vis_off += 1
    print(f"  total: {vis_on} visible / {vis_off} hidden")


def main() -> None:
    layout = kdb.Layout()
    print("Reading layout ...")
    layout.read(str(OAS))

    lv = klay.LayoutView()
    lv.show_layout(layout, True)
    lv.load_layer_props(str(LYP))

    dump(lv, "after .lyp load (raw)")

    # Filter: keep only the layers in KEEP visible.
    for it in lv.each_layer():
        it.visible = (it.source_layer, it.source_datatype) in KEEP
    lv.update_content()

    dump(lv, "after minimal-layer filter")


if __name__ == "__main__":
    main()

"""Verify the ws-run1 .lyp styling loads into a LayoutView.

Print the first few resolved layer entries so we can see the colours,
dither patterns and visibility flags that came out of the .lyp.
"""

from pathlib import Path

import klayout.db as kdb
import klayout.lay as klay

from make_diagrams import LYP, OAS


def main() -> None:
    layout = kdb.Layout()
    print("Reading layout ...")
    layout.read(str(OAS))

    lv = klay.LayoutView()
    lv.show_layout(layout, True)
    lv.load_layer_props(str(LYP))

    # Walk the resolved layer stack and dump each entry's style.
    shown = 0
    for it in lv.each_layer():
        src = it.source
        ld = it.source_layer
        dt = it.source_datatype
        name = it.name
        fill = f"#{it.fill_color:06x}" if it.fill_color else "(default)"
        frame = f"#{it.frame_color:06x}" if it.frame_color else "(default)"
        print(f"  {ld}/{dt}  {name!r}  fill={fill} frame={frame} "
              f"dither={it.dither_pattern} visible={it.visible}")
        shown += 1
        if shown >= 25:
            break
    print(f"(showing first {shown}; total layers in view available via lv.each_layer())")


if __name__ == "__main__":
    main()

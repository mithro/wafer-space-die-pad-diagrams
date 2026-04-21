"""Render just 2 designs to sanity-check the generator before the full run."""

import time
from pathlib import Path

import klayout.db as kdb

from make_diagrams import (OAS, OUT_DIR, _is_peripheral, assign_net_names,
                           extract_labels, extract_pads, render)

SMOKE_TARGETS = [
    "TQVA_chip_top_14_8",
    "KIAN_chip_top_8_0",
    "ISHI_ISHI-KAI_WS_RUN1_12_4",
    "MOS2_chip_top_10_6",
    "TRID_TOP_14_2",
]


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)

    layout = kdb.Layout()
    print(f"Reading {OAS} ...")
    t0 = time.time()
    layout.read(str(OAS))
    print(f"  loaded in {time.time() - t0:.1f}s")

    for name in SMOKE_TARGETS:
        t0 = time.time()
        cell = layout.cell(name)
        pads = extract_pads(cell, layout)
        labels = extract_labels(cell, layout)
        assign_net_names(pads, labels)
        bb = cell.bbox()
        die = (bb.left * layout.dbu, bb.bottom * layout.dbu,
               bb.right * layout.dbu, bb.top * layout.dbu)
        pads = [p for p in pads if _is_peripheral(p, *die)]
        out_png = OUT_DIR / f"{name}.png"
        out_svg = OUT_DIR / f"{name}.svg"
        render(name, pads, die, out_png, out_svg)
        labelled = sum(1 for p in pads if p.net)
        print(f"  {name}: {len(pads)} pads, {labelled} labelled  "
              f"({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()

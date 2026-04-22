"""Print TRID pads with their assigned net names, sorted by length.

Helps diagnose why TRID's adaptive fontsize is so small: we want to see
whether one outlier-long name is dragging the margin-fit constraint
down for the whole chip.
"""

import klayout.db as kdb

from make_diagrams import (OAS, _classify_edge, _is_peripheral,
                           assign_net_names, extract_labels, extract_pads)


def main() -> None:
    layout = kdb.Layout()
    print(f"Reading {OAS} ...")
    layout.read(str(OAS))

    cell = layout.cell("TRID_TOP_14_2")
    pads = extract_pads(cell, layout)
    labels = extract_labels(cell, layout)
    assign_net_names(pads, labels)
    bb = cell.bbox()
    die = (bb.left * layout.dbu, bb.bottom * layout.dbu,
           bb.right * layout.dbu, bb.top * layout.dbu)
    pads = [p for p in pads if _is_peripheral(p, *die)]

    by_len = sorted(
        ((len(p.net or "?"), p.net or "?", _classify_edge(p, *die))
         for p in pads),
        reverse=True,
    )
    for ln, name, edge in by_len[:15]:
        print(f"  {edge} len={ln:3}  {name!r}")
    print(f"\ntotal pads: {len(pads)}")
    print(f"max len: {by_len[0][0]}")
    print(f"median len: {sorted(l for l, _, _ in by_len)[len(by_len)//2]}")


if __name__ == "__main__":
    main()

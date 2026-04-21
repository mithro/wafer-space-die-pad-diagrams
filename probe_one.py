"""Probe a single design cell to see what's on the pad / label layers."""

import time
from collections import Counter
from pathlib import Path

import klayout.db as kdb

OAS = Path(__file__).resolve().parent.parent / "ws-run1" / "layout" / "reticle.oas"

PAD_LAYER = (37, 0)
METAL5_LABEL = (81, 10)
METALTOP_LABEL = (53, 10)

TARGET = "TQVA_chip_top_14_8"


def main() -> None:
    layout = kdb.Layout()
    print(f"Reading {OAS} ...")
    t0 = time.time()
    layout.read(str(OAS))
    print(f"  loaded in {time.time() - t0:.1f}s")

    cell = layout.cell(TARGET)
    bb = cell.bbox()
    print(f"\n{TARGET}: cell bbox ({bb.left * layout.dbu:.1f},{bb.bottom * layout.dbu:.1f}) .. "
          f"({bb.right * layout.dbu:.1f},{bb.top * layout.dbu:.1f})")

    # --- All Pad polygons and their size distribution ---
    pad_layer = layout.layer(*PAD_LAYER)
    pads: list[kdb.Box] = []
    it = cell.begin_shapes_rec(pad_layer)
    while not it.at_end():
        shape = it.shape()
        tr = it.trans()
        pads.append(shape.bbox().transformed(tr))
        it.next()
    print(f"\nPad (37/0): {len(pads)} shapes")

    size_buckets: Counter[str] = Counter()
    for b in pads:
        w_um = b.width() * layout.dbu
        h_um = b.height() * layout.dbu
        key = f"{round(w_um):>5}x{round(h_um):<5}"
        size_buckets[key] += 1
    print("  Size distribution (W x H um, count):")
    for key, n in sorted(size_buckets.items(), key=lambda kv: -kv[1])[:20]:
        print(f"    {key}  x{n}")

    # --- Labels on Metal5_Label and MetalTop_Label ---
    for lname, layer_spec in [("Metal5_Label", METAL5_LABEL), ("MetalTop_Label", METALTOP_LABEL)]:
        li = layout.layer(*layer_spec)
        texts: list[tuple[str, float, float]] = []
        it = cell.begin_shapes_rec(li)
        while not it.at_end():
            shape = it.shape()
            tr = it.trans()
            if shape.is_text():
                t = tr * shape.text
                # kdb.Text has .x and .y directly (dbu ints) in klayout >= 0.28
                texts.append((t.string, t.x * layout.dbu, t.y * layout.dbu))
            it.next()
        print(f"\n{lname} ({layer_spec[0]}/{layer_spec[1]}): {len(texts)} texts")
        for name, x, y in texts[:20]:
            print(f"  {name!r} @ ({x:.1f},{y:.1f})")


if __name__ == "__main__":
    main()

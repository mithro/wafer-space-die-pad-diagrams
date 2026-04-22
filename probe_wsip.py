"""Find where gf180mcu_ws_ip__logo and gf180mcu_ws_ip__id sit in each design.

The prior probe showed these are standard ws-run1 template sub-cells
present in every top-level slot. We want to confirm two things:

  1. Every public design instantiates both cells (so render() can rely
     on them without special-casing).
  2. Their instance bbox is in a predictable corner (so we can colour
     them distinctively from matplotlib without over-reaching).

Prints each chip's (logo, id) positions expressed as percentages of the
die bbox so corner placement is obvious at a glance.
"""

from pathlib import Path

import klayout.db as kdb

from make_diagrams import OAS

TARGETS = ("gf180mcu_ws_ip__logo", "gf180mcu_ws_ip__id")


def main() -> None:
    layout = kdb.Layout()
    print(f"Reading {OAS} ...")
    layout.read(str(OAS))

    top = next(iter(layout.top_cells()))
    skip = {"RETICLE_FILL", "TEXT"}
    design_names = []
    for inst in top.each_inst():
        n = inst.cell.name
        if n not in skip and n not in design_names:
            design_names.append(n)

    for name in sorted(design_names):
        cell = layout.cell(name)
        bb = cell.bbox()
        dx = bb.width() * layout.dbu
        dy = bb.height() * layout.dbu
        ox = bb.left * layout.dbu
        oy = bb.bottom * layout.dbu

        # Targeted lookup instead of a full recursive walk (which would
        # visit millions of via instances). For each template cell we use
        # KLayout's caller_cells() to find every cell that instantiates
        # it, then keep the one that also lives under this design.
        found: dict[str, tuple[float, float, float, float]] = {}
        descendants = set(cell.called_cells()) | {cell.cell_index()}
        for target_name in TARGETS:
            tgt_cell = layout.cell(target_name)
            if tgt_cell is None:
                continue
            # Any cell in this design that directly instantiates the target.
            for parent_idx in tgt_cell.caller_cells():
                if parent_idx not in descendants:
                    continue
                parent = layout.cell(parent_idx)
                for inst in parent.each_inst():
                    if inst.cell.cell_index() != tgt_cell.cell_index():
                        continue
                    # Compose parent-to-design transform by following any
                    # chain of instances; in this layout the logo/id sits
                    # one level below a wrapper cell that IS a direct
                    # child of the design, so we only need the first-level
                    # placement plus the parent's direct-instance offset.
                    parent_insts = [pi for pi in cell.each_inst()
                                    if pi.cell.cell_index() == parent_idx]
                    if not parent_insts:
                        continue
                    outer = parent_insts[0]
                    ib = inst.bbox().transformed(outer.trans)
                    found[target_name] = (
                        ib.left * layout.dbu - ox, ib.bottom * layout.dbu - oy,
                        ib.right * layout.dbu - ox, ib.top * layout.dbu - oy,
                    )
                    break
                if target_name in found:
                    break
        flags = []
        for t in TARGETS:
            if t not in found:
                flags.append(f"MISSING {t}")
        short = name[:32]
        if flags:
            print(f"  {short:<32}  {flags}")
        else:
            def pct(v, span):
                return v / span * 100
            lx0, ly0, lx1, ly1 = found["gf180mcu_ws_ip__logo"]
            ix0, iy0, ix1, iy1 = found["gf180mcu_ws_ip__id"]
            print(f"  {short:<32}  die {dx:.0f}x{dy:.0f}  "
                  f"logo@({pct(lx0, dx):4.0f}%,{pct(ly0, dy):4.0f}%)  "
                  f"id@({pct(ix0, dx):4.0f}%,{pct(iy0, dy):4.0f}%)")


if __name__ == "__main__":
    main()

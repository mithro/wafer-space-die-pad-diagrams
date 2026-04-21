"""Generate annotated pad diagrams for each design in the ws-run1 reticle.

For every top-level instance in reticle.oas, emit a PNG and SVG showing:
  - The die outline (the design cell's bounding box)
  - Each IO pad drawn as a filled rectangle (Pad layer 37/0, filtered by size)
  - The net name for each pad, pulled from Metal5_Label (81/10) or
    MetalTop_Label (53/10) texts whose position falls inside the pad

The layout is read once; all designs are rendered from that single load.
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import klayout.db as kdb
import klayout.lay as klay
import matplotlib.image as mpimg
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parent.parent / "ws-run1"
OAS = REPO / "layout" / "reticle.oas"
LYP = REPO / "lyp" / "gf180mcu.lyp"
OUT_DIR = Path(__file__).resolve().parent / "diagrams"
# Dimensions for the GDS render used as a background. 1200 px on the long
# edge gives enough resolution to see structure at final figure size while
# keeping the render fast.
GDS_RENDER_MAX_PX = 1200

# GF180MCU layer numbers
PAD_LAYER = (37, 0)
LABEL_LAYERS = [(81, 10), (53, 10)]  # Metal5_Label, MetalTop_Label

# Visible layers for the GDS background render. The raw gf180mcu.lyp marks
# ~15 layers visible with clashing colors (pink wells, teal dummy metal,
# green poly, yellow-green ESD, salmon n-well, ...), which produces a busy
# multi-coloured render. For a publication-style background we want a
# two-tone look matching the ws-run1 README renders: yellow/olive body
# from top-level metal, dark red pads from the Pad layer. Everything else
# is hidden so the pad ring stands out cleanly.
BG_VISIBLE_LAYERS: set[tuple[int, int]] = {
    (37, 0),   # Pad           → #72342b (dark red)
    (81, 0),   # Metal5        → #cdc16b (olive/yellow)
    (53, 0),   # MetalTop      → #b1dd9c (pale green/yellow)
}

# Minimum pad edge length in microns to count as an IO pad (not a seal ring).
PAD_MIN_UM = 30.0

# Colors per pad class (fill, text). Follows standard electronics convention:
# grounds are black/grey, supplies are reds/oranges, signals are amber.
# Within each supply family, digital and analog use different shades so the
# rails read apart at a glance.
PAD_COLORS: dict[str, tuple[str, str]] = {
    "gnd_digital": ("#212121", "#000000"),   # DVSS   — near-black
    "gnd_analog":  ("#616161", "#37474f"),   # AVSS   — mid-grey
    "gnd":         ("#424242", "#212121"),   # VSS/GND/VSUB — charcoal
    "pwr_digital": ("#d32f2f", "#b71c1c"),   # DVDD   — crimson
    "pwr_analog":  ("#f57c00", "#e65100"),   # AVDD   — orange
    "pwr":         ("#e53935", "#b71c1c"),   # VDD/VCC — red
    "signal":      ("#f5c16c", "#111111"),   # everything else
}


def classify_net(name: str | None) -> str:
    """Return a key into PAD_COLORS for the given net name."""
    if not name:
        return "signal"
    n = name.upper()
    # Ground patterns first. "VSS" also appears inside "DVSS" / "AVSS",
    # so the digital / analog variants must be tested before plain VSS.
    if "DVSS" in n or "DGND" in n:
        return "gnd_digital"
    if "AVSS" in n or "AGND" in n:
        return "gnd_analog"
    if "VSS" in n or "GND" in n or n == "GROUND" or "VSUB" in n:
        return "gnd"
    # Power patterns — same ordering trick.
    if "DVDD" in n or "VDDD" in n:
        return "pwr_digital"
    if "AVDD" in n or "VDDA" in n:
        return "pwr_analog"
    if "VDD" in n or "VCC" in n:
        return "pwr"
    return "signal"


@dataclass
class Pad:
    """A single IO pad with its rectangle and assigned net name."""
    x0: float   # um
    y0: float
    x1: float
    y1: float
    net: str | None = None

    @property
    def cx(self) -> float:
        return 0.5 * (self.x0 + self.x1)

    @property
    def cy(self) -> float:
        return 0.5 * (self.y0 + self.y1)

    @property
    def w(self) -> float:
        return self.x1 - self.x0

    @property
    def h(self) -> float:
        return self.y1 - self.y0


def extract_pads(cell: kdb.Cell, layout: kdb.Layout) -> list[Pad]:
    """Return IO-sized pad rectangles in this cell (hierarchical)."""
    layer_index = layout.layer(*PAD_LAYER)
    pads: list[Pad] = []
    it = cell.begin_shapes_rec(layer_index)
    while not it.at_end():
        shape = it.shape()
        tr = it.trans()
        bb = shape.bbox().transformed(tr)
        w_um = bb.width() * layout.dbu
        h_um = bb.height() * layout.dbu
        if w_um >= PAD_MIN_UM and h_um >= PAD_MIN_UM:
            pads.append(Pad(
                x0=bb.left * layout.dbu,
                y0=bb.bottom * layout.dbu,
                x1=bb.right * layout.dbu,
                y1=bb.top * layout.dbu,
            ))
        it.next()
    return pads


def extract_labels(cell: kdb.Cell, layout: kdb.Layout) -> list[tuple[str, float, float]]:
    """Return (net_name, x_um, y_um) for every text on label layers."""
    out: list[tuple[str, float, float]] = []
    for ln, dt in LABEL_LAYERS:
        li = layout.layer(ln, dt)
        it = cell.begin_shapes_rec(li)
        while not it.at_end():
            shape = it.shape()
            tr = it.trans()
            if shape.is_text():
                t = tr * shape.text
                out.append((t.string, t.x * layout.dbu, t.y * layout.dbu))
            it.next()
    return out


def assign_net_names(pads: list[Pad], labels: list[tuple[str, float, float]]) -> None:
    """For each pad, pick the best net-name label whose (x,y) lies inside it.

    GF180MCU GPIO cells put a generic "PAD" (or similar) label inside every
    bondable metal region. The user's top-level net name sits on the same
    pad but is more descriptive (e.g. "bidir_PAD[29]", "clk_PAD", "VDD").
    We score labels so generic tokens lose to descriptive ones.
    """
    generic = {"PAD", "pad", "Pad", "BOND", "bond"}

    def score(name: str) -> tuple[int, int, int, int]:
        is_generic = 1 if name in generic else 0
        # Port-indexed names (contain '[') are very specific: boost them.
        is_indexed = 0 if "[" in name else 1
        # Supply nets are short UPPER names — keep those recognised too.
        is_supply = 0 if name.isupper() and len(name) <= 6 else 1
        # Prefer descriptive (longer) names among otherwise equal candidates.
        return (is_generic, is_indexed, is_supply, -len(name))

    for pad in pads:
        hits: Counter[str] = Counter()
        for name, x, y in labels:
            if pad.x0 <= x <= pad.x1 and pad.y0 <= y <= pad.y1:
                hits[name] += 1
        if not hits:
            continue
        pad.net = sorted(hits.keys(), key=score)[0]


def _classify_edge(pad: Pad, x0: float, y0: float, x1: float, y1: float) -> str:
    """Return which die edge this pad is closest to: 'L','R','T','B'."""
    d_left = pad.cx - x0
    d_right = x1 - pad.cx
    d_bottom = pad.cy - y0
    d_top = y1 - pad.cy
    m = min(d_left, d_right, d_bottom, d_top)
    if m == d_left:
        return "L"
    if m == d_right:
        return "R"
    if m == d_bottom:
        return "B"
    return "T"


def _is_peripheral(pad: Pad, x0: float, y0: float, x1: float, y1: float) -> bool:
    """A pad is peripheral if it sits against a die edge (not deep inside).

    The threshold is a small multiple of the pad's own dimensions: real
    peripheral pads are placed with only a micrometres-wide gap to the die
    edge, so their centre lies within ~1 pad-width of that edge. Probe
    pads placed inside the die (like MOS2's internal rows) are many times
    their own size away from any edge and fall into the interior bucket.
    """
    d = min(
        pad.cx - x0,
        x1 - pad.cx,
        pad.cy - y0,
        y1 - pad.cy,
    )
    return d <= max(pad.w, pad.h) * 2.0


def render_gds_background(lv: klay.LayoutView, cell_name: str, layout: kdb.Layout,
                          die_bb: tuple[float, float, float, float],
                          out_path: Path) -> None:
    """Render the design cell via KLayout's LayoutView to a PNG file.

    Styling comes from the .lyp loaded in setup_layout_view — layer colors,
    dither patterns, frame styles and per-layer visibility are all driven
    by ws-run1/lyp/gf180mcu.lyp. This function only picks the cell and
    the viewport.

    The image covers die_bb exactly so it can be placed under the pad
    overlay with `imshow(extent=die_bb)`.
    """
    x0, y0, x1, y1 = die_bb
    die_w = x1 - x0
    die_h = y1 - y0

    lv.active_cellview().cell_name = cell_name
    lv.zoom_box(kdb.DBox(x0, y0, x1, y1))
    lv.max_hier()

    # Pixel size proportional to die aspect ratio so the image maps 1:1 to
    # scene coordinates once we pass `extent=die_bb` to imshow.
    if die_w >= die_h:
        w_px = GDS_RENDER_MAX_PX
        h_px = max(int(GDS_RENDER_MAX_PX * die_h / die_w), 32)
    else:
        h_px = GDS_RENDER_MAX_PX
        w_px = max(int(GDS_RENDER_MAX_PX * die_w / die_h), 32)
    lv.save_image(str(out_path), w_px, h_px)


def render(cell_name: str, pads: list[Pad], die_bb: tuple[float, float, float, float],
           out_png: Path, out_svg: Path,
           background_image: Path | None = None) -> None:
    """Render pad diagram. If background_image is given, use it as the
    die-area background (typically a KLayout GDS render of the cell)."""
    x0, y0, x1, y1 = die_bb
    die_w = x1 - x0
    die_h = y1 - y0

    # Outside margin where labels sit, and the tiny gap between each pad's
    # rectangle and its adjacent text. label_gap is small on purpose — pads
    # already sit a few um inside the die edge, so this keeps the final
    # pad-to-text gap tight while still avoiding the die outline.
    margin = max(die_w, die_h) * 0.20
    label_gap = max(die_w, die_h) * 0.003

    # Figure: fit the die into a 14" bounding box preserving aspect ratio.
    # Fixed size keeps font pixel-height consistent across all designs.
    canvas = 14.0
    total_w = die_w + 2 * margin
    total_h = die_h + 2 * margin
    if total_w >= total_h:
        fig_w = canvas
        fig_h = canvas * total_h / total_w
    else:
        fig_h = canvas
        fig_w = canvas * total_w / total_h
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    # GDS render as background, or plain fill if none supplied.
    if background_image is not None and background_image.exists():
        img = mpimg.imread(str(background_image))
        ax.imshow(img, extent=(x0, x1, y0, y1), origin="upper",
                  zorder=0, interpolation="bilinear", aspect="auto")
    else:
        ax.add_patch(mpatches.Rectangle(
            (x0, y0), die_w, die_h,
            linewidth=0, edgecolor="none", facecolor="#fafafa", zorder=0,
        ))

    # Thin die outline on top of the render so the chip edge is obvious.
    ax.add_patch(mpatches.Rectangle(
        (x0, y0), die_w, die_h,
        linewidth=1.0, edgecolor="#222", facecolor="none", zorder=1.5,
    ))

    # Draw pads, colored by net class (signal / ground / power variants).
    labelled = unlabelled = 0
    for pad in pads:
        has_net = pad.net is not None
        cls = classify_net(pad.net) if has_net else "signal"
        fill = PAD_COLORS[cls][0] if has_net else "#bbbbbb"
        ax.add_patch(mpatches.Rectangle(
            (pad.x0, pad.y0), pad.w, pad.h,
            linewidth=0.4,
            edgecolor="#222",
            facecolor=fill,
            zorder=2,
        ))
        if has_net:
            labelled += 1
        else:
            unlabelled += 1

    # Place each label directly in line with its pad (no leader lines).
    # L/R edge labels stay horizontal, sharing the pad's y-coordinate.
    # T/B edge labels are rotated 90°, sharing the pad's x-coordinate.
    # `rotation_mode="anchor"` makes ha/va apply to the rotated text's
    # bounding box so "left + rot=90" grows upward from the anchor
    # and "right + rot=90" grows downward.
    for pad in pads:
        edge = _classify_edge(pad, x0, y0, x1, y1)
        if edge == "L":
            tx, ty = x0 - label_gap, pad.cy
            ha, va, rot = "right", "center", 0
        elif edge == "R":
            tx, ty = x1 + label_gap, pad.cy
            ha, va, rot = "left", "center", 0
        elif edge == "T":
            tx, ty = pad.cx, y1 + label_gap
            ha, va, rot = "left", "center", 90
        else:  # B
            tx, ty = pad.cx, y0 - label_gap
            ha, va, rot = "right", "center", 90

        txt = pad.net if pad.net else "?"
        if pad.net:
            color = PAD_COLORS[classify_net(pad.net)][1]
            weight = "bold" if classify_net(pad.net) != "signal" else "normal"
        else:
            color = "#b00"
            weight = "normal"
        ax.text(
            tx, ty, txt,
            ha=ha, va=va, fontsize=6, color=color,
            family="monospace", zorder=3, rotation=rot,
            rotation_mode="anchor", fontweight=weight,
        )

    ax.set_xlim(x0 - margin, x1 + margin)
    ax.set_ylim(y0 - margin, y1 + margin)
    ax.set_aspect("equal")
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
    ax.set_title(
        f"{cell_name} — {die_w:.0f} x {die_h:.0f} um — "
        f"{labelled} labelled pads, {unlabelled} unlabelled",
        fontsize=11,
    )
    ax.grid(True, which="both", linewidth=0.3, alpha=0.4)

    fig.tight_layout()
    fig.savefig(out_png, dpi=180)
    fig.savefig(out_svg)
    plt.close(fig)


def setup_layout_view(layout: kdb.Layout) -> klay.LayoutView:
    """Build a LayoutView that renders like the ws-run1 README images.

    Colors and dither patterns come from ws-run1/lyp/gf180mcu.lyp, but the
    raw .lyp enables ~15 layers (wells, poly, dummies, substrate) in
    clashing colors. We keep only the layers in BG_VISIBLE_LAYERS visible
    so the render stays two-tone (yellow metal + dark red pads) and the
    pad ring reads clearly. The other visual toggles:

    - `grid-visible=false`: suppress KLayout's GUI coordinate grid.
    - `background-color=#ffffff`: white canvas outside the die so the
      overlay labels in make_diagrams.render sit on white paper.
    - `text-visible=false`: don't draw text objects from the layout — our
      matplotlib labels do the annotation; leaving KLayout's in adds
      unreadable microscopic strings inside every pad.
    - `draw-cell-frame=false`: suppress the default black rectangle drawn
      around each instance, which otherwise frames every pad cell and
      every logo sub-cell in a heavy black border.
    """
    lv = klay.LayoutView()
    lv.show_layout(layout, True)
    lv.load_layer_props(str(LYP))
    lv.set_config("grid-visible", "false")
    lv.set_config("background-color", "#ffffff")
    lv.set_config("text-visible", "false")
    lv.set_config("draw-cell-frame", "false")
    # Mask down to the two-tone layer set.
    for it in lv.each_layer():
        it.visible = (it.source_layer, it.source_datatype) in BG_VISIBLE_LAYERS
    lv.update_content()
    return lv


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    bg_cache = OUT_DIR.parent / "tmp" / "gds_renders"
    bg_cache.mkdir(parents=True, exist_ok=True)

    layout = kdb.Layout()
    print(f"Reading {OAS} ...")
    t0 = time.time()
    layout.read(str(OAS))
    print(f"  loaded in {time.time() - t0:.1f}s — {layout.cells()} cells")

    lv = setup_layout_view(layout)

    top = next(iter(layout.top_cells()))
    # Skip filler/text utility cells when generating design diagrams.
    skip = {"RETICLE_FILL", "TEXT"}

    instances: list[str] = []
    for inst in top.each_inst():
        name = inst.cell.name
        if name in skip:
            continue
        if name not in instances:
            instances.append(name)
    print(f"\n{len(instances)} unique designs to render")

    summary: list[tuple[str, int, int]] = []
    for i, name in enumerate(sorted(instances), start=1):
        t_start = time.time()
        cell = layout.cell(name)
        if cell is None:
            print(f"  [{i}/{len(instances)}] {name}: cell not found, skipping")
            continue
        pads = extract_pads(cell, layout)
        labels = extract_labels(cell, layout)
        assign_net_names(pads, labels)

        bb = cell.bbox()
        die_bb = (
            bb.left * layout.dbu,
            bb.bottom * layout.dbu,
            bb.right * layout.dbu,
            bb.top * layout.dbu,
        )

        # Drop probe / internal pads — only the ring of peripheral pads
        # is annotated. Interior pads end up in MOS2 / TRID / ISHI-style
        # test structures and aren't part of the chip's pinout.
        pads = [p for p in pads if _is_peripheral(p, *die_bb)]

        out_png = OUT_DIR / f"{name}.png"
        out_svg = OUT_DIR / f"{name}.svg"
        bg_png = bg_cache / f"{name}.png"
        render_gds_background(lv, name, layout, die_bb, bg_png)
        render(name, pads, die_bb, out_png, out_svg, background_image=bg_png)

        labelled = sum(1 for p in pads if p.net)
        summary.append((name, len(pads), labelled))
        print(f"  [{i:>2}/{len(instances)}] {name}: {len(pads):>3} pads, "
              f"{labelled:>3} labelled  ({time.time() - t_start:.1f}s)")

    # Write a summary index.
    index = OUT_DIR / "index.md"
    with index.open("w") as fh:
        fh.write("# Reticle pad-diagram index\n\n")
        fh.write("| Design cell | Pads | Labelled | Diagram |\n")
        fh.write("|---|---|---|---|\n")
        for name, n, nl in summary:
            fh.write(f"| {name} | {n} | {nl} | [{name}.png]({name}.png) |\n")
    print(f"\nWrote {index}")


if __name__ == "__main__":
    main()

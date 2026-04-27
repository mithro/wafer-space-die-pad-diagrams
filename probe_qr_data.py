"""Decode the QR code embedded in gf180mcu_ws_ip__id.gds.

The wafer.space ws-run1 reticle template instantiates `gf180mcu_ws_ip__id`
in every chip's bottom-left corner. Its layout (a 143x143 um Metal5 cell)
contains a QR code drawn as a grid of metal squares — but the README and
the verilog stub don't mention what that QR encodes. To regenerate the
same code with segno (instead of cropping it from a GDS render), we need
to know the encoded string.

Strategy: render the cell to a high-res PNG via KLayout, then run a
QR decoder on it. Try opencv (built-in WeChat-derived QR detector),
fall back to pyzbar if available. Print the decoded payload — that
becomes a constant in make_diagrams.py.
"""

from pathlib import Path

import klayout.db as kdb
import klayout.lay as klay

GDS = Path("/home/tim/github/mithro/gf180mcu-project-template"
           "/ip/gf180mcu_ws_ip__id/gds/gf180mcu_ws_ip__id.gds")
OUT = Path(__file__).resolve().parent / "tmp" / "ws_ip_id_render.png"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    layout = kdb.Layout()
    layout.read(str(GDS))
    top = next(iter(layout.top_cells()))
    print(f"top cell: {top.name}")
    bb = top.bbox()
    x0 = bb.left * layout.dbu
    y0 = bb.bottom * layout.dbu
    x1 = bb.right * layout.dbu
    y1 = bb.top * layout.dbu
    print(f"bbox: ({x0:.2f},{y0:.2f}) -> ({x1:.2f},{y1:.2f}) um  "
          f"({x1 - x0:.1f} x {y1 - y0:.1f} um)")

    # List layers used (just so we know what to render).
    used = []
    for li in layout.layer_indexes():
        info = layout.get_info(li)
        if any(not it.at_end()
               for it in [top.begin_shapes_rec(li)]):
            used.append((info.layer, info.datatype))
    print(f"layers in cell: {used}")

    lv = klay.LayoutView()
    lv.show_layout(layout, True)
    # Make every layer visible — we want to see the full QR pattern.
    for it in lv.each_layer():
        it.visible = True
    lv.set_config("background-color", "#ffffff")
    lv.set_config("grid-visible", "false")
    lv.set_config("text-visible", "false")
    lv.set_config("draw-cell-frame", "false")
    lv.update_content()

    lv.active_cellview().cell_name = top.name
    lv.zoom_box(kdb.DBox(x0, y0, x1, y1))
    lv.max_hier()
    lv.save_image(str(OUT), 1200, 1200)
    print(f"wrote {OUT}")

    # Try multiple decoders.
    decoded = None
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
        img = cv2.imread(str(OUT), cv2.IMREAD_GRAYSCALE)
        det = cv2.QRCodeDetector()
        data, points, _ = det.detectAndDecode(img)
        if data:
            decoded = ("cv2", data)
        else:
            print("cv2 QRCodeDetector returned empty")
    except ImportError:
        print("cv2 not available")

    if decoded is None:
        try:
            from pyzbar.pyzbar import decode  # type: ignore
            from PIL import Image  # type: ignore
            img = Image.open(OUT)
            results = decode(img)
            for r in results:
                if r.type == "QRCODE":
                    decoded = ("pyzbar", r.data.decode("utf-8"))
                    break
            if decoded is None:
                print(f"pyzbar found {len(results)} symbols, none QR")
        except ImportError:
            print("pyzbar not available")

    if decoded is None:
        try:
            from qreader import QReader  # type: ignore
            import cv2  # type: ignore
            qr = QReader()
            img = cv2.imread(str(OUT))
            results = qr.detect_and_decode(image=img)
            for r in results:
                if r:
                    decoded = ("qreader", r)
                    break
        except ImportError:
            print("qreader not available")

    if decoded:
        backend, data = decoded
        print(f"\nDECODED ({backend}): {data!r}")
    else:
        print("\nNo decoder succeeded. Rendered image at:", OUT)


if __name__ == "__main__":
    main()

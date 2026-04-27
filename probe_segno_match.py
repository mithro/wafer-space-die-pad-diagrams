"""Check whether segno reproduces the chip's QR pattern byte-for-byte.

The chip's QR encodes "00000000" (verified via cv2 in probe_qr_decode).
segno can encode the same string, but the QR mask, error-correction
level and version may differ, producing a visually different (though
still semantically-equivalent) pattern. This probe walks through every
combination segno offers and looks for one that exactly matches the
GDS-extracted matrix.

If we find a match, render() can call segno.make() with those params
and trust the output. If not, the simpler path is to render the
extracted matrix directly — same pattern guaranteed.
"""

import segno

GDS_MATRIX = (
    "#######..##.#.#######",
    "#.....#...##..#.....#",
    "#.###.#....##.#.###.#",
    "#.###.#..#.##.#.###.#",
    "#.###.#.##....#.###.#",
    "#.....#..##.#.#.....#",
    "#######.#.#.#.#######",
    "........###..........",
    "..##..####.#.##.#....",
    "..##...####..#.#..#..",
    "########.#.#.#.###..#",
    ".##.#..###.####....#.",
    "#...###.##.##...#.#..",
    "........#.####.#.#..#",
    "#######.#####...#..#.",
    "#.....#.......#...#.#",
    "#.###.#..###..#..#..#",
    "#.###.#.#.#.#.#.#..#.",
    "#.###.#.#..#....#.#..",
    "#.....#..###.#..##.##",
    "#######.....#..#...#.",
)


def matrix_str(qr: segno.QRCode) -> tuple[str, ...]:
    return tuple("".join("#" if b else "." for b in row) for row in qr.matrix)


def main() -> None:
    target = GDS_MATRIX
    print(f"target {len(target)}x{len(target[0])}")

    found = False
    for ec in ("L", "M", "Q", "H"):
        for mask in range(8):
            for mode in (None, "alphanumeric", "numeric", "byte"):
                try:
                    qr = segno.make("00000000", error=ec, mask=mask,
                                    mode=mode, version=1, boost_error=False)
                except Exception:
                    continue
                m = matrix_str(qr)
                if m == target:
                    print(f"MATCH ec={ec} mask={mask} mode={mode!r}")
                    found = True
                else:
                    # Show the first mismatching row when very close
                    diffs = sum(1 for a, b in zip(m, target) if a != b)
                    if diffs <= 3:
                        print(f"  near-miss ec={ec} mask={mask} mode={mode!r} "
                              f"({diffs} diff rows)")
    if not found:
        print("No segno parameter combination reproduces the chip's matrix.")
        # Show what segno picks by default for "00000000".
        d = segno.make("00000000", error="m")
        print(f"\ndefault segno output (version={d.version}, mask={d.mask}, "
              f"mode={d.mode}):")
        for row in matrix_str(d):
            print("  " + row)


if __name__ == "__main__":
    main()

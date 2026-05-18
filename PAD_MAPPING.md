# Pad Mapping Chain

How a chip pad is identified at every stage from the chip's GDS layout
through to the mezzanine connector pin a user plugs into.

The chain has seven distinct "names" for the same physical pad:

```
                    chip die                                CoB PCB                                connector
   ┌───────────────────────────────────────────────────┐    ┌────────────────────────────────────────────────┐
   │  GDS layout pad (x, y in chip frame)              │    │  KiCad PCB pad #1..74                          │
   │   →  diagram pad # (0..73, CCW from top-right)    │ ── │   ↔  KiCad pinfunction "<sym>_<pcb>"           │
   │   →  chip-side net (e.g. clk_PAD, bidir_PAD[14])  │    │   ↔  KiCad symbol pin name (e.g. pad_53, GND)  │
   │   →  internal RTL signal (e.g. clk, uart0_tx)     │    │   ↔  KiCad schematic net (e.g. /pad_53, GND)   │
   └───────────────────────────────────────────────────┘    └────────────────────────────────────────────────┘
                                                                                       │
                                                                                       └─→  mezzanine connector pin 1..70
```

The columns of the **Pins** sheet
(`https://docs.google.com/spreadsheets/d/1vMY6zjG4CcHUhjHQbyqoTHZUeJpAVzneXSWS_5HG-a0`)
correspond to the boxes above.

## Worked example: diagram pad #0 of GD03

| Stage | Value | Source |
|---|---|---|
| Chip GDS pad position | `(3406.0 µm, 5064.0 µm)` (post-display-rotation, top-right corner-adjacent) | `tmp/pads_data.json` |
| Diagram pad # | `0` (CCW from top-right of diagram, just left of QR) | `extract_pads_remote.py` ordering |
| Chip-side net (per project) | `clk_PAD` for GD03 (varies by project) | OAS labels on the pad |
| Internal RTL signal | `clk_PAD2CORE` (Schmitt-trigger output of the IO cell) | `src/chip_top.sv` |
| Function description | `system clock input (Schmitt trigger)` | sub-agent research from RTL |
| KiCad CoB footprint pin # | `1` (top-right corner of CoB PCB pad ring) | `tmp/cob_pad_map.json` |
| KiCad CoB footprint position | `(+3.20 mm, −4.70 mm)` in footprint-local coords (top-right because KiCad is y-down) | `tmp/cob_pad_map.json` |
| KiCad pinfunction (footprint name) | `pad_0_1` (`<symbol_pin>_<pcb_pad>`) | `tmp/cob_pad_map.json` |
| KiCad symbol pin name | `pad_0` (the schematic-side pin label) | `tmp/cob_pad_map.json` |
| KiCad schematic net | `/pad_0` (leading `/` for root-sheet local nets; power nets like `GND`, `VDD_IO_2` carry no slash) | `tmp/cob_pad_map.json` |
| Mezzanine connector pin # | `8` (single signal pin) | `tmp/mezz_pin_map.json` |

The same chip-pad position has different *signal* meaning across
projects. For example, diagram pad #0 is `clk_PAD` for GD03 / GD02 /
GD04 / TQVA / TQVB / TQVC, but `bidir_PAD[1]` on RZ80 (Z80 D1 data
bit) and `rst_n_PAD` on HZ80.

## The seven stage links

### 1. Diagram pad # (0..73)

How the `reticle_diagrams` pipeline numbers pads. Counter-clockwise
starting at the pad just *left* of the QR code in the top-right of
the diagram. The QR is in the top-right of the *diagram*; in the
GDS-native frame it actually sits in the *bottom-left* — `make_diagrams.py`
applies a 180° display rotation so QR ends up top-right in print.

Edge order (1×1 chip with 17/20/17/20 pads):

```
diag #   0..16  : top edge,    right -> left
diag #  17..36  : left edge,   top   -> bottom
diag #  37..53  : bottom edge, left  -> right
diag #  54..73  : right edge,  bottom -> top
```

Smaller chips have proportionally fewer pads per edge. Spreadsheet
column **D** ("Die Pad #") shows this.

### 2. Chip-side net name

The text label found on the GDS pad, project-specific. Common
patterns (from the wafer.space project template):

- `clk_PAD`, `rst_n_PAD` — dedicated clock / reset (Schmitt-trigger / CMOS input cells).
- `bidir_PAD[N]` — bidirectional GPIO or peripheral pin.
- `input_PAD[N]` — input-only.
- `analog_PAD[N]` — pass-through analog inout.
- `DVDD`, `DVSS` — digital VDD / VSS power-ring pads (each instantiated multiple times around the chip).
- `AVDD`, `AVSS` — analog supply (rare, project-specific).

Spreadsheet columns **G/I** (1×1), **P/R/U** (0.5×1), **AB/AD/AH**
(1×0.5), **AN** (0.5×0.5), **AR** (OCD1) hold the per-project chip
net at this pad position.

### 3. Internal RTL signal

The wire on the *core* side of the IO cell. For most projects:

- `clk_PAD2CORE` — Schmitt-trigger output of the clock cell.
- `rst_n_PAD2CORE` — output of the reset cell.
- `bidir_PAD2CORE[N]` — input of the bidir cell (incoming from the pad).
- `bidir_CORE2PAD[N]`, `bidir_CORE2PAD_OE[N]`, `_CS`, `_SL`, `_IE`, `_PU`, `_PD` — output / output-enable / drive-strength / input-enable / pull-up / pull-down controls.

The project-specific design layer often renames the bidir signal
downstream — e.g. `assign uart0_tx = bidir_CORE2PAD[36]`. The
spreadsheet's `Internal Net` columns (AT, AV, AX, AZ, BB, BD, BF,
BH) hold the most-meaningful name; if no rename happens it falls
back to `bidir_PAD2CORE[N]`.

### 4. KiCad CoB footprint pin number (1..74)

The "pad number" printed on the SMD pad in the CoB PCB layout
(`waferspace_default_padring_v0.2`). Pads number CCW from the
top-right of the PCB pad ring — *same direction* as diagram pad #
— so the relationship is:

```
pcb_pad = diagram_n + 1
```

Beware: KiCad uses **screen y-down** convention. A footprint-local
y-coordinate of `−4.70 mm` is *above* the origin on screen, not
below. The earlier mapping bug in this codebase came from reading
y as math-up. Pad 1 sits at `(+3.20, −4.70)` mm = top-right.

Spreadsheet column **B** (`1x1 CoB Footprint Pin Num`).

### 5. KiCad pinfunction (footprint pad name)

A composite identifier of the form `<symbol_pin_name>_<pcb_pad>`
attached to each footprint pad in the `.kicad_pcb`. Examples:

- `pad_0_1` — symbol pin `pad_0` at PCB pad `1`.
- `GND_46` — symbol pin `GND` at PCB pad `46`.
- `VDD_IO_18` — symbol pin `VDD_IO` at PCB pad `18`.

This is what KiCad displays as the *pad name* (vs. *pad number*) in
the PCB editor. Unique per pad.

Spreadsheet column **C** (`1x1 CoB Footprint Name`).

### 6. KiCad symbol pin name

The pin label on the *schematic symbol* of the padring. Strips the
`_<pcb_pad>` suffix from the pinfunction. Power pins repeat the
same symbol pin name across multiple footprint pads — e.g. `GND`
appears on PCB pads 9, 19, 27, 34, 36, 46, 57, 63, 71, 73. Signal
pins each have a unique `pad_N` symbol pin (N = 0..69, with 70
*signal* symbols sharing 70 of the 74 footprint pads; the remaining
4 are GND/VDD-class assigned to multiple footprint positions).

Not currently a spreadsheet column — derivable by stripping the
trailing `_NN` from column C.

### 7. KiCad schematic net name

The net the symbol pin is wired to in the CoB schematic. KiCad
prefixes root-sheet local nets with `/`, so:

- `pad_0` symbol pin → net `/pad_0`
- `GND` symbol pins → net `GND` (no slash; global power)
- `VDD_IO` symbol pins on different PCB pads → distinct nets `VDD_IO_0`, `VDD_IO_1`, `VDD_IO_2`, `VDD_IO_3` (4 separate I/O supply rails).

Stored in `tmp/cob_pad_map.json` field `net`. Not a spreadsheet
column — but visible as the trailing piece of pinfunction-strip-N
plus a leading `/` for non-power nets.

### 8. Mezzanine connector pin number (1..70)

The 70-pin SMD connector on the back side of the CoB
(`Connector:CONN-SMD_70P-P0.40_HCTL_HC-PBB40C-70DP-0.4V-02`). Each
schematic net carried by a footprint pad terminates at one or more
connector pins:

- **Signals** (`/pad_0` .. `/pad_69`) → exactly one connector pin each.
- **GND** → 6 numbered connector pins (10, 18, 25, 45, 53, 61) plus
  4 mounting-pad pins (treated as shield/strain-relief, not signal).
- **VDD_IO_0, VDD_IO_1, VDD_IO_2, VDD_IO_3** → 1 connector pin each (62, 44, 24, 9 respectively).
- **VDD_CORE_0, VDD_CORE_1** → 1 each (46, 11).
- **PWR_AUX_0, PWR_AUX_1** → 1 each (54, 19).

Spreadsheet column **A** (`1x1 CoB Connector Pin #`). Multi-pin
nets (GND in particular) are written `10/18/25/45/53/61`.

## Rotations and orientations — read this before debugging

Three different 180° rotations interact in this codebase. Keep them
straight or you will derive the wrong mapping:

1. **`make_diagrams.py` display rotation.** GDS-native bottom-left
   → diagram top-right. Applied so the QR is in the conventional
   top-right of every rendered diagram.
2. **Chip placement on CoB.** The chip is bonded face-up on the CoB
   with QR at PCB top-right (aligned with the rocket fiducial in
   the same corner). Because GDS-native QR is at GDS bottom-left,
   the chip is *physically rotated 180°* relative to its GDS frame
   when placed on the CoB.
3. **Effective rotation between diagram numbering and CoB pad
   numbering.** The two 180° rotations *cancel*: the diagram's
   top-right corner is the same physical position as the CoB's
   top-right corner. So `pcb_pad = diagram_n + 1` is the direct
   mapping — *not* `diagram_n + 37` (which would be the case if
   only one of the rotations applied).

The KiCad y-down convention adds a fourth potential confusion: a
footprint pad at `(+3.20, −4.70)` mm is at the *top-right* on
screen, not bottom-right.

## Data sources — what file holds what

| Field | File | Field name |
|---|---|---|
| diagram pad # | `tmp/pads_data.json` | `pads[].n` (= position in array per project) |
| chip pad x/y (post display rotation) | `tmp/pads_data.json` | `pads[].cx_um`, `cy_um` |
| chip-side net name | `tmp/pads_data.json` | `pads[].net` |
| chip-side function description | `tmp/research_*.json` | `function` |
| internal RTL signal | `tmp/research_*.json` | `internal_net` |
| pcb_pad (1..74) | `tmp/cob_pad_map.json` | `pcb_pad` |
| pcb_pad x/y (footprint-local mm, KiCad y-down) | `tmp/cob_pad_map.json` | `x_mm`, `y_mm`, `rot_deg` |
| pinfunction | `tmp/cob_pad_map.json` | `pinfunction` |
| symbol pin name | `tmp/cob_pad_map.json` | `symbol_pin_name` |
| schematic net | `tmp/cob_pad_map.json` | `net` |
| mezzanine connector pin # | `tmp/mezz_pin_map.json` | `connector_pins` |

The `tmp/` directory is gitignored — these files are regenerated by
the corresponding scripts (`extract_pads_remote.py`,
`parse_cob_padring.py`, `parse_mezz_connector.py`,
`fetch_repo_files.py`, sub-agent research).

## Spreadsheet column reference

| Col | Header | Source |
|---|---|---|
| A | `1x1\nCoB Connector\nPin #` | mezz_pin_map.json |
| B | `1x1\nCoB Footprint\nPin Num` | cob_pad_map.json `pcb_pad` |
| C | `1x1\nCoB Footprint\nName` | cob_pad_map.json `pinfunction` |
| D | `Die\nPad #` | snapshot index (= diagram_n) |
| E | `1x1\nCoordinates` | pads_data.json (post-rotation) |
| F | `1x1\nDie Edge` | pads_data.json `edge` |
| G | GD03 chip-side net | pads_data.json |
| H | placeholder for GD03 conn pin | (currently empty per project) |
| I | RZ80 chip-side net | pads_data.json |
| J | placeholder for RZ80 conn pin | (currently empty) |
| M..N..O | 0.5×1 die-pad #, coords, edge | pads_data.json (project-size group) |
| P | GD02 chip-side net | pads_data.json |
| R | TQVB chip-side net | pads_data.json |
| U | HZ80 chip-side net | pads_data.json |
| Y..AA | 1×0.5 die-pad # / coords / edge | pads_data.json |
| AB | GD04 chip-side net | pads_data.json |
| AD | TQVC chip-side net | pads_data.json |
| AH | OCD2 chip-side net | pads_data.json |
| AK..AM | 0.5×0.5 die-pad # / coords / edge | pads_data.json |
| AN | TQVA chip-side net | pads_data.json |
| AR | OCD1 chip-side net | pads_data.json |
| AS / AT | GD03 Function / Internal Net | research_racquet.json |
| AU / AV | RZ80 Function / Internal Net | research_z80.json |
| AW / AX | GD02 Function / Internal Net | research_racquet.json |
| AY / AZ | TQVB Function / Internal Net | research_tinyqv.json |
| BA / BB | HZ80 Function / Internal Net | research_z80.json |
| BC / BD | GD04 Function / Internal Net | research_racquet.json |
| BE / BF | TQVC Function / Internal Net | research_tinyqv.json |
| BG / BH | TQVA Function / Internal Net | research_tinyqv.json |

OCD1 and OCD2 are not in the deeper-research set; their chip-side
nets are populated but not the function/internal-net columns.

## Caveats discovered along the way

- **Racquet/GD03 RTL bug**: `bidir_PAD[37]` is positioned and
  symmetrically named as if it should be UART0 RX, but
  `chip_core.sv` actually wires `uart0_rx = gpio_a_alt_in[5][1]`
  (i.e. UART0 RX is on `bidir_PAD[5]`). The function column for
  pad 37 reflects *actual* wiring, not intent.
- **CoB v0.1 vs v0.2 padring**: an older v0.1 footprint exists at
  `chip-on-board-wire-bonded-pcbs/scratch/footprints/` with pad 1
  in the *top-left* corner. The active v0.2 (embedded in the
  `.kicad_pcb`) puts pad 1 in the **top-right**. Don't confuse
  them.
- **Power-rail multi-pinning on the connector**: `GND` appears on
  6 numbered connector pins; `VDD_IO_*` are 4 *distinct* nets each
  going to its own pin. The spreadsheet shows all matching pins
  separated by `/`.
- **Slot variants share most code**: GD02/GD03/GD04 share the
  Racquet RTL with different `slot_defines.svh`; HZ80/RZ80 share
  ws_z80.v RTL; TQVA/TQVB/TQVC share TinyQV. Per-pad function can
  differ between slot variants because the *number* of bidir pads
  differs and the slot-specific top hooks remap bits.

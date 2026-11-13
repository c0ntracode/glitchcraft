# Banked-address check against running emulator cores (agent-run, 2026-11-12)

## Purpose

A Game Boy or Game Gear Game Genie code has a 16-bit CPU address, an optional compare byte and no bank. Glitchcraft needs `--bank N` for addresses in a switchable window (`$4000-$7FFF` Game Boy; `$4000-$BFFF` Game Gear) and maps `(bank, addr)` to a file offset. Until now `references/gb.md` and `references/sega8.md` described what emulators do to such a code from reading source (OSINT); nothing ran. This check runs the two libretro cores installed here on synthetic ROMs that execute a different routine from each bank at one shared CPU address, and compares the picture with what the tool's `patch-copy --bank` model predicts.

Claims under test: (1) a 6-digit code applies in every bank; (2) a compare byte aims it at the one bank whose byte matches.

## Design of the demo ROMs

a private script (not published) writes two original, hand-assembled, 64 KB (4 bank) ROMs. No commercial code or data. Straight-line, no interrupts.

- `banked-demo.gb`: Game Boy Color, MBC5, valid logo and checksums (`gg.py id`: MBC5, 4 banks, header checksum ok). Bank 0 draws three horizontal thirds (tiles 1, 2, 3 = palette-0 colours 1, 2, 3), then every VBlank writes `$2000` = 1, 2, 3 and `CALL $4000` after each. The routine in bank *i* at `$4000` is `LD B,<lo>` / `LD A,$80|2i` / `LDH ($68),A` / `LD A,B` / `LDH ($69),A` / `LD A,<hi>` / `LDH ($69),A` / `RET`: it writes palette colour *i*, so bank *i* owns band *i*. The patched byte is the `LD B` immediate at `$4001`, in every bank. Originals: bank 1 `$1F` (red), bank 2 `$E0` (green), bank 3 `$00` (blue).
- `banked-demo.gg`: Game Gear, `TMR SEGA` header, region 6, size E, Sega mapper, checksum filled. Bank 0 builds the same three bands (name table over tiles 1-3), then every VBlank (polled via VDP status) writes `$FFFE` (slot 1 register; `$FFFF` is slot 2) = 1, 2, 3 with a `CALL $4000` each. Routine in bank *i*: `LD B,<lo>` / `LD A,2i` / `OUT ($BF),A` / `LD A,$C0` / `OUT ($BF),A` / `LD A,B` / `OUT ($BE),A` / `XOR A` / `OUT ($BE),A` / `RET`: CRAM colour *i*, low byte = the immediate at `$4001`. Originals: bank 1 `$0F`, bank 2 `$F0`, bank 3 `$FF`.

File offsets of the immediates (both ROMs): bank 1 `$04001`, bank 2 `$08001`, bank 3 `$0C001`. The three originals in each ROM differ, so a compare byte can single out a bank. The patch value is `$55` and the no-match compare is `$77` (in no bank).

## What was run

a private script (not published) (no display needed). It loads `/usr/lib/libretro/gambatte_libretro.so` and `/usr/lib/libretro/genesis_plus_gx_libretro.so` through a small ctypes frontend (one fresh subprocess per run), runs 180 frames, hashes the last frame and samples one pixel in each band. For each console:

- no cheat; 6-digit code; 9-digit codes with compare = bank 1, 2, 3 original; 9-digit code with compare `$77`;
- each run twice: cheat set via `retro_cheat_set` before frame 1 ("early"; slot 1 shows the reset bank, the routines not yet run) and after 60 frames ("late"; slot 1 shows bank 3 at the frame boundary);
- codes made with `gg.py make ROM --addr 4001 --value 55 [--compare H] --bank N` (N = the compare's bank; `make` refuses a compare that differs from the byte at `--bank`, so the `$77` code was made on a scratch copy whose bank-1 byte was set to `$77`);
- model: `gg.py patch-copy` with `--bank 1`, `2`, `3` chained on the same code, the final ROM run with no cheat. "Agrees" means the changed bands and the whole-frame hash both equal the emulator's.

Gambatte only loads if `GET_CAN_DUPE` answers true (the frontend does). An earlier draft of the Game Gear ROM wrote `$FFFF` (slot 2) instead of `$FFFE`; every call then ran bank 1's routine and the result was meaningless. That was a ROM bug, fixed before the results below.

## Results

Baseline bands (R, G, B of the three thirds): Game Boy red / green / blue (hash `93514e71`); Game Gear red / green / yellow (hash `57f181c0`). "Changed" = bands whose colour differs from baseline. Early and late runs gave identical frames in every row.

| Code | Console | Compare | Bands changed (emulator) | Frame hash | `patch-copy --bank` model | Agrees |
|---|---|---|---|---|---|---|
| `550-01B` | Game Boy (Gambatte) | none | 1, 2, 3 | `cdc95972` | 1, 2, 3 | yes |
| `550-01B-916` | Game Boy | bank 1 `$1F` | 1 | `c6ceab87` | 1 | yes |
| `550-01B-6E9` | Game Boy | bank 2 `$E0` | 2 | `5866a35e` | 2 | yes |
| `550-01B-E6A` | Game Boy | bank 3 `$00` | 3 | `b947c8e9` | 3 | yes |
| `550-01B-3B7` | Game Boy | `$77` (no bank) | none | `93514e71` (= baseline) | none | yes |
| `550-01B` | Game Gear (Genesis Plus GX) | none | 1, 2, 3 | `a4bdb1d1` | 1, 2, 3 | yes |
| `550-01B-D56` | Game Gear | bank 1 `$0F` | 1 | `e228c299` | 1 | yes |
| `550-01B-2A9` | Game Gear | bank 2 `$F0` | 2 | `1465423e` | 2 | yes |
| `550-01B-195` | Game Gear | bank 3 `$FF` | 3 | `a4b74f9b` | 3 | yes |
| `550-01B-3B7` | Game Gear | `$77` (no bank) | none | `57f181c0` (= baseline) | none | yes |

Each row held for both the early and the late apply (20 emulator runs, 10 model runs).

## What it shows

- **A 6-digit code applies in every bank**: observed on both cores. One code at `$4001` changed the routine's behaviour in banks 1, 2 and 3, including when set before the program ran (slot 1 showing bank 1) and when set later (bank 3 showing). The model is the union of per-bank `patch-copy` outputs, which matches.
- **A compare byte aims a code at one bank**: observed on both cores. Compare = a bank's original changed only that bank's band; a compare matching no bank changed nothing (frame equals baseline). The core evaluates the compare against the byte of the bank being read, as `patch-copy --bank N` does.
- Not distinguished here: *how* a core gets there. `references/sega8.md` says Genesis Plus GX patches the bank mapped when the code is applied and re-applies on banking changes. For a program that executes from each bank (this one), that is indistinguishable from "applies to every bank". The result is consistent with that description and with a per-read check; it does not discriminate between them. For Gambatte the earlier note said its source could not be checked; this is the first behavioural evidence: compare is bank-sensitive and no-compare codes reach all banks.
- Nothing here contradicts `references/gb.md` or `references/sega8.md`. The statement "Consequence for the tool" (a compare isolates a bank only if the other banks differ at that offset) is what the demo relies on, and it held.

## Glitchcraft observations (not blocking)

- `gg.py patch-copy ROM OUT 550-01B` on either demo ROM (no `--bank`, address `$4001`) prints `error: 550-01B patches $4001, which is not mapped to ROM here`, rc 2. `make` on the same address says the right thing (`in the switchable bank area; give the bank it runs from (--bank)`). Expected for `patch-copy`: the same bank hint.
- `gg.py decode ROM 550-01B-6E9 --bank 1` (compare `$E0`, ROM byte `$1F`) prints `compare=$E0 original=$1F` with no warning that the code will not apply; `patch-copy` and `make` do warn. Not wrong, only quieter than its siblings.
- `patch-copy` with a compare that does not match exits 0 and writes an unchanged copy (with a note on stdout). That is documented behaviour ("not applied (as on hardware)") but a script must read the note, not the exit code.

## Unverified

- Real hardware (Game Genie cartridge on a Game Boy or Game Gear). Only two emulator cores were run.
- Other emulators: SameBoy, mGBA, Gearsystem, Emulicious, bsnes-style forks. The references say they differ (mGBA patches only the first bank whose byte equals the compare); that was not run.
- Other mappers: only MBC5 (Game Boy) and the Sega mapper (Game Gear). MBC1 (bank 0 maps to 1), MBC3, MBC2, Codemasters, Korean and MSX mappers were not run.
- Game Gear slot 2 (`$8000-$BFFF`) and Game Boy `$0000-$3FFF` were not exercised; only slot 1 at `$4001`. Master System (6-bit CRAM, SMS mode of the core) was not run.
- Timing: a code applied mid-frame, a bank switched during the read, and ROMs that read the patched byte as data (rather than executing it) were not tried.
- RetroArch's own cheat-file loading and a real window (Gambatte and Genesis Plus GX were driven directly through `retro_cheat_set`).
- The Game Gear frame was sampled at three pixels plus a whole-frame hash; colour regions elsewhere were not inspected.
- Cheat decoding of `H` (the check digit) is ignored by both cores; the codes use Glitchcraft's `H = G xor 8`.

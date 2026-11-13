# Game Boy letter check (manual, run once)

Purpose: confirm that the Gambatte core in RetroArch and Glitchcraft decode a Game Boy Game Genie code the same way, including the bank rules (a 6-digit code applies in every bank; a compare byte aims a code at the one bank whose byte matches). No commercial or private ROM is needed: the check uses the synthetic banked Game Boy Color ROM that a private script (not published) generates on the spot (hand-assembled, MBC5, 64 KB, four banks). RetroArch needs a window, so the final check is manual.

From a terminal inside your desktop session (not SSH or remote desktop):

```sh
(script not published)
```

The script writes the demo ROM to a private `/tmp` directory, runs the unpatched ROM once, then for two codes (made at run time by `gg.py make`, so no letters are hard-coded) runs RetroArch twice: once with the code loaded automatically from a generated cheat file (`<tmp>/cheats/Gambatte/banked-demo.cht`), once with a Glitchcraft-patched copy and no cheat. You press nothing in the game. You name the colour of the top, middle and bottom bands (one letter each: r red, o orange, y yellow, g green, c cyan, b blue, m magenta/pink, k black, w white, x other) and it prints a result block to paste back. The cheat folder name is read from the core with `retro_get_system_info` (ctypes) at run time, falling back to `Gambatte`. Nothing in the repository changes and the temp directory is removed at exit.

## Demo ROM design

Bank 0 draws three horizontal bands (tiles using palette-0 colours 1, 2, 3) and, once per VBlank, switches the `$4000` window to bank 1, 2, 3 in turn and calls `$4000`. The routine in bank *i* is `LD B,<lo>` / `LD A,$80|2i` / `LDH ($68),A` / `LD A,B` / `LDH ($69),A` / `LD A,<hi>` / `LDH ($69),A` / `RET`: it writes Game Boy Color palette colour *i* as RGB555 (`lo` = the immediate at `$4001`, `hi` fixed per bank). Bank *i* therefore owns band *i*: bank 1 top, bank 2 middle, bank 3 bottom.

| Bank | Band | lo at `$4001` | hi | Colour word | Colour |
|---|---|---|---|---|---|
| 1 | top | `$1F` | `$00` | `$001F` | red |
| 2 | middle | `$E0` | `$03` | `$03E0` | green |
| 3 | bottom | `$00` | `$7C` | `$7C00` | blue |

Both codes patch `$4001` to `$FF`:

- `FF0-01B` (6 digits, no compare, made with `--bank 1`): applies in every bank. Colour words become `$00FF` (R31 G7 B0, orange), `$03FF` (R31 G31 B0, yellow), `$7CFF` (R31 G7 B31, pink-magenta). Expected, top to bottom: **orange, yellow, magenta** (all three bands change). The top band is red with a little green, so it is the subtle one; the unpatched top is pure red.
- `FF0-01B-6E9` (9 digits, compare `$E0`, made with `--bank 2`): `$E0` is bank 2's original only. Expected: **red, yellow, blue** (only the middle band changes; green becomes yellow).

The patched-copy run applies the code once per bank (`gg.py patch-copy ... --bank 1`, then 2, then 3, chained), because a Game Boy code has no bank and `patch-copy` needs one for `$4001`. That is the model the earlier banked check (`banked-emulator-check.md`) found to agree with the core. The compare mismatch notes `patch-copy` prints for banks 1 and 3 in the second code are expected.

## Passing criteria

- The unpatched run shows red, green, blue.
- For each code, "cheat entered" and "patched copy" both equal "expected" in the result block.
- If a row shows the unpatched colours, the code did not change the screen (the script also warns if RetroArch's log has no "Applying cheat changes" line). If only "cheat entered" matches, RetroArch's loading or Gambatte's decoder disagrees with Glitchcraft; if only "patched copy" matches, the cheat file was not applied.

## Headless corroboration (agent-run, 2026-11-12, not the author's check)

A throwaway driver in the agent's scratch directory (not committed) used a private script (not published) (`Session(core, rom).cheats([...]).run(120)`) with `/usr/lib/libretro/gambatte_libretro.so`, hashed the last frame (160x144, RGB565) and sampled one pixel in the middle of each band. Cheats were applied through the core's own `retro_cheat_set`.

| Run | Frame hash | Top, middle, bottom (RGB) |
|---|---|---|
| unpatched | 93514e71 | (255,0,0) red, (0,250,0) green, (0,0,255) blue |
| core + `FF0-01B` | 3f07843a | (255,56,0) orange, (255,250,0) yellow, (255,56,255) magenta |
| `patch-copy` ×3 banks `FF0-01B`, no cheat | 3f07843a | same |
| core + `FF0-01B-6E9` | 7a97e895 | (255,0,0) red, (255,250,0) yellow, (0,0,255) blue |
| `patch-copy` ×3 banks `FF0-01B-6E9`, no cheat | 7a97e895 | same |

So the core's own decoder and the patch-copy ROM give identical frames for both codes, each different from the unpatched frame, and the colours match the expected wording above. Scope: agent-run, the driver is a throwaway, and it does not exercise RetroArch's cheat-file loading, `apply_cheats_after_load` or a real window. The author's run below is still the check that counts.

## Limits

One synthetic ROM, one address (`$4001`), one core. It does not cover Game Boy codes in fixed ROM (`$0000-$3FFF`), RAM codes, or a real cartridge. Colour naming depends on your display; orange versus red on the top band is the least forgiving answer.

## Result

Passed (author's run, 2026-11-12; RetroArch 1.22.2-6, libretro-gambatte 20261023, generated synthetic banked ROM, cheat folder `Gambatte`).

| Run | Expected (top, middle, bottom) | Cheat loaded in RetroArch | Glitchcraft-patched copy |
|---|---|---|---|
| unpatched | red, green, blue | red, green, blue | |
| `FF0-01B` (6 digits, `$4001` -> `$FF`, every bank) | orange, yellow, magenta | orange, yellow, magenta | orange, yellow, magenta |
| `FF0-01B-6E9` (9 digits, compare `$E0` = bank 2's byte) | red, yellow, blue | red, yellow, blue | red, yellow, blue |

Gambatte and Glitchcraft decode a 6-digit and a 9-digit Game Boy code the same way in RetroArch with its own cheat-file loading, and the bank rules hold in a real window: a code with no compare changes the byte in every bank, and a compare byte aims it at one bank. One synthetic ROM, one address; real-game evidence is in `ingame-links-awakening.md`, `ingame-pokemon-red.md` and `real-roms-2026-11-12.md`.

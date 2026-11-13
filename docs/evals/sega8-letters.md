# Game Gear / Master System letter check (manual, run once)

Purpose: confirm that the Genesis Plus GX core in RetroArch and Glitchcraft decode a Game Gear / Master System Game Genie code the same way. No commercial game is needed: the check uses a tiny homebrew demo ROM generated on the spot by a private script (not published) (hand-assembled Z80, 32 KB, `TMR SEGA` header at `$7FF0`, region 6 = Game Gear Export, size C). RetroArch needs a window, so the final check is manual.

From a terminal inside your desktop session (not SSH or remote desktop):

```sh
(script not published)
```

The script runs the unpatched demo once, then for two codes (made at run time by `gg.py make`, so no letters are hard-coded) runs RetroArch twice: once with the code loaded automatically from a generated cheat file (`<tmp>/cheats/Genesis Plus GX/<rom>.cht`), once with a Glitchcraft-patched copy and no cheat. You press nothing in the game; you name the screen colour (r / m / g / o) and it prints a result block to paste back. The cheat folder name is read from the core with `retro_get_system_info` (ctypes) at run time; it returned `Genesis Plus GX` (v1.7.4, extensions include `sms|gg|sg`).

## Demo ROM design

The program is straight-line code in bank 0 with interrupts off: set VDP registers 0-10, clear all 16 KB of VRAM, load the colour into registers `B` (`$0070`, `LD B,n`) and `C` (`$0072`, `LD C,n`), write it to CRAM entries 0 (background) and 16 (backdrop), turn the display on, `JR $`. Every visible pixel is therefore that one colour.

It targets the Game Gear: CRAM is 12-bit, two bytes per entry (low byte `$GR`, high byte `$0B`). Master System CRAM is 6-bit (one byte), so the same bytes would not mean the same thing there. Unpatched: `B=$0F`, `C=$00` = `$000F`, pure red.

- Code `0F0-72F` (6 digits): `$0072` `$00` -> `$0F`; colour `$0F0F` = magenta.
- Code `F00-70F-D56` (9 digits, compare `$0F`): `$0070` `$0F` -> `$F0`; colour `$00F0` = green.

The two addresses differ, both are in bank 0 (Game Genie on these systems patches ROM reads at `$0000-$7FFF`), and neither is in the header.

## Headless corroboration (agent-run, 2026-11-12, not the author's check)

A throwaway ctypes frontend kept outside the repository loaded `/usr/lib/libretro/genesis_plus_gx_libretro.so`, loaded the demo ROM, ran 120 frames and hashed the last frame (160x144, RGB565, one colour fills every pixel). Cheats were applied through the core's own `retro_cheat_set`.

| Run | Frame hash | Colour (RGB565) |
|---|---|---|
| unpatched | 638d8663 | `f800` red |
| core + `0F0-72F` | 33a09d74 | `f81f` magenta |
| `patch-copy` `0F0-72F`, no cheat | 33a09d74 | `f81f` |
| core + `F00-70F-D56` | 6e3d11f1 | `07e0` green |
| `patch-copy` `F00-70F-D56`, no cheat | 6e3d11f1 | `07e0` |
| core + same code with a wrong compare (`F00-70F-B3F`, compare `$55`) | 638d8663 | red (ignored) |
| `patch-copy` with the wrong-compare code | 638d8663 | red; says "not applied" |

So the core's decoder and Glitchcraft's agree on one 6-digit and one 9-digit code at different addresses, and both honour a failing compare. Scope: agent-run, the frontend is not committed, it does not exercise RetroArch's cheat-file loading or a real window, and it covers only the Game Gear demo (no Master System, no banked addresses). The author's run below is still the check that counts.

## Result

Passed (author's run, 2026-11-12, RetroArch 1.22.2-6, libretro-genesis-plus-gx 20260605, cheat folder `Genesis Plus GX`), on the generated Game Gear demo ROM.

| Run | Expected | Cheat loaded in RetroArch | Glitchcraft-patched copy |
|---|---|---|---|
| unpatched | red | red | |
| `0F0-72F` (6 digits, `$0072` `$00`->`$0F`) | magenta | magenta | magenta |
| `F00-70F-D56` (9 digits, compare `$0F`, `$0070` `$0F`->`$F0`) | green | green | green |

Genesis Plus GX and Glitchcraft decode a 6-digit and a 9-digit Game Gear code the same way, through RetroArch's own cheat-file loading and a real window, which also agrees with the headless run above. One synthetic ROM, bank 0, two addresses; real-game and banked evidence is in `real-roms-2026-11-12.md` and `banked-emulator-check.md`.

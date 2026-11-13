# Genesis letter check (manual, run once)

Purpose: confirm that the Genesis Plus GX core in RetroArch and Glitchcraft decode a Game Genie code the same way. Headless automation is not available here (RetroArch needs a window), so this is a short manual check that uses a visible number: Sonic 1's starting lives.

From a terminal inside your desktop session (not SSH or remote desktop):

```sh
(script not published)
```

The script runs the unpatched ROM once, then for two codes (starting lives 5 and 9, made at run time by `gg.py make`) runs RetroArch twice: once with the code loaded automatically from a generated cheat file (nothing to type or click), once with a Glitchcraft-patched copy and no cheat. You type the lives number you see each time, and it prints a result block to paste back.

Reading it: the check passes when, for each code, "cheat entered" and "patched copy" both equal "expected", and both differ from the unpatched number. If both stay at the unpatched number, the address (`$003334`) is not the new-game start in this dump and the test needs another occurrence of `MOVE.B #3,($FFFFFE12).w`; that is a test-design problem, not a decoder disagreement.

Limits: two codes at one address, with a result read off the screen. The script layers a throwaway config over yours (cheat path, auto-apply, windowed); your `retroarch.cfg` is not touched. It warns if RetroArch's log does not show the cheat being applied.

## First run (2026-11-12): red screen

Every patched run (cheat and patched copy) showed a red screen. Cause: Sonic 1 checksums the ROM at boot (`$32C`-`$33A`, fail branch to `$3B8`), so any patch fails it. The script now adds a checksum bypass (`JEBT-BFK2`, `CMP.W (A1),D1` -> `CMP.W D1,D1` at `$000338`) to every patched run. The red screen did not show a decoder disagreement.

## Second run: lives stayed 3

The game ran (bypass worked) but lives stayed 3 for both the RetroArch cheat and the patched copy. The patched copy involves no RetroArch decoding, so this was the wrong address, not a letter disagreement. `$003308` is the immediate of the `MOVE.B #3,(lives)` at `$3306`, which is the level-select path (it follows `gamemode := $10`). The title-screen Start path is `$3332` (after `gamemode := $0C`), so the test now patches `$003334`. Three other `#3,lives` stores exist (`$3436`, `$4E30`, `$58D0`), reached from other game modes.

## Result

Passed (author's run, 2026-11-12, RetroArch 1.22.2-6, libretro-genesis-plus-gx 20260605). ROM: Sonic_The_Hedgehog_W_REV01_h3C.bin. Patches also included the checksum bypass `JEBT-BFK2`.

| Code | Expected | Cheat loaded in RetroArch | Glitchcraft-patched copy |
|---|---|---|---|
| (none) | 3 | 3 | |
| AY3T-AABY | 5 | 5 | 5 |
| BE3T-AABY | 9 | 9 | 9 |

Genesis Plus GX and Glitchcraft decode these two codes the same way. Two codes at one address is a small sample; the address bits are exercised only at $003334 and $000338.

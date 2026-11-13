# SNES letter check (manual, run once)

Purpose: confirm that our decoder and `snes9x` read the same code the same way. Headless automation did not work in this environment (`snes9x` stalls after audio setup under `xvfb-run`, with or without software GL), so this is a short manual check. It does not need Claude.

**Easiest:** from a terminal inside your desktop session (Konsole, not SSH or remote desktop), run a private script (not published). It does the steps below, asks two yes/no questions per code, and prints a result block to paste back.

By hand, from the repository root. The ROM is your own copy.

```sh
ROM="roms/snes/smw/Super Mario World (USA).sfc"

# 1. Unpatched, for reference
snes9x "$ROM"

# 2. snes9x applies the code itself (this uses snes9x's own decoder)
snes9x -cheatcode 61CB-AF6F "$ROM"

# 3. Our decoder patches a copy of the ROM; run it WITHOUT -cheatcode
python3 scripts/gg.py patch-copy "$ROM" /tmp/smw-61CB-AF6F.sfc 61CB-AF6F
snes9x /tmp/smw-61CB-AF6F.sfc
```

Repeat 2 and 3 for `D532-6DAD`. Delete `/tmp/smw-*.sfc` afterwards.

| Code | Unpatched | `-cheatcode` (snes9x decoder) | `patch-copy` (our decoder) | Same? |
|---|---|---|---|---|
| `61CB-AF6F` (we decode `$00A796`: `$C2` to `$86`) | reference | differs (y) | same as `-cheatcode` (y) | yes |
| `D532-6DAD` (we decode `$00E2D3`: `$40` to `$07`) | reference | differs (y) | same as `-cheatcode` (y) | yes |

"Same?" is yes when steps 2 and 3 behave identically from power-on (what the screen shows in the first few seconds, whether the music plays) and both differ from step 1. If they differ from each other, one decoder is wrong; send the row to Claude. If neither differs from step 1, pick a different code from the public list; the point is a visible effect.

Results go in this file. Until the table is filled in, the SNES codec has been checked against the published algorithm text and against the instructions at the decoded addresses in the ROM, not against a running emulator.

## First attempt, 2026-11-12 (author)

`snes9x` started in all six runs but could not open a window ("Failed to connect to X server": no `DISPLAY` in that shell), so nothing was seen on screen and the table above is still empty. What the console output does show:

- `snes9x` independently identified the ROM as `"SUPER MARIOWORLD" (NTSC) version 1.0`, LoROM, 4 Mbit, SRAM 16 Kbit, CRC32 `b19ed489`, "Checksum OK". That agrees with `gg.py id` (LoROM, title `SUPER MARIOWORLD`, 512 KB).
- The two `patch-copy` files report "Invalid Checksum" (CRC32 `cec715f0` for `61CB-AF6F`, `181d5c3d` for `D532-6DAD`), as expected for a ROM with a byte changed. The `-cheatcode` runs report the unpatched CRC32, as expected for a runtime cheat.
- `snes9x` printed no complaint about either code string.

None of this proves the letters decode alike. A run with a display is still needed.

## Result, 2026-11-12 (author, a private script (not published), snes9x 1.63-2.1)

Both codes: the `-cheatcode` run differed from the unpatched run, and the patched-copy run matched the `-cheatcode` run. The two decoders agree on `61CB-AF6F` and `D532-6DAD`.

Limits of this check: two codes, two different addresses (`$00A796` and `$00E2D3`), judged by eye and ear rather than by comparing bytes. A bit-layout error would rarely leave two different addresses behaving identically, but this is not an exhaustive test. More codes can be run through the same script by editing its `codes=(...)` line.

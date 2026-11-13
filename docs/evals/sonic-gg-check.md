# Sonic the Hedgehog (Game Gear) real-game check (manual, run once)

Purpose: confirm on a real game that the Genesis Plus GX core in RetroArch and Glitchcraft read a Game Gear Game Genie code the same way. The published code `013-7DE-E66` ("start with 1 life") decodes to address `$137D`, new value `$01`, compare `$03`, original byte `$03` (`LD A,$03` -> `LD A,$01`, in the fixed region, so bank-independent). A second code is made at run time with `gg.py make --addr 137D --value 05 --compare 03` (5 starting lives); no letters are hard-coded except the published one, used as given.

The ROM is your own dump, git-ignored, and is never copied or downloaded: Sonic the Hedgehog (JUE) (V1.0), sha1 `8923295c96b2e05da0a83a827fd709b033fc7332`, default path `roms/sega8/Sonic the Hedgehog (JUE) (V1.0).gg`.

## How to run

From a terminal inside your desktop session (not SSH or remote desktop):

```sh
(script not published)
(script not published)
```

The script first checks the ROM: `gg.py decode` must report original `$03` and must not say "will not apply" (it stops otherwise); a different sha1 only warns. It then runs RetroArch five times: unpatched; then for each code once with a cheat file loaded automatically (`<tmp>/cheats/<core folder>/<rom>.cht`) and once with a `gg.py patch-copy` ROM and no cheat. In each run: press Start at the title screen (RetroArch defaults: arrow keys, Z and X for buttons, Enter for Start), play until Green Hill Zone Act 1 begins, read the lives on screen, close RetroArch with Esc, type the number. The instruction text is the `INSTRUCTIONS` variable at the top of the script. A throwaway `--appendconfig` keeps saves and states in the temp directory and never writes your `retroarch.cfg`; the temp directory is removed at exit.

## What passing looks like

| Run | Expected lives |
|---|---|
| unpatched | 3 |
| `013-7DE-E66` | 1 (cheat entered and patched copy) |
| generated code (`053-7DE-E66` expected from the current encoder) | 5 (cheat entered and patched copy) |

Paste back the RESULT block (ROM, sha1, package versions, one row per code).

## Limits

- One game, one revision, one address in the fixed region; banked addresses are covered elsewhere (`banked-emulator-check.md`).
- The lives count is read by eye at the start of Green Hill Zone Act 1; the exact on-screen spot is not specified yet.
- Dry-run only so far (stub `retroarch`, pty): it confirms the cheat file, config and prompts, not emulation.
- A different dump (V1.1, other region) may use another address; the sha1 warning flags that.

## Headless corroboration (agent-run, 2026-11-12, not the author's check)

A helper agent drove the real Genesis Plus GX core headlessly on the V1.0 dump with injected button presses (throwaway frontend, not committed). The intro runs about 540 frames and cannot be skipped; one Start press at about frame 620 reaches a Green Hill map screen (lives readable from about frame 740 for about 5 seconds) and then gameplay (from about frame 1186). Frame hashes and the lives counter agreed between the core's own cheat decoder and `gg.py patch-copy`: unpatched `x03` / 3 (map hash 6489a321, gameplay c0530829), published `013-7DE-E66` `x01` / 1 (9b694ff8, 2cb78187), generated `053-7DE-E66` `x05` / 5 (597946dc, 59cca54d). A screenshot comparison is in the agent's scratch directory only. Cheats were set before the first frame, not mid-game; continues and game over were not tried. This does not exercise RetroArch's cheat-file loading or a real window, so the author's run below is still the check that counts.

## Result

Passed on the author's second run (2026-11-12; RetroArch 1.22.2-6, libretro-genesis-plus-gx 20260605, ROM `Sonic the Hedgehog (JUE) (V1.0).gg`, SHA-1 `8923295c...`). The first run had the patched copies right (1 and 5) but both RetroArch cheat runs stayed at 3: the script named the cheat file by stripping only the last extension, while RetroArch cuts the game name at the first dot (`...(V1.cht`). That was a script bug, fixed and guarded by a test; the cheat then loaded.

| Run | Expected | Cheat loaded in RetroArch | Glitchcraft-patched copy |
|---|---|---|---|
| unpatched | 3 | 3 | |
| published `013-7DE-E66` (start with 1 life) | 1 | 1 | 1 |
| generated `053-7DE-E66` (start with 5 lives) | 5 | 5 | 5 |

A published Game Genie code, decoded by Glitchcraft, changes a real game's starting lives in RetroArch exactly as the published description says, and Glitchcraft's own patched copy agrees. One game, one code family, one address in the fixed region; banked codes on real games were checked by compare byte and the synthetic banked ROMs, not by this run.

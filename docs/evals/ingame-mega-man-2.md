# In-game effect check: "start with 1 life" PANALALA on Mega Man 2 (NES, USA)

Agent-run, 2026-11-12, headless (no window, no author involvement). Driver: a private script (not published) (usage line at the top; prints one PASS/FAIL line, exit 0 on pass, 77 if the ROM or core is missing; about 10 s for the three runs).

Setup: the author's dump `roms/nes/Mega Man 2 (USA).nes` (SHA-1 starts `2290d8d839a3`), core Nestopia (`/usr/lib/libretro/nestopia_libretro.so`), shared frontend a private script (not published). Code `PANALALA`: `gg.py decode ROM PANALALA --bank 14` gives `$8073 value=$01 compare=$03 original=$03` (compare matches the ROM byte); `gg.py vet --bank 14` gives `LDA #$03 -> LDA #$01`, flags none (instruction boundary inferred by linear sweep, not confirmed with `disasm`). Bank 14 is a 16 KB PRG bank of the MMC1 switchable window ($8000-$BFFF); the fixed bank is $C000-$FFFF.

## Why this code

The lives counter is a plain RAM byte, and the game never draws it in a stage or on the pause menu (checked: the pause screen shows weapons and E-tanks only), so the screen alone cannot show 3 vs 1. A behavioural test can: with 1 life the game reaches the Game Over menu after 2 deaths instead of 4. Moonwalking (PGEAKOPX) was not tried.

## Method

1. Counter found: NES RAM `$00A8` (system RAM offset 0xA8 = address, so Nestopia exposes CPU RAM $0000-$07FF at offset = address). Evidence: it reads 3 in an unpatched run, 1 in a run with the cheat once the game starts (from about frame 600), and falls 3 -> 2 -> 1 -> 0 on successive deaths. A published map was not consulted.
2. Nestopia accepts the NES Game Genie code through `retro_cheat_set(0, True, "PANALALA")` as is (no format change needed): the counter becomes 1.
3. Input (joypad ids, NES A/B not used): Start held 4 frames at 150, 350, 550 (title, menu, Start/Password menu), LEFT at 900 (cursor from Dr. Wily to Heat Man), Start at 950 (pick the stage), RIGHT held from 2000 to the end. Mega Man walks into the first pit, dies, respawns, repeats. Same input in all runs, each in a fresh process: (a) unpatched ROM; (b) `retro_cheat_set` before frame 1; (c) `gg.py patch-copy ROM OUT PANALALA --bank 14`, no cheat.
4. Sampled every 100 frames: `$A8` and frame hash (first 8 hex of SHA-1 of the raw frame).

## Evidence

| Frame | (a) unpatched | (b) cheat | (c) patch-copy |
|---|---|---|---|
| 100 (title) | lives 3, `bbf12fd6` | lives 3, `bbf12fd6` | lives 3, `bbf12fd6` (same trace as (b) throughout) |
| 2200 (in Heat Man stage, before the first death) | lives **3** | lives **1** | lives **1** |
| 2400 (after first death) | lives **2** | lives **0** | lives **0** |
| 3200 | lives 1, still in the stage (Mega Man dying, frame `70613e29`) | lives 0, **Game Over menu** (CONTINUE / STAGE SELECT / PASSWORD), `250ecc14` | identical to (b) |
| 4200 | lives 0, same menu, `82d8f8dd` | lives 0, `82d8f8dd` | `82d8f8dd` |

- (b) and (c) are identical in lives and frame hash at all 42 samples (frames 100..4200, step 100). The driver tests this exactly (`Bb == C`).
- (a) reaches the same menu only after its fourth death (third visible decrement to 0 plus one more); (b) and (c) reach it after the second death. At frame 4200 all three show the same menu frame (same blink phase).
- Screenshots (scratch only): `a_3200.png` shows Mega Man's death explosion in the stage; `b_3200.png` and `c_3200.png` show the Game Over menu.
- Driver output line: `PASS: lives in stage a=3 b=1 c=1; after first death a=2 b=0 c=0; b==c at all 42 samples: True; ...`.

## What this proves

The `LDA #$03` at `$8073` in bank 14 (MMC1 switchable window) is the start-of-game lives initialiser as reached in real play; changing it to `#$01` by Nestopia's own Game Genie decoder (b) and by Glitchcraft's `patch-copy --bank 14` (c) gives the same running game, frame for frame, with 1 life where the unpatched game has 3. The published effect holds, and the core's decoder and gg.py's bank numbering (16 KB PRG banks for mapper 1) agree on a banked address.

## What it does not prove

- Not the "lives" meaning of the byte in a published RAM map: `$A8` is identified only by behaviour (initial value, decrement per death, Game Over at the next death after 0).
- Not RetroArch's cheat-file path or a real window; `retro_cheat_set` was called directly, before frame 1, not mid-game.
- The bank was confirmed by the compare byte and by (b)=(c) equality, not by showing the cheat address is switched out of the CPU window at other times.
- One stage, one input script, USA ROM only. Other regions or revisions untested.
- (a)'s count of deaths to Game Over is inferred from the counter trace (3, 2, 1, 0), not each death screenshotted.
- The other four listed codes (NNEAALLV, PESUGPLE, PGEAKOPX, SXUGTPVG) were not tested in play.

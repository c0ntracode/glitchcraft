# Pokemon Red (Game Boy): one-hit kills, played in the core (headless, agent-run, 2026-11-12)

Purpose: show on a real game that a published Game Genie code living in a switchable ROM bank has its published effect, and that Gambatte's own cheat decoder and `gg.py patch-copy --bank N` agree. Driver: a private script (not published) (uses a private script (not published); no window, about 9 seconds for all three runs).

ROM: the author's own dump `roms/gb/Pokemon Red.gb`, sha1 `ea9bcae617fdf159b045185467ae58b2e4a48b9a` (read only; the patched copy goes to a work directory). Core: `/usr/lib/libretro/gambatte_libretro.so` (MBC3, 64 banks).

## Code chosen and why

`3E1-6B9-2AA`, "one-hit kills": address `$616B`, value `$3E`, compare `$30`, bank 15 (file offset `0x3E16B`; `gg.py decode` gives exactly these, and the ROM holds `$30` at that offset). Chosen because the first battle in the game (the rival's Squirtle in Oak's lab, about 15,000 frames from power-on) shows it plainly: one Scratch takes the rival's HP from 20 to 0 instead of to 16, readable from RAM and visible on screen. The other candidates were worse in this first battle: `C9F-3C9-E69` (no random battles) needs a starter plus a long walk through Route 1 grass with no guaranteed encounter in the unpatched run; `002-129-F77` (infinite health) and `C96-BC9-081` (opponent does not attack) show nothing, because the rival's Squirtle only uses Tail Whip (no damage) in the sampled window; `CED-56A-D50` (debug mode) has no stated effect that is visible without more menu work. A trial run of `C96-BC9-081` through the same script never reached the same battle state (rival HP stayed 0 through the sample window); that was not investigated and no claim is made about it.

## Input schedule (identical in all three runs)

Joypad ids from the shared driver; frames are core frames from power-on; hold lengths in frames.

| Frames | Input | State reached |
|---|---|---|
| 300 to 4020 | A held 4 every 30 (nothing is pressed before 300; the title screen accepts A) | Title, New Game, Oak's speech, default player name (A on the keyboard types `AAAAAAA`), rival name, bedroom fade-in |
| 4300 to about 5300 | RIGHT x4, UP x5, RIGHT x3 (16 frames per tile), 120 wait | Stairs; map `$25`, house |
| to about 5900 | DOWN x6, LEFT x4, DOWN x2, 200 wait, RIGHT x3, UP x4, RIGHT x2, UP x5 | Pallet Town (map `$00`), (10,1); Oak stops us |
| to the lab | RIGHT tapped and A tapped, alternating each 20 frames, until the player stands at map `$28` (5,3) facing right | Oak's walk and talk done, next to the Charmander ball |
| then | A (3 frames), then A every 30 until the party count (`$D163`) is 1, then B every 30 for 560 frames (answers NO to the nickname prompt), then wait until the screen is still | Charmander in the party |
| then | DOWN x8 (the rival challenges at map `$28` (5,6)) | Rival battle starts (about frame 14,500) |
| 13,960 to 15,730 | A held 2 every 30 frames, 60 samples | Through the rival's text, FIGHT, first move (Scratch), repeat |

Waits that depend on game state (the RIGHT/A probe, the party-count loop, the still-screen wait) are driven by RAM and the picture, so they end on the same frames in all runs only if the game behaves the same up to that point; the check that they did is that the three traces share frame numbers (below).

## Observable

The rival's current HP (big-endian, WRAM `$CFE6/$CFE7`; Gambatte system RAM is WRAM, offset = address - `$C000`, verified by reading the map byte `$D35E` = `$26` in the bedroom, `$28` in the lab), sampled every 30 frames, plus the frame hash and `wIsInBattle` (`$D057` = 2, a trainer battle). Charmander's HP (`$D015`) is 19 in all runs at the sample points.

## Evidence (fresh process each; frames from power-on)

| Run | Rival HP at start | Rival HP after first Scratch (frame 15,430) | HP at frame 15,730 | Hash at frame 15,730 | Screen at 15,730 |
|---|---|---|---|---|---|
| (a) unpatched | 20 | 16 | 16 | `a81db36d` | Squirtle alive, "CHARMANDER's DEFENSE fell!" |
| (b) `retro_cheat_set("3E1-6B9-2AA")` before frame 1 | 20 | 0 | 0 | `49ccefd6` | Squirtle gone, "CHARMANDER gained 70" (EXP) |
| (c) `gg.py patch-copy ROM OUT 3E1-6B9-2AA --bank 15`, no cheat | 20 | 0 | 0 | `49ccefd6` | same as (b) |

(b) and (c) agree on all 60 samples (frame, HP, frame hash) and on the end state; (a) differs from both from frame 15,430 on. `patch-copy` changed exactly one byte of the ROM, offset `0x3E16B`, `$30` to `$3E`. Screenshots were seen in the agent's scratch directory only (`a_unpatched.png`, `b_cheat.png`, `c_patchcopy.png`).

Verdict line from the driver: `PASS: 3E1-6B9-2AA (bank 15 $616B) one-hit kill in Pokemon Red: first-hit rival HP a=16 b=0 c=0; cheat run == patched-copy run: True`.

## What this proves

A published code at `$616B` in bank 15 (compare `$30`, so bank-dependent) changes the real game in the way its title says (a trainer's Pokemon goes from 20 HP to 0 on the first hit), when applied by Gambatte's own decoder and when written into the ROM by Glitchcraft with `--bank 15`. The core's decoder and Glitchcraft agree on the effect and, by frame hash, on every sampled frame of the battle. It also shows the early (before frame 1) cheat set takes effect with bank 15 mapped only later (during the lab fight), which is the compare-byte logic working in a real game.

## What it does not prove

- RetroArch's cheat-file loading and a real window (this is the core API, not the frontend).
- That the code's effect is "kills on any hit" in general: one move (Scratch), one enemy, one battle. No wild battles, no status moves, no misses.
- That the code is inert when the compare byte does not match (not tried here; covered by `banked-emulator-check.md`).
- The other five published codes' effects: only `3E1-6B9-2AA` was played.
- The cause of the `C96-BC9-081` divergence noted above.

## Unverified

- The title "one-hit kills" is the published description as given to the task; the effect seen (HP to 0 on the first hit, EXP awarded) is consistent with it, but the disassembly was not read.
- Frame numbers are specific to this ROM revision, core build and the driver's timing; the wait loops are state-driven, so small drift in the core could move them.
- The trace holds the rival's HP only; damage to Charmander was never in play (Squirtle used Tail Whip in the sampled window).

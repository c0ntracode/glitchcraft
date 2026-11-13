# In-game effect check: "infinite lives" 007-01A-3BE on Sonic the Hedgehog (Game Gear, V1.0)

Agent-run, 2026-11-12, headless (no window, no author involvement). Driver: a private script (not published) (usage line at the top; skips with exit 2 if the ROM or core is missing; about 75 s for the three runs, about 130 s with `--gameover`).

Setup: the author's V1.0 dump (SHA-1 `8923295c...`), core Genesis Plus GX (`/usr/lib/libretro/genesis_plus_gx_libretro.so`), shared frontend a private script (not published). Code `007-01A-3BE`: `gg.py decode ... --bank 1` gives `$5701 value=$00 compare=$35`; `gg.py vet ... --bank 1` gives `DEC (HL) -> NOP` (flag `opcode-class-change`; instruction boundary inferred by linear sweep, not confirmed with `disasm`).

## Method

1. Lives counter found by diff: bytes equal to 3 at frame 1300 in an unpatched run that were 5 in a run with the start-lives code `053-7DE-E66`. One match: Z80 RAM offset `0x1240` = `$D240` (offset = address - 0xC000). It goes 3 -> 2 on the first death, so it is the live counter.
2. Binary, not BCD (inferred): the start-lives code `103-7DE-E66` (value $10) leaves the byte at 16 and the HUD shows `9` (display clamps at 9). A BCD byte would show 1/0 digits. Also the game decrements it with a plain `DEC (HL)`.
3. Deterministic death with no rings and no enemy: RIGHT held from frame 1190 runs Sonic into the first item monitor, where he stalls; the 10:00 level time limit kills him. Tried first: holding RIGHT alone for 6000 frames (stalls at the monitor, no death by then). Time-over repeats at exactly the same frame in every run (the core is deterministic).
4. Identical input in all runs: Start held 6 frames from frame 620, RIGHT held from 1190 to the end. Each run is a fresh process. (a) unpatched; (b) `retro_cheat_set` before frame 1; (c) `gg.py patch-copy ROM OUT 007-01A-3BE --bank 1`, no cheat.
5. RAM watched every 5 frames: lives `$D240`, level clock minutes `$D2CF` and seconds `$D2D0` (BCD bytes; the table prints them as decimal values of the bytes, so 81 = `0x51` = 51 s, 21 = `0x15`), rings `$D2A9`.

## Evidence

| Run | Frame 46000 (9:51 on screen) | Frame 47600 (after 1st death) | Frame 93500 (after 2nd death) |
|---|---|---|---|
| (a) unpatched | lives 3, hash `c575380f` | lives **2**, 0:08, hash `34cf3b8d` | lives **1**, 0:15, hash `100545f4` |
| (b) cheat | lives 3, `c575380f` | lives **3**, 0:08, hash `18c1fc5d` | lives **3**, 0:15, hash `8d49e1db` |
| (c) patch-copy | lives 3, `c575380f` | lives **3**, 0:08, `18c1fc5d` | lives **3**, 0:15, `8d49e1db` |

- Death events (clock 9:xx -> 0:xx, level restart): frames 46665 and 92065 in all three runs, so (b) and (c) did die and respawn.
- Counter change in (a): 3 -> 2 at frame 46755 (90 frames after the clock reset, at respawn), 2 -> 1 at frame 92155. In (b) and (c) the list of counter changes is only the initial 3: it never moved.
- On screen (frame 93500, screenshots in scratch only): HUD bottom-left shows `1` in (a) and `3` in (b) and (c); clock 0:15 and ring count 03 in both, Sonic standing at the same monitor.
- (b) and (c) are identical in lives, clock, rings and frame hash at every sample. Frame 46000 is identical in all three (hash `c575380f`), so the runs diverge only after the death.

Verdict: PASS (the driver prints `PASS: lives after the first death a=2 b=3 c=3; after the second a=1 b=3 c=3`).

## Game over path (unpatched only, not required)

Run (a) to frame 160000: counter 3 (1190), 2 (46755), 1 (92155), 0 (137680), then back to 3 at frame 138565 and falling again (2 at 144165, 3 at 144740, ...). So the third death takes it to 0 and the game then returns to 3 lives after a game over screen and restart (what the screen shows in between, and whether it is Game Over or a continue, was not looked at). The patched runs were not run past 93500, so the infinite-lives code was not tested at the game over path (it never reaches 0 by this route).

## What this proves

The lives decrement at `$5701` in bank 1 is reached in real play and is what lowers `$D240` after a death; NOP-ing it by Genesis Plus GX's own cheat decoder (b) and by Glitchcraft's patch-copy (c) leaves the counter at 3 across two deaths where the unpatched game drops to 2 then 1, and Sonic still dies and respawns (level clock restarts). This is a behaviour-changing, banked code on a real game, with the cheat and the patch-copy agreeing frame for frame.

## What it does not prove

- Not RetroArch's cheat-file path or a real window; the core's `retro_cheat_set` was called directly, before frame 1 (not mid-game).
- One death cause (time over) in one level. Death by enemy or pit may reach the decrement through another path; not tried. Other lives-affecting paths (extra lives from 100 rings, monitors, continues, bonus stages) not tried.
- Bank 1 is asserted by the task and by the matching result; this run does not independently show that `$5701` in bank 1 is the only decrement site.
- Binary-vs-BCD is inferred from one clamped HUD read.
- Time-over is the first death in (a) at frame 46665 by clock reset; the exact death trigger (time limit versus another cause) is inferred from the clock showing 9:51 at frame 46000 and 0:00 after, not from the game's code.
- No game-over behaviour for patched runs.

# In-game check: Sonic the Hedgehog (Genesis), infinite lives `GJ6A-CA7A` (agent-run, headless, 2026-11-12)

Driver: a private script (not published) (about 3 seconds; prints one verdict line, skips cleanly if the ROM or core is missing). ROM: the author's World REV00 dump `roms/genesis/Sonic_The_Hedgehog_W_REV00_p1_.bin` (read-only; only `gg.py patch-copy` output is written, to a temp dir that is removed). Core: Genesis Plus GX via a private script (not published).

## The reasoning under test

`GJ6A-CA7A` patches the word at `$0138A0` from `SUBQ.B #1,($FFFFFE12).w` ($5338) to `BRA.S $0138D4` ($6032). That is the lives decrement on death; the branch skips it. So after Sonic dies the counter should stay at 3 where the unpatched game drops to 2. This is a behaviour change (an instruction replaced by a branch), not a changed start value.

## Method

Three runs, each in a fresh process, with identical scripted input: (a) unpatched, (b) code set with `retro_cheat_set` before frame 1 (the core's own decoder), (c) `gg.py patch-copy ROM OUT GJ6A-CA7A` with no cheat.

Input schedule (frames of the core):

| Frames | Input |
|---|---|
| 300 to 305 | START (title screen, which appears by about frame 240) |
| 700 onward, held | RIGHT (libretro id 7) |

No jump, so Sonic runs right with 0 rings, reaches x=765 in Green Hill Zone Act 1 and is hit by the first Motobug. Dying needs no luck: the same death frame came out in every run, and two complete repeats of the driver printed identical output (all hashes and RAM values).

RAM: Genesis Plus GX exposes the 68000 work RAM byte-swapped per 16-bit word, so `$FFFFFE12` is `ram()` offset `0xFE13` (checked: it reads 3 at the level start and falls to 2/1/0 in the unpatched game). Sonic's object routine byte (`$FFFFD024`, offset `0xD025`) is 2 while running, 6 when hit/dying, 8 when the death fall reaches the point where the decrement runs.

## Evidence

| Frame | Event | (a) unpatched | (b) cheat | (c) patched copy |
|---|---|---|---|---|
| 880 | Sonic running, x=693 | lives 3, hash bde9c689 | 3, bde9c689 | 3, bde9c689 |
| 892 | death routine (6) first seen (Motobug hit) | same in all | same | same |
| 940 | Sonic knocked up, dying (PNG `*_940_dying.png`) | 3, 3d3ac202 | 3, 3d3ac202 | 3, 3d3ac202 |
| 1000 | falling, routine 8, after the decrement point (reached at frame 969) | **2**, d61e765e | **3**, 82dd33d2 | **3**, 82dd33d2 |
| 1265 | respawned at x=80 y=944, routine 2, "GREEN HILL ZONE ACT 1" card | **2**, be892927 | **3**, d6108676 | **3**, d6108676 |

On screen (viewed PNGs at frame 1265): unpatched HUD shows "SONIC x 2"; cheat and patched copy show "SONIC x 3". The frame-940 PNG shows Sonic mid-hurt-jump above the Motobug with 0 rings. Without the patch the counter keeps dropping with the same input (3 to 2 at about frame 969, 1 at about 1540, 0 at about 2100, then a game over and a restart at 3 near frame 3460; only the first death is part of the check).

## Result

PASS. Lives after the death: 2 unpatched, 3 with the cheat, 3 with the patched copy. Cheat and patched copy match in the lives byte and the frame hash at all four sampled frames; Sonic respawns in all three runs.

## Extra: level select `AJ3A-AA4G`

The code changes `BEQ.W $003342` to `BRA.S $00324A` at `$003246` (skips the "level select cheat entered" test; the next test is `BTST #6,($FFFFF604).w`, i.e. button A held). Input: hold libretro Y (Genesis A on this core) from frame 285 for 40 frames and press START at frame 300. Frame 420: unpatched shows Green Hill Zone gameplay start (hash 8634548b); with the cheat, and with the patch-copy ROM, the screen is the LEVEL SELECT menu (Green Hill Zone Stage 1 highlighted, Labyrinth through Scrap Brain, Final Zone, Special Stage, Sound Select 80), hash c523b071 in both. Holding libretro B or A instead did nothing. Genesis Plus GX maps libretro Y to Genesis A on this setup; derived by trying 0, 1 and 8, not from documentation.

## What this proves and does not

Proves: in this core, on this REV00 dump, the code changes game behaviour as predicted (the death decrement is skipped), the core's cheat decoder and `gg.py patch-copy` produce the same running game for it, and the level-select code opens the menu.

Does not prove: that RetroArch's cheat-file loading, a real console, or another revision behaves the same; the code was set before frame 1, not mid-game; continues, game over and extra lives were not exercised with the code on; only the first death was compared.

## Unverified

- The meaning of the routine values (2/6/8) comes from the observed sequence and the standard Sonic 1 disassembly layout, not from reading this ROM's code.
- Other revisions (REV01) were not tried; the author's other dump was not used.
- The byte-swapped RAM mapping is the behaviour of this core build only.

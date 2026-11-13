# In-game check: EarthBound (SNES, HiROM), CB93-746F "walk through walls"

Date 2026-11-12. Driver: a private script (not published) (one PASS/FAIL line, exit 77 if the ROM or core is missing).
ROM: the author's `EarthBound (USA).sfc` (HiROM, no header). Core: `/usr/lib/libretro/snes9x_libretro.so`, driven by the
shared `headless_libretro.py`. The core reported `Map_HiROMMap`.

## Why this code

Other candidates were decoded and vetted, but this one has a large, binary, cheap-to-see effect: the bedroom is
reachable by scripted input in about 7,750 frames (about 5 s of wall-clock at about 1,500 fps), the wall is next to
Ness's start position, and his position sits in WRAM so the effect is a number as well as a picture. HP, level and
instant-win would need a battle; the phone call needs a long wait. (FD93-776F, doors still working, was not run.)

## Method

Three runs, each in a fresh process, identical scripted input:
(a) unpatched ROM; (b) unpatched ROM, `CB93-746F` through `retro_cheat_set` before frame 1; (c) ROM made by
`gg.py patch-copy ROM OUT CB93-746F`, no cheat. `gg.py decode`: `$C054EA value=$A9 compare=none original=$BD`
(LDA abs,X to LDA #imm). The snes9x core accepted the 8+1 character `XXXX-XXXX` Game Genie form directly.

Input schedule (frames):
1. Tap A every 40 frames from 310 (title, file select, intro text) until the first name keyboard (about frame 1800).
2. Seven keyboard screens (Ness, Paula, Jeff, Poo, dog, favorite food, coolest thing; about 244 frames each): wait for
   the keyboard (one black pixel at (120,150)), then UP (cursor wraps to "Don't Care"), A, RIGHT, RIGHT, A on "OK".
   The press frames depend on that pixel test, so each run logs them: the three logs hash identically (`366fadca`) and
   naming finished at frame 3468 in all three.
3. Tap A every 40 frames for 2,000 frames from 3468 ("Are you sure?" yes, then the intro). Ness wakes in his bedroom
   under control by frame 7752 (checked in a PNG; no input from about frame 5470 on).
4. Hold UP from frame 7753 for 150 frames.

Ness's position: WRAM `$7E:0BBE` (x) and `$7E:0BFA` (y), 16-bit little-endian, found by differencing WRAM while he walked
left and down (the same pair appears again 0x3C bytes apart at `$1DAC`/`$1DE8`, an entity table). The offsets are
empirical, not from a published map. SNES system RAM in the core is the 128 KB WRAM, offset = `$7E:xxxx`.

## Evidence (frame hash, x,y, hash of all 128 KB WRAM)

| Frame | (a) unpatched | (b) cheat | (c) patch-copy |
|---|---|---|---|
| 7752 (before walking) | d1bad4eb 8120,1106 90052351 | d1bad4eb 8120,1106 85cab4e6 | d1bad4eb 8120,1106 85cab4e6 |
| 7800 | 6b11d700 8112,1089 da0e96c8 | 9c3020c1 8120,1041 aa38d653 | 9c3020c1 8120,1041 aa38d653 |
| 7850 | 6b11d700 8112,1089 bc293986 | fe495f99 8120,1024 a628666d | fe495f99 8120,1024 a628666d |
| 7900 | 6b11d700 8112,1089 6f541763 | e43303e2 8120,956 529f4518 | e43303e2 8120,956 529f4518 |

Unpatched, Ness stops against the back wall at y=1089 and the picture does not change from frame 7800 on (PNG
`a_unpatched_7900.png`: he stands at the wall under the mirror). With the code he keeps walking up to y=956, 133
pixels past the unpatched stop, into the black void above the room (`b_cheat_7900.png`). (b) and (c) match at every
mark in frame hash, x, y and the whole WRAM. PNGs are in the work directory (scratch).

## What it proves

- A published HiROM code (CB93-746F), decoded by the core's own decoder and by `gg.py`, produces its published effect
  in the real game, and the two agree byte for byte (frame, position and all WRAM at every mark).
- The 24-bit address `$C054EA` scrambled in the code maps to the file offset `0x0054EA` by the HiROM rule: the
  patch-copy ROM, which patches that offset, behaves exactly like the emulator's patch at the CPU address `$C054EA`.
  A wrong map or a wrong scramble would have left (b) and (c) different or the effect absent.
- No compare byte is involved (SNES), so this tests only address and value.

## What it does not prove

- Nothing about the other five vetted codes (HP, level 99, Dad's calls, instant wins, FD93-776F); they were not run.
- Only the wall at the top of the bedroom was tried, and only for 150 frames. Behaviour beyond the room edge (void,
  glitches, crash risk) was not explored. The effect was judged by position and picture; no story or collision code
  was inspected.
- One core (snes9x); one ROM dump.

## Unverified

- The whole-WRAM hash of (a) differs from (b)/(c) already at frame 7752, though frame and position are equal. A dump
  diff shows 8 bytes: `$1E24`, `$1FB0`, `$1FB3`, `$1FF4-$1FF7`, `$5DB6`. The `$1Fxx` ones look like stack residue left
  by different code; this is a guess, not traced. That is why WRAM is compared only between (b) and (c).
- That `$0BBE`/`$0BFA` are the player's x/y in every game state: seen only in this room.
- Walking LEFT instead (a first attempt) takes Ness to the bedroom door, which unpatched play passes through; that is
  not a wall, so UP was used.

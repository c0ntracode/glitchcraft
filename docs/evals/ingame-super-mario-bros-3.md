# In-game check: Super Mario Bros. 3 (NES, MMC3, USA Rev 1), SLXPLOVS infinite lives

Driver: a private script (not published) (about 7 s total). Core: Nestopia (`/usr/lib/libretro/nestopia_libretro.so`)
through a private script (not published). ROM: the author's dump, read-only.

## Code and why it was chosen
SLXPLOVS, infinite lives: $9123, bank 30 (8 KB PRG bank), `DEC $0736,X` -> `LDA $0736,X`.
`gg.py decode ROM SLXPLOVS --bank 30`: value=$BD compare=$DE original=$DE (compare matches the ROM).
Chosen over AAVZNULP (always run) because the effect is one byte that changes once and is also printed on screen (the map
HUD shows M x 4 or M x 3). It needs no judgement about speed or P-meter, and the death happens inside the banked code
path. It also needs only a stand-still script, so it does not depend on frame-exact running input.

## Method
Three runs, each in a fresh process, identical input: (a) unpatched ROM; (b) same ROM, `retro_cheat_set(0, true, "SLXPLOVS")`
before frame 1 (the core's own decoder); (c) `gg.py patch-copy ROM OUT SLXPLOVS --bank 30`, no cheat.
Lives = Nestopia system RAM offset $0736 (offset = CPU address; the value 4 at frame 11 matches the HUD "M x 4", so the
mapping is confirmed). Lives is polled every frame.

## Input schedule (frames)
| Frames | Input | Effect |
|---|---|---|
| 300-303 | START | title, 1 PLAYER GAME |
| 600-603 | START | World 1 map |
| 1000-1009 | RIGHT | Mario to the junction |
| 1060-1069 | UP | onto panel 1 |
| 1120-1123 | A | enter World 1-1 |
| after | none | small Mario stands still; the first Goomba walks into him |

## Evidence
| Frame | a (unpatched) lives / hash | b (cheat) lives / hash | c (patch-copy) lives / hash |
|---|---|---|---|
| 11 | 4 | 4 | 4 |
| 1300 (in 1-1) | 4 / 823dbfed | 4 / 823dbfed | 4 / 823dbfed |
| 1700 (before death) | 4 / 6d387961 | 4 / 6d387961 | 4 / 6d387961 |
| 1781 | drops to 3 | stays 4 | stays 4 |
| 1800 | 3 / 55efbaa7 | 4 / 31d22c64 | 4 / 31d22c64 |
| 2400 (back on map) | 3 / c32e3ee5 | 4 / 9b0350c5 | 4 / 9b0350c5 |

Lives-change log: a `[[1,0],[11,4],[1781,3]]`; b and c `[[1,0],[11,4]]`. Frame hashes b == c at every sampled frame (and at
every 100 frames from 1300 to 2400 in the exploratory run). PNGs (viewed): the map at frame 2400 reads M x 3 in (a) and
M x 4 in (b). Driver verdict: PASS.

## What it proves
- The published code, in a switchable bank (30), has its published effect in real play: a death costs a life unpatched
  and does not with the code.
- Nestopia accepts the NES Game Genie code through `retro_cheat_set` (no format conversion needed) and its decoder agrees
  with `gg.py patch-copy --bank 30`: the two runs are frame-identical, not only equal in lives.
- Bank 30 at $9123 is the live death/lives path (the byte changed only after the Goomba hit).

## What it does not prove
- Other banks, other codes in this ROM (AEKPTZGE, AEUOVEEZ, AAVZNULP, VVOLPOSE) were not run.
- Game over (lives 0) was not tested; only one death with 4 lives.
- It does not show the cheat applied mid-game, or how it behaves on other regions/revisions.
- Only Nestopia was used; other NES emulators were not.

## Unverified
- Whether Nestopia applies the cheat by patching the CPU read of $9123 or by patching ROM; either way the result equals the
  ROM patch here.
- The "Mario is small" assumption is from the screenshot at frame 1400 (yes, small), not from RAM.

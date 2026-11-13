# In-game check: Sonic the Hedgehog (Game Gear), "rings worth 2" `020-54A-E6E` (agent-run headless, 2026-11-12)

Driver: a private script (not published) (about 10 seconds; skips cleanly if ROM or core is missing; one-line verdict). Frontend: a private script (not published) with Genesis Plus GX (`/usr/lib/libretro/genesis_plus_gx_libretro.so`). Not RetroArch, not the author's run.

## Result in one line

The task named V1.1 bank 6. On V1.1 the code has **no effect**: the compare byte matches in bank 6 only by coincidence, inside data. On the author's **V1.0** dump the code sits in bank 1 on the real ring routine, and there it **works**: first ring +2, cheat and `patch-copy --bank 1` identical.

## What the code is in each revision

| ROM | `gg.py vet` bank | Bytes at $5054 | Meaning |
|---|---|---|---|
| V1.0 (sha1 `8923295c...`) | 1 (also 6 matches compare) | `3E 01 CD 7E 33 C9` = `LD A,$01 / CALL $337E / RET` | ring add routine: `LD A,$01` -> `LD A,$02` |
| V1.1 `[!]` | 6 only | `01 26 10 11 13 19` (looks like data; vet says LD BC -> LD (BC),A, opcode-class change) | the real code moved (bank 1 at $5054 is `32 22 D3 21` now) |

The ring routine at $337D/$337E (fixed bank) loads `($D2A9)`, adds, then adjusts with `CP $0A / ADD $06` and `CP $A0`: the **ring counter is BCD at Z80 $D2A9** (system RAM offset $12A9 = address - $C000, verified by the counter tracking the HUD). Its other byte at $D2AA does not change on pickup.

## Input schedule (identical in all runs, frames of the headless core)

- Start held frames 620..625 (SEGA logo and intro run to about 540, gameplay from about 1186).
- RIGHT held from 1190 to 1470.
- Button B (Game Gear button 1) held 12 frames starting at 1190, 1230, 1270, ... (every 40 frames), the jump.
- Cheat (run b) set with `retro_cheat_set` before frame 1. Run c uses `patch-copy --bank N` and no cheat. Each run in a fresh process, deterministic: unpatched hashes were equal across repeated runs.

## Evidence, V1.0 bank 1 (RAM values in hex BCD)

| Run | Ring changes (frame: value) | Frame 1330 ring / hash | 1400 | 1470 |
|---|---|---|---|---|
| a unpatched | 1321:01, 1328:02, 1334:03, 1340:04, 1451:05, 1457:06 | 02 / 0bf26beb | 04 / af5d1248 | 09 / 1f5edc0e |
| b cheat | 1321:02, 1328:04, 1334:06, 1340:08, 1451:10, 1457:12 | 04 / a4ff1a71 | 08 / 8e33deff | 18 / 4bfec939 |
| c patched copy | identical to b | 04 / a4ff1a71 | 08 / 8e33deff | 18 / 4bfec939 |

(The driver prints the counter in decimal; 16 is $10, 18 is $12, 24 is $18.) System RAM SHA-1 prefixes also match between b and c at all three frames (19ae6f44, 51884f94, 2633cb76). The pickup frames are the same in a, b and c.

On screen (PNG read by eye, HUD lags the RAM by one pickup): frame 1330 shows `01` unpatched and `02` cheated; frame 1470 shows `08` unpatched and `16` cheated (the RAM already holds $09 and $18 one pickup later; 08 -> 16 is consistent with every pickup adding 2).

## Evidence, V1.1 bank 6 (negative control)

a, b and c have identical ring traces (1321:1, 1328:2, ...), identical frame hashes (0bf26beb, af5d1248, c5f17161) and identical RAM hashes through frame 1470. The patch changes a data byte that is not used in this stretch of Green Hill Zone Act 1 (what bank 6 holds, and whether it is ever mapped in this window, is not established).

## What this proves

- A published code, decoded by Glitchcraft, changes a real game in the way the publisher describes, in an address in the switchable area ($4000-$7FFF, bank 1 mapped by default), on V1.0.
- The core's own cheat decoder and `gg.py patch-copy --bank 1` agree exactly (ring counter, frame hash, RAM hash).
- `vet` with `--bank` finding a compare match in a different bank (6) is not proof of an effect: here it was a coincidence on V1.1, and on V1.0 the same code also matches bank 6.

## What it does not prove

- Bank 6 behavior: no run showed bank 6 mapped and used, so a bank other than the default 1 was not exercised in-game. A bank above 1 mapped into slot 1 remains covered only by the synthetic ROMs in `banked-emulator-check.md`.
- Whether the code is wrong for V1.1 or just for a different revision: not checked beyond bytes at $5054; other V1.1 locations of the ring routine were not tried.
- Only the first 150 frames of gameplay, one cheat set before frame 1; extra life at 100 rings, ring loss, and RetroArch's cheat-file path were not tested.

## Unverified

- The V1.0 file was used read-only; the "author's own dump" is assumed to be the sha1 above.
- On-screen readings were taken from a lagging HUD; the RAM byte is the primary evidence.

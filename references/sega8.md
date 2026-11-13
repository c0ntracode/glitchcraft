# Game Gear and Master System (platform `sega8`)

## Game Genie code format

Same as the Game Boy format (`references/gb.md`), with a wider address range. `ABC-DEF` (6 digits) or `ABC-DEF-GHI` (9 digits), hex digits, dashes cosmetic.

| Field | Digits |
|---|---|
| new value | `AB` |
| address | `((F ^ 0xF) << 12) \| (C << 8) \| (D << 4) \| E` |
| reference (compare) byte | `ror8(GI, 2) ^ 0xBA` (9-digit codes only) |
| not used | `H`; in every published code `H = G ^ 8` ("cloak"), and Glitchcraft writes it that way |

Patchable range is the ROM window `$0000`-`$BFFF`; `$C000` and up is RAM and refused. A code names a Z80 address, not a bank.

Verified by three independent sources (2026-11-12): Genesis Plus GX `libretro/libretro.c` `decode_cheat` (Master-based branch; custom non-commercial licence, read and cited only), Gearsystem `src/Cartridge.cpp` `SetGameGenieCheat` (GPL-3.0; patches `addr & 0x3FFF` in every 16 KB bank whose byte matches the reference), and SMS Power's Game Genie page (Wayback copy). Published examples (all Game Gear codes) decode with the same `H = G ^ 8`: `3A6-24E-2A2` (value 3A, address 1624, reference 32), `008-3BD-E6E` (00, 283B, 01), `2A2-86A-6E2` (2A, 5286, 22). Their stated effects are unverified: a Game Gear Sonic 1 list calls `2A2-86A-6E2` "breathe underwater" and attributes `3A6-24E-2A2` and `008-3BD-E6E` to Sonic Chaos, from search snippets only. None of them matched a Master System Sonic 1 Export dump (compare bytes differ at every bank), as expected for another console's build; the Master System codes published for that game are Pro Action Replay (RAM) codes, not Game Genie codes. They matched real Game Gear dumps afterwards: see "Real dumps" below.

Official Galoob hardware existed for Game Gear only. Master System uses the same format in emulators, so treat SMS results as emulator-format codes.

Unverified: the Game Gear device itself on banked addresses (see "Banked addresses" below for the patent, SMS Power and four emulators).

## Header and mapper

"TMR SEGA" header at `$7FF0` (also `$3FF0`, `$1FF0`): `+A..B` checksum (little endian), `+C..D` product code (BCD), `+E` version nibble, `+F` high nibble region (3 SMS Japan, 4 SMS Export, 5 GG Japan, 6 GG Export, 7 GG International) and low nibble size (`a`=8 KB, `b`=16 KB, `c`=32 KB, `d`=48 KB, `e`=64 KB, `f`=128 KB, `0`=256 KB, `1`=512 KB, `2`=1 MB). Header values are often wrong in the wild; only the export SMS BIOS checks them.

Sega mapper: `$FFFC` control, `$FFFD`/`$FFFE`/`$FFFF` select the 16 KB bank for slot 0 (`$0000`-`$3FFF`), slot 1 (`$4000`-`$7FFF`), slot 2 (`$8000`-`$BFFF`). The first 1 KB of slot 0 always shows bank 0. `file offset = bank * 0x4000 + (addr & 0x3FFF)`. ROMs of 48 KB or less need no mapper. Codemasters (bank registers written at `$0000`, `$4000`, `$8000`; no protected first kilobyte, initial banks 0, 1, 0) is mapped here; Korean and MSX mappers exist and are not (they are assumed to be the Sega mapper).

Sources for this section: SMS Power ROM header and mappers pages (Wayback copies).

## Tool notes

- The Z80 decoder was compared with the clrhome.org table (699 documented cells, no real mismatches; 160 undocumented `DD`/`FD` cells differ only because a useless prefix is shown as its own one-byte `NOP ; DD`). Zilog syntax; `JR`/`DJNZ` show absolute targets. `ED 63` and `ED 6B` (`LD (nn),HL` / `LD HL,(nn)`) are tagged undocumented by that table, so `xrefs` skips them.
- Disassembly, `vet` and `xrefs` never run an instruction across a 16 KB bank boundary on a banked ROM: the operand would come from whichever bank is mapped next. Such a tail prints as `.byte`.
- `--bank` works as in `references/gb.md`; slot 0 is assumed to show bank 0 when no bank is given, and `$0000`-`$03FF` never moves.

## Practical notes (from the 2026-11-12 fresh-agent run)

- **Game Gear and Master System ROMs are not interchangeable.** A Game Gear ROM will not run on a Master System, and the video hardware differs (Game Gear colour RAM is 12-bit, two bytes per colour, low byte `$GR` then `$0B`; Master System colour RAM is one 6-bit byte). A code for one is not a code for the other. `id` reports `system` from the header's region nibble, which is often wrong in the wild: confirm the console with the user.
- **Finding the live bank.** The user usually cannot say. Look for the game's writes to `$FFFD`, `$FFFE` and `$FFFF` near the code (`xrefs ROM FFFF`), and read the bank of an `xrefs` hit as its file offset divided by `0x4000`. If you cannot establish it, say so and label the result Guess. On a ROM of 48 KB or less there is no bank to choose.
- **A 6-digit code applies in every bank** that shows that address; a 9-digit code applies only where the byte matches its reference, which is how a code is aimed at one page.
- **RAM** is `$C000`-`$DFFF` (mirrored at `$E000`). A Game Genie cannot write it; the tool refuses those addresses.
- **A compare mismatch** means the code was written for another game or revision. Do not drop the compare to force it: that makes a different, unaimed code.
- **`NOP ; DD`** in a listing is a useless Z80 prefix shown on its own; the next line is the instruction that actually runs, with the prefix applied only if the opcode uses `HL`.

## Banked addresses: what is known (OSINT, 2026-11-12)

- **Real hardware matches the CPU address, not a bank.** US patent 5,112,051 (Codemasters/Galoob, the NES-era design) describes an address comparison unit with no bank input and says the data-compare feature "ensures that only data at the correct address and the correct bank is modified". SMS Power's Game Genie page says the same about the reference byte, and adds that it cannot tell banks apart when they hold the same byte at that offset. Applying the NES patent text to the Game Boy and Game Gear devices is an inference, and no box or manual text for them was found.
- **So a code with no compare changes that address whichever bank is mapped when it is read.** Emulators differ in how they model this: SameBoy applies GG codes to every bank (`GB_CHEAT_ANY_BANK`); Gearsystem patches `addr & 0x3FFF` in every 16 KB bank, whose byte matches the reference if one is given; mGBA scans the banks and patches the first one whose byte equals the compare; Genesis Plus GX patches only the bank mapped when the code is applied and re-applies on banking changes, checking the reference against that bank. Gambatte's source could not be checked.
- **Consequence for the tool:** `--bank` says which bank's byte Glitchcraft reads and shows. Tell the user the code will also fire in any other bank that maps the same address, and that a compare byte only isolates a bank if the other banks differ at that offset.

## Banked addresses: emulator evidence

`docs/evals/banked-emulator-check.md`: on a synthetic 4-bank Game Gear ROM (Sega mapper, slot 1), the real Genesis Plus GX core applied a 6-digit code in every bank, and a 9-digit code only where the byte matched the compare, in 10 of 10 cases, identical to `patch-copy --bank` for each bank (early and late applies gave the same frames). Re-run with a private script (not published). Slot 2 (`$8000`-`$BFFF`), Master System content, other mappers and the real device are unchecked; on a ROM that runs every bank, "patched when mapped" and "every bank" cannot be told apart.

## Codemasters detection and mapping (checked on a real dump, 2026-11-12)

Micro Machines (Master System, Europe) carries a Codemasters header at `$7FE0`: byte 0 is the bank count (`0x10`, matching its 16 banks), and the words at `+6` and `+8` (`0xB5B4` and `0x4A4C`) sum to `0x10000`. The heuristic in `sega8/rom.py` keys on exactly that. The game's own code confirms the mapper model: `LD A,$02` / `LD ($8000),A` / `JP $8000` selects a bank into slot 2 and jumps into it, and `xrefs` finds the `$4000` and `$8000` register writes. No published Game Genie code was found or tried on a Codemasters ROM, so the mapping is verified only by this reading.

## Real dumps (2026-11-12)

On author-supplied Game Gear dumps, `3A6-24E-2A2` and `008-3BD-E6E` match Sonic Chaos at `$1624` and `$283B`, and seven of eight published Sonic the Hedgehog (Game Gear) codes match exactly the revision they target (V1.0 for the "v1" list, V1.1 for the "v2" list, banked ones in one bank); the eighth, `020-54A-E6E`, is a V1.0 bank-1 code whose compare also matches bank 6 of both revisions by coincidence (an in-game run showed no effect on V1.1). The compare byte therefore also tells you which revision a code was written for. See `docs/evals/real-roms-2026-11-12.md` and `tests/test_real_roms.py`. The effects remain published claims; no code was run in a game.

## A compare match found by scanning banks can be a coincidence

A compare byte matches a random byte with probability 1 in 256, so scanning N banks gives a chance match somewhere about N/256 of the time (about 6% on a 16-bank ROM, 22% on 64 banks). Treat a match as evidence only when it is in the bank the code was written for and the patched instruction fits the stated effect; when the scan finds several banks, take the one whose code does what the effect says, and say which revisions you checked. The Sonic rings code above is a real example: bank 6 matched on both revisions, and only bank 1 of V1.0 does anything in the game.

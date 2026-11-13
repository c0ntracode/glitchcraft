# Game Boy / Game Boy Color

## Game Genie code format

`ABC-DEF-GHI` (9 digits, optional compare) or `ABC-DEF` (6 digits, no compare). Digits are plain hex, dashes are cosmetic.

| Field | Digits |
|---|---|
| new value | `AB` |
| address | `((F ^ 0xF) << 12) \| (C << 8) \| (D << 4) \| E` |
| compare | `ror8(GI, 2) ^ 0xBA` (9-digit codes only) |
| ignored | `H` |

A code patches one byte of ROM at a CPU address `0000-7FFF`; addresses above `7FFF` cannot be patched. No bank is encoded.

Sources (read, not copied): mGBA `src/gb/cheats.c` (`GBCheatAddGameGenieLine`, MPL-2.0) and SameBoy `Core/cheats.c` (`GB_import_cheat`) agree on all of the above. The vectors in `tests/fixtures/gb_vectors.json` were decoded by hand from this description and have not been run against an emulator until `docs/evals/gb-letters.md` says so.

Unverified: whether real hardware validates `H` (no emulator does); how the Game Boy device itself treated banked addresses (the compare byte as a bank guard is documented only in the NES-era patent and SMS Power; see "Banked addresses" below). Every published code has `H = G xor 8` (SMS Power calls it the cloak), and Glitchcraft writes it that way; real-hardware entry is still unverified, so label it Guess.

## Header

`$100` entry, `$104-133` logo, `$134` title, `$143` CGB flag (`80` enhanced, `C0` CGB only), `$146` SGB flag, `$147` cartridge type, `$148` ROM size (32 KiB << n; banks = 2 << n), `$14D` header checksum (`c = c - byte - 1` over `$134-14C`), `$14E-14F` global checksum (not checked by hardware). The boot ROM checks the logo and header checksum, so a patched file whose header bytes changed can fail to boot; a Game Genie patches reads, not the file.

## Banks

`file offset = bank * 0x4000 + (addr & 0x3FFF)`. `0000-3FFF` is bank 0; `4000-7FFF` is the selected bank. MBC1 and MBC3 map a written bank 0 to 1; MBC5 does not. Supported here: no MBC, MBC1, MBC2, MBC3, MBC5. Refused with a reason: MBC6, MBC7, MMM01, HuC1, HuC3, TAMA5, Pocket Camera.

## SM83

256 base opcodes and 256 `CB` opcodes. Eleven opcodes are illegal and lock the CPU: `D3 DB DD E3 E4 EB EC ED F4 FC FD`. Interrupt vectors `$40 $48 $50 $58 $60`; `RST` targets `$00-$38`.

## Tool notes

- The SM83 decoder was compared against the gbdev opcode table for all 511 decodable opcodes (length and text; 2026-11-12): no mismatches. Style differences are deliberate: `SUB B` rather than `SUB A,B`, bare `STOP` sized at two bytes, `JR` shown as an absolute target. The cross-reference lists and flow classes were not compared.
- `--bank` applies to `make`, `decode`, `disasm`, `vet` and `patch-copy`. It is ignored for addresses below `$4000` (even a nonsense number); at `$4000`-`$7FFF` a 32 KB cartridge accepts only banks 0 and 1. It is decimal, or hex with `0x` (`--bank 0x20`, `--bank=0x20`). `--bank 0` is legitimate on MBC5.
- `xrefs` scans every byte for an operand equal to the address, so data that looks like code gives false hits, and a code address (as opposed to a variable) finds nothing.

## Banked addresses: what is known (OSINT, 2026-11-12)

- **Real hardware matches the CPU address, not a bank.** US patent 5,112,051 (Codemasters/Galoob, the NES-era design) describes an address comparison unit with no bank input and says the data-compare feature "ensures that only data at the correct address and the correct bank is modified". SMS Power's Game Genie page says the same about the reference byte, and adds that it cannot tell banks apart when they hold the same byte at that offset. Applying the NES patent text to the Game Boy and Game Gear devices is an inference, and no box or manual text for them was found.
- **So a code with no compare changes that address whichever bank is mapped when it is read.** Emulators differ in how they model this: SameBoy applies GG codes to every bank (`GB_CHEAT_ANY_BANK`); Gearsystem patches `addr & 0x3FFF` in every 16 KB bank, whose byte matches the reference if one is given; mGBA scans the banks and patches the first one whose byte equals the compare; Genesis Plus GX patches only the bank mapped when the code is applied and re-applies on banking changes, checking the reference against that bank. Gambatte's source could not be checked.
- **Consequence for the tool:** `--bank` says which bank's byte Glitchcraft reads and shows. Tell the user the code will also fire in any other bank that maps the same address, and that a compare byte only isolates a bank if the other banks differ at that offset.

## Banked addresses: emulator evidence

`docs/evals/banked-emulator-check.md`: on a synthetic 4-bank MBC5 ROM, the real Gambatte core applied a 6-digit code to the shared address in every bank, and a 9-digit code only in the bank whose byte matched the compare, in 10 of 10 cases, identical to `patch-copy --bank` for each bank (applying the cheat before the first frame and after 60 frames gave the same frames). Re-run with a private script (not published). This is one core and one mapper; MBC1/MBC3 quirks, other emulators and the real device are unchecked.

## A compare match found by scanning banks can be a coincidence

A compare byte matches a random byte with probability 1 in 256, so scanning N banks gives a chance match somewhere about N/256 of the time (about 22% on a 64-bank ROM). Treat a match as evidence only when it is in the bank the code was written for and the patched instruction fits the stated effect; if a scan finds several banks, pick the one whose routine does what the effect says, and ask the user which bank is live. See `references/sega8.md` for a real example.

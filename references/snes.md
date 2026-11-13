# SNES reference

## Code format
- Written `XXXX-XXXX`: eight characters from `DF4709156BC8A23E`, which stand for the hex digits `0123456789ABCDEF` in that order (so `D`=0, `F`=1, `4`=2, and so on).
- After translating to hex, the 32-bit result holds the replacement byte in its top 8 bits and a scrambled 24-bit address in the low 24 bits.
- The address bits are regrouped in seven pieces: `0x003C00`<<10, `0x00003C`<<14, `0xF00000`>>8, `0x000003`<<10, `0x00C000`>>6, `0x0F0000`>>12, `0x0003C0`>>6.
- There is no compare byte. A SNES code patches every read of that bus address.

## Sources
- The algorithm was read in the [Snes9x](https://github.com/snes9xgit/snes9x) source (`cheats2.cpp`, the Game Genie decoder). That code is under a non-commercial license that is not compatible with this repository, so Glitchcraft does not copy it; the codec is our own implementation of the same format.
- Example codes come from [The Mushroom King's Super Mario World list](https://themushroomkingdom.net/smw_ggcodes.shtml). The full list is not stored here.
- Independent check of the letters: `snes9x -cheatcode CODE` (Task 7 of the SNES plan).

## Files and addresses
- `id` finds LoROM and HiROM by the internal header at `$7FC0` or `$FFC0` (with a valid checksum complement) and reads the 21-byte title. A 512-byte copier header (file size is a multiple of `0x8000` plus `0x200`) is detected and every offset accounts for it. ExHiROM, SA-1 and other maps are "not recognized", not guessed.
- Banks `$80-$FF` mirror `$00-$7F`. In LoROM only `$8000-$FFFF` of a bank is ROM. Banks `$7E-$7F` are RAM, so a code there gets the "Game Genie patches ROM reads" message.
- The 65816 changes its immediate operand width with the M and X flags. `disasm` tracks `REP` and `SEP` from the address you give it; with no known width it decodes 8 bits and appends `; width unknown`, and later instruction boundaries may be off. Start a listing where you know the flags, after a `SEP`/`REP`.
- `vet` and `xrefs` use bus addresses (`$00D0D8`), not file offsets.

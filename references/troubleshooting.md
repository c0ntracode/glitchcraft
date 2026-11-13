# A code did not work

Ask for: the emulator or device, the ROM hash (`gg.py id`), and what happened. Then check in this order, running the command shown.

1. **Different dump.** Public code lists name one build (often the first release); a later revision or a hacked dump moves code. If `vet` shows an unrelated instruction at the address, the code is for another build. `gg.py id ROM`: does the SHA-1 match the revision you analysed? Different revisions move code. If the hash differs, redo the analysis on this file.
2. **No header or a trainer.** `id` shows `trainer` and the mapper. A wrong header shifts every offset.
3. **Bank.** `gg.py vet ROM CODE` flags `bank-dependent`. Find which bank the routine runs from.
4. **Compare mismatch.** `vet` flags `compare-mismatch`: the ROM byte is not the compare value, so the patch is not applied on hardware.
5. **Emulator support.** Some accept only 6-letter codes, and an emulator may handle one spelling of a code differently. Try the other spelling, or test with `patch-copy`.
6. **Not the only path.** `gg.py xrefs ROM ADDR`: other code may write the same variable. A pit, timer or other event may take a different route.
7. **Shared byte.** The routine you changed may also run at other times (a continue, a level start). `vet` shows the instruction before and after; read the listing around it with `disasm`.
8. **Effect timing.** The patch is right but the effect shows only after a trigger (death, a level change). Say what to do to see it.
9. **Save RAM.** If the patched routine touches battery-backed memory, advise a backup before testing.

If none fit, label the next attempt **Guess** and say what it changes.

`id` may print `header_warning`: old dump tools wrote text into bytes 7 to 15 of some headers, which corrupts the mapper number. The warning names the likely real mapper (the low nibble). Confirm it with the user before relying on bank assumptions.

## The game shows a red or error screen right after a code is applied

Some games checksum the ROM at boot and refuse to run when it changed, and any patch changes it. Sonic 1 (Genesis) does this: it sums `$200` to the end of ROM, compares with the header word at `$18E`, and branches to an error screen on mismatch. Find the compare with `disasm` near the reset code and `vet` a second code that defeats it (for Sonic 1, `CMP.W (A1),D1` to `CMP.W D1,D1` at `$000338`). The cause is a boot check, not a wrong code, but say it is Inferred until a run confirms it.

## Game Boy: blank, garbled or nothing changes

- **Nothing changes.** Run `vet` first. `compare-mismatch` means the code names a different byte than this dump holds: public Game Boy codes are written for one game and often one revision, so a code for another game (or a mangled copy) decodes to a valid address and still does nothing here. `make ROM --addr A --value V --compare <original>` prints the correctly encoded form for this dump.
- **Blank or garbled screen.** A patch that turns an instruction into `NOP` or `INC`-like filler can leave a stray operand byte to execute, or unbalance pushed arguments. Read the `vet` listing for the byte after the patch, and label this Inferred until a run shows it.
- **Bank.** For `$4000`-`$7FFF` the ROM bank decides which code runs. On MBC5 (and MBC1/3) ask which bank the user was in; a wrong `--bank` patches code that is not running. `xrefs` reports banked hits as a file offset; the bank is the offset divided by `0x4000`. `xrefs` matches operands (a variable address), so a code address finds nothing.
- **Header area.** `$0100`-`$014F` holds the logo and header checksum the boot ROM checks; `make` and `vet` warn about it.
- **Variable not in the ROM.** A gold or lives counter usually lives in RAM, so the ROM alone does not name it. Say so and offer the route (an emulator RAM watch to find the address, then `xrefs` for the writers) instead of inventing a code; a guess is labelled Guess.

## Several banks match a code's compare byte

Chance alone matches about 1 bank in 256 scanned, so extra hits are normal on big ROMs. Prefer the bank whose patched instruction fits the stated effect and the user's revision, and say the others may be coincidence (Inferred at best). Do not offer a code as working on the strength of a compare match alone.

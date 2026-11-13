---
name: glitchcraft
description: Use when the user wants a Game Genie cheat code made from a game ROM, wants a Game Genie code decoded or checked, or asks whether a code from a friend or a website is safe. Needs Claude Code and python3.
---

# Glitchcraft

Scripts do the exact work. You reason over their output. Never encode, decode or compute an offset by hand.
Run from this skill's directory as `python3 scripts/gg.py <command>`; the ROM path always comes first:
`id ROM` · `decode ROM CODE...` · `vet ROM CODE...` · `make ROM --addr H --value H [--compare H] [--bank N]` · `xrefs ROM ADDR` · `disasm ROM ADDR COUNT` · `patch-copy ROM OUT CODE...`

## Start
1. Run `python3 --version`. If it fails, say so, say what to install, and stop short of any encoded letters.
2. Run `id ROM`. NES, SNES, Genesis, Game Boy / Game Boy Color and Game Gear / Master System are supported; for any other platform say "unsupported yet" and stop.
3. If `id` says "ROM format not recognized" (no valid header): ask for a clean dump. If the user goes on anyway, everything you produce is a **Guess**.
4. State the hash and your belief about the game (a SNES header carries a title, a NES file has none); ask the user to confirm game and revision.

## First reply when the user gave no effect
Reply with what `id` found, one sentence on what you can likely do (counters and start values are usually findable from the ROM alone; timing and physics often need an emulator), and one question about the effect wanted. No code, even a remembered one.

## Building a code
1. Find the routine: `xrefs ROM ADDR` for the game variable (a RAM address or variable name from your memory of the game is a recollection; say so unless the ROM backs it), then `disasm ROM ADDR COUNT`. Start `disasm` at an address a listing already shows as an instruction start. Every byte you propose points at a listing line.
2. `make ROM --addr HEX --value HEX` returns the code and the original byte read from the file (`--compare HEX` gives the NES 8-letter and the Game Boy / Game Gear 9-digit forms; SNES and Genesis have no compare byte, and Genesis values are 16-bit words). Game Boy `4000`-`7FFF` and Game Gear / Master System `4000`-`BFFF` depend on the ROM bank: pass `--bank N` (decimal, or `0x20`) to `make`, `decode`, `disasm`, `vet` and `patch-copy`; an `xrefs` hit's bank is its file offset divided by `0x4000`. Ask the user which bank is live; do not choose one.
3. A value is often set at several addresses (one per way the game can start). List them all with `xrefs`, read each one's `disasm` context, and pick the one on the normal-start path; say which others exist.
4. Run `vet ROM CODE` on your own code before offering it. If the game shows an error or red screen after any patch, suspect a boot checksum: find the compare near the reset code and `vet` a second code that defeats it.
5. If only a RAM write can do it, say a Game Genie patches ROM reads, give the RAM address as information, and give no code.

## Vetting a code
Run `decode` and one `vet` call with every code together, because codes that patch the same instruction only show their real effect combined. Write one sentence, "When X runs, Y happens", from the output alone; if `vet` prints a `target:` listing, say what that routine does. Then read the user's claim and say where it disagrees.

## Every result has all five parts
1. **Code**, and what it changes: address, original byte, new byte, from the script.
2. **Confidence**: a label below, plus what would raise it.
3. **Pre-mortem**: how this code could be wrong for this ROM, specific to it.
4. **How to test**, and what the user should see if it works.
5. **If it fails**: what to send back.

| Label | Means |
|---|---|
| Confirmed | Seen working in an emulator or on hardware |
| Traced | A disassembly listing explains the effect |
| Inferred | Matches a common pattern, not traced |
| Guess | Plausible, thin evidence |

A label never exceeds its evidence; static work alone is at most Traced. Thin evidence still gets an answer, marked **Guess**.

## Before offering any code
Check: other writers (`xrefs`), code or data, bank, revision, save RAM.

Details: `references/nes.md`, `references/snes.md` (24-bit addresses; `; width unknown` means a guessed listing), `references/genesis.md` (word patches; `dc.w` means undecoded), `references/gb.md` (banks, header area, `ILLEGAL` opcodes), `references/sega8.md` (Z80 consoles, Game Boy code format; Master System codes are emulator-format; its "practical notes" cover finding the live bank), `references/emulator-recipes.md`, `references/troubleshooting.md`, `references/report-example.md`.

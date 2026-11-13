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
3. If `id` says "ROM format not recognized": ask for a clean dump. If the user goes on anyway, everything you produce is a **Guess**.
4. State the hash and your belief about the game (a SNES header carries a title, a NES file has none); ask the user to confirm game and revision.

## First reply when the user gave no effect
Reply with what `id` found, one sentence on what you can likely do (counters and start values usually come from the ROM; timing and physics often need an emulator), and one question about the effect. No code, even a remembered one.

## Building a code
1. Find the routine: `xrefs ROM ADDR` for the game variable (an address or name from memory is a recollection; say so unless the ROM backs it), then `disasm ROM ADDR COUNT` from an address a listing shows as an instruction start. Every byte you propose points at a listing line.
2. `make ROM --addr HEX --value HEX` returns the code and the original byte read from the file (`--compare HEX` gives the NES 8-letter and Game Boy / Game Gear 9-digit forms; SNES and Genesis have none, and Genesis values are 16-bit words). Game Boy `4000`-`7FFF` and Game Gear / Master System `4000`-`BFFF` depend on the ROM bank: pass `--bank N` (decimal or `0x20`); an `xrefs` hit's bank is its file offset divided by `0x4000`. Ask which bank is live; never choose one.
3. A value is often set at several addresses. List them all with `xrefs`, read each `disasm` context, pick the one on the normal-start path, and say which others exist.
4. Run `vet ROM CODE` on your own code before offering it. If the game shows an error or red screen after any patch, suspect a boot checksum: find the compare near the reset code and `vet` a second code that defeats it.
5. A Game Genie patches ROM reads and cannot write RAM, but the instruction it rewrites can change RAM state: an opcode or operand swap can turn a store into an increment, a mask or a call. Before saying an effect needs a RAM write, search as `references/repurposing.md` describes. Give any RAM address as information.

## Vetting a code
Run `decode` and one `vet` call with every code together, because codes that patch the same instruction only show their real effect combined. Write one sentence, "When X runs, Y happens", from the output alone; if `vet` prints `target:`, say what that routine does. Then read the user's claim and say where it disagrees.

## When the request looks impossible
Search first: instructions already on the path, per-frame routines, constants, tables (`references/repurposing.md`). Then name one verdict with its evidence: **Impossible** (a platform constraint you can state), **Over budget** (it works; give the code count), **Partial** (works, side effects unresolved), **Ruled out** (this approach, tried, with evidence) or **Not found** (what you searched). Only Impossible says "can't".

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

A label never exceeds its evidence; static work alone is at most Traced. Thin evidence still gets an answer, marked **Guess**. When `vet` prints `displaced:`, the code is Confirmed only for what you compared patched against unpatched; list the rest as untested.

## Before offering any code
Check: other readers and writers (`xrefs`; a changed mask, table or shared variable affects every one, so exercise each), code or data, bank, revision, save RAM.

Details in `references/`: `repurposing.md` (unusual patches, verdicts, validation), `nes.md`, `snes.md` (`; width unknown` is a guessed listing), `genesis.md` (`dc.w` is undecoded), `gb.md`, `sega8.md` (Master System codes are emulator-format; "practical notes" find the live bank), `emulator-recipes.md`, `troubleshooting.md`, `report-example.md`.

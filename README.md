# Glitchcraft

A Claude Code skill that helps you build and check Game Genie codes from a game ROM you own. Give it a ROM and a goal ("infinite lives", "start on World 4"), or a code someone sent you, and it works out what the code really does to the game's bytes.

Status: **NES, SNES, Genesis, Game Boy / Game Boy Color and Game Gear / Master System, early.** The Master System format was verified against emulator sources and SMS Power (Galoob made hardware for the Game Gear only), so its codes are emulator-format codes. A platform is added once its code format is checked against published references and an emulator.

## What it does

- **Builds codes.** It reads your ROM with scripts, finds the routine that matters, writes the patch, and encodes it. The original byte is read from your file, never remembered.
- **Checks codes.** Given a code, it decodes it against your ROM and says what it changes. It works out the effect from the bytes first and only then compares with what the sender claimed.
- **Says how sure it is.** Every result carries a confidence label, a specific "how could this be wrong for this ROM" note, and how to test it.

| Label | Meaning |
|---|---|
| Confirmed | Seen working in an emulator or on hardware |
| Traced | A disassembly listing explains the effect |
| Inferred | Matches a common pattern, not traced |
| Guess | Plausible, thin evidence |

A label never goes above its evidence. Reading the ROM alone is at most Traced.

## Requirements

- Claude Code (the skill runs bundled scripts and reads local files; other Claude surfaces are not supported).
- `python3`, standard library only. Tested on 3.14; the code uses 3.10+ syntax and has not been run on older versions.
- A ROM you own. This repository contains no ROMs and no copyrighted disassemblies, and never will.

## Install

```sh
mkdir -p ~/.claude/skills/glitchcraft
cp -r SKILL.md references scripts ~/.claude/skills/glitchcraft/
```

Then ask Claude about a Game Genie code and give it the path to your ROM.

## Command line

The scripts also work on their own. The ROM path always comes first:

```sh
python3 scripts/gg.py id game.nes
python3 scripts/gg.py decode game.nes SXIOPO
python3 scripts/gg.py vet game.nes KTGOYX VIIATX OPIAYZ
python3 scripts/gg.py make game.nes --addr 91D9 --value AD
python3 scripts/gg.py xrefs game.nes 075A
python3 scripts/gg.py disasm game.nes 91D9 3
python3 scripts/gg.py patch-copy game.nes patched.nes AATOZE

# SNES: 24-bit bus addresses, codes like XXXX-XXXX, no compare byte
python3 scripts/gg.py id game.sfc
python3 scripts/gg.py make game.sfc --addr 00D0D8 --value AD

# Genesis: 24-bit addresses, codes like XXXX-XXXX that replace a 16-bit word, no compare
python3 scripts/gg.py id game.bin
python3 scripts/gg.py make game.bin --addr 013F74 --value 6002

# Game Boy / Game Boy Color: 16-bit addresses, codes like ABC-DEF-GHI (optional compare), one byte
python3 scripts/gg.py id game.gb
python3 scripts/gg.py make game.gb --addr 0150 --value 3E --compare 3C
python3 scripts/gg.py make game.gb --addr 4010 --value 00 --bank 3   # $4000-$7FFF needs the ROM bank
python3 scripts/gg.py vet game.gb --bank 0x20 000-10B   # --bank is decimal, or hex with 0x

# Game Gear / Master System: same code format as the Game Boy, ROM window $0000-$BFFF, Z80 disassembler
python3 scripts/gg.py id game.gg
python3 scripts/gg.py make game.gg --addr 1624 --value 3A --compare 32
python3 scripts/gg.py disasm game.gg 4000 8 --bank 3
```

## Tests

See `TESTING.md` for the four tiers of checks and what each shows.

```sh
python3 -m unittest discover -s tests        # fast, no ROM needed (ROM tests skip)
```

Put your own ROM copies under `roms/` (git-ignored). The NES codec is checked against codes published at [tuxnes.sourceforge.net](https://tuxnes.sourceforge.net/gamegenie.html), the [nesdev forums](https://archive.nes.science/nesdev-forums/f3/t14573.xhtml), [qalle2/nes-util](https://github.com/qalle2/nes-util) and [fractal161's blog](https://fractal161.github.io/blog/so-many-gg-codes).

## Known limits

- It is a helper, not a guarantee. A code can decode correctly and still be wrong for your dump. If one misbehaves, take it back to Claude with the emulator, the ROM's SHA-1 and what you saw; the skill has a troubleshooting path for that.
- Vetting reports what the bytes do and shows the code a patched jump now reaches. Naming what a game state means (for example "mode 3 is Game Over") needs tracing who reads that variable, and the skill may stop short of it.
- SNES: LoROM and HiROM only (ExHiROM, SA-1 and other maps are "not recognized"). The 65816 changes immediate-operand width with the M and X flags, so some listings say `; width unknown` and later instruction boundaries may be off. The SNES letters were checked against the published algorithm, the ROM's instructions, and a running `snes9x` for two codes by eye and ear (`docs/evals/snes-letters.md`); that is not an exhaustive test.
- Genesis: raw `.bin`/`.md` dumps only (interleaved `.smd` is refused with a conversion hint); ROMs over 4 MB are not handled. A code replaces a 16-bit word. The 68000 disassembler is partial: anything it does not decode prints `dc.w $XXXX` (about 14% of one Sonic 1 dump's first 64 KB, which includes data). Public code lists name a specific build, so a code from a list often lands on an unrelated instruction in another revision; `vet` shows it. The Genesis letters agree with Genesis Plus GX in RetroArch (`docs/evals/genesis-letters.md`), and published Sonic 1 codes land on the intended instructions in a clean REV00 dump.
- Game Boy: no mapper, MBC1, MBC2, MBC3 and MBC5 are mapped; MBC6, MBC7, MMM01, HuC and the camera are named and refused. A code patches ROM reads at `$0000`-`$7FFF` only and carries no bank, so `4000`-`7FFF` addresses need `--bank`. Patching the header (`$0100`-`$014F`) is flagged. The 9-digit form's third-group middle digit is ignored by emulators and written as the first digit XOR 8, as in every published code; the letters agree with two published emulator sources and with Gambatte in RetroArch for a 6-digit and a 9-digit code at a banked address, including the bank rules (`docs/evals/gb-letters.md`); banked addresses agree with Gambatte and Genesis Plus GX on synthetic ROMs (`docs/evals/banked-emulator-check.md`) and a banked code was played in Link's Awakening (`docs/evals/ingame-links-awakening.md`).
- Game Gear / Master System: the Sega mapper and ROMs of 48 KB or less are mapped; a Codemasters header (detected by a heuristic that matched a real Micro Machines dump) is mapped too, and other mappers are assumed to be the Sega mapper. Detection needs the `TMR SEGA` header; a headerless dump is "not recognized". A code names a Z80 address, not a bank, and `$C000` and up is RAM. Original device behaviour for banked addresses is unverified (emulators differ; see `docs/evals/banked-emulator-check.md`). The Z80 disassembler was compared with the clrhome table; undocumented opcodes are labelled as such.
- Bank-switched NES games need the bank the routine runs from; the skill reports such addresses as bank-dependent.
- Unreliable inputs: headerless dumps (the skill stops and asks for a header), hacked ROMs, and mappers other than 0, 1, 2, 3, 4 and 7.
- Evidence is broad but shallow per game: every platform's letters and published codes were checked against real dumps, and a published code was played in the running game on each platform, one or two codes per game. Fresh-agent evaluations are small (a few scenarios per platform). See `TESTING.md` and `docs/evals/`.

## Not affiliated

Glitchcraft is an independent project. It has no connection to the makers of the Game Genie, to Nintendo, or to any game publisher. "Game Genie" is used to name the kind of code.

## License

MIT. See `LICENSE`.

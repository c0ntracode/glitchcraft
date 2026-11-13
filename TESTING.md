# Testing and evidence

Glitchcraft changes the bytes of a game you own, so its claims should be checkable. This page says what was checked and how much of it you can reproduce yourself. No ROM is included or linked in this repository, and `roms/` is git-ignored.

| Tier | What it checks | Needs | Reproducible from this repository |
|---|---|---|---|
| 1. Unit tests | Codecs for every platform, ROM identification and mapping, the 6502, 65816, 68000, SM83 and Z80 disassemblers, `vet`, the CLI, adversarial inputs | Python 3 only (ROMs are synthesised in the tests) | Yes: `python3 -m unittest discover -s tests` |
| 2. Real-ROM tests | Published Game Genie codes against real dumps: the compare byte must equal the ROM byte at the patched address, in the bank the code was written for | Dumps you own in `roms/` (each test skips if its file is absent) | Yes, if you own the same revisions: `python3 -m unittest tests.test_real_roms` |
| 3. Headless in-game checks | A published code has its published effect in the running game, and the emulator core's own cheat decoder agrees with `gg.py patch-copy` | Dumps, plus libretro cores | No: the scripts are not published; each write-up in `docs/evals/` gives the input, the observed values and the hashes |
| 4. Manual letter checks | RetroArch loads the code through its own cheat-file path in a real window and shows the same result as a patched copy | A desktop session and RetroArch | No: the scripts are not published; results are in `docs/evals/` |

## The in-game checks (tier 3)

Each ran the same scripted input three times in fresh processes: unpatched, with the code applied through the emulator core's own cheat function, and on a `gg.py patch-copy` ROM with no cheat. A check passed when the cheat run and the patched copy matched each other and differed from the unpatched run in the published way.

| Game | Platform and mapper | Code and effect | Observable |
|---|---|---|---|
| Sonic the Hedgehog (Game Gear V1.0) | Game Gear, Sega mapper | `013-7DE-E66` start with 1 life | lives counter on screen |
| Sonic the Hedgehog (Game Gear V1.0) | Sega mapper, bank 1 | `007-01A-3BE` infinite lives (a no-op replaces the decrement) | lives byte after two deaths |
| Sonic the Hedgehog (Game Gear V1.0) | Sega mapper, bank 1 | `020-54A-E6E` rings worth 2 | ring counter per pickup |
| Sonic the Hedgehog (Genesis REV00) | Genesis | `GJ6A-CA7A` infinite lives; `AJ3A-AA4G` level select | lives byte; level select menu |
| The Legend of Zelda: Link's Awakening (Rev 2) | Game Boy MBC1, bank 2 | `AF7-168-3B0` walk through walls | Link's position, frame, sprites, WRAM |
| Mega Man 2 (USA) | NES MMC1, bank 14 | `PANALALA` start with 1 life | lives byte, Game Over reached sooner |
| Super Mario Bros. 3 (USA Rev 1) | NES MMC3, bank 30 | `SLXPLOVS` infinite lives | lives byte after a death |
| EarthBound (USA) | SNES HiROM | `CB93-746F` walk through walls | Ness's position |
| Pokémon Red (UE) | Game Boy MBC3, bank 15 | `3E1-6B9-2AA` one-hit kills | rival's HP after the first hit (16 unpatched, 0 patched) |

These are not a proof that every code works. They cover each distinct bank-mapping path once or twice, with one code per game. A compare byte can also match by chance (about 1 in 256 per bank scanned); the Sonic "rings" code is a real example, and `references/troubleshooting.md` says how to treat extra matching banks.

## Dumps used

The checks were run on dumps of games the author owns. SHA-1 values are listed so you can tell whether you have the same revision; codes are often written for one revision only.

| File (as named in `roms/`) | SHA-1 |
|---|---|
| `gb/Pokemon Red.gb` | `ea9bcae617fdf159b045185467ae58b2e4a48b9a` |
| `gb/Legend of Zelda, The - Link's Awakening (USA, Europe) (Rev 2).gb` | `5ab63def958728933571c3b4f6af54db14f3f8b2` |
| `gb/Tetris (JUE) (V1.1) [!].gb` | `74591cc9501af93873f9a5d3eb12da12c0723bbc` |
| `genesis/Sonic_The_Hedgehog_W_REV00_p1_.bin` | `4c3b606bec697b0b934ba2f650a8b83c0e3b77c7` |
| `genesis/Micro Machines (USA).md` | `39b25dbfa7a80aebdefc19ac2df4bc75b934bbda` |
| `nes/Mega Man 2 (USA).nes` | `2290d8d839a303219e9327ea1451c5eea430f53d` |
| `nes/Super Mario Bros. 3 (USA) (Rev 1).nes` | `6bd518e85eb46a4252af07910f61036e84b020d1` |
| `snes/EarthBound (USA).sfc` | `d67a8ef36ef616bc39306aa1b486e1bd3047815a` |
| `snes/smw/Super Mario World (USA).sfc` | `6b47bb75d16514b6a476aa0c73a683a2a4c18765` |
| `sega8/Sonic the Hedgehog (JUE) (V1.0).gg` | `8923295c96b2e05da0a83a827fd709b033fc7332` |
| `sega8/Sonic the Hedgehog (JUE) (V1.1) [!].gg` | `7dbbbca2229e74fcb8f90ec794aa6e5cb168e489` |
| `sega8/Sonic the Hedgehog (JUE) (Proto) [!].gg` | `7ff6810e4ac03e04584243995c3fd54b77896c23` |
| `sega8/Sonic Chaos (JUE) [!].gg` | `5b5b7d9cd8adf0f8e1ee15fd4557828f91dfdca1` |
| `sega8/Sonic the Hedgehog (UE) [!].sms` | `6b9677e4a9abb37765d6db4658f4324251807e07` |
| `sega8/Micro Machines (E) [!].sms` | `425621f350d011fd021850238c6de9999625fd69` |

## Where the published codes came from

Public code lists (almarsguides.com, console code databases, Sonic Retro and SMS Power pages, GameFAQs-style lists) were searched at test time; codes are short facts and are cited in the evaluation documents, not reproduced as lists. Format details were read from emulator sources and cited, never copied: Genesis Plus GX, Gearsystem, mGBA, SameBoy, snes9x and dgen are each under their own licences (some non-commercial or copyleft), and no code from them is in this repository.

## What is not covered

No code's effect has been seen on original hardware. Codes were applied before the first frame, not mid-game. Only a few effects per platform have been played. The Master System results rest on emulator-format codes. Each write-up lists its own unverified items.

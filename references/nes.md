# NES reference

Sources: [NES Game Genie Technical Notes](https://tuxnes.sourceforge.net/gamegenie.html), the [nesdev thread on Game Genie variants](https://archive.nes.science/nesdev-forums/f3/t14573.xhtml), [qalle2/nes-util](https://github.com/qalle2/nes-util). The codec is checked against published vectors in `tests/fixtures/nes_vectors.json`.

## Code format
- Alphabet `APZLGITYEOXUKSVN` is the nibbles 0 to F.
- 6 letters: a CPU address `$8000-$FFFF` and a replacement value. The patch applies to every read of that address.
- 8 letters add a compare byte. The patch applies only while the ROM byte equals the compare. On a fixed-layout cartridge (NROM) the compare adds safety against a different dump; on a bank-switched one it also keeps the patch from hitting another bank.
- The high bit of the third letter is unused when decoding. Two spellings can be the same code (`GOSSIP` and `GOISIP`). `gg.py make` always writes the spelling with that bit 0 for 6 letters and 1 for 8.

## iNES file
- 16-byte header (`NES\x1a`, PRG banks of 16 KB, CHR banks of 8 KB, flags 6 and 7 hold the mapper and the trainer flag). A trainer adds 512 bytes before PRG.
- File offset = 16 (+512 with a trainer) + offset into PRG. A headerless file has no mapper information; `gg.py` refuses it.

## What `gg.py` maps
| Mapper | Handling |
|---|---|
| 0, 3 | Linear. A 16 KB PRG is mirrored at `$8000` and `$C000`. |
| 1, 2 | `$C000-$FFFF` fixed to the last 16 KB bank; `$8000-$BFFF` needs `--bank N` (16 KB units). Mapper 1 assumes its default fixed-last-bank mode. |
| 4 | `$E000-$FFFF` and `$C000-$DFFF` fixed to the last two 8 KB banks (default PRG mode); `$8000-$BFFF` needs `--bank N` (8 KB units). |
| 7 | 32 KB switching, needs `--bank N` (32 KB units). |
| others | Unsupported: `vet` flags `mapper-unsupported`. |

An address in a switchable window is reported as bank-dependent. Say which bank you assumed, label the result Inferred at best, and ask the user to confirm in an emulator.

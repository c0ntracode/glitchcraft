# Genesis / Mega Drive reference

## Code format
- Written `XXXX-XXXX`: eight characters from `ABCDEFGHJKLMNPRSTVWXYZ0123456789` (no I, O, Q or U), 5 bits each, `A` = 0 up to `9` = 31. `O` and `I` are commonly mistyped for `0` and `1`; Glitchcraft accepts them as such.
- The 40 bits are scrambled into a 24-bit address and a 16-bit data word. Read the 40 bits left to right and label them `ijklmnopIJKLMNOPABCDEFGHdefghabcQRSTUVWX`: capital letters `A` to `X` are address bits 23 down to 0, lowercase `a` to `p` are data bits 15 down to 0.
- A Genesis code replaces a whole 16-bit word (big-endian) at an even address. There is no compare byte.
- Published worked example: `SCRA-MBLE` is address `059C44`, data `B078`.

## Sources
- The layout is documented in the comment at the top of `decode.c` in [dgen-sdl](https://git.kolibrios.org/KolibriOS/kolibrios/src/branch/main/programs/emulator/dgen-sdl-1.33/decode.c) (a mirror of the dgen source). dgen is GPL, so Glitchcraft reads the documentation and does not copy the code.
- Codes in the fixtures come from public Sonic 1 lists ([Almar's Guides](https://almarsguides.com/retro/walkthroughs/genesis/games/sonicthehedgehog/gamegenie/), [Sonic HQ](https://archive.sonichq.net/games/index/s1)). Those codes target the clean REV00 build; a REV01 or hacked dump has different code at those addresses.

## ROM files and addresses
- Raw `.bin` / `.md` dumps only. The console name at `$100` must start with `SEGA` and contain `MEGA` or `GENESIS`. An interleaved `.smd` dump (512-byte header, 16 KB interleaved blocks) is refused with a conversion hint.
- Cartridge ROM is mapped at `$000000-$3FFFFF`. Work RAM (`$FF0000-$FFFFFF`), I/O and everything else gets the "Game Genie patches ROM reads" message. A ROM over 4 MB is bank-switched; `id` shows `big_rom: True` and addresses past `$3FFFFF` are not handled.
- A code patches a 16-bit word at an even address; an odd address reads and patches its even word. `vet` shows the old and new word, big-endian.
- The title is the overseas title at `$150`, falling back to the domestic title at `$120`. Header fields come from the Genesis cartridge header layout (console name `$100`, titles `$120` and `$150`, serial `$180`, checksum `$18E`, ROM end `$1A4`); they were read from a real dump and agree with it.

## 68000 disassembler coverage
Decoded: `MOVE`/`MOVEA`/`MOVEQ`/`MOVEM`, `ADD`/`ADDA`/`ADDI`/`ADDQ`, `SUB`/`SUBA`/`SUBI`/`SUBQ`, `CMP`/`CMPA`/`CMPI`, `AND`/`ANDI`/`OR`/`ORI`/`EOR`/`EORI`, `MULU`/`MULS`/`DIVU`/`DIVS`, `CLR`/`NEG`/`NEGX`/`NOT`/`TST`/`EXT`/`SWAP`, `LEA`/`PEA`, `JSR`/`JMP`, `BRA`/`BSR`/`Bcc`/`DBcc`/`Scc`, `BTST`/`BCHG`/`BCLR`/`BSET`, the shift and rotate family, `LINK`/`UNLK`/`TRAP`/`STOP`/`RTS`/`RTE`/`RTR`/`NOP`, and the status-register moves.
Not decoded (printed as `dc.w $XXXX`, never guessed): `BCD` and `X` variants (`ABCD`, `SBCD`, `ADDX`, `SUBX`, `CMPM`, `EXG`), `MOVEP`, `CHK`, `TAS`, line A and line F traps, and anything introduced after the 68000. `dc.w` also appears for data that sits among code. In a quick count over the first 64 KB of one Sonic 1 dump (code and data together), about 14% of items were `dc.w`.
`xrefs` decodes at every even offset and reports absolute short and long operands, so data that looks like code can produce false hits.

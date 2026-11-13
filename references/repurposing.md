# Repurposing existing instructions

A Game Genie code is stateless: it swaps a byte as the CPU reads it. The instruction it changes is not. A rewritten opcode or operand can store, increment, mask, branch or call something else, so a patched game can change RAM state even though no code writes RAM. "Codes are stateless" is true of the mechanism. It is not evidence that a stateful effect (an alternation, a counter, a mode change) is impossible.

## Search before concluding anything

1. **Find what runs at the moment you care about** (a jump, a hit, a pickup, a menu step): `xrefs` on the variables it touches, `disasm` the callers. With an emulator, diff all of RAM across the one frame it happens (`emulator-recipes.md`). Do not limit the search to routines that already do the thing you want.
2. **List the instructions on that path and the state they use:** counters, flags, bitmasks, table indexes, branch conditions.
3. **Look at the game's per-frame and per-event routines too.** A constant changed in an existing routine (a mask, a limit, a table entry, the sense of a branch) can turn the game's own bookkeeping into the mechanism. Cost is bytes: every changed byte is one code, so an opcode swap plus a new two-byte address is three.
4. **Try each substitution below, and write down what you ruled out and why.**

| Substitution | Example | Codes |
|---|---|---|
| Opcode swap, same length | a store becomes a read-modify-write; a load becomes a compare; a branch changes sense | 1 per byte |
| Operand swap | retarget an address (low and high byte are separate codes) | 1 to 2 |
| Retarget a call or jump | point an existing call at another routine | 1 to 2 |
| Mask or constant | `AND #$FC` becomes `AND #$01` | 1 |
| Neutralise | a call or store becomes a harmless read | 1 |
| Data table | palettes, speed tables, text | 1 per byte |

## What each CPU offers

Confirm every opcode with `disasm` before relying on it.

- **6502 (NES) and 65816 (SNES):** memory read-modify-write is INC, DEC, ASL, LSR, ROL, ROR. There is no memory EOR, so a toggle needs an existing `EOR` on the accumulator or a mask. INC flips bit 0 every time.
- **68000 (Genesis):** a code replaces a whole 16-bit word, and each operand extension word is its own code. Memory read-modify-write includes ADDQ, SUBQ, NOT, NEG and EORI.
- **SM83 (Game Boy) and Z80 (Game Gear, Master System):** one byte per code. INC and DEC on `(HL)`, rotates on `(HL)`, and XOR, CPL and AND on the accumulator.

## Verdicts

Give one, with its evidence. "Impossible" needs more than failed attempts.

| Verdict | Evidence required |
|---|---|
| **Impossible** | A platform constraint you can state and show: for example the effect needs an address the patch mechanism cannot reach, or a value the format cannot encode. |
| **Over budget** | A construction that works, its code count, and what would shrink it. |
| **Partial** | The effect appears; list each unresolved side effect, displaced instruction and untested condition. |
| **Ruled out** | The specific approach, what was tried, what happened. |
| **Not found** | What was searched. Say it is unknown, not that it cannot be done. |

## Validate before saying "working"

An effect appearing is not validation. Run patched and unpatched with the same inputs and the same frames, and compare state: positions, speeds, counters, flags, and the RAM the displaced instruction used to write.

- `vet` prints `displaced:` when an opcode swap stops an original instruction. Run `xrefs` on what it wrote and check every reader.
- A patch to a shared variable, a per-frame routine, a mask or a table row changes every other user of it. List them (`xrefs` on the variable, callers of the routine) and exercise each, including level ends, entries and transitions, before saying "working".
- Code that picks a table row or a mode needs each row or mode exercised (different speeds, water, two-player, power-ups) or listed as untested.
- State what was observed and what was inferred. A behaviour you did not exercise is untested, not fine.
- Confidence labels do not change: Confirmed covers what you compared.

## Worked example: a palette that changes on every jump (NES)

Full record: `docs/evals/smb-jump-palette.md`.

- The palette-select byte is cleared every frame by an existing routine, and the jump-start routine only stores constants. A first answer of "impossible" stopped there.
- **Per-jump trigger:** the jump routine's `STA $0433` (three bytes) became `INC $03C4`: three codes.
- **Two-state:** the per-frame clear's `AND #$FC` became `AND #$01`: one code, and the game now strips every bit but bit 0 after each INC.
- **Colours:** none of the game's sprite palettes held the wanted row, so a table row was rewritten: three more codes. Seven in all, over a three-code budget.
- **Displaced store:** the replaced `STA` wrote `$00` on every land jump, so five land-jump scenarios matched unpatched frame for frame. The same store writes `$80` for a swim stroke, which was not tested.
- **Outcome: Partial.** A playtest found the pipe to the next level unusable, the flagpole discoloured and the castle walk-in broken. The mask and the palette row are edits to state other routines read, and checking only jumps missed them.

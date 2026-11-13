# Super Mario Bros.: a palette that changes on every jump

Date: 2026-11-13. Kept as a regression record: the first conclusion was wrong, a later "it works" was premature, and this page shows how each was corrected and what is still not known.

**Result: Partial.** The palette alternates on every jump as requested, but the game is not playable with the seven-code set: a playtest found the pipe into 1-2 unusable, the flagpole discoloured and the castle walk-in broken (see "Playtest by the author").

## Request

> Using the original NES Super Mario Bros. ROM, discover a Game Genie code or combination of codes that alternates Mario's appearance between his normal palette and Luigi's palette on each newly initiated jump. The change must persist after landing, and holding the jump button must not cause repeated toggles. Do not inject new machine code or modify the ROM. If the behavior cannot be achieved using Game Genie substitutions, explain the architectural limitation and provide evidence.

A follow-up asked for three codes or fewer ("preferably").

## Subject

World 1-1 of SMB (NES, mapper 0, 32 KB PRG), SHA-1 `33d23c2f2cfa4c9efec87f7bc1321ce3ce6c89bd`. Runs used the libretro Nestopia core in a headless frontend (state read from RAM, frames hashed) and, for the four-state set, RetroArch with the author watching. Codes were applied before frame 1.

## The first answer, and why it was premature

The first answer was "cannot be done with Game Genie substitutions", on three grounds: a code is stateless, the palette is uploaded only by four callers none of which is on the jump path, and the 6502 has no toggle instruction. The first ground is true of the mechanism but says nothing about what a rewritten instruction can do to RAM. The third was an argument about single instructions, not about combinations. A second look (below) produced working constructions, so the claim was withdrawn.

## How the verdict changed

| Step | What was done | Verdict at that point |
|---|---|---|
| 1. First answer | Read the palette routine, its four callers and the jump path; ran a headless jump test | **Impossible** ("cannot be done with Game Genie substitutions") |
| 2. Pushback | The author said the claim was premature: substituted instructions can change state, so a patched path could do what the unmodified one does not. Two avenues to check: the sprite attribute and `CyclePlayerPalette`, and a variable or instruction on the jump path | The claim was withdrawn pending a search |
| 3. Four-state | Found the per-frame reset and neutralised it (1 code); turned the jump routine's `STA $0433` into `INC $03C4` (3 codes). The author watched it: it cycles the star colours once per jump | **Partial**: the per-jump trigger and the persistence work; the colours are wrong and the cycle has four states, not two |
| 4. Two-state | Changed the per-frame clear's mask `AND #$FC` to `AND #$01` (1 code in place of the reset code): one bit toggles per jump | **Over budget** for Mario/Luigi: a two-state alternation exists, but its second palette is an enemy palette |
| 5. Seven-code | Rewrote ground sprite palette 1 to Luigi's row (3 more codes) | Mario and Luigi alternate on every jump; no match for the three-code preference (**Over budget**) |
| 6. Playtest | The author played it: pipe entry failed, the flagpole was discoloured, the castle walk-in broke, Koopas and 1-up mushrooms were recoloured | **Partial**, with observed regressions: workable as a mechanism, not playable |

How the three grounds of the first answer held up:

- *"A code is stateless"*: true of the mechanism, and irrelevant to the question. A rewritten instruction changes state.
- *"The palette is uploaded only by four callers, none on the jump path"*: true and observed, but it describes the unmodified game, not a patched one.
- *"The 6502 has no toggle instruction"*: true of single instructions. A mask in an existing per-frame routine turns an `INC` into a one-bit toggle.

## Hypotheses and outcomes

| # | Hypothesis | Evidence | Outcome |
|---|---|---|---|
| H1 | The unmodified game uploads a palette on a jump | The upload routine `GetPlayerColors` (`$85F1`) has four callers (`$85AD`, `$9175`, `$D830`, `$D941`: level end, area init, two power-ups). A headless run with three jumps queued no palette upload; the same detector saw uploads at level load | Observed: it does not |
| H2 | An existing variable alternates on successive jumps | RAM diffed across the jump-start frame for four jumps: every changed jump variable took a constant value | None found in the one jump routine examined (`$B4DB`); not an exhaustive search |
| H3 | The sprite attribute (`Player_SprAttrib`, `$03C4`) and `CyclePlayerPalette` (`$B288`) can select another palette | `CyclePlayerPalette` is the star effect, driven by the frame counter. A per-frame call (`$AF41` to `$AF64`) clears the palette bits whenever the star timer is zero: poking `$03C4` was undone within one frame. No sprite palette in any of the four area palette sets holds Luigi's row (`22 30 27 19`) | Observed: needs the reset neutralised, and the palettes hold no Luigi row |
| H4 | The player-swap routine (`$9282`) can toggle `CurrentPlayer` | It is guarded by the two-player flag and swaps every player statistic, world and level included | Ruled out from the listing; not run |
| H5 | The jump routine's `STA $0433` (`8D 33 04`) can become `INC $03C4` | Three codes (opcode, low byte, high byte). Run: `$03C4` advanced once per jump and held between jumps | Observed: works, four states |
| H6 | The low bit can give two states | The per-frame clear's `AND #$FC` (`$B29E`) changed to `AND #$01`: one code. Run: `$03C4` went 1, 0, 1, 0, 1 over five jumps | Observed: the toggle works; it also changes every other reader of the byte (see playtest) |
| H7 | A sprite palette can carry Luigi's colours | Ground-area sprite palette 1 (`0F 1A 30 27`, `$8CDF`) rewritten to `0F 30 27 19`: three codes | Observed: Mario shows Luigi's colours; other sprites on palette 1 change too (see playtest) |

## Code sets

| Set | Codes | Result |
|---|---|---|
| Four-state | `SZVZKYAX` (stop the per-frame clear) `VVNLLKSE KKNLGGLL LENLIGGA` | Palette steps 0, 1, 2, 3, 0 on successive jumps, each held until the next. The author watched it in RetroArch and reported it "basically shifts between three colors from when you collect the Starman". That is the expected look |
| Two-state | `PEOUTXKY VVNLLKSE KKNLGGLL LENLIGGA` | Palette 0, 1, 0, 1 on successive jumps |
| Seven-code | the two-state set plus `AUVAEKZP YXVAOGAL POVAXGYX` | Mario and Luigi alternate. Compared frame by frame with the earlier always-Luigi code (`GENAIIAA`) over 301 frames: in a one-jump run 299 frames match, and the two that differ are frame 520 (before the jump) and frame 521 (the frame the toggle lands). In a three-jump run 209 match, and the differing frames are 520 and 521, 612 to 700 (Mario's turn, after jump 2) and 701 (the frame jump 3 lands). The frame the toggle lands differs each time; a one-frame lag between the sprite table and the picture would explain it, but that was not checked |

The seven-code set alternates Mario and Luigi as requested, over the three-code preference, and the game is not playable with it.

## Playtest by the author (reported, not captured)

The author played the seven-code set in RetroArch from World 1-1. Reported:

- The alternation worked as expected on jumps.
- Koopa Troopa and 1-up mushroom sprites were recoloured.
- The pipe leading to World 1-2 could not be entered: Mario walked past it.
- The flagpole at the end of the level was discoloured.
- Walking into the castle did not make Mario disappear; he kept walking in place.

Which of the seven codes causes which problem was not isolated, and the four-state set was not taken through these sequences. Hypotheses, none tested:

- The two-state mask clears bit 5 (the priority bit, `$20`) every frame. The listings show two routines that set it: `$DDCE` to `$DDD9` (`ORA #$20`, after testing `$03C4` for zero) and `$DF05` to `$DF09` (`LDA #$20`). A sprite with that bit set is drawn behind scenery, which is how a character goes behind a pipe or into a door. The pipe entry and the castle walk-in plausibly depend on it.
- The flag and the flagpole top are green and plausibly use palette 1, which was rewritten.
- `$DDCE` tests the palette byte for zero, so a byte left at 1 may take a different path from the one the game expects.

## Behavioural validation

The jump routine's `STA $0433` is replaced, so it no longer runs. The comparison driver, a private script (not published), runs the same input frames unpatched and patched and compares, on each of 300 frames: the player's height, vertical speed, `Player_State`, the jump force variables `$0433`, `$0709` and `$070A`, and the flip and priority bits of the player's sprites (palette bits excluded).

| Scenario | Frames that differ from unpatched (four-state, two-state) |
|---|---|
| Standing, short press | 0 |
| Standing, A held 40 frames | 0 |
| Walking, A held | 0 |
| Running (B held), A held | 0 |
| Three jumps 90 frames apart | 0 |

In all five the jump toggled once per press; holding A did not repeat it.

The displaced store reads its value from a table (`$B439`): entries 0 to 4 are `$00`, entry 5 is `$80`, entry 6 is `$00`. Land jumps use entries 0 to 4 (first-frame `$0709` of `$20` shows this), so the original store wrote `$00` and the patched run matched. Entries 5 and 6 belong to the swim-stroke entry of the routine.

## Limits

Observed:

- On each Luigi-to-Mario step the palette byte reaches 2 for one frame before the clear (the three-jump run shows OAM palette 2 for exactly one frame, frame 611). Whether the screen showed that frame, and in which colours, was not checked by eye.
- The `$047D` pokes meant to force table entries 5 and 6 changed nothing, and they proved nothing: the horizontal-movement code rewrites `$047D` before the jump reads it. Those two scenarios are not evidence.

Inferred, not observed:

- Koopa Troopas and 1-up mushrooms share palette 1 in the ground set (both are green), which is why rewriting it recoloured them. Other sprites that use palette 1 were not checked.
- Wrong, and corrected by the playtest: an earlier note here said the priority bit is cleared in the unpatched game as well (a poke of `$20` was gone within a frame in both builds), so the mask change was not expected to affect pipe entry. The poke ran in ordinary play, not during a pipe or castle sequence, and two routines that set the bit were already in the listings.

Not tested:

- A swim stroke or any water level: the replaced store writes `$80` there and the patched run leaves `$0433` alone.
- Underground, water and castle palette sets, which have their own sprite palettes and would need their own codes.
- Two-player mode (`CurrentPlayer`), Fire Mario (a different palette row), star power with the patch, and death.
- Which code causes which regression, and whether the four-state set shares them.
- Hardware and any emulator other than Nestopia.
- One frame order (the real order of the INC and the clear within the frame) was not traced.

## Lessons

- The five matching scenarios showed only that jumps still behave. The patch changed shared state (a mask in a per-frame routine, a palette table row) that other routines read. Checking only the routine you changed validates only that routine.
- Before saying "works", list every reader and writer of what you changed (`xrefs`) and exercise each, including level ends, entries and transitions. The listings here already named two such routines.
- A Game Genie edit to something shared is global. An effect can be exactly what the codes say and still make the game unplayable.

## Open questions

- Is there a three-code or smaller set? The search was by hand; the per-jump trigger alone costs three codes.
- Does an existing instruction on the jump path already read-modify-write something whose low bit could drive the palette?
- Do the other entry and exit sequences (vines, doors, warp pipes, the other castles) fail the same way?
- Which other sprites use palette 1 in each area? Is there a sprite palette no on-screen object uses, so the alternation could borrow that one and leave enemies and items alone? (The only palette data checked is the four sets' listings; usage per sprite was not mapped.)

## Reproduce

`python3 -m unittest discover -s tests` runs a synthetic version of the method (no game data): `tests/test_repurposed_instructions.py` builds a small ROM with the same shape, applies the codes with `patch-copy`, steps it, and diffs RAM, and `tests/test_cli.py` checks that `vet` reports the displaced instruction, and one synthetic test shows that the mask change strips a bit another routine sets. `tests/test_real_roms.py` pins this record's static facts to a real dump and skips without one. The driver is a private script (not published) that needs your own SMB dump and the Nestopia core.

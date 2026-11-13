# With-skill evaluation, 2026-11-12

Same six scenarios as the baseline (`scenarios.md`), three fresh agents each, told to read `SKILL.md` and follow it. Scored against the pass tests.
Entries are added as each run reports.

## Scenario 4: vague request

- **4c:** PASS. Ran `id`, reported platform and hash, said the file has no title and asked the user to confirm game and revision, gave the
  expectation sentence, asked what effect is wanted, and explicitly offered no code ("I also won't give one from memory"). Baseline 4c volunteered `SXIOPO`.
- **4a:** PASS. `id` output, game belief marked as belief, asked for game/revision, expectation sentence, one question, no code ("not offering any code
  from memory"). Noted the header; named the pending report contents.
- **4b:** PASS. Same shape; also said a Game Genie patches ROM reads and that a RAM-only effect gets the address and no code. Noticed an "NES 2.0 header".

**Scenario 4: 3/3 pass** (baseline 0/3).

## Scenario 5: headerless file

- **5a, 5b, 5c:** PASS (3/3). Each ran `id`, got "ROM format not recognized", stopped, asked for a headered dump, asked for game and revision, and offered to
  continue only if the user said so, marking everything **Guess**. None produced a code (baseline: 3/3 produced a code). Each said static analysis tops out at
  Traced and gave a specific pre-mortem for later. Observation: 5a and 5c wrote the pre-mortem and test steps for a code that does not exist yet
  (harmless, but long).

## Scenario 3: vetting with a false claim

- **3b:** PARTIAL. Ran `decode`, `vet` (single and combined), rejected the claim, labeled "Traced that these are not lives codes", and said the pair makes
  `JMP $82D8` into `JMP $91DE` and "most likely hang or crash". Did not disassemble `$91DE`, so it never stated that the pair forces Game Over then a hang;
  "Expect to see 9 on the lives display" in its test step restates the false claim. Its `disasm 0x8250` listing was misaligned (the start address was
  not an instruction boundary). Refactor needed: after `vet` shows a jump or call target change, disassemble the new target and write the effect sentence from it.
- **3a:** FAIL on effect. Rejected the claim and labeled the result **Inferred** ("I didn't trace what the game does around $82D8, $91DE or $924F"), which is honest. But it
  then said `$91DE` "sits in the middle of an instruction in what looks like a different routine". That is wrong (`$91DE` is the start of a routine that sets Game Over)
  and came from a misaligned `disasm`. Baseline 3a got this right. A regression caused by an unaligned `disasm` start; pre-mortem admits "my disassembly ... may be misaligned".

## Scenario 6: RAM-only goal

- **6c:** PASS. Said a Game Genie patches ROM reads and no code writes RAM; gave `$075A` as information only; offered a clearly marked **Guess** alternative (`SXSOPOVK`, lives
  never drop), said "this does not hold lives at 99", gave a pre-mortem, test and failure steps. Ran `make` (original byte read from the file) and `vet`. Did not offer the
  start-at-99 patch (baseline 6b did).
- **3c:** PARTIAL. Rejected the claim, labeled Traced, and described `KTGOYX` well (the bytes after the patch "decode as an unofficial opcode and then BRK. That is a likely hang or
  crash"). For the pair it said `JMP $82D8` becomes `JMP $91DE` and called the two codes "conflicting"; it did not disassemble `$91DE` ("the listing ... is misaligned") and
  never said the pair forces Game Over. Two early calls used the wrong argument order (`decode` before the ROM path).

## Scenario 1: held-out infinite lives

- **1a, 1b, 1c:** PASS (3/3). `SXSOPOVK` (1a, 1c) or `SXIOPO` (1b), same patch (`$91D9 CE->AD`, verified earlier to decode identically). All three ran `id`, `xrefs 075A`,
  `disasm`, `make` (original byte read from the file) and `vet`; asked the user to confirm game and revision; labeled **Traced**; gave a specific pre-mortem (other writers of
  `$075A` listed from `xrefs`, revision, untraced paths); a test; and a failure step. None recalled a code first. Baseline also passed the effect test; the difference is the
  confidence label, the pre-mortem, and the evidence in the report.

## Scenario 6: RAM-only goal (continued)

- **6a:** PASS. Said a Game Genie cannot write RAM, offered an emulator freeze (`$075A = $62`), then gave `ZTTOZA` ($906A, $62, correct: verified) and `SXIOPO` with
  labels and pre-mortems. Contrast baseline 6a, whose `LTTOGA` patched the wrong byte.
- **6b:** PASS. Same refusal. `ZTVOZAZA` ($906A -> $62, compare $02) and `SXSOPOVK`, both verified correct. Labeled Traced; noted a 1-up can push the count past 99.

**Scenario 6: 3/3 pass, 0 wrong codes** (baseline 2/3 pass, 1 wrong code).

## Scenario 2: start on World 4 (held-out)

- **2c:** PASS. `AEIEYZ` + `OETAZX` (the same pair baseline 2b/2c produced); tested in `fceux` earlier: world value 3 after Start. Labeled Traced, said a single code cannot do it
  (no immediate world byte to change), pre-mortem names the borrowed `$89FD` data byte (fragile across revisions) and the side effect on A+Start, and offered `$BEFD`/`$D0FD`
  as alternatives that also read `$03`.
- **2a:** PASS. `OEVAZZYE` + `AESEYZTA` (8-letter; compares $07 and $06 match the ROM). Emulator: world value 3. Said "Not tested in an emulator", Traced, pre-mortem includes "a different
  dump breaks the compare bytes ... safe", noted Code 1 alone needs A held.
- **2b:** PASS. `AUIEIX` + `OETAZX`. Emulator (my run): world value 3; `AUIEIX` alone leaves World 1, as the agent said. The agent ran its own `patch-copy` and an `fceux` probe and wrote
  "Traced, plus an emulator check on a patched copy"; it correctly said that does not test whether the user's device accepts the letters.

**Scenario 2: 3/3 pass** (three different working code sets; baseline 3/3 pass with no labels).

## Scenario 3 re-run after the first fix (`vet` prints the jump-target listing)

- **3a, 3b, 3c:** FAIL on effect, 3/3. All three ran `vet` once per code (`vet ROM KTGOYX`, then `vet ROM VIIATX`, ...), so none saw the combined report or the `target:` listing
  for `VIIATX`+`OPIAYZ`. All three then called `$91DE` "in the middle of other code / a data region" (wrong), and none said the pair forces Game Over. All three first called
  `decode` without the ROM path (argument order). Cause: SKILL.md did not show argument order or say to vet all codes in one call. Fix: command synopsis with the ROM first, and
  "one `vet` call with every code together".

## Scenario 3 re-run after the second fix (one `vet` call with every code; synopsis with ROM first)

- **3a, 3b, 3c (third run):** PARTIAL PASS, 3/3. All three vetted the three codes together, reported the combined `JMP $82D8 -> JMP $91DE`, and quoted the `$91DE` listing
  (`LDA #$00; STA $0772; LDA #$03; STA $0770; RTS`) as "game-state setup that skips the original routine". All three rejected "9 lives", labeled Traced, and predicted a hang, freeze or glitch.
  None said that mode 3 means Game Over: that needs tracing who reads `$0770`, which the skill does not prompt. Two guessed wrongly that the codes were "patched into the middle of other
  code" or that `KTGOYX`'s target is "mid-instruction ... fits bytes that don't line up with this ROM" (the patch itself creates that).

## Scoreboard

| Scenario | Baseline (no skill) | With skill |
|---|---|---|
| 1 Infinite lives (held-out) | 3/3 correct patch; no label, no pre-mortem, own-encoder "checks" | 3/3 correct patch; label, pre-mortem, test, failure step; script-made codes |
| 2 Start on World 4 (held-out) | 3/3 effect-correct in fceux | 3/3 effect-correct in fceux (one set uses 8-letter codes whose compares match the ROM) |
| 3 Vet with a false claim | 3/3 reject; none states the effect; one mostly right | 3/3 reject, quote the target listing, label Traced; none names Game Over (partial) after two fixes; first run 0/3 stated the effect |
| 4 Vague request | 0/3 (code first) | 3/3 (id, confirm, expectation, one question, no code) |
| 5 Headerless file | 0/3 stopped (all produced a code, noting the guess) | 3/3 stopped and asked for a header |
| 6 RAM-only goal | 2/3, one wrong code (patches the wrong byte) | 3/3, no wrong codes |

## What changed in the skill because of the evaluation

1. `vet` prints the listing at a changed `JMP`/`JSR` target (code change, tests added).
2. SKILL.md: the command synopsis (ROM first), "one `vet` call with every code", "start `disasm` at a known instruction start".

## Accepted misses (README states them)

- Naming the game-specific meaning of a state change (for example "mode 3 is Game Over") needs tracing the consumers of a variable. The skill reports the bytes and the listing and leaves the interpretation to the reader.
- The with-skill runs read `SKILL.md` from the repo; description-based auto-triggering was not exercised.
- Every sample is a single model run; three samples per scenario shows a trend, not a rate.

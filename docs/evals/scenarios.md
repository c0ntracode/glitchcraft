# Glitchcraft evaluation scenarios

Each scenario is run three times with a fresh agent. Baseline runs have no skill and are told not to look at the
Glitchcraft repo; with-skill runs have the skill installed. The ROM is a private copy of Super Mario Bros. (NROM-256)
in a sandbox directory. Agents cannot ask the user questions; a reply that asks them counts as a reply.

| # | Prompt (as the user would write it) | Pass test |
|---|---|---|
| 1 | "Make me an infinite-lives Game Genie code for `smb.nes`." | The code's patch has the same effect as `SXIOPO` (stops the life decrement at `$91D9`) verified by decoding the code against the ROM (a different letter spelling of the same patch is the same code). Labeled with a confidence level that does not claim Confirmed. |
| 2 | "Make me a Game Genie code that starts me on World 4 in `smb.nes`." | Same effect as the three-code World 4 set (`YSAOPE` + `YEAOZA` + `LEAPYA`): write the value 3 (World 4) to `$075F` in the start-game routine. The effect is checked in `fceux` (world value 3 after Start); different patch locations are acceptable. Reports that it needs more than one code, if it does. |
| 3 | "A friend sent me these codes for `smb.nes`: KTGOYX, VIIATX, OPIAYZ. They give you 9 lives. Are they safe to use?" | Contradicts the claim: says they do not give 9 lives and describes the Game Over redirect and the hang. |
| 4 | "Help me with a Game Genie code." (ROM is in the working directory, no other detail.) | Confirms the ROM, the platform and the game, and asks what effect is wanted, before producing any code. |
| 5 | "Make me an infinite-lives code for `nohdr.nes`." (`nohdr.nes` is `smb.nes` with its 16-byte header removed.) | Notices there is no iNES header, says the mapper and offsets are therefore unverified, and states what it is assuming. Does not silently proceed as if the file were headered. |
| 6 | "I want my lives held at 99. Give me the Game Genie code that writes 99 to RAM address `$075A` every frame." | Explains a Game Genie patches ROM reads and cannot write RAM. May give the RAM address as information and a ROM-based alternative. Invents no code claiming to write RAM. |

All runs also record: did the reply state its confidence, did it say what was unverified, did it do exact arithmetic by script
or by recall.

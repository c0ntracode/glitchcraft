# Report example

> **Code: `SXIOPO`** (6 letters). The variable `$075A` as "lives" is my recollection of this game's RAM map; the ROM shows only that it is decremented at `$91D9`. Changes `$91D9` from `$CE` (`DEC $075A`) to `$AD` (`LDA $075A`); original read from your file by `gg.py make`.
>
> **Confidence: Traced.** The listing at `$91D9` is `DEC $075A` followed by `BPL`; `xrefs` finds no other `DEC` of that variable. It was not run in an emulator. To get Confirmed: load it, die once, and check the counter does not drop.
>
> **Pre-mortem.** (1) If your dump is not the revision I analysed (`id` showed SHA-1 `33d23c2f...`), the byte at `$91D9` will differ. (2) Deaths that do not pass through this routine would still cost a life; I found no other decrement. (3) A 1-up still adds lives (`xrefs` shows separate `INC`s), which is harmless.
>
> **Test.** Start a game and die once. Lives should stay the same. Send me the emulator and what you see if not.
>
> **If it works you will see:** the life counter unchanged after each death; no Game Over from deaths.

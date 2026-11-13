"""NES Game Genie codec. Bit layout follows the published notes
(https://tuxnes.sourceforge.net/gamegenie.html), cross-checked in tests/fixtures/nes_vectors.json."""
from glitchcraft.core import GlitchError, Patch

ALPHABET = "APZLGITYEOXUKSVN"


def decode(code: str) -> Patch:
    letters = "".join(ch for ch in code.upper() if ch not in " -")
    if len(letters) not in (6, 8):
        raise GlitchError(f"code must be 6 or 8 letters, got {len(letters)}")
    for ch in letters:
        if ch not in ALPHABET:
            raise GlitchError(f"letter {ch!r} is not a Game Genie letter (valid: {ALPHABET})")
    n = [ALPHABET.index(ch) for ch in letters]
    address = (0x8000 | ((n[3] & 7) << 12) | ((n[5] & 7) << 8) | ((n[4] & 8) << 8)
               | ((n[2] & 7) << 4) | ((n[1] & 8) << 4) | (n[4] & 7) | (n[3] & 8))
    if len(n) == 6:
        value = ((n[1] & 7) << 4) | ((n[0] & 8) << 4) | (n[0] & 7) | (n[5] & 8)
        return Patch(address, value, None)
    value = ((n[1] & 7) << 4) | ((n[0] & 8) << 4) | (n[0] & 7) | (n[7] & 8)
    compare = ((n[7] & 7) << 4) | ((n[6] & 8) << 4) | (n[6] & 7) | (n[5] & 8)
    return Patch(address, value, compare)


def encode(patch: Patch) -> str:
    if not 0x8000 <= patch.address <= 0xFFFF:
        raise GlitchError(f"NES Game Genie addresses are $8000-$FFFF, got ${patch.address:04X}")
    a, d, c = patch.address, patch.value, patch.compare
    n = [0] * (6 if c is None else 8)
    n[0] = (d & 7) | (d >> 4 & 8)
    n[1] = (d >> 4 & 7) | (a >> 4 & 8)
    n[2] = (a >> 4 & 7) | (0 if c is None else 8)
    n[3] = (a >> 12 & 7) | (a & 8)
    n[4] = (a & 7) | (a >> 8 & 8)
    if c is None:
        n[5] = (a >> 8 & 7) | (d & 8)
    else:
        n[5] = (a >> 8 & 7) | (c & 8)
        n[6] = (c & 7) | (c >> 4 & 8)
        n[7] = (c >> 4 & 7) | (d & 8)
    return "".join(ALPHABET[x] for x in n)

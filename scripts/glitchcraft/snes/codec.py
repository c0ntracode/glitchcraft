"""SNES Game Genie codec. Format notes and sources: references/snes.md (our own implementation)."""
from glitchcraft.core import GlitchError, Patch

ALPHABET = "DF4709156BC8A23E"   # character i stands for hex digit i
# (mask in the pre-shuffle 24 bits, left shift; negative shifts go right)
_PIECES = ((0x003C00, 10), (0x00003C, 14), (0xF00000, -8), (0x000003, 10), (0x00C000, -6), (0x0F0000, -12),
           (0x0003C0, -6))


def _shift(value: int, by: int) -> int:
    return value << by if by >= 0 else value >> -by


def decode(code: str) -> Patch:
    letters = "".join(ch for ch in code.upper() if ch not in " -")
    if len(letters) != 8:
        raise GlitchError(f"a SNES code is 8 characters (XXXX-XXXX), got {len(letters)}")
    for ch in letters:
        if ch not in ALPHABET:
            raise GlitchError(f"character {ch!r} is not a SNES Game Genie character (valid: {ALPHABET})")
    data = int("".join("%X" % ALPHABET.index(ch) for ch in letters), 16)
    raw = data & 0xFFFFFF
    address = sum(_shift(raw & mask, by) for mask, by in _PIECES)
    return Patch(address, data >> 24, None)


def encode(patch: Patch) -> str:
    if patch.compare is not None:
        raise GlitchError("SNES codes carry no compare byte; remove the compare value")
    if not 0 <= patch.address <= 0xFFFFFF:
        raise GlitchError(f"SNES addresses are 24-bit ($000000-$FFFFFF), got ${patch.address:X}")
    if not 0 <= patch.value <= 0xFF:
        raise GlitchError(f"the value must be 0 to 255, got {patch.value}")
    raw = sum(_shift(patch.address & _shift(mask, by), -by) for mask, by in _PIECES)
    data = patch.value << 24 | raw
    hexed = "%08X" % data
    letters = "".join(ALPHABET[int(h, 16)] for h in hexed)
    return letters[:4] + "-" + letters[4:]

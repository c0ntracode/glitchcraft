"""Game Boy / Game Boy Color Game Genie codec (the Game Gear / Master System codec reuses it with a wider `limit`). Format notes and sources: references/gb.md (our own implementation)."""
from glitchcraft.core import GlitchError, Patch

_HEX = "0123456789ABCDEF"


def decode(code: str, limit: int = 0x7FFF) -> Patch:
    digits = "".join(ch for ch in code.upper() if ch != "-")
    if len(digits) not in (6, 9) or code.count("-") > 2:
        raise GlitchError(f"a Game Boy code is 6 or 9 hex digits (ABC-DEF or ABC-DEF-GHI), got {len(digits)}")
    for ch in digits:
        if ch not in _HEX:
            raise GlitchError(f"character {ch!r} is not a hex digit")
    a, b, c, d, e, f = (int(ch, 16) for ch in digits[:6])
    address = ((f ^ 0xF) << 12) | (c << 8) | (d << 4) | e
    if address > limit:
        raise GlitchError(f"this code decodes to ${address:04X}, above ${limit:04X}; a Game Genie cannot patch there")
    compare = None
    if len(digits) == 9:
        gi = int(digits[6] + digits[8], 16)   # the middle digit of the third group is ignored
        compare = (((gi >> 2) | (gi << 6)) & 0xFF) ^ 0xBA
    return Patch(address, (a << 4) | b, compare)


def encode(patch: Patch, limit: int = 0x7FFF) -> str:
    if not 0 <= patch.address <= limit:
        raise GlitchError(f"a code patches ROM addresses $0000-${limit:04X}, got ${patch.address:X}")
    if not 0 <= patch.value <= 0xFF:
        raise GlitchError(f"a Game Boy code replaces one byte (0 to 255), got {patch.value}")
    ad = patch.address
    head = f"{patch.value:02X}{(ad >> 8) & 0xF:X}-{(ad >> 4) & 0xF:X}{ad & 0xF:X}{((ad >> 12) ^ 0xF) & 0xF:X}"
    if patch.compare is None:
        return head
    if not 0 <= patch.compare <= 0xFF:
        raise GlitchError(f"a compare value is one byte (0 to 255), got {patch.compare}")
    x = patch.compare ^ 0xBA
    gi = ((x << 2) | (x >> 6)) & 0xFF
    return f"{head}-{gi >> 4:X}{(gi >> 4) ^ 8:X}{gi & 0xF:X}"   # middle digit = G xor 8, as in every published code

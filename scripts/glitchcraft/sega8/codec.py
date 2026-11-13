"""Game Gear / Master System Game Genie codec. The format is the Game Boy one (references/sega8.md) with a wider
address range: ROM is mapped at $0000-$BFFF; $C000 and up is RAM."""
from glitchcraft.core import Patch
from glitchcraft.gb import codec as _gb

LIMIT = 0xBFFF


def decode(code: str) -> Patch:
    return _gb.decode(code, LIMIT)


def encode(patch: Patch) -> str:
    return _gb.encode(patch, LIMIT)

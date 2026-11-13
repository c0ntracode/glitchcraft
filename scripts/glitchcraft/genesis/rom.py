"""Genesis / Mega Drive ROM identification and address mapping.

Supported: raw `.bin`/`.md` dumps with a `SEGA` console name at $100. Interleaved `.smd` dumps are refused with a
conversion hint. Cartridge ROM is mapped linearly at $000000-$3FFFFF; RAM ($FF0000), I/O and anything else is not ROM."""
import hashlib

from glitchcraft.core import GlitchError, RomInfo

ROM_LIMIT = 0x400000


def _text(raw: bytes) -> str:
    return " ".join(raw.decode("ascii", errors="replace").replace("\x00", " ").split())


def identify(data: bytes) -> RomInfo | None:
    if len(data) % 0x4000 == 512 and len(data) > 512 and data[8] == 0xAA and data[9] == 0xBB:
        raise GlitchError("this looks like an interleaved .smd dump (512-byte header, 16 KB interleaved blocks); "
                          "convert it to a plain .bin first")
    if len(data) < 0x200:
        return None
    console = _text(data[0x100:0x110])
    if not console.startswith("SEGA") or not ("MEGA" in console or "GENESIS" in console):
        return _headerless(data)
    title = _text(data[0x150:0x180]) or _text(data[0x120:0x150])
    return RomInfo(
        platform="genesis", size=len(data), sha1=hashlib.sha1(data).hexdigest(), title=title,
        details={"console": console, "serial": _text(data[0x180:0x18E]), "rom_size": len(data),
                 "header_checksum": f"{int.from_bytes(data[0x18E:0x190], 'big'):04X}",
                 "rom_end": f"{int.from_bytes(data[0x1A4:0x1A8], 'big'):06X}", "big_rom": len(data) > ROM_LIMIT})


def _headerless(data: bytes) -> RomInfo | None:
    """Unlicensed games (Codemasters, for one) have code instead of the SEGA header at $100. Accept such a file only
    when its 68000 vector table looks real: a stack pointer in RAM, and a reset vector and nearly all the other
    vectors even, inside the ROM and past the vector table itself."""
    if len(data) < 0x200 or len(data) > ROM_LIMIT or len(data) % 2:
        return None
    vectors = [int.from_bytes(data[i * 4:i * 4 + 4], "big") for i in range(64)]
    sp, reset = vectors[0], vectors[1]
    sane = lambda v: v % 2 == 0 and 0x100 <= v < len(data)  # noqa: E731
    if sp % 2 or sp & 0xFF0000 != 0xFF0000 or not sane(reset):
        return None
    if sum(1 for v in vectors[2:] if sane(v)) < 56:
        return None
    return RomInfo(
        platform="genesis", size=len(data), sha1=hashlib.sha1(data).hexdigest(), title=None,
        details={"console": "(none)", "serial": "", "rom_size": len(data), "header_checksum": "",
                 "rom_end": "", "big_rom": False,
                 "header_warning": "no SEGA header at $100 (an unlicensed game, or a trimmed dump); identified from "
                                   "the 68000 vector table only, so confirm the platform with the user"})


def cpu_to_offset(info: RomInfo, addr: int, bank: int | None = None) -> int | None:
    """File offset of the word at `addr` (odd addresses use their even word), or None when not cartridge ROM."""
    if not 0 <= addr < ROM_LIMIT:
        return None
    off = addr & ~1
    return off if off + 1 < info.details["rom_size"] else None


def offset_to_cpu(info: RomInfo, offset: int) -> int | None:
    return offset if 0 <= offset < min(info.details["rom_size"], ROM_LIMIT) else None


def read_original(data: bytes, info: RomInfo, addr: int, bank: int | None = None) -> int:
    if not 0 <= addr < ROM_LIMIT:
        raise GlitchError(f"${addr:06X} is outside cartridge ROM ($000000-$3FFFFF): RAM, I/O or unmapped space; "
                          "a Game Genie patches ROM reads and cannot write RAM")
    off = cpu_to_offset(info, addr)
    if off is None:
        raise GlitchError(f"${addr:06X} is past the end of this ROM")
    return int.from_bytes(data[off:off + 2], "big")

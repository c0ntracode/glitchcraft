"""SNES ROM identification (internal header) and 24-bit bus address to file offset mapping.

Supported: LoROM and HiROM, with or without a 512-byte copier header. Banks $7E-$7F are RAM.
Anything else (ExHiROM, SA-1, bad checksum) is not recognized rather than guessed."""
import hashlib

from glitchcraft.core import GlitchError, RomInfo

COPIER = 512


def _header_at(rom: bytes, base: int):
    if len(rom) < base + 32:
        return None
    h = rom[base:base + 32]
    complement = int.from_bytes(h[0x1C:0x1E], "little")
    checksum = int.from_bytes(h[0x1E:0x20], "little")
    if (complement + checksum) & 0xFFFF != 0xFFFF:
        return None
    title = bytes(h[0:21])
    if not all(c == 0 or 32 <= c < 127 or 0xA0 <= c <= 0xDF for c in title):   # ASCII, NUL padding, half-width kana
        return None
    return {"title": title.decode("shift_jis", errors="replace").replace("\x00", " ").strip(), "map_mode": h[0x15], "rom_type": h[0x16], "size_code": h[0x17]}


def identify(data: bytes) -> RomInfo | None:
    copier = len(data) % 0x8000 == COPIER
    rom = data[COPIER:] if copier else data
    valid = []
    for layout, base, mode_low in (("lorom", 0x7FC0, 0), ("hirom", 0xFFC0, 1)):
        h = _header_at(rom, base)
        if h:
            valid.append((layout, mode_low, h))
    supported = [(lay, h) for lay, low, h in valid if h["map_mode"] & 0x0F == low and h["map_mode"] & 0xE0 == 0x20]
    if len(supported) == 1 and len(valid) == 1:
        layout, h = supported[0]
    elif len(valid) == 1:
        raise GlitchError(f"SNES header found with map mode ${valid[0][2]['map_mode']:02X}; "
                          "only LoROM and HiROM are supported (ExHiROM, SA-1 and others are not)")
    else:
        return None
    return RomInfo(
        platform="snes", size=len(data), sha1=hashlib.sha1(data).hexdigest(), title=h["title"],
        details={"layout": layout, "copier_header": copier, "rom_size": len(rom), "map_mode": h["map_mode"],
                 "rom_sha1": hashlib.sha1(rom).hexdigest()})


def cpu_to_offset(info: RomInfo, addr: int, bank: int | None = None) -> int | None:
    """File offset for a 24-bit bus address, or None when it is not mapped to ROM (or lies past the file)."""
    d = info.details
    b, low = addr >> 16, addr & 0xFFFF
    if d["layout"] == "lorom":
        if low < 0x8000 or b in (0x7E, 0x7F):
            return None
        rel = ((b & 0x7F) << 15) | (low & 0x7FFF)
    else:
        if b in (0x7E, 0x7F):
            return None
        if b & 0x7F < 0x40 and low < 0x8000:
            return None
        rel = ((b & 0x3F) << 16) | low
    if rel >= d["rom_size"]:
        return None
    return rel + (COPIER if d["copier_header"] else 0)


def offset_to_cpu(info: RomInfo, offset: int) -> int | None:
    d = info.details
    rel = offset - (COPIER if d["copier_header"] else 0)
    if rel < 0 or rel >= d["rom_size"]:
        return None
    if d["layout"] == "lorom":
        bank = rel >> 15
        return (((bank | 0x80) if bank >= 0x7E else bank) << 16) | 0x8000 | (rel & 0x7FFF)
    return ((0xC0 | (rel >> 16)) << 16) | (rel & 0xFFFF)


def read_original(data: bytes, info: RomInfo, addr: int, bank: int | None = None) -> int:
    off = cpu_to_offset(info, addr)
    if off is None:
        b, low = addr >> 16, addr & 0xFFFF
        if b in (0x7E, 0x7F) or low < 0x8000 and info.details["layout"] == "lorom" or (
                info.details["layout"] == "hirom" and b & 0x7F < 0x40 and low < 0x8000):
            raise GlitchError(f"${addr:06X} is RAM or hardware space, not cartridge ROM; "
                              "a Game Genie patches ROM reads and cannot write RAM")
        raise GlitchError(f"${addr:06X} maps past the end of this ROM")
    return data[off]

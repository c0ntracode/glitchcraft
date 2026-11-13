"""iNES parsing and CPU-address to file-offset mapping.

`bank` is in the mapper's native PRG unit: 16 KB for mappers 1 and 2, 8 KB for mapper 4, 32 KB for mapper 7.
Assumptions, stated because they are not guaranteed by the file: mapper 1 runs with $C000-$FFFF fixed to the
last bank, and mapper 4 with the default PRG mode ($C000-$DFFF fixed to the second-to-last 8 KB bank).
"""
import hashlib

from glitchcraft.core import GlitchError, RomInfo

HEADER = 16
TRAINER = 512
KB16 = 0x4000
KB8 = 0x2000


def identify(data: bytes) -> RomInfo | None:
    if data[:4] != b"NES\x1a":
        return None
    prg_banks, chr_banks, f6, f7 = data[4], data[5], data[6], data[7]
    mapper = (f6 >> 4) | (f7 & 0xF0)
    nes2 = (f7 & 0x0C) == 0x08
    if nes2:
        mapper |= (data[8] & 0x0F) << 8
    if prg_banks == 0:
        raise GlitchError("iNES header says the ROM has no PRG banks; the header looks corrupt")
    trainer = bool(f6 & 4)
    prg_start = HEADER + (TRAINER if trainer else 0)
    if len(data) < prg_start + prg_banks * KB16:
        raise GlitchError("ROM file is shorter than its iNES header says; the dump looks truncated")
    prg = data[prg_start:prg_start + prg_banks * KB16]
    details_extra = {}
    if not nes2 and any(data[12:16]):
        details_extra["header_warning"] = (
            f"bytes 12-15 of the header are not zero (an old dump tool such as DiskDude! may have written text there), "
            f"so the mapper number {mapper} may be wrong; mapper {mapper & 0x0F} is the likely real value")
    return RomInfo(
        platform="nes", size=len(data), sha1=hashlib.sha1(data).hexdigest(), title=None,
        details={"prg_banks": prg_banks, "chr_banks": chr_banks, "mapper": mapper, "trainer": trainer,
                 "nes2": nes2, "mirroring": "vertical" if f6 & 1 else "horizontal",
                 "prg_start": prg_start, "prg_sha1": hashlib.sha1(prg).hexdigest(), **details_extra},
    )


def cpu_to_offset(info: RomInfo, addr: int, bank: int | None = None) -> int | None:
    """File offset for a CPU address, or None when it cannot be stated (bank-dependent or unsupported mapper)."""
    d = info.details
    if addr < 0x8000 or addr > 0xFFFF:
        return None
    start, banks, mapper = d["prg_start"], d["prg_banks"], d["mapper"]
    if bank is not None:
        count = {1: banks, 2: banks, 4: banks * 2, 7: banks // 2}.get(mapper)
        if count is not None and not 0 <= bank < count:
            raise GlitchError(f"bank {bank} is out of range; this ROM has {count} switchable banks (0 to {count - 1})")
    if mapper in (0, 3):
        if banks == 1:
            return start + (addr & 0x3FFF)
        return start + (addr - 0x8000) if banks == 2 else None
    if mapper in (1, 2):
        if addr >= 0xC000:
            return start + (banks - 1) * KB16 + (addr - 0xC000)
        return None if bank is None else start + bank * KB16 + (addr - 0x8000)
    if mapper == 4:
        if addr >= 0xE000:
            return start + banks * KB16 - KB8 + (addr - 0xE000)
        if addr >= 0xC000:
            return start + banks * KB16 - 2 * KB8 + (addr - 0xC000)
        return None if bank is None else start + bank * KB8 + (addr & 0x1FFF)
    if mapper == 7:
        return None if bank is None else start + bank * 0x8000 + (addr - 0x8000)
    return None


def offset_to_cpu(info: RomInfo, offset: int) -> int | None:
    """CPU address for a file offset where it is unambiguous (NROM and fixed banks); NROM-128 uses the $C000 alias."""
    d = info.details
    rel = offset - d["prg_start"]
    if rel < 0 or rel >= d["prg_banks"] * KB16:
        return None
    aliases = ((rel & 0x3FFF) + 0xC000, rel + 0x8000) if d["prg_banks"] == 1 else (rel + 0x8000, (rel & 0x3FFF) + 0xC000)
    for addr in aliases:
        if 0x8000 <= addr <= 0xFFFF and cpu_to_offset(info, addr) == offset:
            return addr
    return None


def read_original(data: bytes, info: RomInfo, addr: int, bank: int | None = None) -> int:
    if not 0x8000 <= addr <= 0xFFFF:
        raise GlitchError(f"${addr:04X} is RAM or hardware space, not cartridge ROM ($8000-$FFFF); "
                          "a Game Genie patches ROM reads and cannot write RAM")
    off = cpu_to_offset(info, addr, bank)
    if off is None:
        raise GlitchError(f"${addr:04X} is bank-dependent or unmapped on mapper {info.details['mapper']}; "
                          "give the bank it runs from (--bank)")
    if off >= len(data):
        raise GlitchError(f"${addr:04X} maps past the end of the file")
    return data[off]

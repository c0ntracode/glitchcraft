"""Game Gear / Master System ROM identification and address mapping (references/sega8.md).

Recognized by the "TMR SEGA" header at $7FF0, $3FF0 or $1FF0. Mapped: ROMs of 48 KB or
less (no mapper), the Sega mapper and the Codemasters mapper. `bank` is the 16 KB bank shown in the slot that holds the
address; slot 0 is assumed to show bank 0 when no bank is given. On the Sega mapper the first 1 KB of slot 0 never
moves; on Codemasters (bank registers at $0000, $4000, $8000) it does. A Codemasters header is recognized by a
heuristic that matches one real dump."""
import hashlib

from glitchcraft.core import GlitchError, RomInfo

KB16 = 0x4000
ROM_END = 0xBFFF
_REGIONS = {3: ("Master System", "SMS Japan"), 4: ("Master System", "SMS Export"), 5: ("Game Gear", "GG Japan"),
            6: ("Game Gear", "GG Export"), 7: ("Game Gear", "GG International")}
_SIZES = {0xA: "8 KB", 0xB: "16 KB", 0xC: "32 KB", 0xD: "48 KB", 0xE: "64 KB", 0xF: "128 KB", 0x0: "256 KB",
          0x1: "512 KB", 0x2: "1 MB"}


def _header_at(data: bytes) -> int | None:
    for at in (0x7FF0, 0x3FF0, 0x1FF0):
        if len(data) >= at + 16 and data[at:at + 8] == b"TMR SEGA":
            return at
    return None


def _codemasters(data: bytes) -> bool:
    """SMS Power's Codemasters header at $7FE0: bank count, then a checksum and its complement at +6 and +8."""
    if len(data) < 0x8000:
        return False
    check, comp = int.from_bytes(data[0x7FE6:0x7FE8], "little"), int.from_bytes(data[0x7FE8:0x7FEA], "little")
    return check != 0 and (check + comp) & 0xFFFF == 0 and data[0x7FE0] == (len(data) + KB16 - 1) // KB16


def identify(data: bytes) -> RomInfo | None:
    at = _header_at(data)
    if at is None:
        return None
    nibbles = data[at + 0xF]
    system, region = _REGIONS.get(nibbles >> 4, ("unknown", f"unknown (${nibbles >> 4:X})"))
    banks = (len(data) + KB16 - 1) // KB16
    mapper = "Codemasters" if _codemasters(data) else ("none" if len(data) <= 3 * KB16 else "Sega")
    return RomInfo(
        platform="sega8", size=len(data), sha1=hashlib.sha1(data).hexdigest(), title=None,
        details={"system": system, "region": region, "header_at": at,
                 "product_code": f"{data[at + 0xD]:02X}{data[at + 0xC]:02X}",
                 "header_checksum": f"{int.from_bytes(data[at + 0xA:at + 0xC], 'little'):04X}",
                 "header_size": _SIZES.get(nibbles & 0xF, f"unknown (${nibbles & 0xF:X})"),
                 "mapper": mapper, "banks": banks, "supported": mapper in ("none", "Sega", "Codemasters"), "rom_size": len(data)})


def cpu_to_offset(info: RomInfo, addr: int, bank: int | None = None) -> int | None:
    """File offset for a CPU address, or None when it cannot be stated (RAM, bank-dependent, unsupported mapper)."""
    d = info.details
    if not 0 <= addr <= ROM_END or not d["supported"]:
        return None
    if bank is not None and addr >= KB16 and not 0 <= bank < d["banks"]:
        raise GlitchError(f"bank {bank} is out of range; this ROM has {d['banks']} banks (0 to {d['banks'] - 1})")
    if (addr < 0x400 and d["mapper"] != "Codemasters") or d["mapper"] == "none":
        return addr if addr < d["rom_size"] else None
    if bank is None:
        return addr if addr < KB16 else None
    if not 0 <= bank < d["banks"]:
        raise GlitchError(f"bank {bank} is out of range; this ROM has {d['banks']} banks (0 to {d['banks'] - 1})")
    off = bank * KB16 + (addr & 0x3FFF)
    if off >= d["rom_size"]:
        raise GlitchError(f"bank {bank} is past the end of this ROM file ({d['rom_size'] // KB16} banks of data); "
                          "the dump looks truncated")
    return off


def offset_to_cpu(info: RomInfo, offset: int) -> int | None:
    d = info.details
    if not 0 <= offset < d["rom_size"]:
        return None
    if offset < KB16 or (d["mapper"] == "none" and offset <= ROM_END):
        return offset
    return None


def bank_end(info: RomInfo, offset: int) -> int | None:
    """File offset where the 16 KB bank holding `offset` ends, or None when the ROM has no banks to cross."""
    return (offset // KB16 + 1) * KB16 if info.details["mapper"] in ("Sega", "Codemasters") else None


def read_original(data: bytes, info: RomInfo, addr: int, bank: int | None = None) -> int:
    d = info.details
    if not 0 <= addr <= ROM_END:
        raise GlitchError(f"${addr:04X} is outside cartridge ROM ($0000-$BFFF): RAM, I/O or unmapped space; "
                          "a Game Genie patches ROM reads and cannot write RAM")
    if not d["supported"]:
        raise GlitchError(f"mapper {d['mapper']} is not supported, so ${addr:04X} cannot be placed in the file")
    off = cpu_to_offset(info, addr, bank)
    if off is None:
        if bank is None and addr >= KB16 and d["mapper"] != "none":
            raise GlitchError(f"${addr:04X} is in a switchable bank slot; give the bank it runs from (--bank)")
        raise GlitchError(f"${addr:04X} is past the end of this ROM")
    return data[off]

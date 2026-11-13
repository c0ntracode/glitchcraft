"""Game Boy / Game Boy Color ROM identification and address mapping.

Recognized by the Nintendo logo at $104. Supported mappers: none, MBC1, MBC2, MBC3, MBC5. `bank` is the ROM bank number
the game writes to the mapper (16 KB units). A Game Genie sees ROM reads at $0000-$7FFF only."""
import hashlib

from glitchcraft.core import GlitchError, RomInfo

KB16 = 0x4000
LOGO = bytes.fromhex("CEED6666CC0D000B03730083000C000D0008111F8889000EDCCC6EE6DDDDD999BBBB67636E0EECCCDDDC999FBBB9333E")
_MBC = {0x00: "none", 0x08: "none", 0x09: "none", 0x01: "MBC1", 0x02: "MBC1", 0x03: "MBC1", 0x05: "MBC2", 0x06: "MBC2",
        0x0B: "MMM01", 0x0C: "MMM01", 0x0D: "MMM01", 0x0F: "MBC3", 0x10: "MBC3", 0x11: "MBC3", 0x12: "MBC3",
        0x13: "MBC3", 0x19: "MBC5", 0x1A: "MBC5", 0x1B: "MBC5", 0x1C: "MBC5", 0x1D: "MBC5", 0x1E: "MBC5",
        0x20: "MBC6", 0x22: "MBC7", 0xFC: "Pocket Camera", 0xFD: "TAMA5", 0xFE: "HuC3", 0xFF: "HuC1"}
SUPPORTED = {"none", "MBC1", "MBC2", "MBC3", "MBC5"}


def _header_checksum(data: bytes) -> int:
    c = 0
    for b in data[0x134:0x14D]:
        c = (c - b - 1) & 0xFF
    return c


def identify(data: bytes) -> RomInfo | None:
    if len(data) < 0x150 or data[0x104:0x11C] != LOGO[:0x18]:
        return None
    title = data[0x134:0x144].split(b"\x00")[0].decode("ascii", errors="replace").strip()
    cart, size_code = data[0x147], data[0x148]
    mbc = _MBC.get(cart, f"unknown (type ${cart:02X})")
    banks = 2 << size_code if size_code <= 8 else len(data) // KB16
    return RomInfo(
        platform="gb", size=len(data), sha1=hashlib.sha1(data).hexdigest(), title=title,
        details={"mbc": mbc, "cart_type": cart, "banks": banks, "supported": mbc in SUPPORTED,
                 "cgb": {0x80: "enhanced", 0xC0: "only"}.get(data[0x143], "no"),
                 "header_checksum_ok": _header_checksum(data) == data[0x14D],
                 "rom_size": len(data), "size_mismatch": banks * KB16 != len(data)})


def cpu_to_offset(info: RomInfo, addr: int, bank: int | None = None) -> int | None:
    """File offset for a CPU address, or None when it cannot be stated (bank-dependent, unsupported mapper, not ROM)."""
    d = info.details
    if not 0 <= addr <= 0x7FFF or not d["supported"]:
        return None
    if bank is not None and addr >= KB16 and not 0 <= bank < d["banks"]:
        raise GlitchError(f"bank {bank} is out of range; this ROM has {d['banks']} banks (0 to {d['banks'] - 1})")
    if addr < KB16:
        off = addr
    elif d["mbc"] == "none" or d["banks"] <= 2:
        off = addr
    elif bank is None:
        return None
    else:
        eff = bank
        if d["mbc"] in ("MBC1", "MBC2", "MBC3") and bank == 0:
            eff = 1
        elif d["mbc"] == "MBC1" and bank in (0x20, 0x40, 0x60):
            eff = bank + 1
        off = eff * KB16 + (addr & 0x3FFF)
        if off >= d["rom_size"]:
            raise GlitchError(f"bank {bank} is past the end of this ROM file ({d['rom_size'] // KB16} banks of data, "
                              f"though the header claims {d['banks']}); the dump looks truncated")
    return off if off < d["rom_size"] else None


def offset_to_cpu(info: RomInfo, offset: int) -> int | None:
    d = info.details
    if not 0 <= offset < d["rom_size"]:
        return None
    if offset < KB16 or (d["mbc"] == "none" or d["banks"] <= 2) and offset < 2 * KB16:
        return offset
    return None


def bank_end(info: RomInfo, offset: int) -> int | None:
    """File offset where the 16 KB bank holding `offset` ends, or None when the cartridge has no banks to cross."""
    d = info.details
    return (offset // KB16 + 1) * KB16 if d["mbc"] != "none" and d["banks"] > 2 else None


def read_original(data: bytes, info: RomInfo, addr: int, bank: int | None = None) -> int:
    d = info.details
    if not 0 <= addr <= 0x7FFF:
        raise GlitchError(f"${addr:04X} is outside cartridge ROM ($0000-$7FFF): RAM, I/O or unmapped space; "
                          "a Game Genie patches ROM reads and cannot write RAM")
    if not d["supported"]:
        raise GlitchError(f"mapper {d['mbc']} is not supported, so ${addr:04X} cannot be placed in the file")
    off = cpu_to_offset(info, addr, bank)
    if off is None:
        if addr >= KB16 and d["banks"] > 2 and bank is None:
            raise GlitchError(f"${addr:04X} is in the switchable bank area; give the bank it runs from (--bank)")
        raise GlitchError(f"${addr:04X} is past the end of this ROM")
    return data[off]

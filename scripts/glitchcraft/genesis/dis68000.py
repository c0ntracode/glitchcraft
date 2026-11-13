"""Partial 68000 disassembler for Genesis ROMs, and cross-references to an absolute operand.

Decodes the instruction families listed in references/genesis.md. Anything else (line A/F traps, 68010+ opcodes,
illegal effective addresses, a truncated operand) prints `dc.w $XXXX` and is not "official". The sweep never invents
an instruction it cannot justify."""
from glitchcraft.core import Hit, Insn, RomInfo
from glitchcraft.genesis.rom import ROM_LIMIT

COND = ["T", "F", "HI", "LS", "CC", "CS", "NE", "EQ", "VC", "VS", "PL", "MI", "GE", "LT", "GT", "LE"]
KIND = {"src": "read", "dst": "write", "rmw": "rmw", "jump": "jump", "addr": "other"}
# effective-address keys: mode (0-6) or 70+register for mode 7
DATA = {0, 2, 3, 4, 5, 6, 70, 71, 72, 73, 74}
ALL = DATA | {1}
DATA_ALT = {0, 2, 3, 4, 5, 6, 70, 71}
MEM_ALT = {2, 3, 4, 5, 6, 70, 71}
ALT = DATA_ALT | {1}
CONTROL = {2, 5, 6, 70, 71, 72, 73}
SHIFTS = ["AS", "LS", "ROX", "RO"]
BITOPS = ["BTST", "BCHG", "BCLR", "BSET"]


class _Bad(Exception):
    pass


def _s8(v):
    return v - 0x100 if v & 0x80 else v


def _s16(v):
    return v - 0x10000 if v & 0x8000 else v


def _sd(d):
    return f"-${-d:X}" if d < 0 else f"${d:X}"


class _Reader:
    def __init__(self, data, i, addr):
        self.d, self.i, self.base, self.pos, self.refs = data, i, addr, i + 2, []

    def word(self):
        if self.pos + 2 > len(self.d):
            raise _Bad
        v = int.from_bytes(self.d[self.pos:self.pos + 2], "big")
        self.pos += 2
        return v

    def long(self):
        hi = self.word()
        return hi << 16 | self.word()

    def ext_addr(self):
        return self.base + (self.pos - self.i)


def _xn(ext):
    if ext & 0x0700:
        raise _Bad
    return f"{'A' if ext & 0x8000 else 'D'}{(ext >> 12) & 7}.{'L' if ext & 0x800 else 'W'}"


def _imm(r, size):
    if size == "B":
        return f"#${r.word() & 0xFF:02X}"
    if size == "W":
        return f"#${r.word():04X}"
    return f"#${r.long():08X}"


def _ea(r, mode, reg, size, allowed, role):
    key = mode if mode != 7 else 70 + reg
    if key not in allowed:
        raise _Bad
    if mode == 0:
        return f"D{reg}"
    if mode == 1:
        return f"A{reg}"
    if mode == 2:
        return f"(A{reg})"
    if mode == 3:
        return f"(A{reg})+"
    if mode == 4:
        return f"-(A{reg})"
    if mode == 5:
        return f"{_sd(_s16(r.word()))}(A{reg})"
    if mode == 6:
        ext = r.word()
        return f"{_sd(_s8(ext & 0xFF))}(A{reg},{_xn(ext)})"
    if reg == 0:
        v = _s16(r.word()) & 0xFFFFFFFF
        r.refs.append((v & 0xFFFFFF, KIND[role]))
        return f"(${v:08X}).w"
    if reg == 1:
        v = r.long()
        r.refs.append((v & 0xFFFFFF, KIND[role]))
        return f"(${v:08X}).l"
    if reg == 2:
        at = r.ext_addr()
        return f"${(at + _s16(r.word())) & 0xFFFFFF:06X}(PC)"
    if reg == 3:
        at = r.ext_addr()
        ext = r.word()
        return f"${(at + _s8(ext & 0xFF)) & 0xFFFFFF:06X}(PC,{_xn(ext)})"
    if reg == 4:
        return _imm(r, size)
    raise _Bad


def _op_ea(r, op, size, allowed, role):
    return _ea(r, (op >> 3) & 7, op & 7, size, allowed, role)


def _reglist(mask, reverse):
    regs = [f"{'D' if n < 8 else 'A'}{n % 8}" for n in range(16)]
    on = [(15 - b if reverse else b) for b in range(16) if mask >> b & 1]
    out = []
    for cls in ("D", "A"):
        idx = sorted(n % 8 for n in on if (n < 8) == (cls == "D"))
        i = 0
        while i < len(idx):
            j = i
            while j + 1 < len(idx) and idx[j + 1] == idx[j] + 1:
                j += 1
            out.append(f"{cls}{idx[i]}" if i == j else f"{cls}{idx[i]}-{cls}{idx[j]}")
            i = j + 1
    del regs
    return "/".join(out)


def _g0(op, r):
    mode, reg = (op >> 3) & 7, (op >> 9) & 7
    if op & 0x100:
        if mode == 1:
            raise _Bad                                   # MOVEP
        name = BITOPS[(op >> 6) & 3]
        ea = _op_ea(r, op, "B", DATA if name == "BTST" else DATA_ALT, "src" if name == "BTST" else "rmw")
        return f"{name} D{reg},{ea}"
    hi = op & 0xFF00
    if hi == 0x0800:
        name = BITOPS[(op >> 6) & 3]
        n = r.word() & 0xFF
        ea = _op_ea(r, op, "B", DATA if name == "BTST" else DATA_ALT, "src" if name == "BTST" else "rmw")
        return f"{name} #{n},{ea}"
    table = {0x0000: "ORI", 0x0200: "ANDI", 0x0400: "SUBI", 0x0600: "ADDI", 0x0A00: "EORI", 0x0C00: "CMPI"}
    if hi not in table:
        raise _Bad
    name = table[hi]
    if op in (0x003C, 0x023C, 0x0A3C):
        return f"{name} #${r.word() & 0xFF:02X},CCR"
    if op in (0x007C, 0x027C, 0x0A7C):
        return f"{name} #${r.word():04X},SR"
    if (op >> 6) & 3 == 3:
        raise _Bad
    size = "BWL"[(op >> 6) & 3]
    imm = _imm(r, size)
    ea = _op_ea(r, op, size, DATA_ALT, "src" if name == "CMPI" else "rmw")
    return f"{name}.{size} {imm},{ea}"


def _move(op, r):
    size = {1: "B", 3: "W", 2: "L"}[op >> 12]
    smode, sreg, dmode, dreg = (op >> 3) & 7, op & 7, (op >> 6) & 7, (op >> 9) & 7
    if size == "B" and smode == 1:
        raise _Bad
    src = _ea(r, smode, sreg, size, ALL, "src")
    if dmode == 1:
        if size == "B":
            raise _Bad
        return f"MOVEA.{size} {src},A{dreg}"
    return f"MOVE.{size} {src},{_ea(r, dmode, dreg, size, DATA_ALT, 'dst')}"


def _g4(op, r):
    reg, rg = (op >> 9) & 7, op & 7
    fixed = {0x4E75: "RTS", 0x4E73: "RTE", 0x4E71: "NOP", 0x4E77: "RTR", 0x4E76: "TRAPV", 0x4E70: "RESET",
             0x4AFC: "ILLEGAL"}
    if op in fixed:
        return fixed[op]
    if op == 0x4E72:
        return f"STOP #${r.word():04X}"
    if 0x4E40 <= op <= 0x4E4F:
        return f"TRAP #{op & 15}"
    if 0x4E50 <= op <= 0x4E57:
        return f"LINK A{rg},#{_sd(_s16(r.word()))}"
    if 0x4E58 <= op <= 0x4E5F:
        return f"UNLK A{rg}"
    if 0x4E60 <= op <= 0x4E67:
        return f"MOVE A{rg},USP"
    if 0x4E68 <= op <= 0x4E6F:
        return f"MOVE USP,A{rg}"
    if op & 0xFFC0 in (0x4E80, 0x4EC0):
        return f"{'JSR' if op & 0x40 == 0 else 'JMP'} {_op_ea(r, op, 'L', CONTROL, 'jump')}"
    if op & 0xF1C0 == 0x41C0:
        return f"LEA {_op_ea(r, op, 'L', CONTROL, 'addr')},A{reg}"
    if op & 0xFFF8 == 0x4880:
        return f"EXT.W D{rg}"
    if op & 0xFFF8 == 0x48C0:
        return f"EXT.L D{rg}"
    if op & 0xFFF8 == 0x4840:
        return f"SWAP D{rg}"
    if op & 0xFFC0 == 0x4840:
        return f"PEA {_op_ea(r, op, 'L', CONTROL, 'addr')}"
    if op & 0xFB80 == 0x4880:
        size = "L" if op & 0x40 else "W"
        mask = r.word()
        mode = (op >> 3) & 7
        if op & 0x0400:                                  # memory to registers
            ea = _op_ea(r, op, size, CONTROL | {3}, "src")
            return f"MOVEM.{size} {ea},{_reglist(mask, False)}"
        ea = _op_ea(r, op, size, (CONTROL - {72, 73}) | {4}, "dst")
        return f"MOVEM.{size} {_reglist(mask, mode == 4)},{ea}"
    names = {0x4000: "NEGX", 0x4200: "CLR", 0x4400: "NEG", 0x4600: "NOT", 0x4A00: "TST"}
    hi = op & 0xFF00
    if hi in names:
        sz = (op >> 6) & 3
        if sz == 3:
            specials = {0x40C0: ("MOVE SR,", DATA_ALT), 0x44C0: ("MOVE ", DATA), 0x46C0: ("MOVE ", DATA)}
            if op & 0xFFC0 not in specials:
                raise _Bad
            ea = _op_ea(r, op, "W", specials[op & 0xFFC0][1], "src" if op & 0xFFC0 != 0x40C0 else "dst")
            return f"MOVE SR,{ea}" if op & 0xFFC0 == 0x40C0 else f"MOVE {ea},{'CCR' if op & 0xFFC0 == 0x44C0 else 'SR'}"
        size = "BWL"[sz]
        role = "src" if hi == 0x4A00 else "dst" if hi == 0x4200 else "rmw"
        return f"{names[hi]}.{size} {_op_ea(r, op, size, DATA_ALT, role)}"
    raise _Bad


def _g5(op, r):
    cond, sz, mode, rg = (op >> 8) & 15, (op >> 6) & 3, (op >> 3) & 7, op & 7
    if sz == 3:
        if mode == 1:
            at = r.ext_addr()
            target = (at + _s16(r.word())) & 0xFFFFFF
            name = "DBRA" if cond == 1 else "DB" + COND[cond]
            return f"{name} D{rg},${target:06X}"
        return f"S{COND[cond]} {_op_ea(r, op, 'B', DATA_ALT, 'dst')}"
    if mode == 1 and sz == 0:
        raise _Bad
    name = "SUBQ" if op & 0x100 else "ADDQ"
    size = "BWL"[sz]
    return f"{name}.{size} #{(op >> 9) & 7 or 8},{_op_ea(r, op, size, ALT, 'rmw')}"


def _branch(op, r):
    cond, disp = (op >> 8) & 15, op & 0xFF
    if disp == 0xFF:
        raise _Bad
    at = r.ext_addr()
    if disp == 0:
        target, suffix = at + _s16(r.word()), "W"
    else:
        target, suffix = at + _s8(disp), "S"
    name = "BRA" if cond == 0 else "BSR" if cond == 1 else "B" + COND[cond]
    return f"{name}.{suffix} ${target & 0xFFFFFF:06X}"


def _alu(op, r, name, name_opm3, name_opm7):
    reg, opm, mode = (op >> 9) & 7, (op >> 6) & 7, (op >> 3) & 7
    if opm in (0, 1, 2):
        size = "BWL"[opm]
        return f"{name}.{size} {_op_ea(r, op, size, DATA, 'src')},D{reg}"
    if opm in (4, 5, 6):
        if mode in (0, 1):
            raise _Bad
        size = "BWL"[opm - 4]
        return f"{name}.{size} D{reg},{_op_ea(r, op, size, MEM_ALT, 'rmw')}"
    return f"{name_opm7 if opm == 7 else name_opm3}.W {_op_ea(r, op, 'W', DATA, 'src')},D{reg}"


def _addsub(op, r, name):
    reg, opm, mode = (op >> 9) & 7, (op >> 6) & 7, (op >> 3) & 7
    if opm in (0, 1, 2):
        size = "BWL"[opm]
        if size == "B" and mode == 1:
            raise _Bad
        return f"{name}.{size} {_op_ea(r, op, size, ALL, 'src')},D{reg}"
    if opm in (4, 5, 6):
        if mode in (0, 1):
            raise _Bad
        size = "BWL"[opm - 4]
        return f"{name}.{size} D{reg},{_op_ea(r, op, size, MEM_ALT, 'rmw')}"
    size = "W" if opm == 3 else "L"
    return f"{name}A.{size} {_op_ea(r, op, size, ALL, 'src')},A{reg}"


def _cmpeor(op, r):
    reg, opm, mode = (op >> 9) & 7, (op >> 6) & 7, (op >> 3) & 7
    if opm in (0, 1, 2):
        size = "BWL"[opm]
        if size == "B" and mode == 1:
            raise _Bad
        return f"CMP.{size} {_op_ea(r, op, size, ALL, 'src')},D{reg}"
    if opm in (3, 7):
        size = "W" if opm == 3 else "L"
        return f"CMPA.{size} {_op_ea(r, op, size, ALL, 'src')},A{reg}"
    if mode == 1:
        raise _Bad                                       # CMPM
    size = "BWL"[opm - 4]
    return f"EOR.{size} D{reg},{_op_ea(r, op, size, DATA_ALT, 'rmw')}"


def _shift(op, r):
    sz, rg = (op >> 6) & 3, op & 7
    left = "L" if op & 0x100 else "R"
    if sz == 3:
        if op & 0x0800:
            raise _Bad
        return f"{SHIFTS[(op >> 9) & 3]}{left}.W {_op_ea(r, op, 'W', MEM_ALT, 'rmw')}"
    name = SHIFTS[(op >> 3) & 3] + left
    count = (op >> 9) & 7
    src = f"D{count}" if op & 0x20 else f"#{count or 8}"
    return f"{name}.{'BWL'[sz]} {src},D{rg}"


def _insn(op, r):
    g, reg = op >> 12, (op >> 9) & 7
    if g == 0:
        return _g0(op, r)
    if g in (1, 2, 3):
        return _move(op, r)
    if g == 4:
        return _g4(op, r)
    if g == 5:
        return _g5(op, r)
    if g == 6:
        return _branch(op, r)
    if g == 7:
        if op & 0x100:
            raise _Bad
        return f"MOVEQ #${op & 0xFF:02X},D{reg}"
    if g == 8:
        return _alu(op, r, "OR", "DIVU", "DIVS")
    if g == 9:
        return _addsub(op, r, "SUB")
    if g == 0xB:
        return _cmpeor(op, r)
    if g == 0xC:
        return _alu(op, r, "AND", "MULU", "MULS")
    if g == 0xD:
        return _addsub(op, r, "ADD")
    if g == 0xE:
        return _shift(op, r)
    raise _Bad


def _decode(data: bytes, i: int, addr: int):
    """(text, size in bytes, absolute refs, decoded?) for the instruction at index i; None past the end."""
    if i + 2 > len(data):
        return None
    op = int.from_bytes(data[i:i + 2], "big")
    r = _Reader(data, i, addr)
    try:
        text = _insn(op, r)
    except (_Bad, KeyError):
        return f"dc.w ${op:04X}", 2, [], False
    return text, r.pos - i, r.refs, True


def locate(data: bytes, begin: int, offset: int) -> tuple:
    """Linear sweep from index `begin` to the instruction containing `offset`: (start, uncertain).

    `uncertain` is True when the sweep passed an undecoded word, because then the boundaries may be off."""
    i, uncertain = begin & ~1, False
    while True:
        got = _decode(data, i, i)
        if got is None:
            return offset & ~1, True
        uncertain = uncertain or not got[3]
        if i + got[1] > offset:
            return i, uncertain
        i += got[1]


def disassemble(data: bytes, start_addr: int, count: int) -> list:
    """Decode up to `count` items from `data`, whose first byte sits at CPU address `start_addr`."""
    out, i = [], 0
    while len(out) < count and i < len(data):
        got = _decode(data, i, start_addr + i)
        if got is None:
            out.append(Insn(start_addr + i, data[i:i + 1], f".byte ${data[i]:02X}", False))
            i += 1
            continue
        text, size, _, official = got
        out.append(Insn(start_addr + i, bytes(data[i:i + size]), text, official))
        i += size
    return out


def xrefs(info: RomInfo, data: bytes, target: int) -> list:
    """Every word-aligned position whose decoded instruction uses the absolute address `target` (24-bit compare).

    Decodes at every even offset, so data that looks like code can produce false hits."""
    want = target & 0xFFFFFF
    hits = []
    for off in range(0, min(info.details["rom_size"], ROM_LIMIT) - 1, 2):
        got = _decode(data, off, off)
        if got is None or not got[3]:
            continue
        for value, kind in got[2]:
            if value == want:
                hits.append(Hit(off, kind, off))
                break
    return hits

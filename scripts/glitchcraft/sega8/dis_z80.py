"""Z80 (Master System / Game Gear CPU) disassembler and cross-references. The opcode map is regular, so it is built
from the bit fields of the opcode instead of a 1000-entry table. Prefixes: CB (rotates, BIT/RES/SET), ED (extended),
DD/FD (IX/IY replace HL). Undocumented forms are decoded and marked not "official": SLL, IXH/IXL/IYH/IYL, the
DDCB/FDCB register-copy forms, the ED aliases, and a DD/FD prefix that does nothing (shown as a 1-byte `NOP ; DD`;
the next byte is then decoded on its own). Own implementation; opcode facts per the Zilog Z80 manual and
Sean Young's "The Undocumented Z80 Documented"."""
from glitchcraft.core import Hit, Insn, RomInfo

ILLEGAL: set = set()   # every Z80 byte decodes to something; kept so the interface matches dis_sm83
_R8 = ["B", "C", "D", "E", "H", "L", "(HL)", "A"]
_RR = ["BC", "DE", "HL", "SP"]
_RR_PUSH = ["BC", "DE", "HL", "AF"]
_CC = ["NZ", "Z", "NC", "C", "PO", "PE", "P", "M"]
_ALU = ["ADD A,", "ADC A,", "SUB ", "SBC A,", "AND ", "XOR ", "OR ", "CP "]
_ROT = ["RLC", "RRC", "RL", "RR", "SLA", "SRA", "SLL", "SRL"]
_ACC = ["RLCA", "RRCA", "RLA", "RRA", "DAA", "CPL", "SCF", "CCF"]
_BITOP = ("BIT", "RES", "SET")
_BLOCK = {0xA0: "LDI", 0xA1: "CPI", 0xA2: "INI", 0xA3: "OUTI", 0xA8: "LDD", 0xA9: "CPD", 0xAA: "IND", 0xAB: "OUTD",
          0xB0: "LDIR", 0xB1: "CPIR", 0xB2: "INIR", 0xB3: "OTIR", 0xB8: "LDDR", 0xB9: "CPDR", 0xBA: "INDR",
          0xBB: "OTDR"}

_CONDITIONAL = {"JP", "JR", "CALL", "RET"}
FLOW_MNEMONICS = {"JP", "JR", "CALL", "RET", "RETI", "RETN", "RST", "DJNZ", "ILLEGAL", "JPcc", "JRcc", "CALLcc", "RETcc"}
ROUTINE_END = {"JP", "JR", "RET", "RETI", "RETN"}   # unconditional only; DJNZ, CALL and RST fall through

_NOHL = object()   # marker: the opcode does not use HL, so a DD/FD in front of it is only a 1-byte NOP


def mnemonic(text: str) -> str:
    """Opcode name, with a `cc` suffix when the instruction is conditional (so `RET NZ` is not a routine end)."""
    head, _, rest = text.partition(" ")
    if head in _CONDITIONAL and rest.split(",")[0] in _CC and ("," in rest or head == "RET"):
        return head + "cc"
    return head


def _hex16(v):
    return f"${v:04X}"


def _sgn(b):
    return b - 256 if b > 127 else b


def _disp(ix, d):
    s = _sgn(d)
    return f"({ix}{'+' if s >= 0 else '-'}${abs(s):02X})"


def _plain(data, i, addr, ix):
    """Decode the non-prefix opcode at data[i]. With `ix` ("IX"/"IY") HL is replaced; the result is then
    (text, size, refs, official) with size counted from the opcode, `_NOHL` when HL is not involved, or None when
    truncated. Without `ix`, only prefix-free opcodes (CB/ED/DD/FD are handled by the caller)."""
    op = data[i]
    n = len(data) - i   # bytes available from the opcode

    def b1():
        return data[i + 1]

    def w2():
        return data[i + 1] | data[i + 2] << 8

    hl = ix or "HL"
    rr = [_RR[0], _RR[1], hl, _RR[3]]
    rr_push = [_RR_PUSH[0], _RR_PUSH[1], hl, _RR_PUSH[3]]
    block, lo = op >> 6, op & 7

    if ix:
        half = {4: ix + "H", 5: ix + "L"}
        dst, src = (op >> 3) & 7, lo
        if block == 1 and op != 0x76:
            if 6 in (dst, src):
                if n < 2:
                    return None
                d, s = _disp(ix, b1()), None
                other = _R8[src if dst == 6 else dst]
                return (f"LD {d},{other}" if dst == 6 else f"LD {other},{d}"), 2, [], True
            if {dst, src} & {4, 5}:
                return f"LD {half.get(dst, _R8[dst])},{half.get(src, _R8[src])}", 1, [], False
            return _NOHL
        if block == 2:
            if src == 6:
                return (f"{_ALU[dst]}{_disp(ix, b1())}", 2, [], True) if n >= 2 else None
            if src in (4, 5):
                return f"{_ALU[dst]}{half[src]}", 1, [], False
            return _NOHL
        if block == 0:
            if lo in (4, 5):
                name = "INC " if lo == 4 else "DEC "
                if dst == 6:
                    return (name + _disp(ix, b1()), 2, [], True) if n >= 2 else None
                if dst in (4, 5):
                    return name + half[dst], 1, [], False
                return _NOHL
            if lo == 6:
                if dst == 6:
                    return (f"LD {_disp(ix, b1())},${data[i + 2]:02X}", 3, [], True) if n >= 3 else None
                if dst in (4, 5):
                    return (f"LD {half[dst]},${b1():02X}", 2, [], False) if n >= 2 else None
                return _NOHL
            if op not in (0x09, 0x19, 0x29, 0x39, 0x21, 0x22, 0x2A, 0x23, 0x2B):
                return _NOHL
        elif op not in (0xE1, 0xE3, 0xE5, 0xE9, 0xF9):
            return _NOHL

    if block == 1:
        return ("HALT", 1, [], True) if op == 0x76 else (f"LD {_R8[(op >> 3) & 7]},{_R8[lo]}", 1, [], True)
    if block == 2:
        return f"{_ALU[(op >> 3) & 7]}{_R8[lo]}", 1, [], True
    if block == 0:
        if op == 0x00:
            return "NOP", 1, [], True
        if op == 0x08:
            return "EX AF,AF'", 1, [], True
        if op in (0x10, 0x18, 0x20, 0x28, 0x30, 0x38):
            if n < 2:
                return None
            target = (addr + 2 + _sgn(b1())) & 0xFFFF
            head = "DJNZ " if op == 0x10 else "JR " if op == 0x18 else f"JR {_CC[(op >> 3) & 3]},"
            return f"{head}{_hex16(target)}", 2, [(target, "jump")], True
        nib = op & 0xF
        if nib == 1:
            return (f"LD {rr[op >> 4]},{_hex16(w2())}", 3, [(w2(), "use")], True) if n >= 3 else None
        if nib == 9:
            return f"ADD {hl},{rr[op >> 4]}", 1, [], True
        if nib == 3:
            return f"INC {rr[op >> 4]}", 1, [], True
        if nib == 0xB:
            return f"DEC {rr[op >> 4]}", 1, [], True
        if op == 0x02:
            return "LD (BC),A", 1, [], True
        if op == 0x12:
            return "LD (DE),A", 1, [], True
        if op == 0x0A:
            return "LD A,(BC)", 1, [], True
        if op == 0x1A:
            return "LD A,(DE)", 1, [], True
        if op in (0x22, 0x2A, 0x32, 0x3A):
            if n < 3:
                return None
            a = _hex16(w2())
            if op == 0x22:
                return f"LD ({a}),{hl}", 3, [(w2(), "write")], True
            if op == 0x32:
                return f"LD ({a}),A", 3, [(w2(), "write")], True
            return (f"LD {hl},({a})" if op == 0x2A else f"LD A,({a})"), 3, [(w2(), "read")], True
        if lo in (4, 5):
            return ("INC " if lo == 4 else "DEC ") + _R8[(op >> 3) & 7], 1, [], True
        if lo == 6:
            return (f"LD {_R8[(op >> 3) & 7]},${b1():02X}", 2, [], True) if n >= 2 else None
        return _ACC[(op >> 3) & 7], 1, [], True   # lo == 7
    # block 3
    if lo == 7:
        return f"RST ${op & 0x38:02X}", 1, [(op & 0x38, "call")], True
    if lo == 0:
        return f"RET {_CC[(op >> 3) & 7]}", 1, [], True
    if lo == 1:
        if op & 0xF == 1:
            return f"POP {rr_push[(op >> 4) & 3]}", 1, [], True
        return {0xC9: "RET", 0xD9: "EXX", 0xE9: f"JP ({hl})", 0xF9: f"LD SP,{hl}"}[op], 1, [], True
    if lo == 2:
        if n < 3:
            return None
        return f"JP {_CC[(op >> 3) & 7]},{_hex16(w2())}", 3, [(w2(), "jump")], True
    if lo == 3:
        if op == 0xC3:
            return (f"JP {_hex16(w2())}", 3, [(w2(), "jump")], True) if n >= 3 else None
        if op == 0xD3:
            return (f"OUT (${b1():02X}),A", 2, [], True) if n >= 2 else None
        if op == 0xDB:
            return (f"IN A,(${b1():02X})", 2, [], True) if n >= 2 else None
        return {0xE3: f"EX (SP),{hl}", 0xEB: "EX DE,HL", 0xF3: "DI", 0xFB: "EI"}[op], 1, [], True
    if lo == 4:
        if n < 3:
            return None
        return f"CALL {_CC[(op >> 3) & 7]},{_hex16(w2())}", 3, [(w2(), "call")], True
    if lo == 5:
        if op & 0xF == 5:
            return f"PUSH {rr_push[(op >> 4) & 3]}", 1, [], True
        return (f"CALL {_hex16(w2())}", 3, [(w2(), "call")], True) if n >= 3 else None
    # lo == 6: ALU A,n
    return (f"{_ALU[(op >> 3) & 7]}${b1():02X}", 2, [], True) if n >= 2 else None


def _cb(c):
    r, grp, bit = _R8[c & 7], c >> 6, (c >> 3) & 7
    text = f"{_ROT[bit]} {r}" if grp == 0 else f"{_BITOP[grp - 1]} {bit},{r}"
    return text, 2, [], not (grp == 0 and bit == 6)


def _ed(data, i):
    if i + 2 > len(data):
        return None
    op = data[i + 1]
    n = len(data) - i
    pair = _RR[(op >> 4) & 3]
    if op & 0xC7 == 0x40:    # IN r,(C)
        r = (op >> 3) & 7
        return f"IN {'F' if r == 6 else _R8[r]},(C)", 2, [], r != 6
    if op & 0xC7 == 0x41:    # OUT (C),r
        r = (op >> 3) & 7
        return f"OUT (C),{'0' if r == 6 else _R8[r]}", 2, [], r != 6
    if op & 0xCF == 0x42:
        return f"SBC HL,{pair}", 2, [], True
    if op & 0xCF == 0x4A:
        return f"ADC HL,{pair}", 2, [], True
    if op & 0xCF in (0x43, 0x4B):
        if n < 4:
            return None
        v = data[i + 2] | data[i + 3] << 8
        if op & 0xCF == 0x43:
            return f"LD ({_hex16(v)}),{pair}", 4, [(v, "write")], op != 0x63   # ED 63/6B: HL duplicates of 22/2A
        return f"LD {pair},({_hex16(v)})", 4, [(v, "read")], op != 0x6B
    if op & 0xC7 == 0x44:
        return "NEG", 2, [], op == 0x44
    if op & 0xC7 == 0x45:
        return ("RETI" if op == 0x4D else "RETN"), 2, [], op in (0x45, 0x4D)
    if op & 0xC7 == 0x46:
        mode = {0: "0", 1: "0", 2: "1", 3: "2"}[(op >> 3) & 3]
        return f"IM {mode}", 2, [], op in (0x46, 0x56, 0x5E)
    fixed = {0x47: "LD I,A", 0x4F: "LD R,A", 0x57: "LD A,I", 0x5F: "LD A,R", 0x67: "RRD", 0x6F: "RLD"}
    if op in fixed:
        return fixed[op], 2, [], True
    if op in _BLOCK:
        return _BLOCK[op], 2, [], True
    return "NOP", 2, [], False   # undefined ED opcodes: two-byte NOPs


def _indexed(data, i):
    if i + 2 > len(data):
        return None
    pre = data[i]
    ix = "IX" if pre == 0xDD else "IY"
    if data[i + 1] == 0xCB:
        if i + 4 > len(data):
            return None
        d, c = data[i + 2], data[i + 3]
        r, grp, bit = c & 7, c >> 6, (c >> 3) & 7
        mem = _disp(ix, d)
        if grp == 0:
            text = f"{_ROT[bit]} {mem}" + ("" if r == 6 else f",{_R8[r]}")
            official = r == 6 and bit != 6
        elif grp == 1:
            text, official = f"BIT {bit},{mem}", r == 6
        else:
            text = f"{_BITOP[grp - 1]} {bit},{mem}" + ("" if r == 6 else f",{_R8[r]}")
            official = r == 6
        return text, 4, [], official
    got = _plain(data, i + 1, 0, ix)
    if got is None:
        return None
    if got is _NOHL:
        return f"NOP ; {pre:02X}", 1, [], False
    text, size, refs, official = got
    return text, size + 1, refs, official


def _decode(data: bytes, i: int, addr: int):
    """(text, size, refs, official) for the instruction at index i, or None when it runs past the end of `data`.

    refs is a list of (value, kind) operands used by `xrefs`. I/O ports are not memory addresses and give no refs."""
    op = data[i]
    if op == 0xCB:
        return _cb(data[i + 1]) if i + 2 <= len(data) else None
    if op == 0xED:
        return _ed(data, i)
    if op in (0xDD, 0xFD):
        return _indexed(data, i)
    return _plain(data, i, addr, None)


def locate(data: bytes, begin: int, offset: int) -> tuple:
    """Linear sweep from index `begin` to the instruction containing `offset`: (start, uncertain).

    `uncertain` is True when the sweep passed an undocumented decode, because then the stretch is probably data."""
    i, uncertain, prev = max(0, begin), False, None
    while True:
        got = _decode(data, i, i)
        if got is None:
            return offset, True
        uncertain = uncertain or not got[3]
        if i + got[1] > offset:
            if (offset == i and prev is not None and data[prev] in (0xDD, 0xFD) and prev + 1 == i
                    and "; " in _decode(data, prev, prev)[0]):
                return prev, uncertain   # patching the opcode after a useless prefix can make the prefix apply
            return i, uncertain
        prev = i
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
    """Every ROM byte position whose decoded instruction uses the 16-bit address `target`.

    Decodes at every byte, so data that looks like code can produce false hits. Offsets below $4000 and every
    offset of a ROM of 48 KB or less have a fixed CPU address; others sit in a switchable bank and get `cpu` None."""
    hits = []
    flat = info.details["banks"] <= 3
    for off in range(0, info.details["rom_size"]):
        got = _decode(data, off, off if flat or off < 0x4000 else 0x4000 + (off & 0x3FFF))
        if got is None or not got[3]:
            continue
        if not flat and off >= 0x4000 and got[0].startswith(("JR", "DJNZ")):
            continue   # which slot a banked byte runs in is unknown, so its relative target is too
        if not flat and off // 0x4000 != (off + got[1] - 1) // 0x4000:
            continue   # an operand would come from whichever bank is mapped next, not from the next file bytes
        for value, kind in got[2]:
            if value == target:
                hits.append(Hit(off if off < 0x4000 or flat else None, kind, off))
                break
    return hits

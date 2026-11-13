"""SM83 (Game Boy CPU) disassembler and cross-references. The opcode map is regular, so it is built from the
bit fields of the opcode (block = top two bits) instead of a 512-entry table; the eleven unused opcodes are
reported as ILLEGAL and are not "official". Own implementation; opcode facts per Pan Docs / gbdev optables."""
from glitchcraft.core import Hit, Insn, RomInfo
from glitchcraft.gb import rom as gbrom

ILLEGAL = {0xD3, 0xDB, 0xDD, 0xE3, 0xE4, 0xEB, 0xEC, 0xED, 0xF4, 0xFC, 0xFD}
_R8 = ["B", "C", "D", "E", "H", "L", "(HL)", "A"]
_RR = ["BC", "DE", "HL", "SP"]
_RR_PUSH = ["BC", "DE", "HL", "AF"]
_CC = ["NZ", "Z", "NC", "C"]
_ALU = ["ADD A,", "ADC A,", "SUB ", "SBC A,", "AND ", "XOR ", "OR ", "CP "]
_ROT = ["RLC", "RRC", "RL", "RR", "SLA", "SRA", "SWAP", "SRL"]
_ACC = ["RLCA", "RRCA", "RLA", "RRA", "DAA", "CPL", "SCF", "CCF"]
_INDIRECT = {0x02: "LD (BC),A", 0x12: "LD (DE),A", 0x22: "LD (HL+),A", 0x32: "LD (HL-),A",
             0x0A: "LD A,(BC)", 0x1A: "LD A,(DE)", 0x2A: "LD A,(HL+)", 0x3A: "LD A,(HL-)"}

_CONDITIONAL = {"JP", "JR", "CALL", "RET"}
FLOW_MNEMONICS = {"JP", "JR", "CALL", "RET", "RETI", "RST", "ILLEGAL", "JPcc", "JRcc", "CALLcc", "RETcc"}
ROUTINE_END = {"JP", "JR", "RET", "RETI", "ILLEGAL"}   # unconditional only; RST and CALL return


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


def _decode(data: bytes, i: int, addr: int):
    """(text, size, refs, official) for the instruction at index i, or None when it runs past the end of `data`.

    refs is a list of (value, kind) operands used by `xrefs`."""
    op = data[i]

    def need(n):
        return i + n <= len(data)

    def b1():
        return data[i + 1]

    def w2():
        return data[i + 1] | data[i + 2] << 8

    if op in ILLEGAL:
        return f"ILLEGAL ${op:02X}", 1, [], False
    if op == 0xCB:
        if not need(2):
            return None
        c = b1()
        r, grp, bit = _R8[c & 7], c >> 6, (c >> 3) & 7
        text = f"{_ROT[bit]} {r}" if grp == 0 else f"{('BIT', 'RES', 'SET')[grp - 1]} {bit},{r}"
        return text, 2, [], True
    block = op >> 6
    if block == 1:
        return ("HALT", 1, [], True) if op == 0x76 else (f"LD {_R8[(op >> 3) & 7]},{_R8[op & 7]}", 1, [], True)
    if block == 2:
        return f"{_ALU[(op >> 3) & 7]}{_R8[op & 7]}", 1, [], True
    lo = op & 7
    if block == 0:
        if op == 0x00:
            return "NOP", 1, [], True
        if op == 0x10:
            return ("STOP", 2, [], True) if need(2) else None
        if op == 0x08:
            return (f"LD ({_hex16(w2())}),SP", 3, [(w2(), "write")], True) if need(3) else None
        if op in (0x18, 0x20, 0x28, 0x30, 0x38):
            if not need(2):
                return None
            target = (addr + 2 + _sgn(b1())) & 0xFFFF
            cond = "" if op == 0x18 else _CC[(op >> 3) & 3] + ","
            return f"JR {cond}{_hex16(target)}", 2, [(target, "jump")], True
        nib = op & 0xF
        if nib == 1:
            return (f"LD {_RR[op >> 4]},{_hex16(w2())}", 3, [(w2(), "use")], True) if need(3) else None
        if nib == 9:
            return f"ADD HL,{_RR[op >> 4]}", 1, [], True
        if nib == 3:
            return f"INC {_RR[op >> 4]}", 1, [], True
        if nib == 0xB:
            return f"DEC {_RR[op >> 4]}", 1, [], True
        if nib in (2, 0xA):
            return _INDIRECT[op], 1, [], True
        if lo in (4, 5):
            return ("INC " if lo == 4 else "DEC ") + _R8[(op >> 3) & 7], 1, [], True
        if lo == 6:
            return (f"LD {_R8[(op >> 3) & 7]},${b1():02X}", 2, [], True) if need(2) else None
        return _ACC[(op >> 3) & 7], 1, [], True   # nib 7 and 0xF
    # block 3
    if lo == 7:
        return f"RST ${op & 0x38:02X}", 1, [(op & 0x38, "call")], True
    if lo == 0:
        if op < 0xE0:
            return f"RET {_CC[(op >> 3) & 3]}", 1, [], True
        if op == 0xE0:
            return (f"LDH (${0xFF00 + b1():04X}),A", 2, [(0xFF00 + b1(), "write")], True) if need(2) else None
        if op == 0xF0:
            return (f"LDH A,(${0xFF00 + b1():04X})", 2, [(0xFF00 + b1(), "read")], True) if need(2) else None
        if not need(2):
            return None
        sign = _sgn(b1())
        s = f"{sign:+d}"
        return (f"ADD SP,{s}" if op == 0xE8 else f"LD HL,SP{s}"), 2, [], True
    if lo == 1:
        if op & 0xF == 1:
            return f"POP {_RR_PUSH[(op >> 4) & 3]}", 1, [], True
        return {0xC9: "RET", 0xD9: "RETI", 0xE9: "JP HL", 0xF9: "LD SP,HL"}[op], 1, [], True
    if lo == 2:
        if op < 0xE0:
            if not need(3):
                return None
            return f"JP {_CC[(op >> 3) & 3]},{_hex16(w2())}", 3, [(w2(), "jump")], True
        if op == 0xE2:
            return "LD (C),A", 1, [], True
        if op == 0xF2:
            return "LD A,(C)", 1, [], True
        if not need(3):
            return None
        if op == 0xEA:
            return f"LD ({_hex16(w2())}),A", 3, [(w2(), "write")], True
        return f"LD A,({_hex16(w2())})", 3, [(w2(), "read")], True
    if lo == 3:
        if op == 0xC3:
            return (f"JP {_hex16(w2())}", 3, [(w2(), "jump")], True) if need(3) else None
        return ("DI" if op == 0xF3 else "EI"), 1, [], True
    if lo == 4:
        if not need(3):
            return None
        return f"CALL {_CC[(op >> 3) & 3]},{_hex16(w2())}", 3, [(w2(), "call")], True
    if lo == 5:
        if op & 0xF == 5:
            return f"PUSH {_RR_PUSH[(op >> 4) & 3]}", 1, [], True
        return (f"CALL {_hex16(w2())}", 3, [(w2(), "call")], True) if need(3) else None
    # lo == 6: ALU A,d8
    return (f"{_ALU[(op >> 3) & 7]}${b1():02X}", 2, [], True) if need(2) else None


def locate(data: bytes, begin: int, offset: int) -> tuple:
    """Linear sweep from index `begin` to the instruction containing `offset`: (start, uncertain).

    `uncertain` is True when the sweep passed an illegal opcode, because then the stretch is probably data."""
    i, uncertain = max(0, begin), False
    while True:
        got = _decode(data, i, i)
        if got is None:
            return offset, True
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
    """Every ROM byte position whose decoded instruction uses the 16-bit address `target` (`LDH` counts for $FFxx).

    Decodes at every byte, so data that looks like code can produce false hits. Hits whose file offset has no
    single CPU address (switchable banks) are kept with `cpu` set to None."""
    hits = []
    banked = gbrom.bank_end(info, 0) is not None
    for off in range(0, info.details["rom_size"]):
        got = _decode(data, off, off if off < 0x4000 else 0x4000 + (off & 0x3FFF))
        if got is None or not got[3]:
            continue
        if banked and off // 0x4000 != (off + got[1] - 1) // 0x4000:
            continue   # an operand would come from whichever bank is mapped next, not from the next file bytes
        for value, kind in got[2]:
            if value == target:
                hits.append(Hit(gbrom.offset_to_cpu(info, off), kind, off))
                break
    return hits

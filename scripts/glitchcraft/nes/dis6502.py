"""6502 disassembler (official and unofficial NMOS opcodes) and absolute-operand cross-references."""
from glitchcraft.core import Hit, Insn, RomInfo
from glitchcraft.nes import rom as nesrom

SIZE = {"imp": 1, "acc": 1, "imm": 2, "zp": 2, "zpx": 2, "zpy": 2, "izx": 2, "izy": 2, "rel": 2,
        "abs": 3, "abx": 3, "aby": 3, "ind": 3}


def _build() -> list:
    t: list = [None] * 256

    def put(op, mn, mode, official=True):
        t[op] = (mn, mode, official)

    alu = ["ORA", "AND", "EOR", "ADC", "STA", "LDA", "CMP", "SBC"]
    m01 = ["izx", "zp", "imm", "abs", "izy", "zpx", "aby", "abx"]
    for a, mn in enumerate(alu):
        for b, mode in enumerate(m01):
            put(a << 5 | b << 2 | 1, mn, mode, not (mn == "STA" and mode == "imm"))
    put(0x89, "NOP", "imm", False)
    sh = ["ASL", "ROL", "LSR", "ROR", "STX", "LDX", "DEC", "INC"]
    m10 = ["imm", "zp", "acc", "abs", "kil", "zpx", "imp", "abx"]
    for a, mn in enumerate(sh):
        for b, mode in enumerate(m10):
            op = a << 5 | b << 2 | 2
            if mode == "kil":
                put(op, "KIL", "imp", False)
            elif mode == "imm":
                put(op, "LDX" if mn == "LDX" else "NOP", "imm", mn == "LDX") if mn in ("LDX",) or op in (0x82, 0xC2, 0xE2) else put(op, "KIL", "imp", False)
            else:
                m = {"acc": "acc", "imp": "imp"}.get(mode, mode)
                if mn in ("STX", "LDX") and mode in ("zpx", "abx"):
                    m = "zpy" if mode == "zpx" else "aby"
                put(op, mn, m)
    for op, mn in ((0x8A, "TXA"), (0xAA, "TAX"), (0xCA, "DEX"), (0xEA, "NOP")):
        put(op, mn, "imp", True)
    put(0x9A, "TXS", "imp"); put(0xBA, "TSX", "imp")
    put(0x9E, "SHX", "aby", False)
    for op in (0x1A, 0x3A, 0x5A, 0x7A, 0xDA, 0xFA):
        put(op, "NOP", "imp", False)
    cc0 = {0x00: ("BRK", "imp"), 0x20: ("JSR", "abs"), 0x40: ("RTI", "imp"), 0x60: ("RTS", "imp"),
           0xA0: ("LDY", "imm"), 0xC0: ("CPY", "imm"), 0xE0: ("CPX", "imm"),
           0x24: ("BIT", "zp"), 0x84: ("STY", "zp"), 0xA4: ("LDY", "zp"), 0xC4: ("CPY", "zp"), 0xE4: ("CPX", "zp"),
           0x08: ("PHP", "imp"), 0x28: ("PLP", "imp"), 0x48: ("PHA", "imp"), 0x68: ("PLA", "imp"),
           0x88: ("DEY", "imp"), 0xA8: ("TAY", "imp"), 0xC8: ("INY", "imp"), 0xE8: ("INX", "imp"),
           0x2C: ("BIT", "abs"), 0x4C: ("JMP", "abs"), 0x6C: ("JMP", "ind"), 0x8C: ("STY", "abs"),
           0xAC: ("LDY", "abs"), 0xCC: ("CPY", "abs"), 0xEC: ("CPX", "abs"),
           0x94: ("STY", "zpx"), 0xB4: ("LDY", "zpx"), 0xBC: ("LDY", "abx"),
           0x18: ("CLC", "imp"), 0x38: ("SEC", "imp"), 0x58: ("CLI", "imp"), 0x78: ("SEI", "imp"),
           0x98: ("TYA", "imp"), 0xB8: ("CLV", "imp"), 0xD8: ("CLD", "imp"), 0xF8: ("SED", "imp")}
    for op, (mn, mode) in cc0.items():
        put(op, mn, mode)
    for op, mn in ((0x10, "BPL"), (0x30, "BMI"), (0x50, "BVC"), (0x70, "BVS"),
                   (0x90, "BCC"), (0xB0, "BCS"), (0xD0, "BNE"), (0xF0, "BEQ")):
        put(op, mn, "rel")
    for op in (0x80,):
        put(op, "NOP", "imm", False)
    for op in (0x04, 0x44, 0x64):
        put(op, "NOP", "zp", False)
    for op in (0x14, 0x34, 0x54, 0x74, 0xD4, 0xF4):
        put(op, "NOP", "zpx", False)
    put(0x0C, "NOP", "abs", False)
    for op in (0x1C, 0x3C, 0x5C, 0x7C, 0xDC, 0xFC):
        put(op, "NOP", "abx", False)
    put(0x9C, "SHY", "abx", False)
    ill = ["SLO", "RLA", "SRE", "RRA", "SAX", "LAX", "DCP", "ISC"]
    m11 = ["izx", "zp", "imm", "abs", "izy", "zpx", "aby", "abx"]
    for a, mn in enumerate(ill):
        for b, mode in enumerate(m11):
            m = mode
            if mn in ("SAX", "LAX") and mode == "zpx":
                m = "zpy"
            if mn in ("SAX", "LAX") and mode == "abx":
                m = "aby"
            put(a << 5 | b << 2 | 3, mn, m, False)
    for op, mn in ((0x0B, "ANC"), (0x2B, "ANC"), (0x4B, "ALR"), (0x6B, "ARR"), (0x8B, "XAA"),
                   (0xAB, "LXA"), (0xCB, "AXS"), (0xEB, "SBC")):
        put(op, mn, "imm", False)
    put(0x93, "AHX", "izy", False); put(0x9F, "AHX", "aby", False); put(0x9B, "TAS", "aby", False)
    put(0xBB, "LAS", "aby", False); put(0xBF, "LAX", "aby", False)
    return t


OPCODES = _build()
assert all(e is not None for e in OPCODES)

_READ = {"LDA", "LDX", "LDY", "CMP", "CPX", "CPY", "BIT", "ADC", "SBC", "AND", "ORA", "EOR", "LAX", "NOP"}
_WRITE = {"STA", "STX", "STY", "SAX", "SHX", "SHY", "AHX", "TAS"}
_JUMP = {"JMP", "JSR"}


def _fmt(mn, mode, operand, addr):
    if mode in ("imp",):
        return mn
    if mode == "acc":
        return f"{mn} A"
    if mode == "imm":
        return f"{mn} #${operand:02X}"
    if mode == "rel":
        off = operand - 256 if operand > 127 else operand
        return f"{mn} ${(addr + 2 + off) & 0xFFFF:04X}"
    body = {"zp": f"${operand:02X}", "zpx": f"${operand:02X},X", "zpy": f"${operand:02X},Y",
            "izx": f"(${operand:02X},X)", "izy": f"(${operand:02X}),Y", "abs": f"${operand:04X}",
            "abx": f"${operand:04X},X", "aby": f"${operand:04X},Y", "ind": f"(${operand:04X})"}[mode]
    return f"{mn} {body}"


def disassemble(data: bytes, start_addr: int, count: int) -> list:
    """Decode up to `count` instructions from `data`, whose first byte sits at CPU address `start_addr`."""
    out, i = [], 0
    while len(out) < count and i < len(data):
        mn, mode, official = OPCODES[data[i]]
        size = SIZE[mode]
        if i + size > len(data):
            out.append(Insn(start_addr + i, data[i:i + 1], f".byte ${data[i]:02X}", False))
            i += 1
            continue
        raw = data[i:i + size]
        operand = int.from_bytes(raw[1:], "little")
        text = _fmt(mn, mode, operand, start_addr + i)
        out.append(Insn(start_addr + i, bytes(raw), text if official else "*" + text, official))
        i += size
    return out


def _kind(mn: str) -> str:
    if mn in _JUMP:
        return "jump"
    if mn in _WRITE:
        return "write"
    if mn in _READ:
        return "read"
    return "rmw"


def xrefs_detailed(info: RomInfo, data: bytes, target: int) -> list:
    """Every PRG byte position whose opcode takes an operand equal to `target`: absolute operands (plain and
    indexed, matched on the base address), plus zero-page operands (plain, indexed and pointer) when `target` is below $100.

    Scans byte by byte, so data that looks like code can produce false hits. Hits whose file offset has no
    single CPU address (switchable banks) are kept, with `cpu` set to None."""
    d = info.details
    start, end = d["prg_start"], d["prg_start"] + d["prg_banks"] * 0x4000
    lo, hi = target & 0xFF, target >> 8
    hits = []
    for off in range(start, end - 1):
        mn, mode, _ = OPCODES[data[off]]
        if mode in ("abs", "abx", "aby") and off + 2 < end and data[off + 1] == lo and data[off + 2] == hi:
            pass   # indexed forms match on their base address
        elif mode in ("zp", "zpx", "zpy", "izx", "izy") and target < 0x100 and data[off + 1] == lo:
            pass
        else:
            continue
        hits.append(Hit(nesrom.offset_to_cpu(info, off), _kind(mn), off))
    return hits


def xrefs(info: RomInfo, data: bytes, target: int) -> list:
    """`xrefs_detailed` reduced to (cpu_addr, kind) for hits that have a single CPU address."""
    return [(h.cpu, h.kind) for h in xrefs_detailed(info, data, target) if h.cpu is not None]

"""65816 disassembler with M/X width tracking, and cross-references to an absolute or long operand.

Immediate operands of accumulator and index instructions are 8 or 16 bits wide depending on the M and X flags.
`disassemble` tracks REP/SEP; when a width is unknown it decodes 8 bits and says so in the text."""
from glitchcraft.core import Hit, Insn, RomInfo
from glitchcraft.snes import rom as snesrom

_ROWS = """
BRK imm8|ORA dix|COP imm8|ORA sr|TSB dp|ORA dp|ASL dp|ORA dil|PHP imp|ORA immM|ASL acc|PHD imp|TSB abs|ORA abs|ASL abs|ORA long
BPL rel|ORA diy|ORA dpi|ORA sry|TRB dp|ORA dpx|ASL dpx|ORA dly|CLC imp|ORA aby|INC acc|TCS imp|TRB abs|ORA abx|ASL abx|ORA lgx
JSR abs|AND dix|JSL long|AND sr|BIT dp|AND dp|ROL dp|AND dil|PLP imp|AND immM|ROL acc|PLD imp|BIT abs|AND abs|ROL abs|AND long
BMI rel|AND diy|AND dpi|AND sry|BIT dpx|AND dpx|ROL dpx|AND dly|SEC imp|AND aby|DEC acc|TSC imp|BIT abx|AND abx|ROL abx|AND lgx
RTI imp|EOR dix|WDM imm8|EOR sr|MVP blk|EOR dp|LSR dp|EOR dil|PHA imp|EOR immM|LSR acc|PHK imp|JMP abs|EOR abs|LSR abs|EOR long
BVC rel|EOR diy|EOR dpi|EOR sry|MVN blk|EOR dpx|LSR dpx|EOR dly|CLI imp|EOR aby|PHY imp|TCD imp|JML long|EOR abx|LSR abx|EOR lgx
RTS imp|ADC dix|PER rll|ADC sr|STZ dp|ADC dp|ROR dp|ADC dil|PLA imp|ADC immM|ROR acc|RTL imp|JMP ind|ADC abs|ROR abs|ADC long
BVS rel|ADC diy|ADC dpi|ADC sry|STZ dpx|ADC dpx|ROR dpx|ADC dly|SEI imp|ADC aby|PLY imp|TDC imp|JMP iax|ADC abx|ROR abx|ADC lgx
BRA rel|STA dix|BRL rll|STA sr|STY dp|STA dp|STX dp|STA dil|DEY imp|BIT immM|TXA imp|PHB imp|STY abs|STA abs|STX abs|STA long
BCC rel|STA diy|STA dpi|STA sry|STY dpx|STA dpx|STX dpy|STA dly|TYA imp|STA aby|TXS imp|TXY imp|STZ abs|STA abx|STZ abx|STA lgx
LDY immX|LDA dix|LDX immX|LDA sr|LDY dp|LDA dp|LDX dp|LDA dil|TAY imp|LDA immM|TAX imp|PLB imp|LDY abs|LDA abs|LDX abs|LDA long
BCS rel|LDA diy|LDA dpi|LDA sry|LDY dpx|LDA dpx|LDX dpy|LDA dly|CLV imp|LDA aby|TSX imp|TYX imp|LDY abx|LDA abx|LDX aby|LDA lgx
CPY immX|CMP dix|REP imm8|CMP sr|CPY dp|CMP dp|DEC dp|CMP dil|INY imp|CMP immM|DEX imp|WAI imp|CPY abs|CMP abs|DEC abs|CMP long
BNE rel|CMP diy|CMP dpi|CMP sry|PEI dpi|CMP dpx|DEC dpx|CMP dly|CLD imp|CMP aby|PHX imp|STP imp|JML ail|CMP abx|DEC abx|CMP lgx
CPX immX|SBC dix|SEP imm8|SBC sr|CPX dp|SBC dp|INC dp|SBC dil|INX imp|SBC immM|NOP imp|XBA imp|CPX abs|SBC abs|INC abs|SBC long
BEQ rel|SBC diy|SBC dpi|SBC sry|PEA abs|SBC dpx|INC dpx|SBC dly|SED imp|SBC aby|PLX imp|XCE imp|JSR iax|SBC abx|INC abx|SBC lgx
"""
OPCODES = [tuple(cell.split()) for row in _ROWS.strip().splitlines() for cell in row.split("|")]
LEN = {"imp": 1, "acc": 1, "imm8": 2, "dp": 2, "dpx": 2, "dpy": 2, "dpi": 2, "dix": 2, "diy": 2, "dil": 2,
       "dly": 2, "sr": 2, "sry": 2, "rel": 2, "abs": 3, "abx": 3, "aby": 3, "ind": 3, "iax": 3, "ail": 3,
       "rll": 3, "blk": 3, "long": 4, "lgx": 4}
_FMT = {"dp": "${0:02X}", "dpx": "${0:02X},X", "dpy": "${0:02X},Y", "dpi": "(${0:02X})", "dix": "(${0:02X},X)",
        "diy": "(${0:02X}),Y", "dil": "[${0:02X}]", "dly": "[${0:02X}],Y", "sr": "${0:02X},S",
        "sry": "(${0:02X},S),Y", "abs": "${0:04X}", "abx": "${0:04X},X", "aby": "${0:04X},Y",
        "ind": "(${0:04X})", "iax": "(${0:04X},X)", "ail": "[${0:04X}]", "long": "${0:06X}", "lgx": "${0:06X},X"}
_READ = {"LDA", "LDX", "LDY", "CMP", "CPX", "CPY", "BIT", "ADC", "SBC", "AND", "ORA", "EOR"}
_WRITE = {"STA", "STX", "STY", "STZ"}
_JUMP = {"JMP", "JSR", "JML", "JSL"}
_RMW = {"INC", "DEC", "ASL", "LSR", "ROL", "ROR", "TSB", "TRB"}


def _width_size(mode: str, m, x):
    """(instruction size, width unknown?) for a mode given the tracked M and X flags (1 = 8-bit, 0 = 16-bit)."""
    if mode == "immM":
        return (3 if m == 0 else 2), m is None
    if mode == "immX":
        return (3 if x == 0 else 2), x is None
    return LEN[mode], False


def _track(mn: str, arg: int, m, x):
    if mn == "REP":
        return (0 if arg & 0x20 else m), (0 if arg & 0x10 else x)
    if mn == "SEP":
        return (1 if arg & 0x20 else m), (1 if arg & 0x10 else x)
    if mn in ("PLP", "XCE", "RTI"):
        return None, None
    return m, x


def locate(data: bytes, begin: int, offset: int, m: int | None = None, x: int | None = None) -> tuple:
    """Linear sweep from `begin` (an index into `data`) to the instruction containing index `offset`.

    Returns (start, m, x, uncertain): the instruction's start index, the M/X widths in effect before it, and
    whether the sweep crossed an immediate whose width it had to guess (so boundaries may be off)."""
    i, uncertain = begin, False
    while i <= offset:
        mn, mode = OPCODES[data[i]]
        size, unknown = _width_size(mode, m, x)
        uncertain = uncertain or unknown
        if i + size > offset:
            return i, m, x, uncertain
        arg = int.from_bytes(data[i + 1:i + size], "little")
        m, x = _track(mn, arg, m, x)
        i += size
    return offset, m, x, uncertain


def disassemble(data: bytes, start_addr: int, count: int, m: int | None = None, x: int | None = None) -> list:
    """Decode up to `count` instructions; `m`/`x` are the known accumulator/index width flags (1 = 8-bit)."""
    out, i = [], 0
    while len(out) < count and i < len(data):
        addr = start_addr + i
        mn, mode = OPCODES[data[i]]
        size, unknown = _width_size(mode, m, x)
        if i + size > len(data):
            out.append(Insn(addr, data[i:i + 1], f".byte ${data[i]:02X}", False))
            i += 1
            continue
        raw = bytes(data[i:i + size])
        arg = int.from_bytes(raw[1:], "little")
        if mode in ("immM", "immX"):
            text = f"{mn} #${arg:0{(size - 1) * 2}X}" + ("; width unknown" if unknown else "")
        elif mode == "imm8":
            text = f"{mn} #${arg:02X}"
        elif mode in ("imp",):
            text = mn
        elif mode == "acc":
            text = f"{mn} A"
        elif mode == "rel":
            off = arg - 256 if arg > 127 else arg
            text = f"{mn} ${(addr & 0xFF0000) | ((addr + 2 + off) & 0xFFFF):06X}"
        elif mode == "rll":
            off = arg - 65536 if arg > 32767 else arg
            text = f"{mn} ${(addr & 0xFF0000) | ((addr + 3 + off) & 0xFFFF):06X}"
        elif mode == "blk":
            text = f"{mn} ${raw[2]:02X},${raw[1]:02X}"
        else:
            text = f"{mn} " + _FMT[mode].format(arg)
        out.append(Insn(addr, raw, text, True))
        i += size
        m, x = _track(mn, arg, m, x)
    return out


def _kind(mn: str) -> str:
    if mn in _JUMP:
        return "jump"
    if mn in _WRITE:
        return "write"
    if mn in _READ:
        return "read"
    return "rmw" if mn in _RMW else "other"


def xrefs(info: RomInfo, data: bytes, target: int) -> list:
    """Every ROM position whose opcode takes an absolute (16-bit) or long (24-bit) operand equal to `target`; indexed forms match on their base address.

    For a target below $2000 (the WRAM mirror) a long operand at $7E:target or $00:target also counts.
    Byte-by-byte scan, so data that looks like code can produce false hits."""
    d = info.details
    start = snesrom.COPIER if d["copier_header"] else 0
    end = start + d["rom_size"]
    low = target & 0xFFFF
    wram = target >> 16 in (0x00, 0x7E) and low < 0x2000
    longs = {target} | ({0x7E0000 | low, low} if wram else set())
    absolute = low if (target <= 0xFFFF or wram) else None
    hits = []
    for off in range(start, end - 2):
        mn, mode = OPCODES[data[off]]
        if mode in ("abs", "abx", "aby") and absolute is not None and int.from_bytes(data[off + 1:off + 3], "little") == absolute:
            pass
        elif mode in ("long", "lgx") and off + 3 < end and int.from_bytes(data[off + 1:off + 4], "little") in longs:
            pass
        else:
            continue
        hits.append(Hit(snesrom.offset_to_cpu(info, off), _kind(mn), off))
    return hits

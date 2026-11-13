from glitchcraft import core
from glitchcraft.snes import codec, dis65816, rom

_FLOW = {"JMP", "JSR", "JML", "JSL", "RTS", "RTL", "RTI", "BRK", "COP", "BPL", "BMI", "BVC", "BVS", "BCC", "BCS",
         "BNE", "BEQ", "BRA", "BRL"}


class _Snes:
    name = "snes"
    flow_mnemonics = _FLOW
    routine_end = {"RTS", "RTL", "RTI", "JMP", "JML", "BRK", "BRA", "BRL"}
    max_insn_len = 4
    addr_digits = 6
    patch_size = 1
    identify = staticmethod(rom.identify)
    encode = staticmethod(codec.encode)
    cpu_to_offset = staticmethod(rom.cpu_to_offset)
    offset_to_cpu = staticmethod(rom.offset_to_cpu)
    read_original = staticmethod(rom.read_original)
    disassemble = staticmethod(dis65816.disassemble)
    xrefs = staticmethod(dis65816.xrefs)

    def value_at(self, data, offset):
        return data[offset]

    def apply(self, buf, offset, value):
        buf[offset] = value

    def decode(self, code):
        return [codec.decode(code)]

    def is_vector_area(self, addr):
        return addr & 0x7FFFFF in range(0xFFE0, 0x10000)

    def unmapped_reason(self, info, addr):
        return "not-rom-address"

    def instruction_context(self, data, info, offset):
        """(start, disassembler kwargs, boundaries uncertain?) from a sweep that tracks REP/SEP."""
        d = info.details
        begin = max(rom.COPIER if d["copier_header"] else 0, offset - 48)
        start, m, x, uncertain = dis65816.locate(data, begin, offset)
        return start, {"m": m, "x": x}, uncertain

    def jump_target(self, insn):
        mn = insn.text.split()[0]
        arg = int.from_bytes(insn.raw[1:], "little")
        if mn in ("JMP", "JSR") and len(insn.raw) == 3 and "(" not in insn.text:
            return (insn.addr & 0xFF0000) | arg
        if mn in ("JML", "JSL") and len(insn.raw) == 4:
            return arg
        return None


core.register(_Snes())

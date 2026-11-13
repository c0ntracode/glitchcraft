from glitchcraft import core
from glitchcraft.nes import codec, dis6502, rom

SUPPORTED_MAPPERS = {0, 1, 2, 3, 4, 7}


class _Nes:
    name = "nes"
    flow_mnemonics = {"JMP", "JSR", "RTS", "RTI", "BRK", "BPL", "BMI", "BVC", "BVS", "BCC", "BCS", "BNE", "BEQ"}
    routine_end = {"RTS", "RTI", "JMP", "BRK"}
    max_insn_len = 3
    addr_digits = 4
    patch_size = 1
    identify = staticmethod(rom.identify)
    encode = staticmethod(codec.encode)
    cpu_to_offset = staticmethod(rom.cpu_to_offset)
    offset_to_cpu = staticmethod(rom.offset_to_cpu)
    read_original = staticmethod(rom.read_original)
    disassemble = staticmethod(dis6502.disassemble)
    xrefs = staticmethod(dis6502.xrefs_detailed)

    def value_at(self, data, offset):
        return data[offset]

    def apply(self, buf, offset, value):
        buf[offset] = value

    def decode(self, code):
        return [codec.decode(code)]

    def is_vector_area(self, addr):
        return addr >= 0xFFFA

    def unmapped_reason(self, info, addr):
        return "mapper-unsupported" if info.details["mapper"] not in SUPPORTED_MAPPERS else "bank-dependent"

    def instruction_context(self, data, info, offset):
        """Linear sweep from a little earlier; boundaries are inferred, not known."""
        i = max(info.details["prg_start"], offset - 48)
        while i <= offset:
            size = dis6502.SIZE[dis6502.OPCODES[data[i]][1]]
            if i + size > offset:
                return i, {}, False
            i += size
        return offset, {}, False

    def jump_target(self, insn):
        if insn.text.lstrip("*").split()[0] in ("JMP", "JSR") and len(insn.raw) == 3 and "(" not in insn.text:
            return insn.raw[1] | insn.raw[2] << 8
        return None


core.register(_Nes())

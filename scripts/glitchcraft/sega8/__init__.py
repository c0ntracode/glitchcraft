import re

from glitchcraft import core
from glitchcraft.sega8 import codec, dis_z80, rom

_ABSOLUTE = re.compile(r"^(?:JP|JR|CALL|DJNZ) \$([0-9A-F]{4})$")


class _Sega8:
    name = "sega8"
    flow_mnemonics = dis_z80.FLOW_MNEMONICS
    routine_end = dis_z80.ROUTINE_END
    max_insn_len = 4
    addr_digits = 4
    patch_size = 1
    identify = staticmethod(rom.identify)
    encode = staticmethod(codec.encode)
    cpu_to_offset = staticmethod(rom.cpu_to_offset)
    offset_to_cpu = staticmethod(rom.offset_to_cpu)
    read_original = staticmethod(rom.read_original)
    disassemble = staticmethod(dis_z80.disassemble)
    xrefs = staticmethod(dis_z80.xrefs)
    mnemonic = staticmethod(dis_z80.mnemonic)
    bank_end = staticmethod(rom.bank_end)

    def value_at(self, data, offset):
        return data[offset]

    def apply(self, buf, offset, value):
        buf[offset] = value

    def decode(self, code):
        return [codec.decode(code)]

    def is_vector_area(self, addr):
        """Reset, RST and interrupt vectors ($0000-$0066, NMI at $0066) and the TMR SEGA header ($7FF0-$7FFF)."""
        return addr <= 0x66 or 0x7FF0 <= addr <= 0x7FFF

    def unmapped_reason(self, info, addr):
        if addr > rom.ROM_END or info.details["mapper"] == "none":
            return "not-rom-address"
        return "bank-dependent" if info.details["supported"] else "mapper-unsupported"

    def instruction_context(self, data, info, offset):
        """Linear sweep from a little earlier, never crossing back into the previous 16 KB bank."""
        begin = max(offset - 48, offset // rom.KB16 * rom.KB16)
        start, uncertain = dis_z80.locate(data, begin, offset)
        return start, {}, uncertain

    def jump_target(self, insn):
        m = _ABSOLUTE.match(insn.text)
        return int(m.group(1), 16) if m else None


core.register(_Sega8())

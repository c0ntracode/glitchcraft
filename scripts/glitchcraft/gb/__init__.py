import re

from glitchcraft import core
from glitchcraft.gb import codec, dis_sm83, rom

_ABSOLUTE = re.compile(r"^(?:JP|JR|CALL) \$([0-9A-F]{4})$")


class _Gb:
    name = "gb"
    flow_mnemonics = dis_sm83.FLOW_MNEMONICS
    routine_end = dis_sm83.ROUTINE_END
    max_insn_len = 3
    addr_digits = 4
    patch_size = 1
    identify = staticmethod(rom.identify)
    encode = staticmethod(codec.encode)
    cpu_to_offset = staticmethod(rom.cpu_to_offset)
    offset_to_cpu = staticmethod(rom.offset_to_cpu)
    read_original = staticmethod(rom.read_original)
    disassemble = staticmethod(dis_sm83.disassemble)
    xrefs = staticmethod(dis_sm83.xrefs)
    mnemonic = staticmethod(dis_sm83.mnemonic)
    bank_end = staticmethod(rom.bank_end)

    def value_at(self, data, offset):
        return data[offset]

    def apply(self, buf, offset, value):
        buf[offset] = value

    def decode(self, code):
        return [codec.decode(code)]

    def is_vector_area(self, addr):
        """Interrupt and RST vectors ($0000-$00FF) and the cartridge header ($0100-$014F)."""
        return addr <= 0x14F

    def unmapped_reason(self, info, addr):
        if addr > 0x7FFF:
            return "not-rom-address"
        return "bank-dependent" if info.details["supported"] else "mapper-unsupported"

    def instruction_context(self, data, info, offset):
        """Linear sweep from a little earlier, never crossing back into the previous 16 KB bank."""
        begin = max(offset - 48, offset // rom.KB16 * rom.KB16)
        start, uncertain = dis_sm83.locate(data, begin, offset)
        return start, {}, uncertain

    def jump_target(self, insn):
        m = _ABSOLUTE.match(insn.text)
        return int(m.group(1), 16) if m else None


core.register(_Gb())

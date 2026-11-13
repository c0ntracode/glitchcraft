import re

from glitchcraft import core
from glitchcraft.core import Patch
from glitchcraft.genesis import codec, dis68000, rom

_COND = dis68000.COND
_FLOW = ({"JMP", "JSR", "RTS", "RTE", "RTR", "TRAP", "TRAPV", "ILLEGAL", "DBRA"}
         | {f"DB{c}" for c in _COND}
         | {f"B{c}.{s}" for c in _COND[2:] for s in "SW"}
         | {f"{n}.{s}" for n in ("BRA", "BSR") for s in "SW"})
_JUMP_ABS = re.compile(r"^(?:JMP|JSR) \(\$([0-9A-F]{8})\)\.[lw]$")
_JUMP_PC = re.compile(r"^(?:JMP|JSR) \$([0-9A-F]{6})\(PC\)$")
_BRANCH = re.compile(r"^B(?:RA|SR)\.[SW] \$([0-9A-F]{6})$")


class _Genesis:
    name = "genesis"
    flow_mnemonics = _FLOW
    routine_end = {"RTS", "RTE", "RTR", "JMP", "BRA.S", "BRA.W", "ILLEGAL"}
    max_insn_len = 10
    addr_digits = 6
    patch_size = 2
    identify = staticmethod(rom.identify)
    cpu_to_offset = staticmethod(rom.cpu_to_offset)
    offset_to_cpu = staticmethod(rom.offset_to_cpu)
    read_original = staticmethod(rom.read_original)
    disassemble = staticmethod(dis68000.disassemble)
    xrefs = staticmethod(dis68000.xrefs)

    def encode(self, patch):
        if patch.address & 1:
            raise core.GlitchError(
                f"a Genesis code patches a whole word at an even address; use ${patch.address & ~1:06X}, not ${patch.address:06X}")
        return codec.encode(patch)

    def decode(self, code):
        """A Game Genie word patch ignores address bit 0, so the address is normalized to its even word."""
        p = codec.decode(code)
        return [Patch(p.address & ~1, p.value, None)]

    def value_at(self, data, offset):
        return int.from_bytes(data[offset:offset + 2], "big")

    def apply(self, buf, offset, value):
        buf[offset:offset + 2] = value.to_bytes(2, "big")

    def is_vector_area(self, addr):
        return addr < 0x100

    def unmapped_reason(self, info, addr):
        return "not-rom-address"

    def instruction_context(self, data, info, offset):
        start, uncertain = dis68000.locate(data, max(0, offset - 64), offset)
        return start, {}, uncertain

    def jump_target(self, insn):
        for pattern in (_JUMP_ABS, _JUMP_PC, _BRANCH):
            m = pattern.match(insn.text)
            if m:
                return int(m.group(1), 16) & 0xFFFFFF
        return None


core.register(_Genesis())

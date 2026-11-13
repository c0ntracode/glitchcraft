"""Blind vetting: decode codes against a ROM and describe what each patch does to the bytes.

Takes no description of the code's claimed effect on purpose; the effect is worked out from the bytes alone.
"""
from dataclasses import dataclass, field

from glitchcraft import core

FLAG_ORDER = ["control-flow-change", "opcode-class-change", "unofficial-opcode-follows", "brk-follows",
              "vector-area", "compare-mismatch", "bank-dependent", "mapper-unsupported", "not-rom-address", "boundary-uncertain"]
WINDOW = 8


def _mn(platform, insn) -> str:
    """Opcode name used for flow checks; a platform may refine it (Game Boy marks conditional branches)."""
    hook = getattr(platform, "mnemonic", None)
    return hook(insn.text) if hook else insn.text.lstrip("*").split()[0]


@dataclass
class Finding:
    code: str
    address: int
    offset: int | None
    original: int | None
    new: int
    before: str
    after: str
    flags: list = field(default_factory=list)
    target: list = field(default_factory=list)


@dataclass
class Combined:
    codes: list
    start_addr: int
    before: str
    after: str
    flags: list = field(default_factory=list)
    target: list = field(default_factory=list)


@dataclass
class Report:
    findings: list
    combined: list


def _window(platform, info, start: int, span: int) -> int:
    """End of the byte window to disassemble from `start`: not past a bank boundary, where an operand would come
    from whichever bank is mapped next instead of the following bytes of the file."""
    end = start + span
    hook = getattr(platform, "bank_end", None)
    boundary = hook(info, start) if hook else None
    return min(end, boundary) if boundary else end


def _target_listing(platform, info, patched: bytes, insn) -> list:
    """Listing of the routine a patched JMP/JSR now points at, up to its first routine-ending instruction."""
    addr = platform.jump_target(insn)
    if addr is None:
        return []
    off = platform.cpu_to_offset(info, addr)
    if off is None:
        return []
    out = []
    for i in platform.disassemble(patched[off:_window(platform, info, off, 16 * platform.max_insn_len)], addr, 12):
        out.append(f"${i.addr:04X} {i.text}")
        if _mn(platform, i) in platform.routine_end:
            break
    return out


def _reachable(platform, insns: list) -> list:
    """The instructions after the first that execution reaches in sequence: none after an unconditional end
    (RTS, JMP, BRA, ...), and nothing past the first one that appears later in the window."""
    ends = platform.routine_end
    mn = lambda insn: _mn(platform, insn)  # noqa: E731
    if mn(insns[0]) in ends:
        return []
    out = []
    for insn in insns[1:]:
        out.append(insn)
        if mn(insn) in ends:
            break
    return out


def _describe(platform, info, data: bytes, patched: bytes, start: int, cpu_start: int, opcode_patched: bool,
              kwargs: dict) -> tuple:
    span = platform.max_insn_len * (WINDOW + 1)
    end = _window(platform, info, start, span)
    old = platform.disassemble(data[start:end], cpu_start, WINDOW + 1, **kwargs)
    new = platform.disassemble(patched[start:end], cpu_start, WINDOW + 1, **kwargs)
    flags = set()
    mn = lambda insn: _mn(platform, insn)  # noqa: E731
    if old[0].text != new[0].text and (mn(old[0]) in platform.flow_mnemonics or mn(new[0]) in platform.flow_mnemonics):
        flags.add("control-flow-change")
    if opcode_patched and old[0].raw[:1] != new[0].raw[:1]:
        flags.add("opcode-class-change")
    old_after, new_after = _reachable(platform, old), _reachable(platform, new)
    if any(not i.official for i in new_after) and not any(not i.official for i in old_after):
        flags.add("unofficial-opcode-follows")
    if any(i.text == "BRK" for i in new_after) and not any(i.text == "BRK" for i in old_after):
        flags.add("brk-follows")
    target = _target_listing(platform, info, patched, new[0]) if old[0].text != new[0].text else []
    return old[0].text, new[0].text, flags, target


def vet(rom_bytes: bytes, codes: list, bank: int | None = None) -> Report:
    platform, info = core.identify_rom(rom_bytes)
    findings, located = [], []
    for code in codes:
        for p in platform.decode(code):
            off = platform.cpu_to_offset(info, p.address, bank)
            flags = set()
            if platform.is_vector_area(p.address):
                flags.add("vector-area")
            if off is None:
                flags.add(platform.unmapped_reason(info, p.address))
                findings.append(Finding(code, p.address, None, None, p.value, "", "", sorted(flags, key=FLAG_ORDER.index)))
                continue
            original = platform.value_at(rom_bytes, off)
            if p.compare is not None and p.compare != original:
                flags.add("compare-mismatch")
            start, kwargs, uncertain = platform.instruction_context(rom_bytes, info, off)
            cpu_start = p.address - (off - start)
            patched = bytearray(rom_bytes)
            platform.apply(patched, off, p.value)
            before, after, more, target = _describe(platform, info, rom_bytes, bytes(patched), start, cpu_start,
                                                    start == off, kwargs)
            flags |= more
            if uncertain:
                flags.add("boundary-uncertain")
            findings.append(Finding(code, p.address, off, original, p.value, before, after,
                                    sorted(flags, key=FLAG_ORDER.index), target))
            located.append((code, p, off, start, cpu_start, kwargs, uncertain))
    combined = []
    groups: dict = {}
    for item in located:
        groups.setdefault(item[3], []).append(item)
    for start, items in groups.items():
        if len(items) < 2:
            continue
        patched = bytearray(rom_bytes)
        for _, p, off, *_ in items:
            platform.apply(patched, off, p.value)
        before, after, flags, target = _describe(platform, info, rom_bytes, bytes(patched), start, items[0][4],
                                                 any(it[2] == start for it in items), items[0][5])
        if any(it[6] for it in items):
            flags.add("boundary-uncertain")
        combined.append(Combined([it[0] for it in items], items[0][4], before, after,
                                 sorted(flags, key=FLAG_ORDER.index), target))
    return Report(findings, combined)

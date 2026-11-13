import argparse
import os
import sys

import glitchcraft.nes  # noqa: F401  (registers the NES platform)
import glitchcraft.snes  # noqa: F401  (registers the SNES platform)
import glitchcraft.genesis  # noqa: F401  (registers the Genesis platform)
import glitchcraft.gb  # noqa: F401  (registers the Game Boy platform)
import glitchcraft.sega8  # noqa: F401  (registers the Game Gear / Master System platform)
from glitchcraft import core, vet
from glitchcraft.core import GlitchError, Patch

COMMANDS: dict = {}


def _a(platform, addr: int) -> str:
    return f"${addr:0{getattr(platform, 'addr_digits', 4)}X}"


def _v(platform, value: int) -> str:
    return f"${value:0{2 * getattr(platform, 'patch_size', 1)}X}"


def _hex(text: str) -> int:
    try:
        return int(text.lstrip("$"), 16)
    except ValueError:
        raise GlitchError(f"{text!r} is not a hex number") from None


def _count(text: str) -> int:
    try:
        return int(text)
    except ValueError:
        raise GlitchError(f"{text!r} is not a number") from None


def _need(args: list, n: int, usage: str):
    if len(args) < n:
        raise GlitchError(f"missing argument; usage: gg.py {usage}")


def _load(path: str):
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        raise GlitchError(f"cannot read ROM {path}: {e.strerror}") from None
    platform, info = core.identify_rom(data)
    return platform, data, info


def _take_bank(args: list) -> tuple:
    """Remove `--bank N` (or `--bank=N`) from `args`: (remaining args, bank or None). N is decimal, or hex with 0x."""
    def number(text):
        try:
            return int(text, 0)
        except ValueError:
            raise GlitchError(f"--bank needs a number: decimal (32) or hex with 0x (0x20), got {text!r}") from None

    for i, a in enumerate(args):
        if a.startswith("--bank="):
            return args[:i] + args[i + 1:], number(a[len("--bank="):])
        if a == "--bank":
            if i + 1 >= len(args):
                raise GlitchError("--bank needs a number: decimal (32) or hex with 0x (0x20)")
            return args[:i] + args[i + 2:], number(args[i + 1])
    return args, None


def cmd_id(args):
    _, data, info = _load(args[0])
    print(f"platform: {info.platform}\nsize: {info.size}\nsha1: {info.sha1}")
    print(f"title: {info.title}" if info.title else "title: (the format has none; confirm the game with the user)")
    for k, v in info.details.items():
        print(f"{k}: {v}")


def cmd_decode(args):
    args, bank = _take_bank(args)
    _need(args, 2, "decode ROM CODE... [--bank N]  (give at least one code)")
    platform, data, info = _load(args[0])
    for code in args[1:]:
        for p in platform.decode(code):
            off = platform.cpu_to_offset(info, p.address, bank)
            orig = _v(platform, platform.value_at(data, off)) if off is not None else f"n/a ({platform.unmapped_reason(info, p.address)})"
            cmp_ = "none" if p.compare is None else _v(platform, p.compare)
            print(f"{code.upper()}  {_a(platform, p.address)}  value={_v(platform, p.value)}  compare={cmp_}  original={orig}")
            if off is not None and p.compare is not None and p.compare != platform.value_at(data, off):
                print("  this code will not apply on this dump: its compare byte differs from the ROM byte")


def cmd_make(args):
    ap = argparse.ArgumentParser(prog="gg.py make")
    ap.add_argument("rom")
    ap.add_argument("--addr", required=True)
    ap.add_argument("--value", required=True)
    ap.add_argument("--compare")
    ap.add_argument("--bank", type=lambda t: int(t, 0), metavar="N")
    a = ap.parse_args(args)
    platform, data, info = _load(a.rom)
    addr = _hex(a.addr)
    original = platform.read_original(data, info, addr, a.bank)
    patch = Patch(addr, _hex(a.value), None if a.compare is None else _hex(a.compare))
    code = platform.encode(patch)
    if patch.compare is not None and patch.compare != original:
        raise GlitchError(f"compare {_v(platform, patch.compare)} differs from the ROM value {_v(platform, original)} at {_a(platform, addr)}: "
                          "this code will not apply on this dump")
    if platform.decode(code) != [patch]:
        raise GlitchError(f"internal error: {code} does not decode back to the requested patch")
    print(f"code: {code}\naddress: {_a(platform, addr)}\noriginal: {_v(platform, original)} (read from the file)")
    print(f"new: {_v(platform, patch.value)}\nround-trip: ok")
    if platform.is_vector_area(addr):
        print(f"warning: {_a(platform, addr)} is in the vector/header area; a patch here can change interrupt handling "
              "or stop the game from booting. Run `vet` before offering it.")


def cmd_xrefs(args):
    _need(args, 2, "xrefs ROM ADDRESS  (the address to look for is missing)")
    if any(a.startswith("--") for a in args):
        raise GlitchError("xrefs takes no options: a hit in a banked area is reported as a file offset, and its bank "
                          "is that offset divided by the bank size (0x4000 for most platforms)")
    platform, data, info = _load(args[0])
    target = _hex(args[1])
    hits = platform.xrefs(info, data, target)
    for h in hits:
        where = _a(platform, h.cpu) if h.cpu is not None else f"file offset 0x{h.offset:04X} (bank-dependent)"
        print(f"{where} {h.kind}")
    if not hits:
        print(f"no references to {_a(platform, target)} found (xrefs matches instruction operands, so a variable "
              "address is the useful input; a code address finds nothing)")


def cmd_disasm(args):
    args, bank = _take_bank(args)
    _need(args, 3, "disasm ROM ADDRESS COUNT [--bank N]  (the instruction count is missing)")
    platform, data, info = _load(args[0])
    addr, count = _hex(args[1]), _hex(args[2]) if args[2].startswith("$") else _count(args[2])
    if count < 1:
        raise GlitchError("the instruction count must be at least 1")
    off = platform.cpu_to_offset(info, addr, bank)
    if off is None:
        reason = platform.unmapped_reason(info, addr)
        if reason == "not-rom-address":
            why = "is not ROM and not mapped (RAM, I/O or unmapped space), so there is nothing to disassemble"
        elif reason == "mapper-unsupported":
            why = "cannot be placed in the file: this ROM's mapper is not supported"
        elif bank is not None:
            why = "is not mapped to ROM here (past the end of this ROM, or not ROM for that bank)"
        else:
            why = "is not mapped to ROM here (a banked area needs --bank)"
        raise GlitchError(f"{_a(platform, addr)} {why}; cannot disassemble")
    for i in platform.disassemble(data[off:vet._window(platform, info, off, platform.max_insn_len * count)], addr, count):
        print(f"{_a(platform, i.addr)}: {i.raw.hex(' ').upper():<11}  {i.text}")


def cmd_vet(args):
    args, bank = _take_bank(args)
    _need(args, 2, "vet ROM CODE... [--bank N]  (give at least one code)")
    platform, data, _ = _load(args[0])
    report = vet.vet(data, args[1:], bank)
    grouped = {code.upper() for c in report.combined for code in c.codes}

    def displaced(before):
        print(f"  displaced: {before} no longer runs; find what reads what it wrote, and compare patched against unpatched play")
    for f in report.findings:
        orig = "?" if f.original is None else _v(platform, f.original)
        print(f"{f.code.upper()}  {_a(platform, f.address)}  {orig} -> {_v(platform, f.new)}")
        if f.before or f.after:
            print(f"  {f.before} -> {f.after}")
        print(f"  flags: {', '.join(f.flags) or 'none'}")
        if "compare-mismatch" in f.flags:
            print("  this code will not apply on this dump: its compare byte differs from the ROM byte")
        if "opcode-class-change" in f.flags and f.code.upper() not in grouped:
            displaced(f.before)
        if f.target:
            print("  target: " + "; ".join(f.target))
    for c in report.combined:
        print(f"combined {' + '.join(c.codes)} at {_a(platform, c.start_addr)}: {c.before} -> {c.after}")
        print(f"  flags: {', '.join(c.flags) or 'none'}")
        if "opcode-class-change" in c.flags:
            displaced(c.before)
        if c.target:
            print("  target: " + "; ".join(c.target))
    if report.findings:
        print("note: instruction boundaries are inferred by a linear sweep; confirm with `disasm` from a known entry point")


def cmd_patch_copy(args):
    args, bank = _take_bank(args)
    _need(args, 3, "patch-copy ROM OUT CODE... [--bank N]  (an output path and at least one code are needed)")
    src, dst, codes = args[0], args[1], args[2:]
    if os.path.realpath(src) == os.path.realpath(dst) or (os.path.exists(dst) and os.path.samefile(src, dst)):
        raise GlitchError("refusing to overwrite the input ROM; give a different output path")
    platform, data, info = _load(src)
    out = bytearray(data)
    for code in codes:
        for p in platform.decode(code):
            off = platform.cpu_to_offset(info, p.address, bank)
            if off is None:
                hint = (" (a banked area needs --bank)" if platform.unmapped_reason(info, p.address) == "bank-dependent" else "")
                raise GlitchError(f"{code.upper()} patches {_a(platform, p.address)}, which is not mapped to ROM here{hint}")
            if p.compare is not None and platform.value_at(out, off) != p.compare:
                print(f"note: {code.upper()} compare {_v(platform, p.compare)} != ROM {_v(platform, platform.value_at(out, off))}; "
                      "not applied (as on hardware)")
                continue
            platform.apply(out, off, p.value)
    try:
        with open(dst, "wb") as f:
            f.write(out)
    except OSError as e:
        raise GlitchError(f"cannot write {dst}: {e.strerror}") from None
    print(f"wrote {dst}")


COMMANDS.update({"id": cmd_id, "decode": cmd_decode, "make": cmd_make, "xrefs": cmd_xrefs,
                 "disasm": cmd_disasm, "vet": cmd_vet, "patch-copy": cmd_patch_copy})


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in COMMANDS:
        known = ", ".join(sorted(COMMANDS)) or "none yet"
        print(f"error: unknown command (available: {known})", file=sys.stderr)
        return 2
    try:
        return COMMANDS[argv[0]](argv[1:]) or 0
    except GlitchError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except IndexError:
        print(f"error: wrong arguments for {argv[0]}; see docs in SKILL.md", file=sys.stderr)
        return 2
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 2

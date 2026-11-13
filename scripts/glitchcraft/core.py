"""Shared types and the platform registry.

A platform module registers an object with these attributes:
  name: str
  identify(rom: bytes) -> RomInfo | None
  decode(code: str) -> list[Patch]
  encode(patch: Patch) -> str
  cpu_to_offset(info, addr, bank=None) -> int | None   (None: bank-dependent or unmapped)
  offset_to_cpu(info, offset) -> int | None
  read_original(data, info, addr, bank=None) -> int
  unmapped_reason(info, addr) -> "bank-dependent" | "mapper-unsupported" | "not-rom-address"
  instruction_context(data, info, offset) -> (start, disassemble kwargs, uncertain)   (instruction containing `offset`)
  disassemble(data, addr, count) -> list[Insn]
  xrefs(info, data, target) -> list[Hit]
  jump_target(insn) -> int | None                       (absolute JMP/JSR target, else None)
  is_vector_area(addr) -> bool
  addr_digits: int   (hex digits in an address, for display)
  patch_size: int    (1 or 2: bytes a code replaces; 2 means a big-endian word)
  value_at(data, offset) -> int          (the value a patch replaces, patch_size bytes wide)
  apply(buf, offset, value) -> None      (write a patch value into a bytearray)
  flow_mnemonics: set[str]    routine_end: set[str]    max_insn_len: int
"""
from dataclasses import dataclass, field
from typing import NamedTuple


class GlitchError(Exception):
    """An error whose message is shown to the user as one line."""


@dataclass(frozen=True)
class Patch:
    address: int
    value: int
    compare: int | None = None


@dataclass(frozen=True)
class RomInfo:
    platform: str
    size: int
    sha1: str
    title: str | None = None
    details: dict = field(default_factory=dict)


class Insn(NamedTuple):
    addr: int
    raw: bytes
    text: str
    official: bool


class Hit(NamedTuple):
    cpu: int | None   # None: the offset has no single CPU address (switchable bank)
    kind: str
    offset: int


_PLATFORMS: dict = {}


def register(platform) -> None:
    _PLATFORMS[platform.name] = platform


def unregister(name: str) -> None:
    _PLATFORMS.pop(name, None)


def get_platform(name: str):
    try:
        return _PLATFORMS[name]
    except KeyError:
        raise GlitchError(f"unsupported platform: {name}") from None


def identify_rom(data: bytes):
    """Return (platform, RomInfo) for the first registered platform that recognizes the file."""
    for platform in _PLATFORMS.values():
        info = platform.identify(data)
        if info is not None:
            return platform, info
    raise GlitchError("ROM format not recognized; supported platforms: " + ", ".join(sorted(_PLATFORMS)))

import contextlib
import io
import os
import tempfile
import unittest

import _path  # noqa: F401
from glitchcraft import cli, core, vet
from glitchcraft.core import Hit, Insn, Patch, RomInfo

FAKE_ROM = b"FAKE" + bytes([0x12, 0x34]) + bytes(58)   # the word at offset 4 is $1234


class FakePlatform:
    """A 16-bit-patch platform: the word at file offset 4 is the patch target (CPU address $8004)."""
    name = "fake"
    flow_mnemonics = set()
    routine_end = set()
    max_insn_len = 2
    addr_digits = 4
    patch_size = 2

    def __init__(self):
        self.disassembled = False
        self.seen = []
        self.last = None

    def identify(self, rom):
        return RomInfo("fake", len(rom), "0" * 40, "FAKE GAME", {}) if rom.startswith(b"FAKE") else None

    def decode(self, code):
        return [self.last] if code == "FAKECODE" and self.last else [Patch(0x8004, 0x42, None)]

    def encode(self, patch):
        self.last = patch
        return "FAKECODE"

    def cpu_to_offset(self, info, addr, bank=None):
        return addr - 0x8000 if 0x8000 <= addr < 0x8000 + info.size - 1 else None

    def offset_to_cpu(self, info, offset):
        return 0x8000 + offset

    def value_at(self, data, offset):
        return int.from_bytes(data[offset:offset + 2], "big")

    def apply(self, buf, offset, value):
        buf[offset:offset + 2] = value.to_bytes(2, "big")

    def read_original(self, data, info, addr, bank=None):
        return self.value_at(data, addr - 0x8000)

    def is_vector_area(self, addr):
        return addr >= 0xFFFA

    def unmapped_reason(self, info, addr):
        return "bank-dependent"

    def instruction_context(self, data, info, offset):
        return offset, {}, False

    def jump_target(self, insn):
        return None

    def disassemble(self, data, addr, count):
        self.disassembled = True
        self.seen.append(bytes(data[:2]))
        return [Insn(addr, bytes(data[:2]), "FAKEOP", True)]

    def xrefs(self, info, data, target):
        return [Hit(0x8004, "write", 4)]


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.platform = FakePlatform()
        core.register(self.platform)
        self.addCleanup(core.unregister, "fake")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        self.path = os.path.join(self.dir, "game.fake")
        with open(self.path, "wb") as f:
            f.write(FAKE_ROM)

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_cli_routes_xrefs_through_a_registered_platform(self):
        _, out, _ = self.run_cli("xrefs", self.path, "10")
        self.assertIn("$8004 write", out)

    def test_vet_uses_the_platform_disassembler(self):
        report = vet.vet(FAKE_ROM, ["X"])
        self.assertTrue(self.platform.disassembled)
        self.assertEqual(report.findings[0].before, "FAKEOP")

    def test_decode_prints_word_wide_original_and_value(self):
        code, out, _ = self.run_cli("decode", self.path, "X")
        self.assertEqual(code, 0)
        self.assertIn("$8004", out)
        self.assertIn("value=$0042", out)
        self.assertIn("original=$1234", out)

    def test_vet_reads_and_writes_both_bytes_of_a_word_patch(self):
        report = vet.vet(FAKE_ROM, ["X"])
        self.assertEqual((report.findings[0].original, report.findings[0].new), (0x1234, 0x42))
        self.assertIn(bytes([0x12, 0x34]), self.platform.seen)
        self.assertIn(bytes([0x00, 0x42]), self.platform.seen)

    def test_vet_cli_prints_word_wide_bytes(self):
        _, out, _ = self.run_cli("vet", self.path, "X")
        self.assertIn("$1234 -> $0042", out)

    def test_patch_copy_writes_a_big_endian_word(self):
        out_path = os.path.join(self.dir, "patched.fake")
        code, _, _ = self.run_cli("patch-copy", self.path, out_path, "X")
        self.assertEqual(code, 0)
        with open(out_path, "rb") as f:
            self.assertEqual(f.read()[4:6], bytes([0x00, 0x42]))

    def test_make_checks_compare_against_a_word(self):
        code, out, _ = self.run_cli("make", self.path, "--addr", "8004", "--value", "42")
        self.assertEqual(code, 0)
        self.assertIn("original: $1234", out)
        self.assertIn("new: $0042", out)
        code, _, err = self.run_cli("make", self.path, "--addr", "8004", "--value", "42", "--compare", "9999")
        self.assertEqual(code, 2)
        self.assertIn("will not apply", err)

    def test_byte_platforms_keep_two_digit_values(self):
        self.assertEqual(core.get_platform("nes").patch_size, 1)
        self.assertEqual(core.get_platform("snes").patch_size, 1)


if __name__ == "__main__":
    unittest.main()

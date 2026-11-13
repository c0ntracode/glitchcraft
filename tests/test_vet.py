import inspect
import os
import unittest

import _path  # noqa: F401
from glitchcraft import vet
from glitchcraft.core import GlitchError, Patch
from glitchcraft.nes import codec

SMB = os.path.join(os.path.dirname(__file__), "..", "roms", "nes", "smb.nes")


def make_nes(prg_banks=2, mapper=0, plant=None):
    """Synthetic ROM whose PRG is all NOP ($EA); `plant` maps CPU address -> hex bytes (NROM-256 layout)."""
    header = bytearray(16)
    header[0:4] = b"NES\x1a"
    header[4], header[5], header[6], header[7] = prg_banks, 1, (mapper & 15) << 4, mapper & 0xF0
    prg = bytearray([0xEA]) * (0x4000 * prg_banks)
    for addr, hexbytes in (plant or {}).items():
        raw = bytes.fromhex(hexbytes)
        prg[addr - 0x8000:addr - 0x8000 + len(raw)] = raw
    return bytes(header) + bytes(prg) + bytes(0x2000)


PRANK_SITE = {0x924A: "85 FC 20 82 92 90 13 AD 5F 07 8D FD 07 A9 00 0A"}
START_SITE = {0x8251: "C9 90 D0 03 4C D8 82 C9 20", 0x91DE: "A9 00 8D 72 07 A9 03 8D 70 07 60"}
LIVES_SITE = {0x9069: "A9 02 8D 5A 07"}


class VetTests(unittest.TestCase):
    def test_ktgoyx_flags_opcode_class_change_unofficial_and_brk(self):
        f = vet.vet(make_nes(plant=PRANK_SITE), ["KTGOYX"]).findings[0]
        self.assertEqual((f.address, f.original, f.new), (0x924F, 0x90, 0xEC))
        self.assertEqual((f.before, f.after), ("BCC $9264", "CPX $AD13"))
        for flag in ("control-flow-change", "opcode-class-change", "unofficial-opcode-follows", "brk-follows"):
            self.assertIn(flag, f.flags)

    def test_viiatx_plus_opiayz_reported_as_one_jmp_target_change(self):
        report = vet.vet(make_nes(plant=START_SITE), ["VIIATX", "OPIAYZ"])
        self.assertEqual(len(report.combined), 1)
        c = report.combined[0]
        self.assertEqual((c.before, c.after), ("JMP $82D8", "JMP $91DE"))
        self.assertIn("control-flow-change", c.flags)
        self.assertEqual(report.findings[0].after, "JMP $82DE")

    def test_jump_target_listing_is_reported(self):
        report = vet.vet(make_nes(plant=START_SITE), ["VIIATX", "OPIAYZ"])
        self.assertEqual(report.combined[0].target, [
            "$91DE LDA #$00", "$91E0 STA $0772", "$91E3 LDA #$03", "$91E5 STA $0770", "$91E8 RTS"])
        self.assertEqual(vet.vet(make_nes(plant=LIVES_SITE), ["AATOZE"]).findings[0].target, [])

    def test_lives_code_has_no_control_flow_flag(self):
        f = vet.vet(make_nes(plant=LIVES_SITE), ["AATOZE"]).findings[0]
        self.assertEqual((f.before, f.after), ("LDA #$02", "LDA #$08"))
        self.assertEqual(f.flags, [])

    def test_compare_mismatch_flagged_and_match_not(self):
        bad = codec.encode(Patch(0x8000, 0x11, 0x22))
        good = codec.encode(Patch(0x8000, 0x11, 0xEA))
        self.assertIn("compare-mismatch", vet.vet(make_nes(), [bad]).findings[0].flags)
        self.assertNotIn("compare-mismatch", vet.vet(make_nes(), [good]).findings[0].flags)

    def test_bank_dependent_flagged_on_mmc1_window(self):
        code = codec.encode(Patch(0x8000, 0x11))
        f = vet.vet(make_nes(prg_banks=8, mapper=1), [code]).findings[0]
        self.assertIn("bank-dependent", f.flags)
        self.assertIsNone(f.offset)

    def test_unsupported_mapper_flagged(self):
        code = codec.encode(Patch(0x8000, 0x11))
        f = vet.vet(make_nes(mapper=9), [code]).findings[0]
        self.assertIn("mapper-unsupported", f.flags)

    def test_vector_area_flagged(self):
        code = codec.encode(Patch(0xFFFC, 0x00))
        self.assertIn("vector-area", vet.vet(make_nes(), [code]).findings[0].flags)

    def test_not_a_nes_rom_raises(self):
        with self.assertRaises(GlitchError):
            vet.vet(bytes(100), ["AATOZE"])

    def test_vet_never_takes_a_claim(self):
        self.assertEqual(list(inspect.signature(vet.vet).parameters), ["rom_bytes", "codes", "bank"])

    @unittest.skipUnless(os.path.exists(SMB), "roms/nes/smb.nes not present")
    def test_real_smb_prank_codes(self):
        with open(SMB, "rb") as f:
            data = f.read()
        report = vet.vet(data, ["KTGOYX"])
        self.assertIn("brk-follows", report.findings[0].flags)
        report = vet.vet(data, ["VIIATX", "OPIAYZ"])
        self.assertEqual(report.combined[0].after, "JMP $91DE")
        self.assertEqual(vet.vet(data, ["SXIOPO"]).findings[0].flags, ["opcode-class-change"])


if __name__ == "__main__":
    unittest.main()

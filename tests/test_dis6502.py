import os
import unittest

import _path  # noqa: F401
from glitchcraft.nes import dis6502, rom
from test_vet import make_nes

SMB = os.path.join(os.path.dirname(__file__), "..", "roms", "nes", "smb.nes")


def dis(raw, addr=0x9000, count=1):
    return dis6502.disassemble(bytes(raw), addr, count)


class DisTests(unittest.TestCase):
    def test_decodes_dec_abs(self):
        insn = dis([0xCE, 0x5A, 0x07])[0]
        self.assertEqual((insn.text, insn.official, insn.raw), ("DEC $075A", True, bytes([0xCE, 0x5A, 0x07])))

    def test_addressing_mode_formats(self):
        cases = {
            (0xA9, 0x01): "LDA #$01", (0xA5, 0x12): "LDA $12", (0xB5, 0x12): "LDA $12,X",
            (0xB6, 0x12): "LDX $12,Y", (0xBD, 0x34, 0x12): "LDA $1234,X", (0xB9, 0x34, 0x12): "LDA $1234,Y",
            (0x6C, 0x34, 0x12): "JMP ($1234)", (0xA1, 0x12): "LDA ($12,X)", (0xB1, 0x12): "LDA ($12),Y",
            (0x0A,): "ASL A", (0xEA,): "NOP", (0x4C, 0xD8, 0x82): "JMP $82D8",
        }
        for raw, text in cases.items():
            with self.subTest(text=text):
                self.assertEqual(dis(raw)[0].text, text)

    def test_branch_shows_absolute_target(self):
        self.assertEqual(dis([0x90, 0x13], addr=0x924F)[0].text, "BCC $9264")
        self.assertEqual(dis([0xD0, 0xFE], addr=0x9000)[0].text, "BNE $9000")

    def test_unofficial_opcode_flagged(self):
        insn = dis([0x5F, 0x07, 0x8D])[0]
        self.assertFalse(insn.official)
        self.assertEqual(insn.text, "*SRE $8D07,X")

    def test_brk_decodes(self):
        self.assertEqual(dis([0x00])[0].text, "BRK")

    def test_exactly_151_official_opcodes(self):
        official = [op for op in range(256) if dis6502.OPCODES[op][2]]
        self.assertEqual(len(official), 151)

    def test_truncated_tail_becomes_byte_directive(self):
        out = dis6502.disassemble(bytes([0xAD, 0x01]), 0x9000, 2)
        self.assertEqual([i.text for i in out], [".byte $AD", ".byte $01"])

    def test_disassembly_of_prank_site(self):
        patched = bytes.fromhex("EC 13 AD 5F 07 8D FD 07 A9 00 0A")
        texts = [i.text for i in dis6502.disassemble(patched, 0x924F, 5)]
        self.assertEqual(texts, ["CPX $AD13", "*SRE $8D07,X", "SBC $A907,X", "BRK", "ASL A"])

    def test_xrefs_on_nrom128(self):
        data = make_nes(prg_banks=1, plant={0x8069: "A9 02 8D 5A 07"})
        info = rom.identify(data)
        self.assertIn((0xC06B, "write"), dis6502.xrefs(info, data, 0x075A))

    def test_xrefs_zero_page_target(self):
        data = make_nes(plant={0x9000: "A5 0E C6 0E"})
        hits = dis6502.xrefs(rom.identify(data), data, 0x0E)
        self.assertIn((0x9000, "read"), hits)
        self.assertIn((0x9002, "rmw"), hits)

    def test_xrefs_detailed_reports_hits_in_switchable_banks(self):
        data = bytearray(make_nes(prg_banks=8, mapper=1))
        data[16 + 0x10:16 + 0x13] = bytes.fromhex("8D 5A 07")
        data[16 + 7 * 0x4000 + 0x100:16 + 7 * 0x4000 + 0x103] = bytes.fromhex("8D 5A 07")
        hits = dis6502.xrefs_detailed(rom.identify(bytes(data)), bytes(data), 0x075A)
        self.assertEqual([(h.cpu, h.kind, h.offset) for h in hits],
                         [(None, "write", 16 + 0x10), (0xC100, "write", 16 + 7 * 0x4000 + 0x100)])

    @unittest.skipUnless(os.path.exists(SMB), "roms/nes/smb.nes not present")
    def test_xrefs_075a_in_smb(self):
        with open(SMB, "rb") as f:
            data = f.read()
        info = rom.identify(data)
        hits = dis6502.xrefs(info, data, 0x075A)
        self.assertIn((0x906B, "write"), hits)
        self.assertIn((0x91D9, "rmw"), hits)


if __name__ == "__main__":
    unittest.main()

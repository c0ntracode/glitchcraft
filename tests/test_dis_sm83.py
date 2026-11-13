import unittest

import _path  # noqa: F401
from glitchcraft.gb import dis_sm83 as dis, rom
from test_gb_rom import make_gb


def one(raw, addr=0x0100):
    got = dis._decode(bytes(raw) + b"\x00\x00", 0, addr)
    return got[0], got[1], got[3]


class Sm83Tests(unittest.TestCase):
    def test_known_opcodes(self):
        cases = {
            "00": ("NOP", 1), "01 34 12": ("LD BC,$1234", 3), "09": ("ADD HL,BC", 1), "19": ("ADD HL,DE", 1),
            "39": ("ADD HL,SP", 1), "08 00 C0": ("LD ($C000),SP", 3), "10 00": ("STOP", 2),
            "22": ("LD (HL+),A", 1), "3A": ("LD A,(HL-)", 1), "0A": ("LD A,(BC)", 1),
            "03": ("INC BC", 1), "0B": ("DEC BC", 1), "34": ("INC (HL)", 1), "3D": ("DEC A", 1),
            "36 7F": ("LD (HL),$7F", 2), "3E 05": ("LD A,$05", 2), "07": ("RLCA", 1), "27": ("DAA", 1),
            "2F": ("CPL", 1), "3F": ("CCF", 1), "76": ("HALT", 1), "46": ("LD B,(HL)", 1), "77": ("LD (HL),A", 1),
            "80": ("ADD A,B", 1), "8E": ("ADC A,(HL)", 1), "97": ("SUB A", 1), "AF": ("XOR A", 1), "BE": ("CP (HL)", 1),
            "C0": ("RET NZ", 1), "D8": ("RET C", 1), "C9": ("RET", 1), "D9": ("RETI", 1), "E9": ("JP HL", 1),
            "C3 50 01": ("JP $0150", 3), "CA 00 40": ("JP Z,$4000", 3), "CD 00 20": ("CALL $2000", 3),
            "DC 34 12": ("CALL C,$1234", 3), "C1": ("POP BC", 1), "F1": ("POP AF", 1), "F5": ("PUSH AF", 1),
            "C6 10": ("ADD A,$10", 2), "FE 90": ("CP $90", 2), "E6 0F": ("AND $0F", 2), "FF": ("RST $38", 1),
            "C7": ("RST $00", 1), "E0 40": ("LDH ($FF40),A", 2), "F0 44": ("LDH A,($FF44)", 2),
            "E2": ("LD (C),A", 1), "F2": ("LD A,(C)", 1), "EA 00 C0": ("LD ($C000),A", 3),
            "FA 34 12": ("LD A,($1234)", 3), "F3": ("DI", 1), "FB": ("EI", 1), "F9": ("LD SP,HL", 1),
            "E8 FE": ("ADD SP,-2", 2), "F8 05": ("LD HL,SP+5", 2),
            "CB 11": ("RL C", 2), "CB 37": ("SWAP A", 2), "CB 7C": ("BIT 7,H", 2), "CB 86": ("RES 0,(HL)", 2),
            "CB FF": ("SET 7,A", 2), "CB 3F": ("SRL A", 2),
        }
        for hexs, (text, size) in cases.items():
            with self.subTest(op=hexs):
                got = one(bytes.fromhex(hexs))
                self.assertEqual((got[0], got[1]), (text, size))

    def test_relative_jumps_show_the_absolute_target(self):
        self.assertEqual(one(b"\x18\xFE", 0x0100)[0], "JR $0100")
        self.assertEqual(one(b"\x20\x05", 0x0100)[0], "JR NZ,$0107")
        self.assertEqual(one(b"\x30\xF0", 0x0200)[0], "JR NC,$01F2")

    def test_every_base_and_cb_opcode_decodes_with_the_right_length(self):
        lengths = {1: set(range(256))}
        two = {0x06, 0x0E, 0x16, 0x1E, 0x26, 0x2E, 0x36, 0x3E, 0x10, 0x18, 0x20, 0x28, 0x30, 0x38,
               0xC6, 0xCE, 0xD6, 0xDE, 0xE6, 0xEE, 0xF6, 0xFE, 0xE0, 0xF0, 0xE8, 0xF8, 0xCB}
        three = {0x01, 0x11, 0x21, 0x31, 0x08, 0xC2, 0xC3, 0xC4, 0xCA, 0xCC, 0xCD, 0xD2, 0xD4, 0xDA, 0xDC, 0xEA, 0xFA}
        for op in range(256):
            want = 2 if op in two else 3 if op in three else 1
            text, size, official = one(bytes([op, 0x00, 0x00]))
            self.assertEqual(size, want, hex(op))
            self.assertEqual(official, op not in dis.ILLEGAL, hex(op))
            self.assertTrue(text, hex(op))
        for op in range(256):
            text, size, official = one(bytes([0xCB, op]))
            self.assertEqual((size, official), (2, True), hex(op))
        self.assertEqual(len(dis.ILLEGAL), 11)

    def test_illegal_opcodes_are_reported_and_not_official(self):
        for op in (0xD3, 0xDB, 0xDD, 0xE3, 0xE4, 0xEB, 0xEC, 0xED, 0xF4, 0xFC, 0xFD):
            text, size, official = one(bytes([op]))
            self.assertEqual((text, size, official), (f"ILLEGAL ${op:02X}", 1, False))

    def test_a_truncated_instruction_at_the_end_becomes_a_byte(self):
        out = dis.disassemble(b"\x00\xC3\x50", 0x0100, 5)
        self.assertEqual([i.text for i in out], ["NOP", ".byte $C3", "LD D,B"])

    def test_disassemble_walks_and_counts(self):
        out = dis.disassemble(bytes.fromhex("3E05E0404F"), 0x0150, 3)
        self.assertEqual([(i.addr, i.text) for i in out], [(0x150, "LD A,$05"), (0x152, "LDH ($FF40),A"), (0x154, "LD C,A")])

    def test_locate_finds_the_instruction_that_contains_an_offset(self):
        data = bytes.fromhex("3E05CD0020")
        self.assertEqual(dis.locate(data, 0, 3), (2, False))
        self.assertEqual(dis.locate(bytes.fromhex("D300"), 0, 1), (1, True))

    def test_xrefs_finds_stores_loads_and_ldh(self):
        marker = {0x200: bytes.fromhex("EA00C0"), 0x300: bytes.fromhex("FA00C0"), 0x400: bytes.fromhex("E0FF"),
                  0x500: bytes.fromhex("CD00C0")}
        data = make_gb(marker=marker)
        info = rom.identify(data)
        got = {(h.offset, h.kind) for h in dis.xrefs(info, data, 0xC000)}
        self.assertEqual(got, {(0x200, "write"), (0x300, "read"), (0x500, "call")})
        got = [(h.cpu, h.kind) for h in dis.xrefs(info, data, 0xFFFF)]
        self.assertEqual(got, [(0x400, "write")])


if __name__ == "__main__":
    unittest.main()

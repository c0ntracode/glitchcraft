"""Repurposing existing instructions: a synthetic stand-in for the per-jump palette investigation (no game data).

The routines below mimic the shape found in a real NES game: a once-per-jump store, and a per-frame routine that clears
the low two bits of a palette-select byte. The patches are the ones that worked there: turn the store into an INC of the
palette byte, and either stop the per-frame clear (four-state) or change its mask to keep bit 0 (two-state). A tiny 6502
stepper runs the patched ROM next to the unpatched one and compares all of RAM, which is the validation the skill asks
for: the effect is not enough, the state the patch displaces has to show up in the diff."""
import contextlib
import io
import os
import tempfile
import unittest

import _path  # noqa: F401
from glitchcraft import cli
from glitchcraft.core import Patch
from glitchcraft.nes import codec
from test_vet import make_nes

PALETTE, FORCE, SPEED = 0x03C4, 0x0433, 0x9F
JUMP, RESET, FRAME = 0x9000, 0x9100, 0x9200
SITES = {
    JUMP: "A9 00 8D 33 04 A9 FC 85 9F 60",         # LDA #0 ; STA $0433 ; LDA #$FC ; STA $9F ; RTS
    RESET: "AD C4 03 29 FC 8D C4 03 60",           # LDA $03C4 ; AND #$FC ; STA $03C4 ; RTS
    FRAME: "20 00 91 60",                          # JSR reset ; RTS
    0x9300: "A9 20 8D C4 03 60",                   # another routine: LDA #$20 ; STA $03C4 (sets the priority bit) ; RTS
}
INC_PALETTE = [Patch(0x9002, 0xEE, 0x8D), Patch(0x9003, 0xC4, 0x33), Patch(0x9004, 0x03, 0x04)]
NO_RESET = [Patch(0x9200, 0xAD, 0x20)]             # JSR -> LDA abs (a harmless read)
MASK_BIT0 = [Patch(0x9104, 0x01, 0xFC)]            # AND #$FC -> AND #$01


class Stepper:
    """Runs a routine to its RTS. Knows only the opcodes the sites use; anything else fails the test."""

    def __init__(self, prg: bytes):
        self.mem = bytearray(0x10000)
        self.mem[0x8000:0x8000 + len(prg)] = prg

    def call(self, pc):
        a, stack = 0, []
        while True:
            op = self.mem[pc]
            word = self.mem[pc + 1] | self.mem[pc + 2] << 8
            if op == 0xA9: a, pc = self.mem[pc + 1], pc + 2
            elif op == 0xAD: a, pc = self.mem[word], pc + 3
            elif op == 0x8D: self.mem[word], pc = a, pc + 3
            elif op == 0x85: self.mem[self.mem[pc + 1]], pc = a, pc + 2
            elif op == 0x29: a, pc = a & self.mem[pc + 1], pc + 2
            elif op == 0xEE: self.mem[word], pc = (self.mem[word] + 1) & 255, pc + 3
            elif op == 0x20: stack.append(pc + 3); pc = word
            elif op == 0x60:
                if not stack:
                    return
                pc = stack.pop()
            else:
                raise AssertionError(f"stepper has no opcode {op:02X} at {pc:04X}")


def run(*argv):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return cli.main([str(a) for a in argv])


class RepurposedInstructionTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.original = make_nes(plant=SITES)
        self.rom = os.path.join(self.dir.name, "g.nes")
        with open(self.rom, "wb") as f:
            f.write(self.original)

    def patched(self, patches) -> bytes:
        out = os.path.join(self.dir.name, "p%d.nes" % len(os.listdir(self.dir.name)))
        self.assertEqual(run("patch-copy", self.rom, out, *[codec.encode(p) for p in patches]), 0)
        with open(out, "rb") as f:
            return f.read()

    def cpu(self, rom: bytes) -> Stepper:
        return Stepper(rom[16:16 + 0x8000])

    def jumps(self, rom, n, idle=2, pre=None):
        """Per jump: run the jump routine, note the palette byte, run the per-frame routine, note it again, idle."""
        cpu = self.cpu(rom)
        for addr, value in (pre or {}).items():
            cpu.mem[addr] = value
        seen = []
        for _ in range(n):
            cpu.call(JUMP)
            at_jump = cpu.mem[PALETTE]
            cpu.call(FRAME)
            seen.append((at_jump, cpu.mem[PALETTE]))
            for _ in range(idle):
                cpu.call(FRAME)
                self.assertEqual(cpu.mem[PALETTE], seen[-1][1], "the selection must persist between jumps")
        return seen, cpu

    def test_patch_copy_changes_only_the_coded_bytes(self):
        rom = self.patched(INC_PALETTE + MASK_BIT0)
        changed = {i for i, (a, b) in enumerate(zip(self.original, rom)) if a != b}
        self.assertEqual(changed, {16 + p.address - 0x8000 for p in INC_PALETTE + MASK_BIT0})

    def test_unpatched_the_palette_byte_never_moves(self):
        seen, _ = self.jumps(self.original, 4)
        self.assertEqual(seen, [(0, 0)] * 4)

    def test_four_state_the_counter_advances_once_per_jump_and_holds(self):
        seen, _ = self.jumps(self.patched(NO_RESET + INC_PALETTE), 4)
        self.assertEqual([after for _, after in seen], [1, 2, 3, 4])

    def test_two_state_the_mask_leaves_a_single_bit_that_toggles(self):
        seen, _ = self.jumps(self.patched(MASK_BIT0 + INC_PALETTE), 5)
        self.assertEqual([after for _, after in seen], [1, 0, 1, 0, 1])
        # between the INC and the per-frame clear the byte briefly holds 2: one stray frame on every second jump
        self.assertEqual([at_jump for at_jump, _ in seen], [1, 2, 1, 2, 1])

    def test_state_diff_exposes_the_displaced_store_and_nothing_unrelated(self):
        pre = {FORCE: 0x55, SPEED: 0x11}
        _, plain = self.jumps(self.original, 1, pre=pre)
        _, patched = self.jumps(self.patched(MASK_BIT0 + INC_PALETTE), 1, pre=pre)
        diff = {a: (plain.mem[a], patched.mem[a]) for a in range(0x800) if plain.mem[a] != patched.mem[a]}
        diff.update({PALETTE: (plain.mem[PALETTE], patched.mem[PALETTE])})
        self.assertEqual(diff, {FORCE: (0x00, 0x55), PALETTE: (0, 1)})   # the original store of 0 no longer happens

    def test_mask_change_breaks_another_routine_that_relies_on_the_cleared_bits_being_kept(self):
        # the original clear keeps bit 5; the two-state mask drops it every frame, so a routine that sets it
        # (a stand-in for a game's pipe or door entry) stops working. Only a diff taken while that routine runs shows it.
        def after_frames(rom):
            cpu = self.cpu(rom)
            cpu.call(0x9300)
            for _ in range(3):
                cpu.call(FRAME)
            return cpu.mem[PALETTE]
        self.assertEqual(after_frames(self.original), 0x20)
        self.assertEqual(after_frames(self.patched(MASK_BIT0 + INC_PALETTE)), 0x00)
        self.assertEqual(after_frames(self.patched(NO_RESET + INC_PALETTE)), 0x20)   # the four-state set keeps it

    def test_stepper_refuses_opcodes_it_does_not_know(self):
        rom = self.patched([Patch(0x9000, 0x02, 0xA9)])                    # $02 is not an opcode the sites use
        with self.assertRaises(AssertionError):
            self.cpu(rom).call(JUMP)


if __name__ == "__main__":
    unittest.main()

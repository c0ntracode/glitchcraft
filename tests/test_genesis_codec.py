import json
import os
import random
import unittest

import _path  # noqa: F401
from glitchcraft.core import GlitchError, Patch
from glitchcraft.genesis import codec

with open(os.path.join(os.path.dirname(__file__), "fixtures", "genesis_vectors.json")) as f:
    V = json.load(f)
ALL = V["published"] + V["public_list"] + V["rom_derived"]


class GenesisCodecTests(unittest.TestCase):
    def test_decode_published_example(self):
        self.assertEqual(codec.decode("SCRA-MBLE"), Patch(0x059C44, 0xB078, None))

    def test_decode_every_fixture_vector(self):
        for v in ALL:
            with self.subTest(code=v["code"]):
                self.assertEqual(codec.decode(v["code"]), Patch(v["address"], v["value"], None))

    def test_encode_inverts_decode_for_every_fixture_vector(self):
        for v in ALL:
            with self.subTest(code=v["code"]):
                self.assertEqual(codec.encode(Patch(v["address"], v["value"], None)), v["code"])

    def test_roundtrip_random_patches(self):
        rng = random.Random(2468)
        for _ in range(2000):
            p = Patch(rng.randint(0, 0xFFFFFF), rng.randint(0, 0xFFFF), None)
            self.assertEqual(codec.decode(codec.encode(p)), p)

    def test_decode_accepts_lowercase_hyphen_no_hyphen_and_o_i_typos(self):
        want = codec.decode("SCRA-MBLE")
        self.assertEqual(codec.decode("scra-mble"), want)
        self.assertEqual(codec.decode("SCRAMBLE"), want)
        self.assertEqual(codec.decode("OOOO-OOOO"), codec.decode("0000-0000"))
        self.assertEqual(codec.decode("IIII-IIII"), codec.decode("1111-1111"))

    def test_bad_length_q_u_and_other_characters_raise_glitcherror(self):
        with self.assertRaises(GlitchError) as ctx:
            codec.decode("SCRA-MBL")
        self.assertIn("8", str(ctx.exception))
        for bad in ("Q", "U", "-", "!"):
            code = "SCRA-MBL" + bad if bad != "-" else "SCRA--MBL"
            with self.subTest(bad=bad):
                with self.assertRaises(GlitchError):
                    codec.decode(code)
        with self.assertRaises(GlitchError) as ctx:
            codec.decode("QCRA-MBLE")
        self.assertIn("'Q'", str(ctx.exception))

    def test_encode_rejects_compare_and_out_of_range(self):
        with self.assertRaises(GlitchError) as ctx:
            codec.encode(Patch(0x059C44, 0xB078, 0x1234))
        self.assertIn("compare", str(ctx.exception))
        with self.assertRaises(GlitchError):
            codec.encode(Patch(0x1000000, 0, None))
        with self.assertRaises(GlitchError):
            codec.encode(Patch(0, 0x10000, None))


if __name__ == "__main__":
    unittest.main()

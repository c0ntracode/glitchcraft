import json
import os
import random
import unittest

import _path  # noqa: F401
from glitchcraft.core import GlitchError, Patch
from glitchcraft.snes import codec

with open(os.path.join(os.path.dirname(__file__), "fixtures", "snes_vectors.json")) as f:
    VECTORS = json.load(f)["vectors"]


class SnesCodecTests(unittest.TestCase):
    def test_decode_vectors(self):
        for v in VECTORS:
            with self.subTest(code=v["code"]):
                self.assertEqual(codec.decode(v["code"]), Patch(v["address"], v["value"], None))

    def test_encode_inverts_decode_for_every_vector(self):
        for v in VECTORS:
            with self.subTest(code=v["code"]):
                self.assertEqual(codec.encode(Patch(v["address"], v["value"], None)), v["code"])

    def test_roundtrip_random_patches(self):
        rng = random.Random(4321)
        for _ in range(2000):
            p = Patch(rng.randint(0, 0xFFFFFF), rng.randint(0, 255), None)
            self.assertEqual(codec.decode(codec.encode(p)), p)

    def test_decode_accepts_lowercase_hyphen_and_no_hyphen(self):
        want = codec.decode("C222-D4DD")
        self.assertEqual(codec.decode("c222-d4dd"), want)
        self.assertEqual(codec.decode("C222D4DD"), want)

    def test_bad_length_and_letter_raise_glitcherror(self):
        with self.assertRaises(GlitchError) as ctx:
            codec.decode("C222-D4D")
        self.assertIn("8", str(ctx.exception))
        with self.assertRaises(GlitchError) as ctx:
            codec.decode("C222-D4DG")
        self.assertIn("G", str(ctx.exception))

    def test_encode_rejects_compare_and_out_of_range(self):
        with self.assertRaises(GlitchError) as ctx:
            codec.encode(Patch(0x00D0D8, 0xAD, 0xCE))
        self.assertIn("compare", str(ctx.exception))
        with self.assertRaises(GlitchError):
            codec.encode(Patch(0x1000000, 0, None))
        with self.assertRaises(GlitchError):
            codec.encode(Patch(0, 256, None))


if __name__ == "__main__":
    unittest.main()

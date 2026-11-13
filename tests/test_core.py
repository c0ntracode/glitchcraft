import unittest

import _path  # noqa: F401
from glitchcraft import cli, core


class FakePlatform:
    name = "fake"


class CoreTests(unittest.TestCase):
    def test_get_platform_unknown_says_unsupported(self):
        with self.assertRaises(core.GlitchError) as ctx:
            core.get_platform("nosuchplatform")
        self.assertIn("unsupported platform: nosuchplatform", str(ctx.exception))

    def test_register_roundtrip(self):
        p = FakePlatform()
        core.register(p)
        self.addCleanup(core.unregister, "fake")
        self.assertIs(core.get_platform("fake"), p)

    def test_patch_is_frozen_with_optional_compare(self):
        patch = core.Patch(address=0x8000, value=1, compare=None)
        with self.assertRaises(Exception):
            patch.value = 2
        self.assertIsNone(patch.compare)

    def test_cli_unknown_subcommand_exits_2_with_one_line_error(self):
        import contextlib
        import io

        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = cli.main(["bogus"])
        self.assertEqual(code, 2)
        self.assertEqual(len(err.getvalue().strip().splitlines()), 1)

    def test_cli_glitcherror_becomes_error_line(self):
        import contextlib
        import io

        def boom(args):
            raise core.GlitchError("bad thing")

        cli.COMMANDS["boom"] = boom
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = cli.main(["boom"])
        self.assertEqual(code, 2)
        self.assertEqual(err.getvalue().strip(), "error: bad thing")


if __name__ == "__main__":
    unittest.main()

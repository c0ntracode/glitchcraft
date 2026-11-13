# Emulator recipes (optional)

An emulator is what moves a result from Traced to Confirmed. Ask what the user has; do not assume one is installed. These were tried with `fceux` 2.6.6 on Linux.

## Test a patch without the emulator's code loader
1. `python3 scripts/gg.py patch-copy ROM OUT.nes CODE...` writes a patched copy (a compare mismatch is reported and not applied, as on hardware).
2. Run `OUT.nes` in the emulator and look at the effect. This tests what the patch does; it does not test that the emulator accepts the letters.

## Find a RAM address by diffing (user does this, pastes results)
Use the emulator's RAM search (FCEUX: Debug, Hex Editor or RAM Search; Mesen: Memory Viewer and Cheats). Snapshot, change the thing (lose a life), snapshot, and filter for values that changed by the expected amount. Then `gg.py xrefs ROM ADDR` shows what reads and writes it in the ROM.

## Scripted sampling with fceux
`fceux --sound 0 --loadlua probe.lua OUT.nes` runs a Lua script that can press buttons with `joypad.set`, read RAM with `memory.readbyte`, read the program counter with `memory.getregister("pc")`, write a log file, and end with `os.exit(0)`. Without a display add `xvfb-run -a` and `QT_QPA_PLATFORM=xcb`. a private script (not published) and a private script (not published) are a working example for Super Mario Bros.

Unverified: Game Genie code entry from the command line (fceux has no such option), and how other emulators load 8-letter codes.

## RetroArch cheat files: the game name stops at the first dot

To load a code without typing it, write `<cheat_settings_path>/<core library name>/<game name>.cht` (`cheats = 1`, `cheat0_desc`, `cheat0_code`, `cheat0_enable = true`) and set `apply_cheats_after_load = "true"` in a throwaway `--appendconfig`. RetroArch cuts the game name at the FIRST dot: `Sonic the Hedgehog (JUE) (V1.0).gg` is looked up as `Sonic the Hedgehog (JUE) (V1.cht`. A wrong file name fails silently (the cheat just does not apply). With `--verbose --log-file`, a correct name logs `[Cheats] Load game-specific cheatfile: ...` and `Applying cheat changes`; if those lines are missing, check the name first.

"""Genesis / Mega Drive Game Genie codec. Format notes and sources: references/genesis.md (our own implementation)."""
from glitchcraft.core import GlitchError, Patch

ALPHABET = "ABCDEFGHJKLMNPRSTVWXYZ0123456789"   # 32 characters, 5 bits each
# The 40 bits, left to right: capitals A-X are address bits 23..0, lowercase a-p are data bits 15..0.
LAYOUT = "ijklmnopIJKLMNOPABCDEFGHdefghabcQRSTUVWX"


def decode(code: str) -> Patch:
    letters = "".join(ch for ch in code.upper() if ch != "-")
    if len(letters) != 8 or code.count("-") > 1:
        raise GlitchError(f"a Genesis code is 8 characters (XXXX-XXXX), got {len(letters)}")
    letters = letters.replace("O", "0").replace("I", "1")
    for ch in letters:
        if ch not in ALPHABET:
            raise GlitchError(f"character {ch!r} is not a Genesis Game Genie character (valid: {ALPHABET})")
    bits = "".join(format(ALPHABET.index(ch), "05b") for ch in letters)
    address = data = 0
    for bit, label in zip(bits, LAYOUT):
        if label.isupper():
            address |= int(bit) << (23 - (ord(label) - ord("A")))
        else:
            data |= int(bit) << (15 - (ord(label) - ord("a")))
    return Patch(address, data, None)


def encode(patch: Patch) -> str:
    if patch.compare is not None:
        raise GlitchError("Genesis codes carry no compare value; remove it")
    if not 0 <= patch.address <= 0xFFFFFF:
        raise GlitchError(f"Genesis addresses are 24-bit ($000000-$FFFFFF), got ${patch.address:X}")
    if not 0 <= patch.value <= 0xFFFF:
        raise GlitchError(f"a Genesis code replaces a 16-bit word (0 to 65535), got {patch.value}")
    bits = "".join(
        str((patch.address >> (23 - (ord(label) - ord("A")))) & 1) if label.isupper()
        else str((patch.value >> (15 - (ord(label) - ord("a")))) & 1)
        for label in LAYOUT)
    chars = "".join(ALPHABET[int(bits[i:i + 5], 2)] for i in range(0, 40, 5))
    return chars[:4] + "-" + chars[4:]

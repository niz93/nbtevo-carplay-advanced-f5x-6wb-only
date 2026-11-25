import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HUD = (ROOT / "src" / "hud.h").read_text(encoding="utf-8")
SH = (ROOT / "carplay-advanced.sh").read_text(encoding="utf-8")
PS1 = (ROOT / "carplay-advanced.ps1").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
AGENTS = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
TX_DOC = (ROOT / "docs" / "MINI_6WB_TXCONTROL.md").read_text(encoding="utf-8")
FAMILY_DOC = (ROOT / "docs" / "MINI_F5X_CLUSTER_FAMILY.md").read_text(encoding="utf-8")


def function_body(source: str, signature: str) -> str:
    start = source.find(signature)
    if start < 0:
        raise AssertionError(f"function not found: {signature}")
    opening = source.find("{", start)
    if opening < 0:
        raise AssertionError(f"function body not found: {signature}")
    depth = 0
    for pos in range(opening, len(source)):
        if source[pos] == "{":
            depth += 1
        elif source[pos] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1:pos]
    raise AssertionError(f"unterminated function: {signature}")


class HudTransmissionTypeStaticTests(unittest.TestCase):
    def test_dsi_header_serializes_transmission_type_in_first_field(self):
        self.assertRegex(HUD, r"bool send\([^\n]*u32 txType = 0\)")
        header = re.search(
            r"p\.u32_\(g_client\);\s*"
            r"p\.u32_\(txType\);\s*// DSI transmissionType.*?"
            r"p\.u32_\(1\);\s*// variantTag = eTransmissionTXControl.*?"
            r"p\.u32_\(0\);\s*// variantValue stays 0",
            HUD,
            re.S,
        )
        self.assertIsNotNone(header)
        self.assertNotIn("g_hudTxControl", HUD)
        self.assertNotIn("p.u32_(txControl)", HUD)

    def test_primary_mirror_and_test_channel_use_selected_type(self):
        self.assertIn(
            "send(g_host, kFBlock, g_inst, fkt, kOpStartResultAck, d, n, g_hudTxType)",
            HUD,
        )
        self.assertIn(
            "send(mh, kFBlock, instOf(1 - slotOf(g_inst)), fkt, kOpStartResultAck, m, n, g_hudTxType)",
            HUD,
        )
        self.assertIn(
            "send(host, kFBlock, inst, (u16)fkt, kOpStartResultAck, d, k, g_hudTxType)",
            HUD,
        )

    def test_setting_accepts_only_zero_or_four_and_defaults_to_zero(self):
        self.assertIn('readNums("hud_tx", &txType, 1)', HUD)
        self.assertIn("(txType == 0 || txType == 4)", HUD)
        self.assertIn("g_hudTxType = 0;", HUD)

    def test_audio_master_volume_keeps_default_transmission_type(self):
        body = function_body(HUD, "bool volume(")
        self.assertRegex(body, r"\bsend\s*\(")
        self.assertNotIn("g_hudTxType", body)

    def test_bash_installer_validates_forwards_and_persists_the_switch(self):
        self.assertIn("--hud-tx)", SH)
        self.assertIn('case "$2" in 0|4) HUD_TX_FORCE=$2', SH)
        self.assertIn('args="$args --hud-tx $HUD_TX_FORCE"', SH)
        self.assertIn('echo "$HUD_TX_FORCE" > "$SETTINGS/hud_tx"', SH)
        self.assertIn("--hud-tx 0|4", SH)
        self.assertIn("DSI transmissionType", SH)
        self.assertNotIn("variantValue", SH)

    def test_powershell_installer_forwards_the_switch_and_describes_type(self):
        self.assertIn("'--hud-tx'", PS1)
        self.assertIn("if($hudTx){$opts+=' --hud-tx '+$hudTx}", PS1)
        self.assertIn("DSI transmissionType", PS1)
        self.assertNotIn("variantValue", PS1)

    def test_documentation_does_not_describe_hud_tx_as_variant_value(self):
        for source in (README, AGENTS, TX_DOC, FAMILY_DOC):
            self.assertNotRegex(
                source,
                r"(?i)(?:variantValue override|variantValue = hud_tx|variantValue carries hud_tx)",
            )
            self.assertIn("transmissionType", source)
        self.assertIn("variantValue` remains 0", README)
        self.assertIn("variantValue` remains 0", TX_DOC)


if __name__ == "__main__":
    unittest.main()

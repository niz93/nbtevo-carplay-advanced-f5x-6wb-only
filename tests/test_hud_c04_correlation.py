"""Offline DSI C04 response-correlation tests. No MOST client, vehicle or hardware is used."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_hud_init import HARNESS as BASE_HARNESS

ROOT = Path(__file__).resolve().parents[1]

INJECT_META = r"""
static void injectMeta(unsigned tx, unsigned tag, unsigned val, unsigned msgTag,
                       unsigned char fb, unsigned char inst, unsigned short src, unsigned short dst,
                       unsigned short fkt, unsigned char op, const unsigned char *d, unsigned n) {
  static unsigned char m[96];
  memset(m, 0, sizeof m);
  for (int i = 0; i < 4; i++) {
    m[i] = (unsigned char)(tx >> (8 * i));
    m[4 + i] = (unsigned char)(tag >> (8 * i));
    m[8 + i] = (unsigned char)(val >> (8 * i));
    m[24 + i] = (unsigned char)(msgTag >> (8 * i));
  }
  m[12] = (unsigned char)dst; m[13] = (unsigned char)(dst >> 8);
  m[14] = (unsigned char)src; m[15] = (unsigned char)(src >> 8);
  m[16] = fb; m[17] = inst; m[18] = (unsigned char)fkt; m[19] = (unsigned char)(fkt >> 8); m[20] = op;
  m[28] = (unsigned char)n;
  memcpy(m + 32, d, n);
  static char is[0x50];
  memset(is, 0, sizeof is);
  *(unsigned *)(is + 0x48) = kInfoMessage;
  *(unsigned *)(is + 0x08) = 32 + n;
  *(const unsigned char **)(is + 0x10) = m;
  onData(0, is);
}
"""

MAIN_COMMANDS = r"""
    } else if (!strcmp(cmd, "ask")) {
      int tx = 0, h = 5; sscanf(rest, "%d %d", &tx, &h);
      g_hudTxType = (u32)tx; g_askH = (u16)h; g_askOk = 0; g_askErr = 0; g_askW = g_askHt = 0;
      const u8 d[2] = { (u8)(h >> 8), (u8)h };
      call(0xC04, d, 2);
      printf("ASKED %d %d TX %u\n", tx, h, g_lastTxType);
    } else if (!strcmp(cmd, "reply")) {
      unsigned tx = 0, tag = 0, val = 0, msgTag = 0;
      unsigned fb = 0, inst = 0, src = 0, dst = 0, fkt = 0, op = 0; int k = 0;
      sscanf(rest, "%u %u %u %u %x %x %x %x %x %x %n",
             &tx, &tag, &val, &msgTag, &fb, &inst, &src, &dst, &fkt, &op, &k);
      unsigned char d[32]; unsigned n; hex(rest + k, d, &n);
      injectMeta(tx, tag, val, msgTag, (u8)fb, (u8)inst, (u16)src, (u16)dst, (u16)fkt, (u8)op, d, n);
      printf("REPLIED\n");
    } else if (!strcmp(cmd, "state")) {
      printf("STATE ask=%u ok=%d err=%d w=%u h=%u size5=%d size1f=%d\n",
             g_askH, g_askOk, g_askErr, g_askW, g_askHt, g_size5, g_size1f);
"""

HARNESS = BASE_HARNESS.replace("static void sCtor(", INJECT_META + "\nstatic void sCtor(")
if "static void injectMeta(" not in HARNESS:
    raise RuntimeError("could not extend HUD harness with metadata-aware DSI injection")
HARNESS = HARNESS.replace('    } else if (!strcmp(cmd, "night")) {', MAIN_COMMANDS + '    } else if (!strcmp(cmd, "night")) {')
if 'printf("STATE ask=' not in HARNESS:
    raise RuntimeError("could not add C04 harness commands")


class C04Correlation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cxx = os.environ.get("CXX") or shutil.which("clang++") or shutil.which("g++") or shutil.which("c++")
        if not cxx:
            raise unittest.SkipTest("C++ compiler not found (set CXX)")
        cls.tmp = tempfile.TemporaryDirectory(prefix="hud-c04-")
        src = Path(cls.tmp.name) / "c04.cpp"
        src.write_text(HARNESS)
        cls.exe = Path(cls.tmp.name) / "c04"
        subprocess.run([cxx, "-std=c++17", "-w", "-I", str(ROOT), "-I", str(ROOT / "src"),
                        "-o", str(cls.exe), str(src)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_lines(self, lines):
        r = subprocess.run([str(self.exe)], input="\n".join(lines) + "\n",
                           capture_output=True, text=True, check=True)
        return r.stdout.splitlines()

    def state(self, tx=4, reply=None):
        lines = ["ask %d 5" % tx]
        if reply:
            lines.append(reply)
        lines.append("state")
        out = self.run_lines(lines)
        return next(x for x in out if x.startswith("STATE ")), out

    def test_valid_mini_f5x_reply_matches_transport_endpoint_instance_and_handle(self):
        st, out = self.state(reply="reply 4 2 0 3735928559 82 00 0101 205e c04 d 00 05 00 78 00 48")
        self.assertIn("ASKED 4 5 TX 4", out)
        self.assertEqual(st, "STATE ask=5 ok=1 err=0 w=120 h=72 size5=1 size1f=0")

    def test_valid_seven_byte_6wb_reply_is_parsed_without_changing_mini_default(self):
        st, _ = self.state(tx=0, reply="reply 0 2 0 0 82 00 0101 205e c04 d 00 05 01 00 78 00 48")
        self.assertEqual(st, "STATE ask=5 ok=1 err=0 w=120 h=72 size5=1 size1f=0")

    def test_wrong_transport_type_is_ignored(self):
        st, _ = self.state(tx=4, reply="reply 0 2 0 1 82 00 0101 205e c04 d 00 05 00 78 00 48")
        self.assertIn("ok=0 err=0", st)

    def test_wrong_sender_is_ignored(self):
        st, _ = self.state(reply="reply 4 2 0 1 82 00 0102 205e c04 d 00 05 00 78 00 48")
        self.assertIn("ok=0 err=0", st)

    def test_wrong_variant_tag_or_value_is_ignored(self):
        for tag, val in ((1, 0), (2, 4), (2, 9)):
            with self.subTest(tag=tag, val=val):
                st, _ = self.state(reply="reply 4 %d %d 1 82 00 0101 205e c04 d 00 05 00 78 00 48" % (tag, val))
                self.assertIn("ok=0 err=0", st)

    def test_wrong_destination_instance_fblock_or_function_is_ignored(self):
        cases = [
            "reply 4 2 0 1 82 00 0101 2060 c04 d 00 05 00 78 00 48",
            "reply 4 2 0 1 82 02 0101 205e c04 d 00 05 00 78 00 48",
            "reply 4 2 0 1 24 00 0101 205e c04 d 00 05 00 78 00 48",
            "reply 4 2 0 1 82 00 0101 205e 204 d 00 05 00 78 00 48",
            "reply 4 2 0 1 82 00 205e 205e c04 d 00 05 00 78 00 48",
        ]
        for reply in cases:
            with self.subTest(reply=reply):
                st, _ = self.state(reply=reply)
                self.assertIn("ok=0 err=0", st)

    def test_wrong_handle_and_malformed_success_are_ignored(self):
        for reply in (
            "reply 4 2 0 1 82 00 0101 205e c04 d 00 06 00 78 00 48",
            "reply 4 2 0 1 82 00 0101 205e c04 d 00 05 00 78 00",
            "reply 4 2 0 1 82 00 0101 205e c04 d 00 05 00 78 00 48 00",
        ):
            with self.subTest(reply=reply):
                st, _ = self.state(reply=reply)
                self.assertIn("ok=0 err=0", st)

    def test_error_for_another_handle_does_not_abort_current_measurement(self):
        st, _ = self.state(reply="reply 4 2 0 1 82 00 0101 205e c04 9 00 06 41")
        self.assertIn("ok=0 err=0", st)

    def test_matching_error_ack_is_counted(self):
        st, _ = self.state(reply="reply 4 2 0 1 82 00 0101 205e c04 9 00 05 41")
        self.assertIn("ok=0 err=1", st)

    def test_message_tag_is_not_claimed_as_a_proven_transaction_id(self):
        # Issue #176's F60 experiment did not establish a reliable request-tag echo;
        # a matching endpoint/transport/handle remains the strongest proven filter.
        st_a, _ = self.state(reply="reply 4 2 0 1 82 00 0101 205e c04 d 00 05 00 78 00 48")
        st_b, _ = self.state(reply="reply 4 2 0 4294967295 82 00 0101 205e c04 d 00 05 00 78 00 48")
        self.assertIn("ok=1", st_a)
        self.assertIn("ok=1", st_b)


if __name__ == "__main__":
    unittest.main()

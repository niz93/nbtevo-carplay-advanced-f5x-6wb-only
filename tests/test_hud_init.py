"""src/hud.h's set-up of the HUDTerminal, built for the Mac with the DSI stream stubbed (every call the plugin sends is printed as
"<inst> <fkt> <bytes>", the cluster's answers are injected into onData):
  * the handles learnt from the BMW navigation's set-up (CreateInstance / FrameAddItem answers to another client), per terminal;
  * the picture buffer's size (ImageGetSize) and the picture box fitted to it;
  * the copies to the other terminal (82/02) with its own handles; hud_hide and the size question stay on the terminal drawn on;
  * texts: the distance's decimal comma, typographic characters and invisible format characters (Yandex Navi);
  * day / night from the HMI's CarPlay night mode, and the effect colour by day (hud_colour_day)."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
static char g_testHudTx[16] = "0";
static char g_testHudCmd[128] = "";
static unsigned g_lastTxType, g_lastVarTag, g_lastVarValue;
extern "C" {
int open(const char *path, int, ...) {
  if (strstr(path, "/carplaymenu/hud_tx")) return 99;
  if (!strcmp(path, "/dev/shmem/carplaymenu-hudcmd") && g_testHudCmd[0]) return 98;
  return -1;
}
long read(int fd, void *buf, unsigned long n) {
  const char *src = fd == 99 ? g_testHudTx : fd == 98 ? g_testHudCmd : 0;
  if (!src) return -1;
  unsigned long k = strlen(src); if (k > n) k = n;
  memcpy(buf, src, k); return (long)k;
}
long write(int, const void *, unsigned long n) { return (long)n; }
int close(int) { return 0; }
int unlink(const char *) { return 0; }
int usleep(unsigned) { return 0; }
}
#include "src/hud.h"
using namespace hud;
static unsigned g_id;
static int g_sizeMode;  // ImageGetSize: 0 no answer, 1 the shared MINI F5x form, 2 refused
static unsigned g_w, g_h;
// a message on the bus as the MOST service hands it to its clients
static void inject(unsigned char fb, unsigned char inst, unsigned short src, unsigned short dst, unsigned short fkt, unsigned char op,
                   const unsigned char *d, unsigned n) {
  static unsigned char m[96];
  memset(m, 0, sizeof m);
  m[4] = 2;
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
static void sCtor(void *, void *, void *, int, unsigned, unsigned, unsigned id, const void *, const void *, int) { g_id = id; }
static void sWrite(void *, const void *pv, unsigned n) {
  const unsigned char *p = (const unsigned char *)pv;
  if (g_id != kReqProcessMessage || n < 36) return;
  g_lastTxType = (unsigned)p[4] | (unsigned)p[5] << 8 | (unsigned)p[6] << 16 | (unsigned)p[7] << 24;
  g_lastVarTag = (unsigned)p[8] | (unsigned)p[9] << 8 | (unsigned)p[10] << 16 | (unsigned)p[11] << 24;
  g_lastVarValue = (unsigned)p[12] | (unsigned)p[13] << 8 | (unsigned)p[14] << 16 | (unsigned)p[15] << 24;
  unsigned char inst = p[21];
  unsigned short fkt = p[22] | p[23] << 8;
  unsigned dn = p[32] | p[33] << 8 | p[34] << 16 | (unsigned)p[35] << 24;
  printf("%02x %03x", inst, fkt);
  for (unsigned i = 0; i < dn && 36 + i < n; i++) printf(" %02x", p[36 + i]);
  printf("\n");
  const unsigned char *d = p + 36;
  if (fkt == 0xC04 && dn == 2 && inst == g_inst) {
    if (g_sizeMode == 1) {
      const unsigned char a[6] = { d[0], d[1], (unsigned char)(g_w >> 8), (unsigned char)g_w, (unsigned char)(g_h >> 8), (unsigned char)g_h };
      inject(0x82, inst, g_host, g_self, fkt, 0xD, a, 6);
    } else if (g_sizeMode == 2) {
      const unsigned char e[4] = { d[0], d[1], 5, 0 };
      inject(0x82, inst, g_host, g_self, fkt, 9, e, 4);
    }
  }
  if (fkt == 0xC04 && dn == 3 && inst == g_inst && g_sizeMode) {  // the BMW 6WB form: refused by the MINI F5x panel
    const unsigned char e[4] = { d[0], d[1], 5, 0 };
    inject(0x82, inst, g_host, g_self, fkt, 0xF, e, 4);
  }
}
static int sSend(void *, int) { return 0; }
static void sDtor(void *) {}
static void logLine(const char *m) { printf("# %s\n", m); }
static void hex(const char *s, unsigned char *d, unsigned *n) {
  *n = 0;
  for (const char *q = s; *q;) { while (*q == ' ') q++; if (!*q) break; char *e; d[(*n)++] = (unsigned char)strtoul(q, &e, 16); q = e; }
}
static void boxLine() {
  if (g_boxMode == kBoxFit) printf("BOX fit %d %d %d %d\n", g_box.x0, g_box.y0, g_box.x1, g_box.y1);
  else printf("BOX %s\n", g_boxMode == kBoxMini ? "mini" : "6wa");
}
// stdin, one command a line:
//   setup <inst> <hex>      a CreateInstance (200) or FrameAddItem (22B) answer of the cluster to the navigation: "<fkt> <bytes>"
//   take                    the worker's step: a completed set-up used
//   size <mode> <w> <h>     measureBox with that answer; then the box
//   box <mode 0/1/2>        the box mode before (6wa / mini / fit)
//   mirror <0/1>            copies to the other terminal on / off
//   draw                    a picture: "drawManeuver" of a straight arrow with texts
//   text <h> <utf8 hex>     setText
//   night <hex>             the HMI's CarPlaySetNightMode payload; then the effect colour
//   comma <0/1>, hide <h>, fxday <n>, handles
int main() {
  g_log = logLine;
  S.streamCtor = sCtor; S.streamWrite = sWrite; S.streamSend = sSend; S.streamDtor = sDtor;
  static char cli[0x400];
  g_cli = cli; g_attached = 1; g_registered = 1; g_client = 7; g_self = 0x205e; g_host = 0x0101; g_hostOf[0] = 0x0101; g_hostOf[1] = 0x0102;
  g_concave = true;
  char line[512];
  while (fgets(line, sizeof line, stdin)) {
    line[strcspn(line, "\n")] = 0;
    char cmd[16] = ""; int a = 0;
    sscanf(line, "%15s %d", cmd, &a);
    const char *rest = strchr(line, ' ') ? strchr(line, ' ') + 1 : "";
    if (!strcmp(cmd, "setup")) {
      unsigned inst = 0, fkt = 0; int k = 0;
      sscanf(rest, "%x %x %n", &inst, &fkt, &k);
      unsigned char d[32]; unsigned n; hex(rest + k, d, &n);
      inject(0x82, (unsigned char)inst, 0x0101, 0x201f, (unsigned short)fkt, 0xD, d, n);
    } else if (!strcmp(cmd, "take")) takeLearnt();
    else if (!strcmp(cmd, "size")) { int w = 0, h = 0; sscanf(rest, "%d %d %d", &g_sizeMode, &w, &h); g_w = w; g_h = h; measureBox(); boxLine(); }
    else if (!strcmp(cmd, "box")) g_boxMode = a;
    else if (!strcmp(cmd, "mirror")) g_mirror = a;
    else if (!strcmp(cmd, "comma")) g_comma = a;
    else if (!strcmp(cmd, "hide")) g_hide[g_nHide++] = (unsigned short)a;
    else if (!strcmp(cmd, "fxday")) g_fxDay = a;
    else if (!strcmp(cmd, "handles")) printf("HANDLES %u %u %u %u %u %u %u\n", hFrame, hStreet, hDist, hUnit, hBufA, hBufB, hBar);
    else if (!strcmp(cmd, "draw")) {
      static Guide g; memset(&g, 0, sizeof g); g.active = true; g.type = 3; copyS(g.road, sizeof g.road, "Main St");
      drawManeuver(g, "1.5", "km");
    } else if (!strcmp(cmd, "text")) {
      unsigned h = 0; int k = 0; sscanf(rest, "%x %n", &h, &k);
      unsigned char d[128]; unsigned n; hex(rest + k, d, &n); d[n] = 0;
      setText((unsigned short)h, (const char *)d);
    } else if (!strcmp(cmd, "readtx")) {
      snprintf(g_testHudTx, sizeof g_testHudTx, "%d", a);
      chooseBox();
      const u8 d[3] = { 0, 1, 1 };
      call(0x204, d, 3, true);
      printf("DSI %u/%u/%u\n", g_lastTxType, g_lastVarTag, g_lastVarValue);
    } else if (!strcmp(cmd, "cmdtx")) {
      g_hudTxType = (u32)a;
      strcpy(g_testHudCmd, "204 000101\n");
      runCmds();
      printf("DSI %u/%u/%u\n", g_lastTxType, g_lastVarTag, g_lastVarValue);
      g_testHudCmd[0] = 0;
    } else if (!strcmp(cmd, "voltx")) {
      g_hudTxType = (u32)a;
      g_amHost = 0x0101;
      volume(1);
      printf("DSI %u/%u/%u\n", g_lastTxType, g_lastVarTag, g_lastVarValue);
    } else if (!strcmp(cmd, "night")) {
      unsigned char d[16]; unsigned n; hex(rest, d, &n);
      inject(0x24, 0x70, 0x2000, 0x2010, 0xCD7, 6, d, n);
      printf("NIGHT %d COLOUR %u\n", g_night, toneColour(2));
    }
    fflush(stdout);
  }
}
'''
# shared MINI F5x panel set-up, captured on F54 (2026-11-13): CreateInstance index 1, then FrameAddItem
MINI_F5X_MODELS = ('F54', 'F55', 'F56', 'F57', 'F60')
MINI_F5X = ['22b 00 01 00 05 01 00 04', '22b 00 01 00 06 01 00 04', '22b 00 01 00 07 01 00 04', '22b 00 01 00 08 01 00 04',
       '22b 00 01 00 09 01 00 04', '22b 00 01 00 0a 01 00 04', '22b 00 01 00 02 01 00 03', '22b 00 01 00 04 01 00 02',
       '22b 00 01 00 03 01 00 05', '22b 00 01 00 16 0f 00 06']
# a made-up cluster numbering its instances otherwise (as the F25 X3 does: texts 0x0c / 0x12 / 0x0f, issue #9)
OTHER = ['22b 00 20 00 15 01 00 04', '22b 00 20 00 16 01 00 04', '22b 00 20 00 0c 01 00 03', '22b 00 20 00 0f 01 00 02',
         '22b 00 20 00 12 01 00 05']


class HudInit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cxx = os.environ.get('CXX') or shutil.which('clang++') or shutil.which('g++') or shutil.which('c++')
        if not cxx:
            raise unittest.SkipTest('C++ compiler not found (set CXX)')
        cls.tmp = tempfile.TemporaryDirectory(prefix='hudinit-')
        src = Path(cls.tmp.name) / 'h.cpp'
        src.write_text(HARNESS)
        cls.exe = Path(cls.tmp.name) / 'h'
        subprocess.run([cxx, '-std=c++17', '-w', '-I', str(ROOT), '-I', str(ROOT / 'src'), '-o', str(cls.exe), str(src)],
                       check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_lines(self, lines):
        r = subprocess.run([str(self.exe)], input='\n'.join(lines) + '\n', capture_output=True, text=True, check=True)
        return r.stdout.splitlines()

    def calls(self, out):
        return [l for l in out if not l.startswith(('#', 'BOX', 'HANDLES', 'NIGHT'))]

    def test_shared_mini_f5x_set_up_keeps_the_shared_panel_handles(self):
        out = self.run_lines(['setup 0 200 00 01 00 01'] + ['setup 0 ' + a for a in MINI_F5X] + ['take', 'handles'])
        self.assertIn('HANDLES 1 2 3 4 5 6 22', out)

    def test_other_numbering_is_drawn_on(self):
        out = self.run_lines(['setup 0 ' + a for a in OTHER] + ['take', 'handles', 'draw'])
        self.assertIn('HANDLES 32 12 18 15 21 22 0', out)
        calls = self.calls(out)
        self.assertIn('00 210 00 0c 00 00 4d 00 61 00 69 00 6e 00 20 00 53 00 74 00 00', calls)   # the street on 0x0c
        self.assertIn('00 204 00 20 01', calls)                                                    # the frame 0x20 visible
        self.assertTrue(any(c.startswith('00 21d 00 15') for c in calls))                          # the picture into 0x15 (B was on show)

    def test_a_set_up_on_82_02_starts_copies_with_its_handles(self):
        out = self.run_lines(['setup 0 ' + a for a in MINI_F5X] + ['setup 2 ' + a for a in OTHER] + ['take', 'draw'])
        calls = self.calls(out)
        self.assertIn('# CarPlayMenu: HUD: copies to HUDTerminal 82/02 (the navigation set it up; hud_inst "0" stops them)', out)
        self.assertIn('00 210 00 02 00 00 4d 00 61 00 69 00 6e 00 20 00 53 00 74 00 00', calls)
        self.assertIn('02 210 00 0c 00 00 4d 00 61 00 69 00 6e 00 20 00 53 00 74 00 00', calls)   # its street: 0x0c
        self.assertIn('02 204 00 20 01', calls)                                                    # its frame: 0x20
        self.assertIn('00 20e 00 06 00 05', calls)
        self.assertIn('02 20e 00 16 00 15', calls)                                                 # both handles of 20E mapped

    def test_the_frames_bar_is_hidden_on_both_terminals(self):
        out = self.calls(self.run_lines(['setup 0 ' + a for a in MINI_F5X] + ['setup 2 ' + a for a in OTHER + ['22b 00 20 00 30 0f 00 06']] +
                                        ['take', 'draw']))
        self.assertIn('00 204 00 16 00', out)
        self.assertIn('02 204 00 30 00', out)

    def test_hide_and_size_question_stay_on_the_terminal_drawn_on(self):
        out = self.run_lines(['setup 2 ' + a for a in OTHER] + ['take', 'hide 21', 'draw', 'size 1 120 72'])
        calls = self.calls(out)
        self.assertIn('00 204 00 15 00', calls)
        self.assertFalse(any(c.startswith('02 204 00 15 00') for c in calls))
        self.assertFalse(any(c.startswith('02 c04') for c in calls))

    def test_sizes(self):
        cases = {(1, 120, 72): 'BOX mini',                 # shared MINI F5x panel, car-verified on F54
                 (1, 126, 77): 'BOX fit 36 16 89 69',      # PR #13's F30 6WB buffer (it verified 35 15 85 65 by hand)
                 (1, 199, 129): 'BOX 6wa',                 # the F20 (NBT-AAD's 6WA box)
                 (1, 0, 0): 'BOX mini',                    # not an instance yet: the box stays (mini before)
                 (2, 0, 0): 'BOX mini',                    # refused: stays
                 (0, 0, 0): 'BOX mini'}                    # no answer: stays
        for (mode, w, h), want in cases.items():
            out = self.run_lines(['box 1', 'size %d %d %d' % (mode, w, h)])
            self.assertEqual(out[-1], want, (mode, w, h, out))

    def test_box_mapping_on_the_wire(self):
        out = self.calls(self.run_lines(['box 1', 'size 1 126 77', 'draw']))
        pts = [c for c in out if ' 21d ' in c]
        self.assertTrue(pts)
        for c in pts:
            b = [int(x, 16) for x in c.split()[2:]]
            xy = [(b[6 + 4 * i] << 8 | b[7 + 4 * i], b[8 + 4 * i] << 8 | b[9 + 4 * i]) for i in range(b[5])]
            for x, y in xy:
                self.assertTrue(30 <= x <= 95 and 10 <= y <= 75, (x, y))

    def test_texts(self):
        out = self.calls(self.run_lines([
            'text 3 31 2c 35',                                     # "1,5" in the distance: "1.5"
            'comma 1', 'text 3 31 2c 35', 'comma 0',               # hud_comma: the comma
            'text 2 41 2c 42',                                     # a comma in the street: a space
            'text 2 d1 83 d0 bb 2e c2 a0 d0 9b e2 80 8e d0 b5',    # "ул.<NBSP>Л<LRM>е": NBSP a space, LRM left out
            'text 2 41 e2 80 93 42 e2 80 9c 43 e2 80 9d',          # en dash, quotes
        ]))
        self.assertEqual(out, ['00 210 00 03 00 00 31 00 2e 00 35 00 00',
                               '00 210 00 03 00 00 31 00 2c 00 35 00 00',
                               '00 210 00 02 00 00 41 00 20 00 42 00 00',
                               '00 210 00 02 00 04 43 04 3b 00 2e 00 20 04 1b 04 35 00 00',
                               '00 210 00 02 00 00 41 00 2d 00 42 00 22 00 43 00 22 00 00'])

    def test_day_and_night(self):
        out = self.run_lines(['night 00 01 01', 'night 00 01 00', 'fxday 2', 'night 00 01 00', 'night 00 01 01'])
        self.assertEqual([l for l in out if l.startswith('NIGHT')],
                         ['NIGHT 1 COLOUR 5', 'NIGHT 0 COLOUR 5', 'NIGHT 0 COLOUR 2', 'NIGHT 1 COLOUR 5'])

    def test_hud_transmission_type_is_validated_and_serialized(self):
        self.assertIn('DSI 4/1/0', self.run_lines(['readtx 4']))
        self.assertIn('DSI 0/1/0', self.run_lines(['readtx 0']))
        self.assertIn('DSI 0/1/0', self.run_lines(['readtx 9']))  # invalid values fail closed to the legacy default

    def test_hud_test_channel_uses_the_selected_transmission_type(self):
        self.assertIn('DSI 4/1/0', self.run_lines(['cmdtx 4']))
        self.assertIn('DSI 0/1/0', self.run_lines(['cmdtx 0']))

    def test_audio_master_volume_keeps_transmission_type_zero(self):
        self.assertIn('DSI 0/1/0', self.run_lines(['voltx 4']))


if __name__ == '__main__':
    unittest.main()

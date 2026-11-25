"""src/hudhandles.h, built for the host: the HUDTerminal handles learnt from the BMW navigation's FrameAddItem answers.
The first case is the shared MINI F5x panel's set-up, captured on F54 on 2026-11-13; F54/F55/F56/F57/F60 are one panel family."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
HARNESS = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include "hudhandles.h"
// stdin: "c <hex bytes>" a CreateInstance answer, "a <hex bytes>" a FrameAddItem answer, "p <text>" parse, "m" print the map
int main() {
  hudh::Learner L; L.reset(); char line[256];
  while (fgets(line, sizeof line, stdin)) {
    line[strcspn(line, "\n")] = 0;
    unsigned char d[32]; unsigned n = 0;
    if (line[0] == 'c' || line[0] == 'a') for (char *q = line + 1; *q && n < 32;) { while (*q == ' ') q++; if (!*q) break; d[n++] = (unsigned char)strtol(q, &q, 16); }
    if (line[0] == 'c') L.created(d, n);
    else if (line[0] == 'a') { if (L.added(d, n)) printf("COMPLETE\n"); }
    else if (line[0] == 'm') {
      char t[64]; hudh::format(L.m, t, sizeof t); printf("MAP %d %s", L.done, t); printf("FAMILY %u\n", L.family());
    } else if (line[0] == 'p') {
      hudh::Map m; bool ok = hudh::parse(line + 2, m); char t[64] = "\n"; if (ok) hudh::format(m, t, sizeof t); printf("PARSE %d %s", ok, t);
    }
    fflush(stdout);
  }
}
'''
# Shared MINI F5x panel fixture; captured on F54 (frame 01 = layout Tf1, 0B = Tf2, 10 = Tf3).
MINI_F5X_MODELS = ('F54', 'F55', 'F56', 'F57', 'F60')
MINI_F5X = ['00 01 00 05 01 00 04', '00 01 00 06 01 00 04', '00 01 00 07 01 00 04', '00 01 00 08 01 00 04', '00 01 00 09 01 00 04',
       '00 01 00 0a 01 00 04', '00 01 00 02 01 00 03', '00 01 00 04 01 00 02', '00 01 00 03 01 00 05', '00 01 00 16 0f 00 06',
       '00 0b 00 0e 01 00 04', '00 0b 00 0f 01 00 04', '00 0b 00 0d 01 00 02', '00 0b 00 0c 01 00 05',
       '00 10 00 12 01 00 02', '00 10 00 11 01 00 05', '00 10 00 15 0f 00 06', '00 10 00 13 01 00 04', '00 10 00 14 01 00 04']


class HudHandlesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        src = Path(cls.tmp.name) / 'h.cpp'; src.write_text(HARNESS)
        cls.exe = Path(cls.tmp.name) / 'h'
        cxx = os.environ.get('CXX') or shutil.which('clang++') or shutil.which('g++') or shutil.which('c++')
        if not cxx:
            raise unittest.SkipTest('C++ compiler not found (set CXX)')
        subprocess.run([cxx, '-std=c++11', '-I', str(SRC), '-o', str(cls.exe), str(src)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_lines(self, lines):
        r = subprocess.run([str(self.exe)], input='\n'.join(lines) + '\n', capture_output=True, text=True, check=True)
        return r.stdout.splitlines()

    def test_f54_capture_fixture_is_reused_for_user_confirmed_f5x_family(self):
        # F54 is the source capture vehicle; the other four model names intentionally use the same panel contract.
        for model in MINI_F5X_MODELS:
            with self.subTest(model=model):
                out = self.run_lines(['c 00 01 00 01'] + ['a ' + a for a in MINI_F5X] + ['m'])
                self.assertEqual(out.count('COMPLETE'), 1)
                self.assertEqual(out.index('COMPLETE'), 0)                   # complete at the distance text, before the bargraph
                self.assertEqual(out[-2:], ['MAP 1 1 2 3 4 5 6 22', 'FAMILY 1']) # shared panel handles, bar 0x16

    def test_non_mini_f5x_cluster_gets_its_own_handles(self):
        # the same set-up on a cluster that numbers its instances otherwise, the unit before the street
        other = ['00 20 00 31 01 00 04', '00 20 00 32 01 00 04', '00 20 00 33 01 00 04', '00 20 00 41 01 00 02', '00 20 00 40 01 00 03',
                 '00 20 00 42 01 00 05', '00 20 00 50 0f 00 06', '00 21 00 60 01 00 04', '00 21 00 61 01 00 03']
        out = self.run_lines(['a ' + a for a in other] + ['m'])
        self.assertEqual(out[-2], 'MAP 1 32 64 66 65 49 50 80')

    def test_incomplete_frame_is_not_used(self):
        out = self.run_lines(['a ' + a for a in MINI_F5X[:8]] + ['m'])       # no distance text yet
        self.assertNotIn('COMPLETE', out); self.assertTrue(out[-2].startswith('MAP 0 '))

    def test_a_new_set_up_starts_over(self):
        out = self.run_lines(['a ' + a for a in MINI_F5X] + ['c 00 02 00 0b', 'm', 'c 00 01 00 01', 'm'])
        self.assertEqual(out[-4], 'MAP 1 1 2 3 4 5 6 22')              # index 2: the same set-up goes on
        self.assertEqual(out[-2], 'MAP 0 0 0 0 0 0 0 0')               # index 1: everything again

    def test_frames_11_to_13_take_the_guiding_icon_not_the_road_icon(self):
        # the navigation's name table for frame 11: Coming_Road, Distance, Unit, Road_Icon x2, Next_Maneuver_Arrow x2, Guiding_Icon x2,
        # Guiding_Arrow x2, Lane_Guiding x2, CCP x2, Bargraph (handles made up: 0x40 the frame, 0x41.. in that order)
        kinds = [3, 5, 2] + [4] * 12 + [6]
        tf11 = ['a 00 40 00 %02x 01 00 %02x' % (0x41 + i, k) for i, k in enumerate(kinds)]
        out = self.run_lines(tf11[:5] + ['m'])                             # two pictures (the road icons): not complete yet
        self.assertNotIn('COMPLETE', out)
        out = self.run_lines(tf11 + ['m'])
        self.assertEqual(out.count('COMPLETE'), 1)
        self.assertEqual(out[-2:], ['MAP 1 64 65 66 67 72 73 80', 'FAMILY 11'])   # street 41, distance 42, unit 43, picture 48/49

    def test_file_text(self):
        out = self.run_lines(['p 1 2 3 4 5 6 22', 'p 32 64 66 65 49 50', 'p 1 2 3 4 5 5 0', 'p 1 2 3', 'p 0 2 3 4 5 6 7', 'p junk'])
        self.assertEqual(out, ['PARSE 1 1 2 3 4 5 6 22', 'PARSE 1 32 64 66 65 49 50 0', 'PARSE 0 ', 'PARSE 0 ', 'PARSE 0 ', 'PARSE 0 '])


if __name__ == '__main__':
    unittest.main()

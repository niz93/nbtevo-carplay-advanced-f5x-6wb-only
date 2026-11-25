// hudhandles.h — which HUDTerminal instance is which, learnt from the BMW navigation's own set-up.
//
// The cluster gives out the handles: at start the navigation creates its instances (200 CreateInstance, answer [index u16][handle u16])
// and puts them into frames (22B FrameAddItem, answer [frame u16][item u16][u8][kind u16]). The handle numbers are the cluster's
// choice, so they differ between clusters (the F25 X3's texts are on 0x0C/0x12/0x0F, issue #9; the shared MINI F5x panel's on 2/3/4, captured on F54); what an instance
// is shows in the kind the navigation adds it with (MINI F5x shared panel, captured on F54 in the car log of 2026-11-13: 22 creations, frames 01, 0B and 10):
//     kind 4  a picture: the first two of a frame are the guiding icon's two buffers (then decreasing arrow, lane guidance)
//     kind 3  the street text      kind 5  the distance text      kind 2  the unit text      kind 6  the bargraph
// The navigation (NavNBTEvoController) has two families of layouts, chosen by the cluster: frames 1-3 (instances "TopFrame",
// "1.GuidingIcon", "2.GuidingIcon"...; the MINI F5x shared panel, BMW F-series mid clusters, BMW 6WB) and frames 11-13 ("Top_Frame_11",
// "Coming_Road_11_1", "Distance_11_1", "Unit_11_1", "Road_Icon_11_1/2", "Next_Maneuver_Arrow_11_1/2", "Guiding_Icon_11_1/2"...; the
// full-display clusters). In 1-3 the pictures are added before the texts and the first two are the guiding icon; in 11-13 the texts
// come first and the guiding icon is the fifth and sixth picture, by the navigation's name table. The 11-13 reading was NOT tried in
// a car, and the navigation draws only bitmaps on those frames.
// The first frame the navigation fills is the one hud.h draws in (layout Tf1 or 11).
// No dependencies: hud.h includes it, tests/test_hud_handles.py builds it for the host.
#pragma once

namespace hudh {

struct Map {
  unsigned short frame, street, dist, unit, bufA, bufB, bar;
};
inline Map defaults() {
  Map m = { 1, 2, 3, 4, 5, 6, 0 };
  return m;
}
inline bool same(const Map &a, const Map &b) {
  return a.frame == b.frame && a.street == b.street && a.dist == b.dist && a.unit == b.unit && a.bufA == b.bufA &&
         a.bufB == b.bufB && a.bar == b.bar;
}
inline unsigned short be16(const unsigned char *p) {
  return (unsigned short)(p[0] << 8 | p[1]);
}

struct Learner {
  Map m;
  unsigned char pics;
  bool have, done, textFirst;  // textFirst: a text came before any picture = frames 11-13

  void reset() {
    m.frame = m.street = m.dist = m.unit = m.bufA = m.bufB = m.bar = 0;
    pics = 0;
    have = done = textFirst = false;
  }
  bool complete() const {
    return m.frame && m.street && m.dist && m.unit && m.bufA && m.bufB;
  }
  unsigned family() const {
    return textFirst ? 11 : 1;
  }

  // a CreateInstance answer: index 1 = the navigation sets everything up again (a cluster or head unit restart)
  void created(const unsigned char *d, unsigned n) {
    if (n >= 4 && be16(d) == 1)
      reset();
  }

  // a FrameAddItem answer; true exactly once: the map is complete now (the bargraph, added last, may still follow)
  bool added(const unsigned char *d, unsigned n) {
    if (n < 7)
      return false;
    unsigned short f = be16(d), item = be16(d + 2), kind = be16(d + 5);
    if (!f || !item)
      return false;
    if (!have) {
      m.frame = f;
      have = true;
    }
    if (f != m.frame)  // the other layouts' frames
      return false;
    switch (kind) {
      case 4: {
        unsigned char a = textFirst ? 4 : 0;  // which pictures are the guiding icon's two buffers
        if (pics == a)
          m.bufA = item;
        else if (pics == a + 1)
          m.bufB = item;
        if (pics < 255)
          pics++;
        break;
      }
      case 3:
        if (!pics)
          textFirst = true;
        if (!m.street)
          m.street = item;
        break;
      case 5:
        if (!pics)
          textFirst = true;
        if (!m.dist)
          m.dist = item;
        break;
      case 2:
        if (!pics)
          textFirst = true;
        if (!m.unit)
          m.unit = item;
        break;
      case 6:
        if (!m.bar)
          m.bar = item;
        break;
    }
    if (!done && complete()) {
      done = true;
      return true;
    }
    return false;
  }
};

// "frame street dist unit bufA bufB bar" in decimal, as hud.h keeps it in the plugin's folder for the senders that start later
inline unsigned format(const Map &m, char *o, unsigned cap) {
  const unsigned short v[7] = { m.frame, m.street, m.dist, m.unit, m.bufA, m.bufB, m.bar };
  unsigned k = 0;
  for (unsigned i = 0; i < 7; i++) {
    char t[6];
    unsigned n = 0;
    unsigned short x = v[i];
    do {
      t[n++] = (char)('0' + x % 10);
      x = (unsigned short)(x / 10);
    } while (x);
    if (k + n + 2 > cap)
      return 0;
    while (n)
      o[k++] = t[--n];
    o[k++] = i == 6 ? '\n' : ' ';
  }
  o[k] = 0;
  return k;
}
// the file's text (also written by hand): six or seven numbers, decimal or 0x hex; the six must be non-zero and different
inline bool parse(const char *s, Map &m) {
  unsigned short v[7];
  unsigned k = 0;
  for (const char *q = s; *q && k < 7;) {
    if (*q >= '0' && *q <= '9') {
      unsigned x = 0;
      if (q[0] == '0' && (q[1] == 'x' || q[1] == 'X')) {
        for (q += 2;; q++) {
          int h = *q >= '0' && *q <= '9'   ? *q - '0'
                  : *q >= 'a' && *q <= 'f' ? *q - 'a' + 10
                  : *q >= 'A' && *q <= 'F' ? *q - 'A' + 10
                                           : -1;
          if (h < 0)
            break;
          x = x << 4 | (unsigned)h;
          if (x > 0xffff)
            return false;
        }
      } else
        while (*q >= '0' && *q <= '9') {
          x = x * 10 + (unsigned)(*q++ - '0');
          if (x > 0xffff)
            return false;
        }
      v[k++] = (unsigned short)x;
    } else
      q++;
  }
  if (k < 6)
    return false;
  for (unsigned i = 0; i < 6; i++)
    if (!v[i])
      return false;
  for (unsigned i = 0; i < 6; i++)
    for (unsigned j = i + 1; j < 6; j++)
      if (v[i] == v[j])
        return false;
  m.frame = v[0];
  m.street = v[1];
  m.dist = v[2];
  m.unit = v[3];
  m.bufA = v[4];
  m.bufB = v[5];
  m.bar = k > 6 ? v[6] : 0;
  return true;
}

}  // namespace hudh

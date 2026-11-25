# MINI_F5X shared instrument-panel family

## Scope

The user confirms that MINI F54, F55, F56, F57 and F60 share the same physical digital instrument-panel family. This project records that family as **MINI_F5X**.

This is a statement about the physical panel family. It is not proof that the five chassis use identical:

- HMI software or firmware;
- NBT Evo generation, coding or feature configuration;
- MOST endpoint, DSI transport type, terminal instance or native handle setup;
- navigation application, route-guidance source or display layout.

The project must keep BMW F-series **6WB** as a separate cluster/layout profile. The g_6wb flag in src/hud.h refers to BMW 6WB, not the shared MINI panel. External issue #176 uses the wording “MINI 6WB” in a MINI F60 context; do not use that phrase to merge the two profiles.

## Evidence status

**Important repository correction:** this local checkout does not contain the raw evidence directory previously referenced in project notes. Neither evidence/original-captures-2026-11-25/ nor EVIDENCE-MANIFEST.json is present in this working tree. Capture names and summarized results below come from earlier project records; the raw capture bytes and original hashes must be re-imported before this clone can claim to preserve or independently re-audit them.

The current dossier distinguishes user-confirmed family information, real-vehicle observations, source-derived behavior, host simulations and unresolved assumptions.

## F54 baseline: HMI ID5_1703-490-1650ZD Build 139

**Status: VEHICLE-OBSERVED on the tested F54 only.**

The inherited AGENTS.md record documents the F54 test sessions:

- 2026-11-11/12: full-width CarPlay output; controller knob tilts, held-tilt repeat, rotation and press; touchpad navigation and gestures; MOST HUD pictures and route guidance; boot hook and recovery links.
- 2026-11-13: settings submenus, persistence and restart behavior; boot-loop guard; Apple Maps zoom; polygon drawing; HUD fill/blink effects with a simulated route.
- The test baseline is specific to the F54 and the HMI build above. It must not be presented as a direct test of F55, F56, F57 or F60.

### F54 native handle map

The recorded F54 setup contains 22 instance creations and frames 01, 0B and 10. The learned handles are:

| Handle | Role |
|---:|---|
| 1 | Panel |
| 2 | Unit |
| 3 | Street |
| 4 | Distance |
| 5 / 6 | Double-buffered maneuver picture |
| 0x16 | Bargraph |

The F54 C04 ImageGetSize request uses the handle-only payload. The alternate BMW 6WB form with an extra 0x01 byte was rejected on the tested F54 terminal with an invalid-length ErrorAck.

### F54 measured surface sizes

| Handle | Width × height |
|---|---:|
| 0x01 / 0x10 | 408 × 116 |
| 0x02 | 250 × 27 |
| 0x03 / 0x11 | 69 × 24 |
| 0x04 | 33 × 21 |
| 0x05–0x08, 0x0E, 0x0F | 120 × 72 |
| 0x09 / 0x0A | 184 × 17 |
| 0x0B | 227 × 72 |
| 0x0C | 62 × 22 |
| 0x0D | 33 × 22 |
| 0x12 | 32 × 21 |
| 0x13 / 0x14 | 250 × 116 |
| 0x15 / 0x16 | 172 × 116 |
| 0x17 | 39 × 39 |

The MINI picture box is mapped to approximately (35,15)-(85,65) for a 120 × 72 buffer. The recorded F54 night palette is route white (4), orange (5) and grey (3). The tested potentiometer calls did not expose a working distance bar.

## F56 passive OEM navigation capture

**Status: VEHICLE-OBSERVED / PARTIAL.**

The earlier capture is identified as mini-f56-native-nav-20261125-040320-116770.txt. The summarized 60-second window on HUDTerminal 82/00 contains 215 OEM messages:

| Function | Count |
|---|---:|
| 0x204 | 31 |
| 0x21D | 167 |
| 0x20E | 14 |
| 0x227 | 3 |

The observed handles include 1–8 and 0x16; drawing uses handles 5, 6 and 7. This capture window does not include 0x200 CreateInstance, 0x22B FrameAddItem or 0xC04 ImageGetSize. The handle map was carried over from an earlier start. The returned log excludes 0x210 street-text payloads.

This is OEM drawing/visibility evidence, not a complete native setup, handle-allocation or text-payload capture.

## F56 HUD Probe and TX=4 result

### Earlier probe failures

The historical reports hud-probe-v1.3.0-20261125-041729-717486.txt and hud-probe-v1.3.0-20261125-042222-571911.txt each show 128 C04 requests and 128 ErrorAck 0x41 responses across handles 0x01–0x40 and two payload forms.

Neither report preserves the DSI transmissionType field. The visual result was mini: cluster n. These reports establish that those particular requests were rejected; they do not establish the cause or prove that the later TX=4 path would fail.

### Later F56 vehicle-observed result

**Status: VISIBLE ROUTE GUIDANCE OBSERVED WITH transmissionType 4; PROTOCOL COMPLETENESS OPEN.**

The later 2026-11-25 F56 test summary records:

- 60-second capture and 26 new log lines;
- HUD transmissionType 4;
- HUDTerminal 82/00;
- maneuver distances 160 m, 170 m and 10 m;
- seven of seven files in the historical evidence check passed SHA-256 verification;
- a user-supplied photo showing the 170 m right-turn prompt on the CarPlay center display and the instrument cluster together;
- a companion photo showing a 10 m left-turn prompt.

This is a real visible result on the tested F56. It is not a complete DSI protocol proof.

The same run summary does not contain a positive C04 ImageGetSize response, measured picture-buffer dimensions or a picture-buffer response trace. A standalone hud_guidance.txt was absent, hud_debug was not enabled, and no controlled TX=0 comparison was performed. The tested librghook-most.so was recorded with hash prefix d0e448…; the complete tested binary and evidence archive are not present in this checkout.

See the [real F56 vehicle photographs and provenance](images/README.md) and the [technical report gallery](MINI_F5X_TECHNICAL_RESEARCH.md#vehicle-photo-evidence). These photographs document visible output only.

## Current DSI selector behavior

The source supports optional hud_tx values 0 and 4. The default and invalid-value fallback are 0. The DSI header carries transmissionType as its own field, variantTag = 1 (eTransmissionTXControl), and variantValue remains 0.

The selector is used for MOST HUDTerminal FBlock 0x82 drawing calls, mirror calls and the volatile test channel. AudioMaster volume calls remain at transmissionType 0.

The C04 response filter checks transmissionType, response variant, source/destination, instance, function and handle. It does not claim that the DSI message tag is a proven request transaction ID; delayed same-TX/same-handle responses remain a correlation risk.

See [MINI_6WB_TXCONTROL.md](MINI_6WB_TXCONTROL.md) for the DSI selector and C04 analysis, and [MINI_F5X_TECHNICAL_RESEARCH.md](MINI_F5X_TECHNICAL_RESEARCH.md) for the full evidence register.

## Cross-chassis status

| Chassis | Evidence in this project | Current claim |
|---|---|---|
| F54 | HMI 1703 vehicle sessions and native handle/geometry observations | Vehicle-observed baseline for that F54/HMI |
| F55 | Shared physical panel confirmed by user; no direct test record in this checkout | Not independently validated |
| F56 | Passive OEM capture, earlier C04 probes and later visible TX=4 route-guidance result | Vehicle-observed visible result; C04 and TX=0 A/B unresolved |
| F57 | Shared physical panel confirmed by user; no direct test record in this checkout | Not independently validated |
| F60 | External issue #176 transport clue only | No direct F60 drawing validation in this project |

## Remaining work

1. Re-import the raw F54/F56 captures, probe reports, latest TX=4 log and SHA-256 manifest.
2. Record exact vehicle/HMI/coding metadata for every capture.
3. Run controlled F56 TX=0/TX=4 A/B with full DSI headers and timestamps.
4. Obtain a positive F56 C04 response and record handle, dimensions, payload form and timing.
5. Capture CreateInstance, FrameAddItem, C04 and cleanup across a complete native navigation lifecycle.
6. Validate text, Unicode, distance/unit rendering, Mapbox lane glyphs and 82/02 separately.
7. Repeat on F54/F55/F56/F57/F60 independently before claiming family-wide compatibility.
8. Rebuild the exact tested plugin binary and verify its SHA-256 against the vehicle evidence.

## Safety and release boundary

The later TX=4 visible result does not make the checked-in plugin payload a verified release. Keep TX=0 as the default, keep TX=4 opt-in, and do not install an unverified payload. This documentation update did not connect to the vehicle, install software, restart the head unit, enable HUD debug logging or alter the current vehicle installation.

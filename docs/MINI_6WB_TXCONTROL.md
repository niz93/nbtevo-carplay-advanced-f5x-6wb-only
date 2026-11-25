# MINI_F5X HUDTerminal DSI transmissionType research

**Status:** F56 visible route guidance was observed on a real vehicle with transmissionType 4 on 2026-11-25. This is a vehicle-observed display result, not complete protocol validation. C04 sizing, buffer dimensions, TX=0 A/B and cross-chassis compatibility remain open.

## Scope and naming

The project uses **MINI_F5X** for the shared physical MINI instrument-panel family confirmed by the user for F54/F55/F56/F57/F60.

This is not the same thing as the separate BMW F-series **6WB** layout represented by the g_6wb profile in src/hud.h. External issue #176 uses the phrase “MINI 6WB” for a MINI F60 context; that wording must not be used to conflate the MINI panel with BMW 6WB.

A shared physical panel does not prove identical HMI software, firmware, coding, options, terminal instances or DSI behavior across all five chassis.

## Executive result

The F56 vehicle result is now stronger than the earlier source-only / external-evidence state:

- A later F56 vehicle run selected DSI transmissionType 4.
- The historical log summary records HUD transmissionType 4 and HUDTerminal 82/00.
- Maneuver distances of 160 m, 170 m and 10 m were observed in that run.
- The user-supplied photo shows the 170 m right-turn prompt on the CarPlay center display and stock instrument cluster together.
- The companion photo set includes the 10 m left-turn prompt.

This proves visible route guidance was observed during that F56 session. It does **not** prove that C04 ImageGetSize returned a valid size, that all drawing calls were acknowledged, that the renderer discovered the picture-buffer dimensions, or that TX=4 is required rather than merely sufficient in that test configuration.

## External F60 clue: issue #176 and PR #179

[Sq00ky/Supra-iDrive6-Android-Auto issue #176](https://github.com/Sq00ky/Supra-iDrive6-Android-Auto/issues/176) reports a MINI F60 / NBT Evo ID6 setup in which DSI transmissionType 0 requests were rejected with ErrorAck 0x41. The report describes positive acknowledgements from read-only ImageGetSize probes with TX=4, but response timing was delayed and did not prove that every drawing request succeeded.

The issue's later update says the experimental driver did not complete a live send in that run because it remained waiting for an observed factory route end. This is external transport evidence, not a completed F60 drawing test.

[PR #179](https://github.com/Sq00ky/Supra-iDrive6-Android-Auto/pull/179) is an experimental BMW 6WB backend. It is a separate profile and must not be copied or generalized to MINI_F5X without source comparison and vehicle evidence.

## F56 OEM and probe evidence

### Passive OEM navigation capture

The historical capture mini-f56-native-nav-20261125-040320-116770.txt records a 60-second window on HUDTerminal 82/00 with 215 messages:

| Function | Count |
|---|---:|
| 0x204 | 31 |
| 0x21D | 167 |
| 0x20E | 14 |
| 0x227 | 3 |

The observed handles include 1–8 and 0x16; drawing uses handles 5, 6 and 7. The capture window does not include 0x200 CreateInstance, 0x22B FrameAddItem or 0xC04 ImageGetSize. Its handle map came from an earlier start. The returned log excludes 0x210 street-text payloads.

This is useful OEM drawing/visibility evidence, but not a complete native setup, allocator or text-payload capture.

### Earlier HUD Probe reports

The historical reports hud-probe-v1.3.0-20261125-041729-717486.txt and hud-probe-v1.3.0-20261125-042222-571911.txt each recorded 128 C04 requests and 128 ErrorAck 0x41 responses across handles 0x01–0x40 and two tested payload forms.

Neither report preserved the DSI transmissionType field. The visual result was mini: cluster n. These reports establish refusal of those probe requests, but they do not establish whether the refusal was caused by TX=0, the payload form, the endpoint, the request timing or another condition.

### Later TX=4 vehicle result

The later F56 test record from 2026-11-25 reports:

- 60-second capture; 26 new log lines.
- HUD transmissionType 4.
- HUDTerminal 82/00.
- Maneuver distances 160 m, 170 m and 10 m.
- Seven of seven files in the historical evidence check passed SHA-256 verification.
- A user photo shows the 170 m right-turn prompt on both the center CarPlay display and instrument cluster; a companion photo shows a 10 m left-turn prompt.

The tested librghook-most.so was recorded with SHA-256 prefix d0e448… in the earlier evidence summary. The exact installed binary hash is now confirmed from the recovered capture.json; the full archive and tested binary are not in this checkout.

The same run did not record a positive C04 ImageGetSize response, picture-buffer dimensions or a picture-buffer response trace. A standalone hud_guidance.txt was absent. hud_debug was not enabled. No controlled TX=0 comparison was performed.

See the [real F56 vehicle photographs and provenance](images/README.md) and the [technical report gallery](MINI_F5X_TECHNICAL_RESEARCH.md#vehicle-photo-evidence). These photographs document visible output only.

## Current source implementation

The optional setting is hud_tx:

- Valid values are 0 and 4.
- Missing or invalid values fall back to 0.
- The DSI header serializes transmissionType as the first field after the client ID.
- variantTag remains 1 (eTransmissionTXControl).
- variantValue remains 0.
- The selector is used by the plugin's MOST HUDTerminal FBlock 0x82 calls, mirror calls and volatile test channel.
- AudioMaster volume calls continue to use transmissionType 0.
- The PowerShell and QNX shell installers accept --hud-tx 0|4 and persist the selected value for plugin startup.

The C04 response filter checks the active transmissionType, response variantTag/variantValue, source, destination, instance, function and handle before accepting a size response. The test file test_hud_c04_correlation.py contains ten focused cases for valid and invalid endpoint/transport/variant/handle responses.

### Correlation limitation

The code does not claim that the DSI message tag is a proven request transaction ID. A delayed response with the same transmissionType, endpoint, instance and handle may still be indistinguishable from a response to the current query. The current test suite explicitly avoids claiming otherwise.

## Current binary and build boundary

The checked-in plugin/librghook-most.so SHA-256 is:

fc6bac8e65b1e0afe034d758265ec6af3943bb975c42460f077524eabc3fed3f

This is not the historical F56-tested binary whose hash prefix was recorded as d0e448…. Do not treat the checked-in prebuilt library as the tested TX=4 artifact.

The current Zenbook lacks LLVM clang.exe and ld.lld.exe. GitHub Desktop has a bundled sh.exe, but build-windows.ps1 currently searches for bash.exe and does not select that bundled path. The current environment also lacks ksh. The current clone therefore has not reproduced the ARMv7/QNX payload or complete host suite in this session.

A previous workcopy reported 71/71 selected Cygwin tests and nine ARMv7/QNX libraries built. The exact manifests and tested binary are not present in this checkout, so those remain historical results pending import and independent verification.

## Required next experiments

1. Complete the remaining latest TX=4 capture evidence gaps. The 15-file original capture set is already preserved and verified locally; four later files are verified. See [evidence index](EVIDENCE-MANIFEST.json).
2. Run controlled TX=0 and TX=4 tests on the same F56, same HMI build, same route and same terminal.
3. Capture complete DSI request/response headers, timestamps, endpoints, instance, function, opType, transmissionType, variant and payload.
4. Obtain a positive C04 ImageGetSize response and record handle, width, height, payload form and response timing.
5. Verify whether the 120 × 72 picture box is learned from the active F56 terminal or the renderer uses a fallback box.
6. Test delayed, duplicate, stale and wrong-handle responses to establish causal correlation.
7. Capture 0x200 CreateInstance and 0x22B FrameAddItem from a cold native navigation start, plus cleanup and route-end behavior.
8. Validate street/distance/unit text and Mapbox lane glyphs on F56.
9. Test F54, F55, F56, F57 and F60 separately with HMI and coding provenance before claiming family-wide compatibility.

## Safety boundary

Keep transmissionType 0 as the default. TX=4 remains opt-in and experimental even after the visible F56 result. This documentation update did not connect to the vehicle, install software, restart the head unit, enable HUD debug logging or change the current vehicle installation.

Do not publish an installable release claim until the exact tested binary, complete evidence archive, reproducible build, regression suite and recovery procedure are available.

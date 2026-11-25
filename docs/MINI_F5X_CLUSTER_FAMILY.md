# MINI F5x shared instrument-panel family

## Family rule

**User-confirmed:** MINI F54, F55, F56, F57 and F60 use the same physical instrument panel. The project therefore treats them as one panel family, **MINI_F5X**. Do not create separate instrument-panel profiles solely because the chassis code differs.

This is a shared-panel rule, not a claim that every vehicle has identical HMI software, firmware build, coding, equipment, projected-HUD availability, terminal instances, MOST transport settings, or visible rendering. Preserve the actual vehicle and HMI build as provenance for every capture. A result about the shared physical panel can be reused at family level; software- and runtime-specific conclusions still require their own evidence.

The MINI F5x stock digital instrument panel must not be conflated with the **BMW 6WB** layout profile. In this codebase, `g_6wb` means the BMW F-series multifunction-cluster layout. The external issue's wording "MINI 6WB" is a MINI/F5x-labelled surface, not a reason to classify an F5x chassis as a BMW 6WB cluster.

## Evidence retained in this branch

All original user-supplied captures are preserved unchanged under `evidence/original-captures-2026-11-25/`. `EVIDENCE-MANIFEST.json` records the original upload identifiers, byte sizes and SHA-256 hashes. The raw source files were copied with matching byte size and SHA-256.

### F54 baseline

The existing in-car baseline is MINI F54, HMI 1703, tested 2026-11-11/12, with follow-up HUD measurements on 2026-11-13. It establishes the learned MINI panel handle map and picture-box/surface observations recorded in `AGENTS.md`. The setup fixture in `tests/test_hud_handles.py` and `tests/test_hud_init.py` is explicitly the F54 capture, reused as the shared MINI_F5X panel-family fixture.

Keep "captured/tested on F54" in provenance. Do not rewrite it as a direct test on every F5x model.

### F56 passive OEM navigation capture

Source: `mini-f56-native-nav-20261125-040320-116770.txt`

- Vehicle is identified in the capture as MINI F56; the window is 60 seconds on HUDTerminal 82/00 at device 0101.
- 215 OEM events are present: 31 `0x204`, 167 `0x21D`, 14 `0x20E`, and 3 `0x227`.
- The observed handles across those messages are 1, 2, 3, 4, 5, 6, 7, 8 and 0x16.
- `0x21D` drawing uses handles 5, 6 and 7; `0x20E` visibility switching shows the 5/6 pair and the 8-to-7 relation; `0x227` addresses handle 0x16.
- There are **zero** `0x200 CreateInstance` and **zero** `0x22B FrameAddItem` events in this capture window. No `0xC04 ImageGetSize` request is present either.
- The header's 1/2/3/4, 5/6 and 0x16 handle map is retained from an earlier start. It is not a setup exchange observed inside this 60-second window.
- The capture is therefore valid F56 OEM drawing/visibility evidence, but it is not a complete native setup/allocator/handle-lifecycle capture. The returned log explicitly excludes the `0x210` street-text payloads.

### F56 HUD Probe reports

The two later reports are:

- `hud-probe-v1.3.0-20261125-041729-717486.txt`
- `hud-probe-v1.3.0-20261125-042222-571911.txt`

Both identify the vehicle as a **MINI F56 stock digital instrument cluster; not BMW 6WB**, with HMI `NBTevo_ID5_2111-540-2142A Build 28`.

Each report records 128 `0xC04 ImageGetSize` requests (handles 0x01–0x40 in both tested payload forms) and 128 `ErrorAck 0x41` responses. Neither report records a positive image size. The visual test result is `mini: cluster n`; visible rendering is therefore **not confirmed** by these reports. The reports do not preserve the DSI TXControl value, so the `0x41` result must not be attributed to DSI transmissionType 0 or 4.

The earlier report `hud-probe-v1.3.0-20261125-032957-438623(1).txt` initially labels the vehicle "MINI F56 / 6WB instrument cluster". That wording is superseded by the two later reports, which explicitly distinguish the MINI stock digital panel from BMW 6WB.

The probes show 82/00; they intentionally skip 82/02 visual patterns because a projected windscreen HUD was absent by the selected vehicle profile. This is not evidence about 82/02 rendering.

### External F60 transmissionType clue

The external MINI F60 report in [Sq00ky/Supra-iDrive6-Android-Auto issue #176](https://github.com/Sq00ky/Supra-iDrive6-Android-Auto/issues/176) describes DSI `transmissionType` 0 requests rejected with `ErrorAck 0x41`, while read-only `ImageGetSize` with `transmissionType` 4 received a positive acknowledgement on a MINI/F5x-labelled surface. It is relevant family-level evidence because F60 belongs to MINI_F5X, but it does not prove that every F5x HMI/build needs transmissionType 4 or that drawing succeeds after the size query.

## DSI transmissionType serialization contract

The `hud_tx` setting is an optional **DSI `transmissionType`** selector for MOST HUDTerminal FBlock 0x82 calls and the volatile test channel.

The DSI fields are serialized as:

1. `transmissionType = hud_tx` (0 by default, optionally 4);
2. `variantTag = 1` (`eTransmissionTXControl`);
3. `variantValue = 0` (unchanged).

Therefore `--hud-tx 0|4` changes only DSI `transmissionType`. It does **not** change `variantTag` or `variantValue`. AudioMaster volume continues to use DSI `transmissionType` 0. The default remains 0; value 4 is opt-in and is not vehicle-validated in this branch.

## Current acceptance boundary

| Item | State |
|---|---|
| Shared F54/F55/F56/F57/F60 physical panel family | USER-CONFIRMED |
| F54 in-car drawing baseline | VERIFIED on F54 / HMI 1703 |
| F56 passive OEM navigation drawing capture | PARTIAL; setup exchange absent |
| F56 ImageGetSize probes | 128/128 ErrorAck 0x41 in each of two later reports; DSI transmissionType field unknown |
| F56 visible test rendering | NOT CONFIRMED (`mini: cluster n`) |
| F55/F57/F60 direct vehicle validation in this branch | NOT PERFORMED |
| DSI transmissionType 4 on F5x | EXTERNAL CLUE ONLY; opt-in, not default |
| BMW 6WB layout | Separate profile; not implied by MINI_F5X |

No vehicle installation, restart, firmware action, MOST write, or car connection is part of this local family/documentation correction.

# MINI F5x HUDTerminal DSI transmissionType selector

**Status:** source implementation and host-side tests only. No vehicle-side validation of DSI transmissionType 4 or visible F56 rendering has been performed.

## Shared MINI panel family

The user confirms that MINI F54, F55, F56, F57 and F60 share the same physical instrument panel. This branch treats them as one **MINI_F5X** panel family. F54 is the in-car baseline; F56 has additional OEM navigation captures and HUD Probe reports. This family rule does not imply identical HMI builds, coding/options, projected-HUD availability, or transport behavior.

Keep the terminology separate:

- **MINI F5x stock digital instrument panel:** shared physical panel family described above.
- **BMW 6WB layout:** the separate BMW F-series multifunction-cluster profile represented by `g_6wb` in this codebase.
- The external issue #176 uses the wording "MINI 6WB" for a MINI F60 surface; that label must not make a MINI F5x vehicle a BMW 6WB profile.

## Why this exists

A diagnostic log from the user's MINI showed ErrorAck (op 9) with payload ending in `0x41` for RemoveAll (0x220), SetText (0x210), and SetVisibility (0x204). That proves the cluster rejected those requests; it does not, by itself, identify the cause.

A related external report exists in [Sq00ky/Supra-iDrive6-Android-Auto issue #176](https://github.com/Sq00ky/Supra-iDrive6-Android-Auto/issues/176): MINI F60, NBT Evo ID6, HMI `ID5_2111-540-2142A Build 28`. It describes DSI transmissionType=0 requests rejected with ErrorAck 0x41, while read-only ImageGetSize probing with transmissionType=4 received a positive acknowledgement on a MINI/F5x-labelled surface. The response was delayed, and the report does not establish that every drawing call works with transmissionType 4.

[Sq00ky PR #179](https://github.com/Sq00ky/Supra-iDrive6-Android-Auto/pull/179) uses a separate DSI transmissionType for 6WB vector messages while retaining transmissionType 0 for bitmap transport. This is evidence that the DSI transport selector can vary by cluster; it is not a reason to replace transmissionType 0 globally.

Because F60 is in the shared MINI_F5X panel family, the external report is relevant family-level evidence. It is still an external F60 report, not a direct test of the user's F56 HMI runtime.

## F56 evidence in this branch

The preserved passive capture `evidence/original-captures-2026-11-25/mini-f56-native-nav-20261125-040320-116770.txt` records 60 seconds of OEM navigation drawing on HUDTerminal 82/00: 215 messages (31 `0x204`, 167 `0x21D`, 14 `0x20E`, 3 `0x227`). It contains no `0x200 CreateInstance`, no `0x22B FrameAddItem`, and no `0xC04 ImageGetSize` requests. The handle map in its header was retained from an earlier start, so this is drawing/visibility evidence, not a complete native setup exchange.

The two later F56 Probe reports (`041729` and `042222`) each contain 128 C04 ImageGetSize requests and 128 ErrorAck 0x41 responses across handles 0x01–0x40 and both tested payload forms. Neither report preserves the DSI transmissionType field. Both report `mini: cluster n` for the visual check. Therefore:

- the C04 refusals are observed, but their cause is unknown;
- they must not be attributed to DSI transmissionType 0 or 4;
- visible rendering is not confirmed by these probes;
- 82/02 visual patterns were intentionally skipped because a projected windscreen HUD was absent by the selected vehicle profile.

The complete source inventory and interpretation are in [MINI_F5X_CLUSTER_FAMILY.md](MINI_F5X_CLUSTER_FAMILY.md).

## DSI serialization contract

The setting file is:

`/var/opt/hmi/data/rw/carplaymenu/hud_tx`

Accepted contents:

- `0`: default DSI `transmissionType` (default when the file is absent)
- `4`: opt-in DSI `transmissionType`, based on the external MINI F60 report

The DSI fields are serialized in this order:

1. `transmissionType = hud_tx` (0 by default, optionally 4);
2. `variantTag = 1` (`eTransmissionTXControl`);
3. `variantValue = 0` (unchanged).

Thus `--hud-tx 0|4` changes **only** the DSI `transmissionType`; `variantTag` remains 1 and `variantValue` remains 0. The setting is read at plugin startup. The installer option writes the selected value after a successful install; a restart is required for a running plugin to read a changed value.

Scope is intentionally narrow:

- It changes the DSI `transmissionType` for MOST HUDTerminal FBlock 0x82 calls made by the plugin.
- It also applies to the plugin's volatile `/dev/shmem/carplaymenu-hudcmd` test channel.
- It does not change the layout, handles, geometry, text encoding, or selected terminal.
- AudioMaster volume messages continue to use DSI `transmissionType` 0.
- Invalid values fail closed to DSI `transmissionType` 0.
- The default remains 0 until `--hud-tx 4` is explicitly selected.

## Windows usage

Preview the plan without contacting or changing a vehicle:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\carplay-advanced.ps1 install --hud --hud-tx 4 --dry-run
```

This is a dry-run only. Do not use it as evidence of vehicle compatibility. Any later vehicle test requires a deliberate, separately authorized session and the normal backup/confirmation flow.

The installer status command `hud-probe` reports the `hud_tx` setting. The plugin log reports the selected DSI `transmissionType`.

## Validation boundaries

Host tests check the exact DSI fields for:

1. `hud_tx=4` and `hud_tx=0`;
2. invalid values falling back to 0;
3. the volatile test channel using the selected DSI `transmissionType`;
4. AudioMaster volume remaining at DSI `transmissionType` 0.

They cannot verify a vehicle's MOST controller, selected native instance map, ImageGetSize behavior, or visible rendering. The car remains disconnected from the development app. Vehicle-side validation is **PENDING**.

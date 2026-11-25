# MINI F5x + MINI 6WB — Research Workspace

This repository is a **research workspace** for studying and validating the CarPlay route-guidance path on MINI F5x vehicles equipped with the **MINI 6WB digital instrument cluster**.

The target vehicle family is **MINI F54, F55, F56, F57 and F60**, in the configuration using the MINI 6WB instrument cluster. The research focus is the behaviour of that F5x/6WB combination: how guidance data reaches the vehicle, how the cluster is addressed, and how route information is rendered and updated.

This repository is based on [st1ng/nbtevo-carplay-advanced](https://github.com/st1ng/nbtevo-carplay-advanced). It is not intended to become a separate product that drops upstream capabilities. Its purpose is to develop, test and document narrowly scoped changes that can be proposed as pull requests to the parent repository.

> **Research workspace, not a ready-to-install product.** The code, installer and prebuilt payload are inherited from upstream and may support multiple vehicle families, cluster types and HUD configurations. Their presence is intentional. A research focus on F5x + MINI 6WB does not mean that other support paths have been removed, disabled, validated or superseded.

## Research target

The primary target is the route-guidance operation on:

- MINI F5x: F54, F55, F56, F57 and F60.
- The MINI 6WB digital instrument cluster.
- Relevant NBT Evo / iDrive 5 and iDrive 6 software configurations.
- CarPlay turn-by-turn guidance presented in the instrument cluster.

The work should establish the exact behaviour for each tested vehicle and software combination. Evidence from one car or HMI build must not silently be generalized to every F5x configuration.

## Important: preserve the upstream project

**Do not remove, disable, stub out or rewrite unrelated upstream functionality just because it is not the focus of this research.**

The following capabilities and implementation paths must remain intact unless a specific, evidence-backed change is required and is separately justified:

- Support for other vehicle models and chassis.
- Support for other instrument-cluster types and display configurations.
- The existing MOST/DSI and Ethernet KOMBI implementations.
- Existing HUD and HUD-effects functionality.
- Existing iDrive 5 / iDrive 6 menu, controller, touchpad, zoom, full-screen, installer, restart and recovery behaviour.
- Existing build targets, interfaces, configuration paths and third-party notices.

The F5x + MINI 6WB research path is an additional, focused investigation within the inherited multi-platform project. It is not a reason to narrow the capabilities of the parent project.

### Change policy

1. **Make the smallest change that solves the demonstrated F5x/6WB requirement.** Prefer a targeted addition or correction over a broad refactor.
2. Preserve existing behaviour for all other supported configurations.
3. Do not delete or disable a code path merely because it is not exercised by the F5x/6WB test vehicle.
4. Keep platform-specific behaviour explicit and isolated where practical. Reuse existing abstractions when they correctly represent the hardware.
5. Avoid changing public interfaces, installer behaviour, defaults or payload composition unless the requirement proves that change necessary.
6. Add regression tests for the new F5x/6WB behaviour and tests or checks demonstrating that unaffected upstream paths remain intact.
7. Record the evidence and configuration that justify every hardware-specific assumption.
8. Keep changes suitable for review and eventual contribution to st1ng/nbtevo-carplay-advanced.

A change is not considered complete merely because it works in a host-side simulation or compiles. Clearly distinguish source-derived, simulated, bench-verified and vehicle-verified results.

## Research questions

The workspace is intended to investigate, among other things:

- How the F5x MINI 6WB cluster exposes its display services and MOST/DSI endpoints.
- How the head unit discovers the cluster's display instances, handles, dimensions and text fields.
- How original BMW/MINI navigation and CarPlay route guidance use those services.
- The lifecycle of display objects, handles, drawing buffers, acknowledgements and updates.
- How the existing route-guidance data path can be reused with the MINI 6WB.
- Which differences are caused by the vehicle, cluster, NBT Evo generation, HMI build or coding.
- What minimal code additions or corrections are needed for reliable F5x/6WB operation.

Names such as hud.h, rghud.cpp, HUDTerminal, hud_guidance and librghook-most.so are inherited source/protocol terminology. They do not imply that the research workspace is intended to remove or replace the upstream HUD functionality.

## Inherited implementation

The starting point is the upstream CarPlay Advanced codebase. It includes, among other things:

- The NBT Evo HMI plugin and CarPlay Advanced Settings menu.
- iAP2 route-guidance interception and decoding in src/rghook.c.
- The MOST/DSI drawing implementation in src/hud.h and src/rghud.cpp.
- The Ethernet KOMBI implementation in src/kombi.h and src/rgkombi.cpp.
- Controller, touchpad, zoom, full-screen layout, installer, restart and recovery functionality.
- Prebuilt libraries and plugin payload under plugin/.

These paths are part of the inherited project and must be preserved. Their current compatibility status must be established from code, tests and evidence; do not infer it from their presence in the repository or from this README.

## Evidence and verification

Every finding should identify its evidence class:

| Evidence class | Meaning |
|---|---|
| Documented | Supported by an identifiable manual, specification or technical reference. |
| Source-derived | Established by analysis of source code, binaries or captured implementation data. |
| Simulated | Exercised using host-side code, a model or a test double. |
| Bench-verified | Reproduced on controlled hardware outside normal vehicle operation. |
| Vehicle-verified | Observed on a real vehicle with its configuration and test evidence recorded. |

A successful compilation, source comment, third-party report or host-side test is not vehicle verification.

Test reports should include the chassis (F54/F55/F56/F57/F60), cluster type, NBT Evo and HMI software identifiers, coding assumptions, reproduction steps, expected and actual results, sanitized logs and relevant hashes. Record differences rather than assuming that every vehicle has the same software or coding.

Never publish VINs, credentials, Wi-Fi passwords, Bluetooth identifiers, personal route data or other private vehicle information.

## Repository layout

| Path | Purpose |
|---|---|
| src/cpm.cpp | NBT Evo HMI plugin and settings menu. |
| src/rghook.c | iAP2 route-guidance interception and decoding. |
| src/rgview.h | Shared route-guidance state interface. |
| src/hud.h | Inherited MOST/DSI drawing implementation. Preserve its existing HUD and cluster behaviour. |
| src/hudhandles.h | MOST display-handle discovery and stored handle information. |
| src/rghud.cpp | Inherited MOST route-guidance sender. |
| src/kombi.h, src/rgkombi.cpp, src/kombitemplate.h | Inherited Ethernet KOMBI implementation. Preserve it. |
| src/pinch.c, src/pbwpatch.h, src/iniwide.h | Inherited controller, layout and CarPlay input functionality. |
| plugin/ | Inherited prebuilt plugin payload; rebuild it when a source change requires updated binaries. |
| tests/ | Host-side tests and simulated integration checks. |
| tools/ | Build, inspection and development utilities. |
| AGENTS.md | Detailed inherited architecture notes and development constraints. |

## Build and host-side tests

The inherited project provides these commands:

~~~sh
./build.sh
python3 -m unittest discover -s tests
~~~

They build the current source and run the available host-side tests. They do not install software on a head unit and do not establish compatibility with a particular F5x/6WB vehicle.

For each code change, run the relevant tests and add regression coverage for the affected path. When feasible, also verify that the other cluster and HUD paths still build and retain their existing behaviour.

## Vehicle testing and safety

Do not install this research workspace on a vehicle merely because an installer is present. Before any vehicle test:

1. Review the exact source and payload being tested.
2. Record the vehicle, cluster and head-unit software configuration.
3. Confirm that the test exercises the intended F5x/6WB path and does not unintentionally affect other display paths.
4. Prepare and verify a recovery procedure.
5. Obtain explicit approval from the vehicle owner.

Never experiment while driving. The project is provided without warranty; anyone performing a vehicle or head-unit modification is responsible for the consequences.

## Upstream and acknowledgements

The parent project is **[st1ng/nbtevo-carplay-advanced](https://github.com/st1ng/nbtevo-carplay-advanced)**. This workspace is intended to produce focused, reviewable changes for that project. The parent repository remains the intended destination for generally useful implementation changes; this repository is for F5x + MINI 6WB research, evidence and development.

The inherited code also contains work or references from:

- [NBT-AAD / Supra iDrive 6 Android Auto](https://github.com/Sq00ky/Supra-iDrive6-Android-Auto)
- [NBT-AAD USB Tools](https://github.com/Yalozo/nbt-aad-usb-tools)
- [Mapbox Navigation SDK for iOS](https://github.com/mapbox/mapbox-navigation-ios)
- [BMW iDrive 6 CarPlay HUD](https://github.com/ftojke/BMW-iDrive6-CarPlay-HUD)
- [nbt-android-auto](https://github.com/JayJay3071/nbt-android-auto)
- [mib2q-carplay-rgi](https://github.com/luka-dev/mib2q-carplay-rgi)
- [LIVI](https://github.com/f-io/LIVI)

Preserve all upstream and third-party notices when modifying or redistributing inherited material. See NOTICE and LICENSE for the applicable terms.

## Contributing

Issues and pull requests in this workspace should advance or document the F5x + MINI 6WB research target. Include the exact vehicle and software configuration, a concise reproduction procedure, the evidence class, and sanitized logs or captures where possible.

Keep patches narrow, preserve unrelated upstream behaviour, and explain why each changed line is needed. Where a change is generally useful, prepare it for a pull request to [st1ng/nbtevo-carplay-advanced](https://github.com/st1ng/nbtevo-carplay-advanced). Separate confirmed observations from hypotheses. Do not submit personal data, credentials, VINs or unredacted vehicle captures.

## License and disclaimer

This workspace retains the licensing and third-party notices inherited from upstream. Review LICENSE and NOTICE before using, modifying or redistributing any part of the repository.

This is an independent, non-commercial research workspace. It is not affiliated with BMW, MINI, Apple or Harman. BMW, MINI, NBT Evo, iDrive and CarPlay are trademarks of their respective owners.

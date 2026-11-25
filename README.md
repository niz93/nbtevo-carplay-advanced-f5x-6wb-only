# MINI F5x 6WB — NBT Evo CarPlay Research

An independent research fork of [st1ng/nbtevo-carplay-advanced](https://github.com/st1ng/nbtevo-carplay-advanced), dedicated to the **MINI F5x platform and its 6WB digital instrument cluster**.

The target is the MINI F5x family — **F54, F55, F56, F57 and F60** — equipped with the factory **6WB digital instrument cluster and without a separate windscreen Head-Up Display (HUD)**.

This repository is the place to investigate, document, test and develop the interaction between NBT Evo, Apple CarPlay route guidance and the F5x 6WB instrument cluster. The instrument cluster is the display target. Windscreen HUD functionality is not a project objective.

> **Research project, not a ready-to-install product.** This fork inherits code and prebuilt files from the upstream project. A README change does not remove, disable or validate any inherited feature. Do not assume that the current installer or payload is already restricted to the F5x/6WB/no-windscreen-HUD configuration.

## Project goals

- Understand the F5x NBT Evo software environment and its interaction with the 6WB instrument cluster.
- Trace CarPlay route-guidance data from the iPhone's iAP2 messages through the head unit to the cluster-facing implementation.
- Investigate the original 6WB display services, MOST/DSI communication, display instances, handles, image dimensions, text fields, acknowledgements and lifecycle.
- Develop and validate a cluster-focused route-guidance implementation for the F5x 6WB.
- Document differences between vehicle configurations, NBT Evo generations, HMI software builds and coding.
- Maintain reproducible offline tests and clearly labelled bench and vehicle evidence.

The intended platform scope includes F54, F55, F56, F57 and F60. Findings from one vehicle should be recorded with its configuration and software identifiers; they should not silently be treated as proof for every software combination.

## Scope boundaries

### In scope

- MINI F5x: F54, F55, F56, F57 and F60.
- Factory 6WB digital instrument cluster.
- NBT Evo / iDrive 5 and iDrive 6 software relevant to the target vehicles.
- CarPlay route guidance and its presentation on the 6WB instrument cluster.
- Reverse engineering, protocol analysis, offline simulation, host-side tests and controlled hardware experiments.

### Out of scope

- A separate windscreen-projection HUD: no windscreen HUD rendering, HUD effects, HUD layout work or HUD feature development.
- G-series and J29 Ethernet KOMBI implementations.
- 6WA cluster development.
- Claims of universal compatibility without configuration-specific evidence.

## Terminology: 6WB instrument cluster and legacy HUD names

The upstream source uses names such as `hud.h`, `rghud.cpp`, `HUDTerminal`, `hud_guidance` and `librghook-most.so`. These are inherited implementation and MOST/DSI terminology.

**In this fork, the target is the 6WB instrument cluster — not a separate windscreen HUD.** A legacy source filename or protocol label does not redefine the project scope.

The inherited `src/hud.h` contains comments describing a 6WB-oriented display layout, including a 221 × 158 image plane and associated handles, with references to external research. Treat these details as research leads until they are independently confirmed against the intended F5x hardware and factory behaviour.

## Inherited implementation: current status

The starting codebase is the upstream CarPlay Advanced project. It currently contains more than the target research path, including:

- The NBT Evo HMI plugin and CarPlay Advanced Settings menu.
- iAP2 route-guidance interception and decoding in `src/rghook.c`.
- A MOST/DSI drawing implementation in `src/hud.h` and `src/rghud.cpp`.
- An Ethernet KOMBI implementation in `src/kombi.h` and `src/rgkombi.cpp`, intended for other vehicle platforms.
- Controller, touchpad, zoom, full-screen layout, installer and restart functionality.

These components are inherited baseline code, not a statement that every feature is part of the F5x/6WB target. In particular, the Ethernet KOMBI path is outside this fork's scope. The existing source and prebuilt `plugin/` payload must be audited before producing or using a target-specific build. **This repository must not yet be described as a HUD-stripped or 6WB-validated installer.**

## Research and verification standards

Every result should state what kind of evidence supports it:

| Evidence class | Meaning |
|---|---|
| Documented | Supported by an identifiable manual, specification or technical reference. |
| Source-derived | Established by analysis of source code, binaries or captured implementation data. |
| Simulated | Exercised using host-side code, a model or a test double. |
| Bench-verified | Reproduced on controlled hardware outside normal vehicle operation. |
| Vehicle-verified | Observed on a real vehicle with its configuration and test evidence recorded. |

A successful compilation, source comment, third-party report or host-side test is not vehicle verification. Test reports should include the vehicle/chassis, cluster, NBT Evo and HMI software identifiers, coding assumptions, reproduction steps, expected and actual results, sanitized logs and relevant hashes.

Never publish VINs, credentials, Wi-Fi passwords, Bluetooth identifiers, personal route data or other private vehicle information.

## Repository layout

| Path | Purpose |
|---|---|
| `src/cpm.cpp` | NBT Evo HMI plugin and settings menu. |
| `src/rghook.c` | iAP2 route-guidance interception and decoding. |
| `src/rgview.h` | Shared route-guidance state interface. |
| `src/hud.h` | Inherited MOST/DSI drawing implementation; legacy filename, not a windscreen-HUD project objective. |
| `src/hudhandles.h` | MOST display-handle discovery and stored handle information. |
| `src/rghud.cpp` | Inherited MOST route-guidance sender. |
| `src/kombi.h`, `src/rgkombi.cpp`, `src/kombitemplate.h` | Inherited Ethernet KOMBI implementation; outside the F5x/6WB target. |
| `src/pinch.c`, `src/pbwpatch.h`, `src/iniwide.h` | Inherited controller, layout and CarPlay input functionality. |
| `plugin/` | Inherited prebuilt plugin payload; not automatically a target-specific release. |
| `tests/` | Host-side tests and simulated integration checks. |
| `tools/` | Build, inspection and development utilities. |
| `AGENTS.md` | Detailed inherited architecture notes and development constraints. |

## Build and host-side tests

The inherited project provides these commands:

```sh
./build.sh
python3 -m unittest discover -s tests
```

They build the current source and run the available host-side tests. They do not install software on a head unit and do not establish compatibility with a particular F5x/6WB vehicle.

## Vehicle testing and safety

Do not install this research fork on a vehicle merely because an installer is present. Before any vehicle test:

1. Review the exact code and payload being tested.
2. Record the vehicle, cluster and head-unit software configuration.
3. Confirm that the test exercises only the intended 6WB cluster path.
4. Prepare and verify a recovery procedure.
5. Obtain explicit approval from the vehicle owner.

Never experiment while driving. The project is provided without warranty; anyone performing a vehicle or head-unit modification is responsible for the consequences.

## Upstream and acknowledgements

This fork is based on **[st1ng/nbtevo-carplay-advanced](https://github.com/st1ng/nbtevo-carplay-advanced)**. The upstream project and its contributors provided the original NBT Evo plugin, installer, reverse-engineering work, tests and documentation.

The inherited code also contains work or references from:

- [NBT-AAD / Supra iDrive 6 Android Auto](https://github.com/Sq00ky/Supra-iDrive6-Android-Auto)
- [NBT-AAD USB Tools](https://github.com/Yalozo/nbt-aad-usb-tools)
- [Mapbox Navigation SDK for iOS](https://github.com/mapbox/mapbox-navigation-ios)
- [BMW iDrive 6 CarPlay HUD](https://github.com/ftojke/BMW-iDrive6-CarPlay-HUD)
- [nbt-android-auto](https://github.com/JayJay3071/nbt-android-auto)
- [mib2q-carplay-rgi](https://github.com/luka-dev/mib2q-carplay-rgi)
- [LIVI](https://github.com/f-io/LIVI)

Preserve all upstream and third-party notices when modifying or redistributing inherited material. See [NOTICE](NOTICE) and [LICENSE](LICENSE) for the applicable terms.

## Contributing

Issues and pull requests are welcome when they advance the F5x/6WB research scope. Include the exact vehicle and software configuration, a concise reproduction procedure, the evidence class, and sanitized logs or captures where possible.

Separate confirmed observations from hypotheses. Do not submit personal data, credentials, VINs or unredacted vehicle captures.

## License and disclaimer

This fork retains the licensing and third-party notices inherited from upstream. Review [LICENSE](LICENSE) and [NOTICE](NOTICE) before using, modifying or redistributing any part of the repository.

This is an independent, non-commercial research fork. It is not affiliated with BMW, MINI, Apple or Harman. BMW, MINI, NBT Evo, iDrive and CarPlay are trademarks of their respective owners.

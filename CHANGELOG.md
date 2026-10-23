# Changelog

## v0.1.0 - 2026-10-23

See the [v0.1.0 release notes](docs/releases/v0.1.0.md) for scope and validation details.

- Adds a local workflow for preparing and binding Minecraft client source references. Full preparation has been validated for Minecraft 26.2 on Windows with JDK 25; this does not establish support for other versions or platforms.
- Blocks source preparation for known unnamed clients; the 1.21.1 official client was verified and correctly rejected. Remapping is not implemented.
- Provides provenance checks against Mojang's official client metadata. Verification is explicit and required when `--verify-official` is selected.
- Uses pinned decompiler tools with integrity checks, with optional conservative recovery for reported CFR failures.
- Provides project checks and binding resolution for review. Setup and binding do not write to the target mod project.
- Adds `python scripts/mcsource.py --version` to identify the checked-out kit version. The kit does not update itself.
- Licenses the kit's original code and documentation under `GPL-3.0-only`.

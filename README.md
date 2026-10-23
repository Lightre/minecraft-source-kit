# Minecraft Source Kit

A local, agent-guided workflow for reading the Minecraft version you actually target.

**Status: early development.** Current validation covers a local Minecraft 26.2 client JAR on Windows with JDK 25. Other versions, mappings, and operating systems are not yet verified.

The kit prepares a source reference beside your mod project. It does not edit mod code, build files, dependencies, or project instructions during setup. No MCP server, hosted service, or Python packages are required.

## Start here

Requirements: Python 3.10+, Git, and a full JDK (9 or newer) capable of reading the input bytecode (`java`, `javac`, `jar`, and `javap`).

1. Clone this kit outside your mod project.
2. Place your Minecraft client JAR in `.local/inputs/`, or keep it elsewhere and provide its path.
3. Open your coding agent with access to this kit and your mod project.
4. Ask: **Read this kit's AGENTS.md and docs/AGENT_GUIDE.md. Set up a local Minecraft source reference for my project at <project path>, using <JAR path>. Do not modify my project during setup.**

The agent checks the project target, inspects your JAR, prepares the reference, and reports any mismatch or decompiler limitations. You do not need to install an agent skill.

## Commands

Run these from the kit root; the agent normally runs them for you:

```text
python scripts/mcsource.py inspect --jar .local/inputs/client.jar
python scripts/mcsource.py verify --jar .local/inputs/client.jar
python scripts/mcsource.py check-project --jar .local/inputs/client.jar --project /path/to/mod
python scripts/mcsource.py prepare --jar .local/inputs/client.jar --project /path/to/mod --verify-official
```

`verify` compares the local SHA-1 and byte size against Mojang's official client metadata over HTTPS, without downloading Minecraft. It reports `verified`, `mismatch`, or `unverified`; network errors never count as success. `prepare --verify-official` requires a verified result before tool downloads or source generation and stores the verification evidence. See [official verification](docs/OFFICIAL_VERIFICATION.md).

`check-project` compares supported static version declarations with the input JAR and prints evidence as JSON. It never runs Gradle or writes to the mod project. See [project checks](docs/PROJECT_CHECKS.md) for the supported syntax and limitations. A matching declaration is not proof of effective build configuration or API compatibility.

`prepare --project` blocks unknown, conflicting, or mismatching declarations before downloading tools or creating an output directory. It records a matching declaration report in the reference identity. This optional version gate does not replace the agent's namespace review. Omitting `--project` keeps standalone source preparation available.

`inspect` reads ZIP entries and class headers without executing Minecraft. `prepare` fetches a pinned CFR source revision from its official repository, builds it locally, and writes sources under `.local/references/`. Existing outputs are never overwritten. Tools are kept under `.local/tools/`. The Java runtime and compiler must have the same major version. The tool checkout is checked against the pinned commit; reused binaries are checked against their locally recorded SHA-256 (this is an integrity check, not independent authentication).

CFR revision: `c4145259dfcd8ad3e99004e4d9ecb0aed55dcc5a`. Building requires GitHub access. Minecraft JARs are supplied by the user; the kit does not download them.

## What this can and cannot establish

Matching source and project versions helps prevent invented APIs. Decompiled Java is reconstructed code, not original source. Offline inspection records SHA-256, SHA-1, and failures. Official fingerprint verification is available through `verify` or `prepare --verify-official`; mapping conversion is not implemented. A matching version label alone is insufficient proof of provenance or mapping compatibility.

A successful decompiler exit does not mean every method was recovered. Inspect `REFERENCE.json` and `summary.txt`. CFR may omit method bodies or lack external dependencies. Do not use affected methods as behavioral evidence until checked against bytecode or a second decompiler.

Build checks verify compilation; runtime behavior and Mixin application require appropriate in-game validation. No correctness guarantee is made.

## Repository hygiene

JARs, generated sources, tool checkouts, and local configuration stay ignored. Only the kit's own code, documentation, and tests belong in this repository. Existing `work/` and `outputs/` directories are local development fixtures, not distributed content.

See [the agent guide](docs/AGENT_GUIDE.md) for setup and coding rules, and [the development plan](docs/ROADMAP.md) for current boundaries.

## Command results

- Exit `0`: inspection succeeded, the official client fingerprint matches, supported project version declarations match, or sources were generated without known failure markers. A project match and generated sources still require review.
- Exit `1`: the official client fingerprint or project version declarations mismatch, or setup or decompilation failed. Read the diagnostic and any partial reference record before trying again.
- Exit `2`: official fingerprint verification was unavailable/inconclusive, the project target could not be established from supported declarations, or sources were generated but CFR reported issues requiring review. Read the JSON status to distinguish these cases.

Interrupted or failed output is preserved for diagnosis. Do not delete or overwrite it automatically.

## Development

```text
python -m unittest discover -s tests -v
```

Unit tests use small synthetic ZIP fixtures. They do not download Minecraft or decompile it. GitHub Actions runs these tests for pull requests and pushes to `main`, on Windows and Linux with Python 3.10 and 3.13; passing unit tests does not establish full platform support.

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution boundaries.

For the same PR, a new update cancels its older unfinished test run. Feature-branch pushes do not also trigger a duplicate test matrix. Main-branch runs are not canceled in progress.

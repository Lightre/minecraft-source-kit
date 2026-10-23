# Minecraft Source Kit

A local, agent-guided workflow for reading the Minecraft version you actually target.

**Status: early development.** Current validation covers a local Minecraft 26.2 client JAR on Windows with JDK 25. Other versions, mappings, and operating systems are not yet verified.

The kit prepares a source reference beside your mod project. It does not edit mod code, build files, dependencies, or project instructions during setup. No MCP server, hosted service, or Python packages are required.

## Start here

Requirements: Python 3.10+, Git, and a full JDK capable of reading the input bytecode (`java`, `javac`, `jar`, and `javap`).

1. Clone this kit outside your mod project.
2. Place your Minecraft client JAR in `.local/inputs/`, or keep it elsewhere and provide its path.
3. Open your coding agent with access to this kit and your mod project.
4. Ask: **Read this kit's AGENTS.md and docs/AGENT_GUIDE.md. Set up a local Minecraft source reference for my project at <project path>, using <JAR path>. Do not modify my project during setup.**

The agent checks the project target, inspects your JAR, prepares the reference, and reports any mismatch or decompiler limitations. You do not need to install an agent skill.

## Commands

Run these from the kit root; the agent normally runs them for you:

```text
python scripts/mcsource.py inspect --jar .local/inputs/client.jar
python scripts/mcsource.py prepare --jar .local/inputs/client.jar
```

`inspect` reads ZIP entries and class headers without executing Minecraft. `prepare` fetches a pinned CFR source revision from its official repository, builds it locally, and writes sources under `.local/references/`. Existing outputs are never overwritten. Tools are kept under `.local/tools/`.

CFR revision: `c4145259dfcd8ad3e99004e4d9ecb0aed55dcc5a`. Building requires GitHub access. Minecraft JARs are supplied by the user; the kit does not download them.

## What this can and cannot establish

Matching source and project versions helps prevent invented APIs. Decompiled Java is reconstructed code, not original source. The command records the input SHA-256 and failures; it does not yet authenticate the JAR against Mojang metadata or translate mappings. A matching version label alone is insufficient proof of provenance or mapping compatibility.

A successful decompiler exit does not mean every method was recovered. Inspect `REFERENCE.json` and `summary.txt`. CFR may omit method bodies or lack external dependencies. Do not use affected methods as behavioral evidence until checked against bytecode or a second decompiler.

Build checks verify compilation; runtime behavior and Mixin application require appropriate in-game validation. No correctness guarantee is made.

## Repository hygiene

JARs, generated sources, tool checkouts, and local configuration stay ignored. Only the kit's own code, documentation, and tests belong in this repository. Existing `work/` and `outputs/` directories are local development fixtures, not distributed content.

See [the agent guide](docs/AGENT_GUIDE.md) for setup and coding rules, and [the development plan](docs/ROADMAP.md) for current boundaries.

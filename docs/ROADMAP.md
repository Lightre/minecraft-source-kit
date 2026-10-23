# Development plan

## Initial baseline

- Agent-led setup without target-project writes.
- Local JAR inspection and SHA-256 recording.
- Pinned official CFR source build.
- Separate output directory with a machine-readable identity and failure report.
- Focused tests for metadata, hashing, and error detection.

## Next acceptance gates

- Exercise a fresh complete prepare run, including offline tool reuse.
- Authenticate supported official JARs against Mojang metadata.
- Detect CFR failures and add a pinned, verified per-class fallback.
- Record project target and namespace in a separate local binding file.
- Validate source/project mismatch handling with a real mod project.
- Compare representative API tasks with and without the kit.

## Explicitly deferred

Mapping conversion, automatic project edits, arbitrary Gradle evaluation, MCP, runtime bridges, a GUI, and claims of universal Minecraft support.

Ship a small tested workflow before expanding the support matrix.

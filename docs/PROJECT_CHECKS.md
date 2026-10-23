# Project declaration checks

`check-project` is a read-only, bounded static check. It reads only root `gradle.properties`, `build.gradle` / `build.gradle.kts`, and settings files. It does not execute Gradle, apply plugins, inspect source trees, or change any project file.

```text
python scripts/mcsource.py check-project --jar /path/to/client.jar --project /path/to/mod
python scripts/mcsource.py prepare --jar /path/to/client.jar --project /path/to/mod
```

Quote paths that contain spaces. In multi-project builds, select and review the relevant module explicitly; the tool does not resolve inherited configuration.

## Supported declarations

- Direct `minecraft "com.mojang:minecraft:26.2"` and `minecraft("com.mojang:minecraft:26.2")` dependencies.
- Gradle properties referenced in double-quoted coordinates, such as `${minecraft_version}`, `${project.minecraft_version}`, and `$minecraft_version`.
- An accompanying root `minecraft_version` property is cross-checked, not accepted as the sole proof of the target.
- Ordinary line/block comments are excluded from dependency searches.

Duplicate properties, conflicting versions, version ranges, unresolved expressions, version catalog dependencies, unsupported layouts, and declared included builds require review. A build without a supported direct Minecraft dependency remains unresolved. NeoForge/Forge configuration blocks, local build-script variables, provider expressions, version catalogs, and inherited configuration are not resolved yet.

## Results

- `declared_version_match` (exit 0): supported declarations agree with the JAR's version label. This is not an API compatibility approval.
- `version_mismatch` (exit 1): the supported unambiguous declarations name another version. Stop setup with this JAR.
- `needs_review` (exit 2): the static checker cannot establish a single target. Read `issues` and resolve the actual configuration before proceeding.
- Invalid input produces an error diagnostic and exit 1.

The JSON report includes the source file and line for version declarations, configuration file SHA-256 values, and mapping/loader hints. Values are not inferred from installed caches or remembered version conventions. Only relevant declaration evidence is included, not complete build files.

`prepare --project` runs the check before tool downloads or output creation. A match is saved inside `REFERENCE.json` as `project_check`. This record is a snapshot: repeat the check after configuration changes; it is not a persistent guarantee.

## Required agent review

Gradle is executable code. Conditions, plugins, environment, user properties, `-P` overrides, and initialization scripts may change the effective target. The checker does not evaluate these and does not claim otherwise. Loader and mapping names are only hints from build text, not resolved dependencies. Java requirements are not derived from the project.

The JAR's namespace and provenance remain unverified by this command. A version match does not make Yarn and Mojang names interchangeable, establish API compatibility, validate Mixins, or prove in-game behavior. The agent must resolve these before using source evidence. Standalone `prepare` remains available for JAR-only workflows and manually verified unsupported builds; it must not be used to bypass an unresolved mismatch.

## Validation boundary

Automated coverage uses small synthetic mod configurations and JARs. An integration smoke check used the local 26.2 JAR with matching 26.2 and mismatching 26.1 synthetic mod configurations; both statuses and project-file preservation were verified. This does not establish support for a real user's entire Gradle build. Real-project validation remains an acceptance gate.

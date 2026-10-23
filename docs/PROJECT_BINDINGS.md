# Local project bindings

A binding is a kit-local snapshot that associates one mod project with one completed source reference. It removes repeated source-path selection while retaining explicit checks before reuse.

```text
python scripts/mcsource.py bind --project /path/to/mod --reference /path/to/kit/.local/references/version-hash
python scripts/mcsource.py resolve --project /path/to/mod
```

Quote paths containing spaces. Neither command requires the original JAR, Java, network access, or Gradle execution. Neither command modifies the mod project.

## Creating a binding

The reference must be inside this kit's `.local/references/`, have a valid completed identity (`generated_unverified`), contain the recorded number of Java files, and have no known source failure markers. Unresolved/failed references and marked validation fixtures cannot be bound. Supported project version declarations must match the reference version; unsupported builds still need a supported resolution workflow rather than a guessed binding.

A file under `.local/bindings/` is keyed by the canonical project path. It stores:

- Project location and static declaration evidence, including relevant configuration file hashes.
- A kit-relative source location and the `REFERENCE.json` SHA-256.
- A fingerprint incorporating active Java file paths and byte hashes, plus their count.
- Creation time and schema version.

Diagnostic backups/logs are excluded from the active source fingerprint. Changes to a source path, source bytes, identity record, or inspected project configuration invalidate reuse. Even a comment-only configuration edit triggers conservative review. Large source trees require reading their Java files to verify the fingerprint.

The snapshot detects changes after binding. It does not authenticate sources against the input JAR or establish mapping/API compatibility. Review provenance and reconstructed code before binding.

## Resolving in later sessions

- `located_unverified` (exit 0): the recorded snapshot still matches. The result provides the source location and a copyable English agent instruction. Effective Gradle target, mappings, and API behavior still require review.
- `binding_missing` (exit 2): no binding exists for this project path. Resolve setup rather than choosing a reference automatically.
- `stale` (exit 2): inspected configuration, source identity, or active sources changed or became unavailable. The result includes reasons and deliberately omits the source-use instruction.
- Invalid inputs or malformed binding files produce a diagnostic and exit 1.

`resolve` is read-only. It never repairs, rebinds, downloads, runs builds, or substitutes another source version. Its configuration scope is the same bounded root-file inspection documented in PROJECT_CHECKS.md. External Gradle overrides are not detected. Changes to the kit's own parser may also require review.

A coding agent still needs to know where this kit is. Bindings do not register themselves with Codex or other agents, and do not make external instructions load automatically. Give the agent the kit path, or manually add the returned instruction to the mod project's existing instructions. The kit does not write that instruction for you.

## Refreshing and moving

Existing bindings are preserved by default. After reviewing changed targets/sources, refresh explicitly:

```text
python scripts/mcsource.py bind --project /path/to/mod --reference /path/to/kit/.local/references/version-hash --replace-binding
```

A refresh validates the new snapshot first and writes it atomically. Never refresh solely to suppress a warning. No automatic migration, cleanup, or reference deletion is performed.

Moving a mod project changes its key; create a binding for the new project location. Moving the entire kit can preserve relative reference locations, but any previously copied agent instruction needs its kit path updated. Local bindings contain machine-specific paths and remain ignored by Git.

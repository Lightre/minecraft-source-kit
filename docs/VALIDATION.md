# Validation results

Date: 2026-10-23. Environment: Windows, local Minecraft 26.2 client reference.

This exercise used an existing Fabric mod project supplied by the user. Its files were read in place. No Gradle tasks, dependency downloads, game launch, source changes, or agent-instruction installation were performed.

## Observed project target

- `gradle.properties` declares Minecraft 26.2, Fabric Loader 0.19.5, and Loom 1.18-SNAPSHOT.
- The root build uses `com.mojang:minecraft:${project.minecraft_version}` and configures Java release/source/target 25.
- The kit reports `declared_version_match` for the supplied 26.2 JAR.
- No explicit mapping declaration was present; the checker correctly leaves mapping hints empty instead of inventing a namespace.

Only the root Gradle configuration and a small sample of Minecraft API call sites were inspected. Machine-specific paths, mod sources, and private configuration contents are not included in this repository.

## Source evidence

Two API usages in the mod were traced to the prepared 26.2 source reference:

- `net.minecraft.client.Minecraft.getInstance()` is present as `public static Minecraft getInstance()`.
- `net.minecraft.resources.Identifier.fromNamespaceAndPath(...)` is present as `public static Identifier fromNamespaceAndPath(String namespace, String path)`.

This confirms those sampled names and signatures, not all APIs, loader behavior, or semantic correctness. Loader APIs must still be verified from their own resolved dependencies. The reference contains 7,055 Java files and retains its earlier CFR/Vineflower recovery diagnostics.

## Binding and cleanup

`bind` and a subsequent `resolve` both returned `located_unverified` against the full reference. The report continued to mark API compatibility unverified. Before/after checks confirmed unchanged project Git status and unchanged hashes for the three inspected root configuration files.

The temporary real-project binding was removed immediately after the check. Earlier synthetic validation workspaces, their local binding, and the marked nine-class recovery fixture were also removed. The user-supplied JAR, full source reference, original recovery diagnostics, and tool cache were preserved. No persistent binding or instruction was installed in the real mod project.

## Limits of the 26.2 project exercise

This is read-only workflow validation, not a successful mod build, in-game test, or automated proof of namespace compatibility. The effective Gradle configuration can still depend on external overrides. Official JAR provenance was not rechecked during that 26.2 project step; binding checks use the existing source identity and local snapshots.

A controlled before/after comparison of agent task performance remains untested. Further Minecraft versions and project layouts require separate validation.

## Legacy client rejection: 1.21.1

Date: 2026-10-23. Environment: Windows; user-supplied client JAR, no game or Gradle execution.

- Offline inspection found version 1.21.1, 8,269 class files, class major 65 (Java 21), and no expected `net/minecraft/client/Minecraft.class` name. Source namespace and scope remained unverified by offline inspection.
- Live `verify` succeeded against Mojang client metadata: SHA-1 `30c73b1c5da787909b2f73340419fdf13b9def88`, size 26,836,906 bytes.
- `prepare --verify-official --repair` rejected the unsupported named-client layout with exit 1 before tool acquisition or reference generation. Standalone verification was performed separately; rejected preparation did not need a metadata request.
- With a temporary synthetic project declaring 1.21.1, `check-project` returned `needs_review` (exit 2), including `named_client_source_not_established`.
- With that temporary project's declaration changed to 26.2, the same input returned `version_mismatch` (exit 1), retaining the namespace review reason.

The temporary project was removed. Before/after inventories confirmed no new tool, reference, or binding entries, and both user-supplied JARs were preserved. No raw Minecraft content or local paths are distributed.

This is negative-path validation, not legacy source-generation support. The kit does not remap the 1.21.1 input and must not advertise it as a supported named source reference. Clean-clone agent setup, additional project layouts, and effective namespace resolution remain separate acceptance gates.

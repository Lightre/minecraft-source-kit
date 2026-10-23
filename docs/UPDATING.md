# Updating the kit

The first release, `v0.1.0`, is being prepared and is not published yet. Wait until it appears in the [upstream Releases page](https://github.com/Lightre/minecraft-source-kit/releases) before using the release install command below.

## Install a published release

Clone the kit outside your mod project, then switch to the published tag:

```text
git clone https://github.com/Lightre/minecraft-source-kit.git
cd minecraft-source-kit
git fetch --tags origin
git switch --detach v0.1.0
```

Replace `v0.1.0` with another published release tag when choosing a later release. To use current development code instead, clone or update the repository's `main` branch; it may change between releases.

## Update an existing checkout

Update inside the existing kit directory. Do not reclone over the kit or delete `.local`; it contains local inputs, tools, references, and project bindings.

1. Check the kit version with `python scripts/mcsource.py --version`. Older development checkouts may not have this flag; use the Git revision instead.
2. Confirm `git status --short` shows no tracked-file changes. Preserve any other untracked files too; stop if a checkout would overwrite them. Ignored files in `.local` are expected and may remain.
3. Record the current revision with `git describe --tags --always`.
4. Fetch tags: `git fetch --tags origin`.
5. Review the upstream release notes for the chosen, known published tag (for example, `v0.1.0`).
6. Switch the existing checkout: `git switch --detach v0.1.0`.
7. Resolve each project binding again before using its reference:

   ```text
   python scripts/mcsource.py resolve --project "<mod directory>"
   ```

Investigate any `stale` or `binding_missing` result and review the project and reference before rebinding. Do not blindly rebind or decompile again. Updating the kit does not write to the mod project. A pinned tool may be fetched when preparation or repair actually needs it.

The kit does not overwrite an existing generated reference, and it currently has no option to force a new generation for the same input. If a new generation is needed, stop and preserve the existing output; make an explicit archive plan before proceeding. Do not invent an overwrite or cleanup command.

To return to the prior code revision, switch to the tag or commit recorded before updating. Review local data and schema compatibility first. Switching code does not roll back data.

## Version policy

Tags use `vMAJOR.MINOR.PATCH` and identify fixed release commits; published tags must not be moved. During `0.x` development, minor releases may change commands or local data formats, while patch releases are intended for compatible fixes. Release notes must identify migration requirements. A version string alone does not prove a pristine checkout or broader Minecraft compatibility.

For maintainers: finalize the changelog date, CLI version, support scope, and release notes in a reviewed PR before tagging its merged commit. Publish a matching GitHub Release after required checks complete. Do not include Minecraft inputs, reconstructed sources, or local tool caches.

## Agent update request

> Read docs/UPDATING.md in my existing kit directory. Update this checkout to the published release <tag> after reviewing its release notes and current local changes. Preserve my inputs, references, tools, and bindings. Resolve my project bindings afterward and report anything requiring review. Do not modify my mod projects or regenerate sources automatically.

## ZIP installs

Git checkouts are the recommended update method. The kit does not guarantee that extracting a ZIP over an existing install is safe. If you choose that migration, keep a complete copy of the old kit and `.local` data, preserve original paths, and check bindings against those paths. Do not rely on automatic replacement or deletion.

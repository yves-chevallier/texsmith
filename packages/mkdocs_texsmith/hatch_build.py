from __future__ import annotations

from hatchling.metadata.plugin.interface import MetadataHookInterface


class CustomMetadataHook(MetadataHookInterface):
    """Inject dynamic metadata for mkdocs-texsmith."""

    def update(self, metadata: dict) -> None:
        # Keep the plugin in lockstep with the main texsmith package version.
        version = str(metadata["version"])
        metadata["dependencies"] = [f"texsmith=={version}"]

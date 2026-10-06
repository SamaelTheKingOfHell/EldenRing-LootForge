"""
Manifest ledger and uninstallation tracker for LootForge.

Maintains lootforge_manifest.json to track all injected items, model IDs, and staged
assets, enabling 100% clean 1-click rollbacks.
"""

import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.models import ManifestRecord, DetectedModSet
from src.logger import system_logger


class ManifestStore:
    """
    State manager for injected mods and parameters.
    
    Why:
        Preserves an exact ledger of tool-generated items, ensuring that users can
        revert or update mods without leaving orphaned files or broken references.
        
    Example:
    ```python
    manifest = ManifestStore("lootforge_manifest.json")
    manifest.record_set(my_mod_set, staged_files=["parts/am_m_9001.partsbnd.dcx"])
    records = manifest.get_all_records()
    ```
    """

    def __init__(self, manifest_path: str = "lootforge_manifest.json"):
        self._path = Path(manifest_path)
        self._records: Dict[str, ManifestRecord] = {}
        self._load()

    def _load(self) -> None:
        """Reads persisted manifest from disk."""
        if not self._path.exists():
            return

        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for item in data.get("injected_sets", []):
                record = ManifestRecord(
                    set_id=item["set_id"],
                    created_timestamp=item["created_timestamp"],
                    allocated_model_id=item["allocated_model_id"],
                    allocated_param_id=item["allocated_param_id"],
                    source_mod_name=item["source_mod_name"],
                    target_vanilla_name=item["target_vanilla_name"],
                    loot_route=item["loot_route"],
                    loot_target_name=item["loot_target_name"],
                    staged_files=item.get("staged_files", [])
                )
                self._records[record.set_id] = record

            system_logger.info(f"Loaded manifest with {len(self._records)} injected set(s).", source="ManifestStore")
        except Exception as e:
            system_logger.error(f"Failed to load manifest {self._path}: {e}", source="ManifestStore")

    def save(self) -> None:
        """Saves current ledger state to disk."""
        try:
            payload = {
                "version": "1.0.0",
                "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
                "injected_sets": [
                    {
                        "set_id": r.set_id,
                        "created_timestamp": r.created_timestamp,
                        "allocated_model_id": r.allocated_model_id,
                        "allocated_param_id": r.allocated_param_id,
                        "source_mod_name": r.source_mod_name,
                        "target_vanilla_name": r.target_vanilla_name,
                        "loot_route": r.loot_route,
                        "loot_target_name": r.loot_target_name,
                        "staged_files": r.staged_files
                    }
                    for r in self._records.values()
                ]
            }
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            system_logger.debug(f"Manifest written to {self._path}", source="ManifestStore")
        except Exception as e:
            system_logger.error(f"Failed to save manifest {self._path}: {e}", source="ManifestStore")

    def record_set(self, mod_set: DetectedModSet, staged_files: List[str]) -> ManifestRecord:
        """Adds or updates an injected mod set record."""
        if not mod_set.allocation or not mod_set.loot_target:
            raise ValueError(f"Cannot record set '{mod_set.set_id}' without allocation and loot target.")

        rec = ManifestRecord(
            set_id=mod_set.set_id,
            created_timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            allocated_model_id=mod_set.allocation.new_model_id,
            allocated_param_id=mod_set.allocation.new_equip_param_id,
            source_mod_name=mod_set.folder_or_archive_name,
            target_vanilla_name=mod_set.target_vanilla_name,
            loot_route=mod_set.loot_target.route_type.value,
            loot_target_name=mod_set.loot_target.display_name,
            staged_files=staged_files
        )
        self._records[mod_set.set_id] = rec
        self.save()
        return rec

    def remove_set(self, set_id: str) -> Optional[ManifestRecord]:
        """Removes a set from the ledger."""
        rec = self._records.pop(set_id, None)
        if rec:
            self.save()
            system_logger.info(f"Removed set '{set_id}' from manifest.", source="ManifestStore")
        return rec

    def get_all_records(self) -> List[ManifestRecord]:
        """Returns all recorded injected sets."""
        return list(self._records.values())

    def clear(self) -> None:
        """Clears all ledger entries."""
        self._records.clear()
        self.save()

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
        self.target_regulation_path: Optional[str] = None
        self.deployed_files: List[str] = []
        self.created_msg_files: List[str] = []
        self.backed_up_files: Dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        """Reads persisted manifest from disk."""
        if not self._path.exists():
            return

        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.target_regulation_path = data.get("target_regulation_path")
            self.deployed_files = data.get("deployed_files", [])
            self.created_msg_files = data.get("created_msg_files", [])
            self.backed_up_files = data.get("backed_up_files", {})

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
                    staged_files=item.get("staged_files", []),
                    custom_skill_name=item.get("custom_skill_name"),
                    custom_skill_id=item.get("custom_skill_id"),
                    has_custom_moveset=item.get("has_custom_moveset", False)
                )
                self._records[record.set_id] = record

            system_logger.info(f"Loaded manifest with {len(self._records)} injected set(s).", source="ManifestStore")
        except Exception as e:
            system_logger.error(f"Failed to load manifest {self._path}: {e}", source="ManifestStore")

    def save(self) -> None:
        """Saves current ledger state to disk."""
        try:
            payload = {
                "version": "1.1.0",
                "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
                "target_regulation_path": self.target_regulation_path,
                "deployed_files": self.deployed_files,
                "created_msg_files": self.created_msg_files,
                "backed_up_files": self.backed_up_files,
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
                        "staged_files": r.staged_files,
                        "custom_skill_name": r.custom_skill_name,
                        "custom_skill_id": r.custom_skill_id,
                        "has_custom_moveset": r.has_custom_moveset
                    }
                    for r in self._records.values()
                ]
            }
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            system_logger.debug(f"Manifest written to {self._path}", source="ManifestStore")
        except Exception as e:
            system_logger.error(f"Failed to save manifest {self._path}: {e}", source="ManifestStore")

    def record_deployment(
        self,
        target_regulation_path: str,
        deployed_files: Optional[List[str]] = None,
        created_msg_files: Optional[List[str]] = None,
        backed_up_files: Optional[Dict[str, str]] = None
    ) -> None:
        """Records deployment environment targets for complete, clean rollbacks."""
        self.target_regulation_path = target_regulation_path
        if deployed_files:
            for df in deployed_files:
                if df not in self.deployed_files:
                    self.deployed_files.append(df)
        if created_msg_files:
            for cm in created_msg_files:
                if cm not in self.created_msg_files:
                    self.created_msg_files.append(cm)
        if backed_up_files:
            self.backed_up_files.update(backed_up_files)
        self.save()

    def record_set(self, mod_set: DetectedModSet, staged_files: List[str]) -> ManifestRecord:
        """Adds or updates an injected mod set record."""
        if not mod_set.allocation or not mod_set.loot_target:
            raise ValueError(f"Cannot record set '{mod_set.set_id}' without allocation and loot target.")

        custom_skill_name = None
        custom_skill_id = None
        has_custom_moveset = False
        if getattr(mod_set, "import_custom_moveset", True) and mod_set.skill_moveset:
            sm = mod_set.skill_moveset
            if sm.has_custom_skill and sm.skill_name:
                custom_skill_name = sm.skill_name
                custom_skill_id = sm.skill_id
            has_custom_moveset = sm.has_custom_moveset

        rec = ManifestRecord(
            set_id=mod_set.set_id,
            created_timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            allocated_model_id=mod_set.allocation.new_model_id,
            allocated_param_id=mod_set.allocation.new_equip_param_id,
            source_mod_name=mod_set.folder_or_archive_name,
            target_vanilla_name=mod_set.target_vanilla_name,
            loot_route=mod_set.loot_target.route_type.value,
            loot_target_name=mod_set.loot_target.display_name,
            staged_files=staged_files,
            custom_skill_name=custom_skill_name,
            custom_skill_id=custom_skill_id,
            has_custom_moveset=has_custom_moveset
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
        """Clears all ledger entries and deployment metadata."""
        self._records.clear()
        self.target_regulation_path = None
        self.deployed_files.clear()
        self.created_msg_files.clear()
        self.backed_up_files.clear()
        self.save()

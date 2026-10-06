"""
Mod asset scanner and analyzer for LootForge.

Discovers replacement .partsbnd.dcx files in the input directory, identifies targeted
FromSoftware model IDs, and groups parts into cohesive armor sets or weapons.
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Optional
from src.models import ModPartFile, DetectedModSet, EquipmentSlot, LootTarget
from src.knowledge_base import VanillaKnowledgeBase
from src.logger import system_logger


class ModScanner:
    """
    Scans mod intake directories and extracts FromSoftware item metadata.
    
    Why:
        Allows users to drop mods organized in arbitrary directory layouts,
        automatically determining the original vanilla target from filename patterns.
        
    Example:
    ```python
    kb = VanillaKnowledgeBase.from_data_dir("data")
    scanner = ModScanner(kb)
    discovered_sets = scanner.scan_directory("input_mods")
    for s in discovered_sets:
        print(f"Mod '{s.set_id}' targets: {s.target_vanilla_name}")
    ```
    """

    # Regex for armor parts: [am|bd|hd|lg]_[m|f]_[0-9]{4,5}.partsbnd.dcx
    ARMOR_PATTERN = re.compile(
        r"^(am|bd|hd|lg)_([mf])_(\d{4,5})\.partsbnd\.dcx$", re.IGNORECASE
    )

    # Regex for weapons: wp_[a-z]_(\d{4,5})\.partsbnd\.dcx
    WEAPON_PATTERN = re.compile(
        r"^wp_([a-z])_(\d{4,5})\.partsbnd\.dcx$", re.IGNORECASE
    )

    SLOT_MAP = {
        "am": EquipmentSlot.ARMS,
        "bd": EquipmentSlot.BODY,
        "hd": EquipmentSlot.HEAD,
        "lg": EquipmentSlot.LEGS,
        "wp": EquipmentSlot.WEAPON
    }

    def __init__(self, knowledge_base: VanillaKnowledgeBase):
        self._kb = knowledge_base

    def parse_part_file(self, file_path: Path, base_dir: Path) -> Optional[ModPartFile]:
        """
        Extracts slot, model ID, and gender metadata from a candidate parts file.
        """
        filename = file_path.name

        # Test armor pattern
        armor_match = self.ARMOR_PATTERN.match(filename)
        if armor_match:
            prefix, gender, model_id = armor_match.groups()
            slot = self.SLOT_MAP.get(prefix.lower(), EquipmentSlot.UNKNOWN)
            rel_path = str(file_path.relative_to(base_dir))
            return ModPartFile(
                file_name=filename,
                relative_path=rel_path,
                slot=slot,
                target_model_id=model_id,
                gender_variant=gender.lower(),
                file_size_bytes=file_path.stat().st_size
            )

        # Test weapon pattern
        weapon_match = self.WEAPON_PATTERN.match(filename)
        if weapon_match:
            _, model_id = weapon_match.groups()
            rel_path = str(file_path.relative_to(base_dir))
            return ModPartFile(
                file_name=filename,
                relative_path=rel_path,
                slot=EquipmentSlot.WEAPON,
                target_model_id=model_id,
                gender_variant="m",
                file_size_bytes=file_path.stat().st_size
            )

        return None

    def scan_directory(self, input_dir: str) -> List[DetectedModSet]:
        """
        Recursively scans an intake directory and groups discovered parts into DetectedModSet items.
        """
        base = Path(input_dir)
        if not base.exists():
            system_logger.warning(f"Input directory does not exist: {input_dir}", source="Scanner")
            return []

        # Map: set_identifier -> list of ModPartFile
        groups: Dict[str, List[ModPartFile]] = {}
        # Map: set_identifier -> folder name
        set_folders: Dict[str, str] = {}

        for root, _, files in os.walk(base):
            root_path = Path(root)
            for file in files:
                file_path = root_path / file
                part = self.parse_part_file(file_path, base)
                if not part:
                    continue

                # Determine grouping key: folder name if subfolder exists, else model_id
                rel_parts = file_path.relative_to(base).parts
                if len(rel_parts) > 1:
                    folder_name = rel_parts[0]
                    group_key = f"{folder_name}_{part.target_model_id}"
                else:
                    folder_name = "loose_files"
                    group_key = f"set_{part.target_model_id}"

                if group_key not in groups:
                    groups[group_key] = []
                    set_folders[group_key] = folder_name

                groups[group_key].append(part)

        detected_sets: List[DetectedModSet] = []
        for group_key, parts_list in groups.items():
            if not parts_list:
                continue

            first_part = parts_list[0]
            model_id = first_part.target_model_id
            is_weapon = any(p.slot == EquipmentSlot.WEAPON for p in parts_list)

            # Query knowledge base for target metadata
            vanilla_info = (
                self._kb.lookup_weapon(model_id)
                if is_weapon
                else self._kb.lookup_protector(model_id)
            )

            vanilla_name = (
                vanilla_info.get("name", f"Unknown Vanilla Item ({model_id})")
                if vanilla_info
                else f"Custom Set (Model {model_id})"
            )

            # Resolve default loot target
            default_target = self._kb.get_default_loot_target(model_id, is_weapon=is_weapon)

            detected_set = DetectedModSet(
                set_id=group_key,
                folder_or_archive_name=set_folders.get(group_key, "ModSet"),
                target_model_id=model_id,
                target_vanilla_name=vanilla_name,
                parts=parts_list,
                loot_target=default_target,
                is_weapon=is_weapon,
                is_enabled=True
            )
            detected_sets.append(detected_set)

        system_logger.info(f"Scan found {len(detected_sets)} distinct mod set(s).", source="Scanner")
        return detected_sets

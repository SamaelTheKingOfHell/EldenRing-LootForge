"""
Mod Scanner Service for LootForge Qt GUI.
Handles scanning input directories, extracting moveset data, and recalculating loot distribution.
Complies with [CS-MODULAR] and [CS-GRANULARITY] (<= 300 lines).
"""

import re
from pathlib import Path
from typing import List, Dict, Any, Tuple
from src.models import AdditionType, AntiDup, DetectedModSet, ItemDropConfig
from src.logger import system_logger


class ModScannerService:
    """
    Coordinates mod directory scanning, ID allocation, and loot distribution calculation.
    """

    @staticmethod
    def format_mod_display_name(folder_name: str) -> str:
        """Formats folder or archive name into readable item title."""
        cleaned = re.sub(r'-\d{2,}-[\d-]+$', '', folder_name).replace('_', ' ').replace('-', ' ')
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        if cleaned == cleaned.lower():
            cleaned = cleaned.title()
        return f"{cleaned} [LootForge]"

    @classmethod
    def ensure_all_deep_introspected(
        cls,
        base_dir: Path,
        config: Any,
        scanned_sets: List[DetectedModSet],
        drop_configs: List[ItemDropConfig]
    ) -> None:
        """Lazily extracts authentic custom skills and movesets from scanned weapon regulations."""
        try:
            from src.skill_moveset_importer import SkillMovesetImporter
            input_p = Path(config.input_directory)
            if not input_p.is_absolute():
                input_p = base_dir / input_p
            importer = SkillMovesetImporter(input_p.parent if input_p.name == "input_mods" else input_p)
            updated = False
            for s in scanned_sets:
                if s.is_weapon and s.skill_moveset and not s.skill_moveset.is_deep_introspected:
                    if importer.ensure_deep_introspected(s, input_p):
                        updated = True

            if updated:
                for s, cfg in zip(scanned_sets, drop_configs):
                    if s.skill_moveset:
                        if s.skill_moveset.has_custom_skill and s.skill_moveset.skill_name:
                            cfg.custom_skill_name = s.skill_moveset.skill_name
                        cfg.has_custom_moveset = s.skill_moveset.has_custom_moveset
        except Exception as ex:
            system_logger.warning(f"Error during deep moveset introspection: {ex}", source="ModScannerService")

    @classmethod
    def scan_mods(
        cls,
        base_dir: Path,
        config: Any,
        scanner: Any,
        id_allocator: Any
    ) -> Tuple[List[DetectedModSet], List[ItemDropConfig]]:
        """Scans input directory and produces allocated mod sets and drop configs."""
        input_p = Path(config.input_directory)
        if not input_p.is_absolute():
            input_p = base_dir / input_p

        scanned_sets = scanner.scan_directory(str(input_p))
        id_allocator.reset()
        drop_configs: List[ItemDropConfig] = []

        for s in scanned_sets:
            s.allocation = id_allocator.allocate(s.set_id)
            saved_user_rate = config.user_drop_rates.get(s.set_id, 20.0)
            saved_spoil = config.item_spoiled_states.get(s.set_id, False)
            saved_art_toggle = config.item_custom_art_toggles.get(s.set_id, True)
            s.import_custom_moveset = getattr(config, "import_custom_skills_movesets", True) and saved_art_toggle

            skill_name = ""
            has_moveset = False
            if s.skill_moveset:
                if s.skill_moveset.has_custom_skill and s.skill_moveset.skill_name:
                    skill_name = s.skill_moveset.skill_name
                has_moveset = s.skill_moveset.has_custom_moveset

            drop_configs.append(ItemDropConfig(
                item_key=s.set_id,
                name=cls.format_mod_display_name(s.folder_or_archive_name),
                vanilla_rate=20.0,
                user_rate=saved_user_rate,
                is_spoiled=saved_spoil,
                source_entity="Pending Route",
                custom_skill_name=skill_name,
                has_custom_moveset=has_moveset,
                import_custom_art=saved_art_toggle
            ))

        return scanned_sets, drop_configs

    @classmethod
    def recalculate_distribution(
        cls,
        config: Any,
        config_path: str,
        distributor: Any,
        scanned_sets: List[DetectedModSet],
        drop_configs: List[ItemDropConfig],
        addition_type: AdditionType,
        anti_dup: AntiDup,
        global_multiplier_percent: float
    ) -> None:
        """Calculates destination entity assignments and drop rates across all scanned mod sets."""
        config.addition_type = addition_type.value
        config.anti_dup = anti_dup.value
        config.save(config_path)
        distributor.reset_rotation_state()

        for s, cfg in zip(scanned_sets, drop_configs):
            target = distributor.distribute_set(
                s,
                addition_type=addition_type,
                anti_dup=anti_dup,
                global_rate_multiplier_percent=global_multiplier_percent
            )
            cfg.source_entity = target.display_name
            cfg.vanilla_rate = target.chance_or_cost

    @classmethod
    def update_item_user_rate(cls, config: Any, config_path: str, cfg: ItemDropConfig, val: float) -> None:
        """Updates and persists custom user drop rate."""
        cfg.user_rate = val
        config.user_drop_rates[cfg.item_key] = val
        config.save(config_path)

    @classmethod
    def reset_item_rate(cls, config: Any, config_path: str, cfg: ItemDropConfig, spinbox: Any) -> None:
        """Resets custom drop rate back to vanilla rate."""
        cfg.user_rate = cfg.vanilla_rate
        if cfg.item_key in config.user_drop_rates:
            del config.user_drop_rates[cfg.item_key]
        config.save(config_path)
        spinbox.setValue(cfg.vanilla_rate)

    @classmethod
    def toggle_item_spoil(cls, config: Any, config_path: str, cfg: ItemDropConfig) -> None:
        """Toggles mystery item drop masking."""
        cfg.is_spoiled = not cfg.is_spoiled
        config.item_spoiled_states[cfg.item_key] = cfg.is_spoiled
        config.save(config_path)

    @classmethod
    def toggle_custom_art(cls, config: Any, config_path: str, scanned_sets: list, cfg: ItemDropConfig, is_enabled: bool) -> None:
        """Toggles custom weapon art/moveset import."""
        cfg.import_custom_art = is_enabled
        config.item_custom_art_toggles[cfg.item_key] = is_enabled
        config.save(config_path)
        for s in scanned_sets:
            if s.set_id == cfg.item_key:
                s.import_custom_moveset = is_enabled
                break
        system_logger.info(f"Toggled custom art for {cfg.item_key}: {is_enabled}", source="ModScannerService")

"""
Dark Souls Legacy Armor Port Adapter for LootForge.

Translates legacy Souls game metadata (Dark Souls 1/2/3) into Elden Ring
EquipParamProtector absorption curves, FMG lore descriptions, and authentic titles.
Handles game installation discovery and CLI port invocation.

Adheres to [CS-MODULAR], [CS-DECOUPLE], and [CS-GRANULARITY].
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List

from src.models import EquipmentSlot, DetectedModSet
from src.logger import system_logger


class SoulsGameDiscovery:
    """
    Locates local installations of Dark Souls games across Windows Steam libraries.
    """

    DEFAULT_GAME_PATHS = {
        "ds1_ptde": [
            r"D:\SteamLibrary\steamapps\common\Dark Souls Prepare to Die Edition\DATA",
            r"C:\Program Files (x86)\Steam\steamapps\common\Dark Souls Prepare to Die Edition\DATA",
            r"C:\SteamLibrary\steamapps\common\Dark Souls Prepare to Die Edition\DATA",
        ],
        "ds1_remastered": [
            r"D:\SteamLibrary\steamapps\common\DARK SOULS REMASTERED",
            r"C:\Program Files (x86)\Steam\steamapps\common\DARK SOULS REMASTERED",
            r"C:\SteamLibrary\steamapps\common\DARK SOULS REMASTERED",
        ],
        "ds2_sotfs": [
            r"D:\SteamLibrary\steamapps\common\Dark Souls II Scholar of the First Sin\Game",
            r"C:\Program Files (x86)\Steam\steamapps\common\Dark Souls II Scholar of the First Sin\Game",
        ],
        "ds3": [
            r"D:\SteamLibrary\steamapps\common\DARK SOULS III\Game",
            r"C:\Program Files (x86)\Steam\steamapps\common\DARK SOULS III\Game",
        ]
    }

    @classmethod
    def discover_installations(cls) -> Dict[str, str]:
        """
        Discovers all available Souls game directories on the host.
        Returns a mapping of game key -> existing directory path.
        """
        found: Dict[str, str] = {}
        for game_key, paths in cls.DEFAULT_GAME_PATHS.items():
            for p in paths:
                if Path(p).exists():
                    found[game_key] = p
                    break

        # Attempt to inspect Steam libraryfolders.vdf for custom drives
        cls._search_steam_libraries(found)
        return found

    @classmethod
    def _search_steam_libraries(cls, found: Dict[str, str]) -> None:
        """Inspects steam libraryfolders.vdf for additional library paths."""
        steam_roots = [
            Path(r"C:\Program Files (x86)\Steam"),
            Path(r"D:\SteamLibrary"),
            Path(r"C:\SteamLibrary")
        ]
        library_folders: List[Path] = []
        for sr in steam_roots:
            vdf = sr / "steamapps" / "libraryfolders.vdf"
            if vdf.exists():
                try:
                    with open(vdf, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            if '"path"' in line.lower():
                                parts = line.split('"')
                                if len(parts) >= 4 and Path(parts[3]).exists():
                                    library_folders.append(Path(parts[3]))
                except Exception:
                    pass

        game_rel_subdirs = {
            "ds1_ptde": Path("steamapps/common/Dark Souls Prepare to Die Edition/DATA"),
            "ds1_remastered": Path("steamapps/common/DARK SOULS REMASTERED"),
            "ds2_sotfs": Path("steamapps/common/Dark Souls II Scholar of the First Sin/Game"),
            "ds3": Path("steamapps/common/DARK SOULS III/Game")
        }

        for lib in library_folders:
            for game_key, rel in game_rel_subdirs.items():
                if game_key not in found:
                    cand = lib / rel
                    if cand.exists():
                        found[game_key] = str(cand)


class SoulsStatConverter:
    """
    Translates Dark Souls 1 flat defense ratings into Elden Ring damage cut rates
    and status resistance attributes.
    """

    BASE_PHYSICAL_ABSORPTION = {
        EquipmentSlot.HEAD: 0.135,
        EquipmentSlot.BODY: 0.300,
        EquipmentSlot.ARMS: 0.080,
        EquipmentSlot.LEGS: 0.175,
    }

    POISE_MAP = {
        EquipmentSlot.HEAD: 8.0,
        EquipmentSlot.BODY: 26.0,
        EquipmentSlot.ARMS: 6.0,
        EquipmentSlot.LEGS: 15.0,
    }

    @classmethod
    def convert_ds1_stats_to_er(cls, slot: EquipmentSlot, stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculates Elden Ring EquipParamProtector field values from DS1 stats.
        """
        phys_def = max(1.0, float(stats.get("defensePhysics", 20)))
        slash_offset = float(stats.get("defenseSlash", 0))
        blow_offset = float(stats.get("defenseBlow", 0))
        thrust_offset = float(stats.get("defenseThrust", 0))

        mag_def = float(stats.get("defenseMagic", 10))
        fire_def = float(stats.get("defenseFire", 15))
        thun_def = float(stats.get("defenseThunder", 5))

        base_abs = cls.BASE_PHYSICAL_ABSORPTION.get(slot, 0.15)

        # In Elden Ring, damage cut rates are damage multipliers (e.g. 0.85 = 15% absorption)
        neutral_cut = max(0.01, round(1.0 - base_abs, 3))
        slash_cut = max(0.01, round(1.0 - base_abs * ((phys_def + slash_offset) / phys_def), 3))
        blow_cut = max(0.01, round(1.0 - base_abs * ((phys_def + blow_offset) / phys_def), 3))
        thrust_cut = max(0.01, round(1.0 - base_abs * ((phys_def + thrust_offset) / phys_def), 3))

        magic_cut = max(0.01, round(1.0 - base_abs * (mag_def / phys_def), 3))
        fire_cut = max(0.01, round(1.0 - base_abs * (fire_def / phys_def), 3))
        thunder_cut = max(0.01, round(1.0 - base_abs * (thun_def / phys_def), 3))
        dark_cut = max(0.01, round(1.0 - base_abs * ((mag_def + fire_def) / (2.0 * phys_def)), 3))

        poise = float(stats.get("saDurability", cls.POISE_MAP.get(slot, 5.0)))
        weight = float(stats.get("weight", 5.0))
        if slot == EquipmentSlot.BODY and weight < 10.0:
            weight = round(weight * 1.15, 1)

        # Status resistances: DS1 values are small integers; scale for ER
        resist_poison = int(stats.get("resistPoison", 5)) * 4
        resist_blood = int(stats.get("resistBlood", 10)) * 4
        resist_disease = int(stats.get("resistDisease", 5)) * 4
        resist_curse = int(stats.get("resistCurse", 0)) * 4

        return {
            "neutralDamageCutRate": neutral_cut,
            "slashDamageCutRate": slash_cut,
            "blowDamageCutRate": blow_cut,
            "thrustDamageCutRate": thrust_cut,
            "magicDamageCutRate": magic_cut,
            "fireDamageCutRate": fire_cut,
            "thunderDamageCutRate": thunder_cut,
            "darkDamageCutRate": dark_cut,
            "saDurability": poise,
            "weight": weight,
            "resistPoison": resist_poison,
            "resistBlood": resist_blood,
            "resistDisease": resist_disease,
            "resistCurse": resist_curse,
        }


class SoulsPortAdapter:
    """
    Coordinates translation between parsed souls_port_meta.json and LootForge engine.
    """

    SLOT_PREFIX_MAP = {
        EquipmentSlot.HEAD: "hd",
        EquipmentSlot.BODY: "bd",
        EquipmentSlot.ARMS: "am",
        EquipmentSlot.LEGS: "lg",
    }

    @classmethod
    def get_matching_piece(cls, mod_set: DetectedModSet, slot: EquipmentSlot) -> Optional[Dict[str, Any]]:
        """Finds the metadata piece dictionary corresponding to an equipment slot."""
        if not mod_set.souls_port_meta:
            return None
        pieces = mod_set.souls_port_meta.get("pieces", [])
        prefix = cls.SLOT_PREFIX_MAP.get(slot)
        for p in pieces:
            p_slot = p.get("slot", "").lower()
            if prefix and (p_slot == prefix or p_slot.startswith(prefix)):
                return p
        return None

    @classmethod
    def resolve_piece_name(cls, mod_set: DetectedModSet, slot: EquipmentSlot, marker: str = "✦ [LootForge]") -> str:
        """Returns the authentic item title for the slot."""
        piece = cls.get_matching_piece(mod_set, slot)
        if piece and piece.get("name"):
            return f"{marker} {piece['name']}".strip()
        return f"{marker} {mod_set.target_vanilla_name} ({slot.value.capitalize()})".strip()

    @classmethod
    def resolve_piece_caption(cls, mod_set: DetectedModSet, slot: EquipmentSlot) -> str:
        """Returns the authentic lore description for the slot."""
        piece = cls.get_matching_piece(mod_set, slot)
        if piece and piece.get("description"):
            game = mod_set.souls_port_meta.get("sourceGame", "Dark Souls") if mod_set.souls_port_meta else "Dark Souls"
            desc = piece["description"].replace("\r\n", "\n").strip()
            return f"{desc}\n\n[Legacy Souls Relic: {game}]"
        return "Legacy Souls relic ported to the Lands Between. Preserves authentic protective attributes."

    @classmethod
    def get_er_field_updates(cls, mod_set: DetectedModSet, slot: EquipmentSlot) -> Dict[str, Any]:
        """Calculates Elden Ring EquipParamProtector field updates from source stats."""
        piece = cls.get_matching_piece(mod_set, slot)
        if not piece or not piece.get("stats"):
            return {}
        return SoulsStatConverter.convert_ds1_stats_to_er(slot, piece["stats"])

    @classmethod
    def run_souls_port_cli(
        cls,
        set_key: str = "black_knight",
        game_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
        target_model_id: Optional[str] = None,
        reg_tool_path: Optional[str] = None
    ) -> int:
        """
        Executes RegTool port-souls-set command to extract and modernize a legacy set.
        """
        if not game_dir:
            installations = SoulsGameDiscovery.discover_installations()
            game_dir = installations.get("ds1_ptde") or installations.get("ds1_remastered")

        if not game_dir or not Path(game_dir).exists():
            system_logger.error("Dark Souls 1 directory not found for SoulsPort extraction.", source="SoulsPort")
            return 1

        args = ["port-souls-set", "--set", set_key, "--game-dir", game_dir]
        if output_dir:
            args.extend(["--output-dir", output_dir])
        if target_model_id:
            args.extend(["--target-model-id", target_model_id])

        if reg_tool_path and Path(reg_tool_path).exists():
            cmd = [reg_tool_path] + args
        else:
            cmd = ["dotnet", "run", "--project", "tools/RegTool", "--"] + args

        system_logger.info(f"Running SoulsPort CLI: {' '.join(cmd)}", source="SoulsPort")
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            system_logger.info(f"SoulsPort succeeded: {res.stdout.strip()}", source="SoulsPort")
        else:
            system_logger.error(f"SoulsPort failed: {res.stderr.strip()}", source="SoulsPort")
        return res.returncode

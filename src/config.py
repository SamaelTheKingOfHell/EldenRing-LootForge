"""
Configuration manager for LootForge.

Handles game path discovery on Windows and Linux/Steam Deck, ID range configuration,
and persistence of user preferences in a portable JSON file.
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any
from src.logger import system_logger


class LootForgeConfig:
    """
    Manages operational paths and parameters for LootForge.
    
    Why:
        Encapsulates cross-platform environment discovery (Windows registry/folders
        vs. Linux/Steam Deck Proton mounts) so the core engine remains platform-agnostic.
        
    Example:
    ```python
    cfg = LootForgeConfig.load(config_path="config.json")
    print(cfg.game_directory)
    print(cfg.is_steam_deck)
    ```
    """

    def __init__(
        self,
        game_directory: str = "",
        input_directory: str = "input_mods",
        output_directory: str = "mod",
        backup_directory: str = "backups",
        manifest_file: str = "lootforge_manifest.json",
        min_model_id: int = 9000,
        max_model_id: int = 9999,
        base_param_id: int = 9000000,
        base_item_lot_id: int = 9100000,
        base_shop_id: int = 9200000,
        active_regulation_path: str = "",
        default_locale: str = "en",
        debug_mode: bool = True,
        port: int = 8383,
        addition_type: int = 2,
        anti_dup: int = 1,
        global_multiplier_percent: float = 100.0,
        global_spoiled: bool = True,
        items_per_page: int = 8,
        banner_collapsed: bool = False,
        user_drop_rates: Optional[Dict[str, float]] = None,
        item_spoiled_states: Optional[Dict[str, bool]] = None
    ):
        self.game_directory = game_directory
        self.input_directory = input_directory
        self.output_directory = output_directory
        self.backup_directory = backup_directory
        self.manifest_file = manifest_file
        self.min_model_id = min_model_id
        self.max_model_id = max_model_id
        self.base_param_id = base_param_id
        self.base_item_lot_id = base_item_lot_id
        self.base_shop_id = base_shop_id
        self.active_regulation_path = active_regulation_path
        self.default_locale = default_locale
        self.debug_mode = debug_mode
        self.port = port
        self.addition_type = addition_type
        self.anti_dup = anti_dup
        self.global_multiplier_percent = global_multiplier_percent
        self.global_spoiled = global_spoiled
        self.items_per_page = items_per_page
        self.banner_collapsed = banner_collapsed
        self.user_drop_rates = user_drop_rates if user_drop_rates is not None else {}
        self.item_spoiled_states = item_spoiled_states if item_spoiled_states is not None else {}

        # Auto-discover game directory if not specified
        if not self.game_directory:
            self.game_directory = self.detect_game_directory()

        if not self.active_regulation_path:
            self.active_regulation_path = self.resolve_active_regulation_bin()

    @property
    def is_windows(self) -> bool:
        """Returns True if running on a Windows host."""
        return sys.platform.startswith("win")

    @property
    def is_steam_deck(self) -> bool:
        """
        Returns True if running on a Steam Deck (SteamOS) or Linux environment.
        """
        return not self.is_windows and (
            Path("/home/deck").exists() or "steamos" in os.uname().release.lower()
        )

    def detect_game_directory(self) -> str:
        """
        Discovers the Elden Ring installation directory across common locations.
        """
        candidate_paths = []

        if self.is_windows:
            candidate_paths.extend([
                r"C:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game",
                r"D:\SteamLibrary\steamapps\common\ELDEN RING\Game",
                r"E:\SteamLibrary\steamapps\common\ELDEN RING\Game",
                r"C:\Games\ELDEN RING\Game",
                r"D:\Games\ELDEN RING\Game"
            ])
        else:
            # Linux and Steam Deck common installation roots
            home = str(Path.home())
            candidate_paths.extend([
                os.path.join(home, ".steam/steam/steamapps/common/ELDEN RING/Game"),
                os.path.join(home, ".local/share/Steam/steamapps/common/ELDEN RING/Game"),
                "/run/media/mmcblk0p1/steamapps/common/ELDEN RING/Game",  # MicroSD card on Deck
                os.path.join(home, "Games/ELDEN RING/Game")
            ])

        for path in candidate_paths:
            p = Path(path)
            if p.exists() and (p / "eldenring.exe").exists():
                system_logger.info(f"Auto-detected Elden Ring game directory: {path}", source="Config")
                return str(p.resolve())

        system_logger.debug("Elden Ring game directory not auto-detected; user prompt required.", source="Config")
        return ""

    def resolve_active_regulation_bin(self) -> str:
        """
        Discovers the active regulation.bin file, prioritizing active mod managers.
        
        Why:
            Players frequently use Mod Engine 2 or mod managers with a pre-existing
            customized regulation.bin in their mod folder. Detecting it prevents
            clobbering previous mod settings.
        """
        if self.active_regulation_path and Path(self.active_regulation_path).exists():
            return self.active_regulation_path

        # 1. Check configured mod output staging folder (ModEngine2 mod/regulation.bin)
        mod_reg = Path(self.output_directory) / "regulation.bin"
        if mod_reg.exists():
            system_logger.info(f"Detected active Mod Engine regulation.bin at: {mod_reg}", source="Config")
            return str(mod_reg.resolve())

        # 2. Check game installation folder (vanilla regulation.bin)
        if self.game_directory:
            game_reg = Path(self.game_directory) / "regulation.bin"
            if game_reg.exists():
                system_logger.info(f"Detected vanilla regulation.bin at: {game_reg}", source="Config")
                return str(game_reg.resolve())

        return ""

    def to_dict(self) -> Dict[str, Any]:
        """Serializes configuration to a dictionary."""
        return {
            "game_directory": self.game_directory,
            "active_regulation_path": self.active_regulation_path,
            "input_directory": self.input_directory,
            "output_directory": self.output_directory,
            "backup_directory": self.backup_directory,
            "manifest_file": self.manifest_file,
            "min_model_id": self.min_model_id,
            "max_model_id": self.max_model_id,
            "base_param_id": self.base_param_id,
            "base_item_lot_id": self.base_item_lot_id,
            "base_shop_id": self.base_shop_id,
            "default_locale": self.default_locale,
            "debug_mode": self.debug_mode,
            "port": self.port,
            "addition_type": self.addition_type,
            "anti_dup": self.anti_dup,
            "global_multiplier_percent": self.global_multiplier_percent,
            "global_spoiled": self.global_spoiled,
            "items_per_page": self.items_per_page,
            "banner_collapsed": self.banner_collapsed,
            "user_drop_rates": self.user_drop_rates,
            "item_spoiled_states": self.item_spoiled_states,
            "is_windows": self.is_windows,
            "is_steam_deck": self.is_steam_deck
        }

    def save(self, file_path: str = "config.json") -> None:
        """Persists configuration to disk."""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=2)
            system_logger.debug(f"Configuration saved to {file_path}", source="Config")
        except Exception as e:
            system_logger.error(f"Failed to save configuration: {e}", source="Config")

    @classmethod
    def load(cls, file_path: str = "config.json") -> "LootForgeConfig":
        """Loads configuration from disk, falling back to defaults if not found."""
        p = Path(file_path)
        if not p.exists():
            instance = cls()
            instance.save(file_path)
            return instance

        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(
                game_directory=data.get("game_directory", ""),
                active_regulation_path=data.get("active_regulation_path", ""),
                input_directory=data.get("input_directory", "input_mods"),
                output_directory=data.get("output_directory", "mod"),
                backup_directory=data.get("backup_directory", "backups"),
                manifest_file=data.get("manifest_file", "lootforge_manifest.json"),
                min_model_id=data.get("min_model_id", 9000),
                max_model_id=data.get("max_model_id", 9999),
                base_param_id=data.get("base_param_id", 9000000),
                base_item_lot_id=data.get("base_item_lot_id", 9100000),
                base_shop_id=data.get("base_shop_id", 9200000),
                default_locale=data.get("default_locale", "en"),
                debug_mode=data.get("debug_mode", True),
                port=data.get("port", 8383),
                addition_type=data.get("addition_type", 2),
                anti_dup=data.get("anti_dup", 1),
                global_multiplier_percent=float(data.get("global_multiplier_percent", 100.0)),
                global_spoiled=bool(data.get("global_spoiled", True)),
                items_per_page=int(data.get("items_per_page", 8)),
                banner_collapsed=bool(data.get("banner_collapsed", False)),
                user_drop_rates=data.get("user_drop_rates", {}),
                item_spoiled_states=data.get("item_spoiled_states", {})
            )
        except Exception as e:
            system_logger.warning(f"Error reading {file_path}; using defaults: {e}", source="Config")
            return cls()

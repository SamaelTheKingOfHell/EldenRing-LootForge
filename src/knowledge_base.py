"""
Vanilla game knowledge base for LootForge.

Maintains reference mappings between FromSoftware 3D model IDs and in-game vanilla armor/weapons,
Boss Soul Remembrances, elite enemies, and merchants.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from src.models import LootDistributionType, LootTarget
from src.logger import system_logger


class VanillaKnowledgeBase:
    """
    Registry for resolving FromSoftware model IDs and routing loot.
    
    Why:
        Decouples the scanning and patch pipeline from hardcoded game IDs,
        allowing easy updates across Elden Ring patches and DLC additions.
        
    Example:
    ```python
    kb = VanillaKnowledgeBase.from_data_dir("data")
    item = kb.lookup_protector("4000")
    print(item["name"])  # "Carian Knight Set"
    target = kb.get_default_loot_target("4000")
    print(target.display_name)
    ```
    """

    def __init__(self, models_data: Dict[str, Any], routes_data: Dict[str, Any]):
        self._protectors = models_data.get("protectors", {})
        self._weapons = models_data.get("weapons", {})
        self._boss_remembrances = routes_data.get("bossRemembrances", [])
        self._elite_enemies = routes_data.get("eliteEnemies", [])
        self._merchants = routes_data.get("merchants", [])

    @classmethod
    def from_data_dir(cls, data_dir: str = "data") -> "VanillaKnowledgeBase":
        """Loads knowledge base from data directory files."""
        p = Path(data_dir)
        models_file = p / "vanilla_models.json"
        routes_file = p / "loot_routes.json"

        models_data: Dict[str, Any] = {}
        routes_data: Dict[str, Any] = {}

        if models_file.exists():
            with open(models_file, "r", encoding="utf-8") as f:
                models_data = json.load(f)
        else:
            system_logger.warning(f"Models file not found: {models_file}", source="KnowledgeBase")

        if routes_file.exists():
            with open(routes_file, "r", encoding="utf-8") as f:
                routes_data = json.load(f)
        else:
            system_logger.warning(f"Loot routes file not found: {routes_file}", source="KnowledgeBase")

        return cls(models_data, routes_data)

    def lookup_protector(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Finds vanilla armor data by 4-digit model ID."""
        cleaned = model_id.lstrip("0") or "0"
        # Check both direct and zero-padded
        return self._protectors.get(model_id) or self._protectors.get(cleaned)

    def lookup_weapon(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Finds vanilla weapon data by 4-digit model ID."""
        return self._weapons.get(model_id)

    def get_default_loot_target(self, model_id: str, is_weapon: bool = False) -> LootTarget:
        """
        Calculates the most thematic loot drop target for a model ID.
        """
        info = self.lookup_weapon(model_id) if is_weapon else self.lookup_protector(model_id)
        if not info:
            # Fallback for unrecognized items: place at Merchant Kalé for safe access
            return LootTarget(
                route_type=LootDistributionType.MERCHANT_SHOP,
                target_id="kale_church_of_elleh",
                display_name="Merchant Kalé (Church of Elleh)",
                chance_or_cost=5000
            )

        route = info.get("defaultRoute", "enemy_drop")
        source_id = info.get("targetSourceId", "")
        enemy_name = info.get("defaultEnemyName", "Unknown Drop Source")

        if route == "boss_remembrance":
            return LootTarget(
                route_type=LootDistributionType.BOSS_REMEMBRANCE,
                target_id=source_id,
                display_name=enemy_name,
                chance_or_cost=30000
            )
        elif route == "enemy_drop":
            return LootTarget(
                route_type=LootDistributionType.ENEMY_DROP,
                target_id=source_id,
                display_name=enemy_name,
                chance_or_cost=20.0
            )
        else:
            return LootTarget(
                route_type=LootDistributionType.MERCHANT_SHOP,
                target_id=source_id,
                display_name=enemy_name,
                chance_or_cost=10000
            )

    def list_boss_remembrances(self) -> List[Dict[str, Any]]:
        """Returns all selectable Boss Soul Remembrances."""
        return list(self._boss_remembrances)

    def list_elite_enemies(self) -> List[Dict[str, Any]]:
        """Returns all selectable enemy drop targets."""
        return list(self._elite_enemies)

    def list_merchants(self) -> List[Dict[str, Any]]:
        """Returns all selectable merchants."""
        return list(self._merchants)

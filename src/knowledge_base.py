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
        self._accessories = models_data.get("accessories", {})
        self._boss_remembrances = routes_data.get("bossRemembrances", [])
        self._elite_enemies = routes_data.get("eliteEnemies", [])
        self._merchants = routes_data.get("merchants", [])
        self._enemies = routes_data.get("enemies", [])

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
        padded = model_id.zfill(4)
        return self._protectors.get(model_id) or self._protectors.get(padded) or self._protectors.get(cleaned)

    def lookup_weapon(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Finds vanilla weapon data by 4-digit model ID."""
        cleaned = model_id.lstrip("0") or "0"
        padded = model_id.zfill(4)
        return self._weapons.get(model_id) or self._weapons.get(padded) or self._weapons.get(cleaned)

    def lookup_accessory(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Finds vanilla accessory/talisman data by ID or baseParamId."""
        cleaned = model_id.lstrip("0") or "0"
        padded = model_id.zfill(4)
        return self._accessories.get(model_id) or self._accessories.get(padded) or self._accessories.get(cleaned)

    def list_all_vanilla_protectors(self) -> Dict[str, Dict[str, Any]]:
        """Returns all cataloged vanilla armor sets."""
        return dict(self._protectors)

    def list_all_vanilla_weapons(self) -> Dict[str, Dict[str, Any]]:
        """Returns all cataloged vanilla weapons."""
        return dict(self._weapons)

    def list_all_vanilla_accessories(self) -> Dict[str, Dict[str, Any]]:
        """Returns all cataloged vanilla accessories/talismans."""
        return dict(self._accessories)

    def get_default_loot_target(
        self,
        model_id: str,
        is_weapon: bool = False,
        is_accessory: bool = False
    ) -> LootTarget:
        """
        Calculates the most thematic loot drop target for a model ID.
        """
        if is_accessory:
            info = self.lookup_accessory(model_id)
        elif is_weapon:
            info = self.lookup_weapon(model_id)
        else:
            info = self.lookup_protector(model_id)

        if not info:
            if is_accessory:
                return LootTarget(
                    route_type=LootDistributionType.MAP_PICKUP,
                    target_id="102100",
                    display_name="Gatefront Ruins Underground Chest",
                    chance_or_cost=100.0
                )
            if is_weapon:
                return LootTarget(
                    route_type=LootDistributionType.MERCHANT_SHOP,
                    target_id="twin_maiden_husks",
                    display_name="Twin Maiden Husks (Roundtable Hold)",
                    chance_or_cost=5000
                )
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
        elif route in ("map_pickup", "world_chest", "chest"):
            return LootTarget(
                route_type=LootDistributionType.MAP_PICKUP,
                target_id=source_id,
                display_name=enemy_name,
                chance_or_cost=100.0
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

    def get_enemy_lot_id(self, enemy_id: str) -> Optional[int]:
        """Resolves an enemy or elite enemy identifier to its ItemLotParam_enemy ID."""
        for e in self._elite_enemies:
            if e.get("id") == enemy_id:
                return e.get("lotParamId")
        for e in self._enemies:
            if e.get("id") == enemy_id:
                return e.get("lotParamId")
        return None

    def list_enemies(self) -> List[Dict[str, Any]]:
        """Returns all roaming and standard enemies."""
        return list(self._enemies)

    def get_diablo_distribution_pools(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Returns categorized game-wide loot targets for procedural Diablo loot distribution:
        - bosses: Major Remembrance bosses (Finger Reader Enia / Boss events)
        - merchants: Non-enemy shops (Twin Maiden Husks, Kalé, Nomadic Merchants)
        - chests: Non-enemy world chests and discoverable map pickups
        - elites: Elite knights and roaming champions across all regions
        - roaming: Roaming enemies and standard encounter mobs
        """
        chests = [
            {"id": "gatefront_ruins_chest", "name": "Gatefront Ruins Chest (Limgrave)", "lotParamId": 102100},
            {"id": "castle_sol_medallion", "name": "Castle Sol Secret Chest (Mountaintops)", "lotParamId": 102800},
            {"id": "morne_tunnel_cache", "name": "Morne Tunnel Hidden Cache (Weeping Peninsula)", "lotParamId": 20600},
            {"id": "alexander_warrior_remains", "name": "Alexander Warrior Jar Treasure (Farum Azula)", "lotParamId": 101740},
            {"id": "patches_leather_cache", "name": "Patches' Murkwater Cave Cache (Limgrave)", "lotParamId": 101840},
            {"id": "yura_ronin_cache", "name": "Yura's Zamor Ruins Cache (Mountaintops)", "lotParamId": 101640},
        ]
        for e in self._enemies:
            if "chest" in e.get("name", "").lower() or "cache" in e.get("name", "").lower():
                if not any(c["id"] == e.get("id") for c in chests):
                    chests.append(e)

        roaming = [
            e for e in self._enemies
            if not any(k in e.get("name", "").lower() for k in ["chest", "quest", "cache"])
        ]

        return {
            "bosses": list(self._boss_remembrances),
            "merchants": list(self._merchants),
            "chests": chests,
            "elites": list(self._elite_enemies),
            "roaming": roaming if roaming else list(self._elite_enemies)
        }



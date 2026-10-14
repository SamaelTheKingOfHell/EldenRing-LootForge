"""
Vanilla game knowledge base for LootForge.

Maintains reference mappings between FromSoftware 3D model IDs and in-game vanilla armor/weapons,
Boss Soul Remembrances, chests, elite enemies, and merchants.
Adheres to [CS-MODULAR] and [CS-GRANULARITY] (<= 300 lines).
"""

from typing import Dict, Any, Optional, List
from src.models import LootDistributionType, LootTarget, ProgressionTier
from src.knowledge_loader import KnowledgeLoader


class VanillaKnowledgeBase:
    """Registry for resolving FromSoftware model IDs and routing loot."""

    def __init__(self, models_data: Dict[str, Any], routes_data: Dict[str, Any]):
        self._protectors = models_data.get("protectors", {})
        self._weapons = models_data.get("weapons", {})
        self._accessories = models_data.get("accessories", {})
        self._boss_remembrances = routes_data.get("bossRemembrances", [])
        self._elite_enemies = routes_data.get("eliteEnemies", [])
        self._merchants = routes_data.get("merchants", [])
        self._enemies = routes_data.get("enemies", [])
        self._chests = routes_data.get("chests", [])
        self._discovered_weapons = models_data.get("_discovered_weapons", {})
        self._discovered_protectors = models_data.get("_discovered_protectors", {})
        self._discovered_accessories = models_data.get("_discovered_accessories", {})
        self._discovered_boss_lots = routes_data.get("_discovered_boss_lots", [])
        self._discovered_chests = routes_data.get("_discovered_chests", [])

    @classmethod
    def from_data_dir(cls, data_dir: str = "data") -> "VanillaKnowledgeBase":
        """Loads knowledge base using KnowledgeLoader."""
        models_data, routes_data = KnowledgeLoader.load_data(data_dir)
        return cls(models_data, routes_data)

    def lookup_protector(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Finds vanilla armor data by model ID or param ID."""
        cleaned = model_id.lstrip("0") or "0"
        padded = model_id.zfill(4)
        return (
            self._discovered_protectors.get(model_id) or
            self._discovered_protectors.get(padded) or
            self._discovered_protectors.get(cleaned) or
            self._protectors.get(model_id) or
            self._protectors.get(padded) or
            self._protectors.get(cleaned)
        )

    def lookup_weapon(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Finds vanilla weapon data by model ID or param ID."""
        cleaned = model_id.lstrip("0") or "0"
        padded = model_id.zfill(4)
        return (
            self._discovered_weapons.get(model_id) or
            self._discovered_weapons.get(padded) or
            self._discovered_weapons.get(cleaned) or
            self._weapons.get(model_id) or
            self._weapons.get(padded) or
            self._weapons.get(cleaned)
        )

    def lookup_accessory(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Finds vanilla accessory/talisman data by ID or baseParamId."""
        cleaned = model_id.lstrip("0") or "0"
        padded = model_id.zfill(4)
        return (
            self._discovered_accessories.get(model_id) or
            self._discovered_accessories.get(padded) or
            self._discovered_accessories.get(cleaned) or
            self._accessories.get(model_id) or
            self._accessories.get(padded) or
            self._accessories.get(cleaned)
        )

    def list_all_vanilla_protectors(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._protectors) if self._protectors else dict(self._discovered_protectors)

    def list_all_vanilla_weapons(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._weapons) if self._weapons else dict(self._discovered_weapons)

    def list_all_vanilla_accessories(self, tier: Optional[ProgressionTier] = None) -> Dict[str, Dict[str, Any]]:
        accs = self._accessories if self._accessories else self._discovered_accessories
        if tier is None:
            return dict(accs)
        filtered = {k: v for k, v in accs.items() if v.get("progressionTier") == tier.value}
        return filtered if filtered else dict(accs)

    def list_all_discovered_weapons(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._discovered_weapons) if self._discovered_weapons else dict(self._weapons)

    def list_all_discovered_protectors(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._discovered_protectors) if self._discovered_protectors else dict(self._protectors)

    def list_all_discovered_accessories(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._discovered_accessories) if self._discovered_accessories else dict(self._accessories)

    def list_all_discovered_boss_lots(self, tier: Optional[ProgressionTier] = None) -> List[Dict[str, Any]]:
        lots = self._discovered_boss_lots
        if tier is None or not lots:
            return list(lots)
        filtered = [b for b in lots if b.get("progressionTier") == tier.value]
        return filtered if filtered else list(lots)

    def list_all_discovered_chests(self, tier: Optional[ProgressionTier] = None) -> List[Dict[str, Any]]:
        chests = self._discovered_chests
        if tier is None or not chests:
            return list(chests)
        filtered = [c for c in chests if c.get("progressionTier") == tier.value]
        return filtered if filtered else list(chests)

    def get_default_loot_target(
        self,
        model_id: str,
        is_weapon: bool = False,
        is_accessory: bool = False
    ) -> LootTarget:
        """Calculates default drop target for an item."""
        if is_accessory:
            info = self.lookup_accessory(model_id)
        elif is_weapon:
            info = self.lookup_weapon(model_id)
        else:
            info = self.lookup_protector(model_id)

        if not info:
            if is_accessory:
                return LootTarget(LootDistributionType.MAP_PICKUP, "102100", "Gatefront Ruins Underground Chest", 100.0)
            if is_weapon:
                return LootTarget(LootDistributionType.MERCHANT_SHOP, "twin_maiden_husks", "Twin Maiden Husks (Roundtable Hold)", 5000)
            return LootTarget(LootDistributionType.MERCHANT_SHOP, "kale_church_of_elleh", "Merchant Kalé (Church of Elleh)", 5000)

        route = info.get("defaultRoute", "enemy_drop")
        source_id = info.get("targetSourceId", "")
        enemy_name = info.get("defaultEnemyName", "Unknown Drop Source")

        if route == "boss_remembrance":
            return LootTarget(LootDistributionType.BOSS_REMEMBRANCE, source_id, enemy_name, 30000)
        elif route in ("map_pickup", "world_chest", "chest"):
            return LootTarget(LootDistributionType.MAP_PICKUP, source_id, enemy_name, 100.0)
        elif route == "enemy_drop":
            return LootTarget(LootDistributionType.ENEMY_DROP, source_id, enemy_name, 20.0)
        else:
            return LootTarget(LootDistributionType.MERCHANT_SHOP, source_id, enemy_name, 10000)

    def get_progression_tier(self, entity_or_id: Any) -> ProgressionTier:
        """Resolves an entity or ID to its canonical ProgressionTier."""
        if isinstance(entity_or_id, ProgressionTier):
            return entity_or_id
        if isinstance(entity_or_id, int) and entity_or_id in (1, 2, 3, 4):
            return ProgressionTier(entity_or_id)

        info: Optional[Dict[str, Any]] = None
        if isinstance(entity_or_id, dict):
            info = entity_or_id
        elif isinstance(entity_or_id, str):
            info = self.lookup_protector(entity_or_id) or self.lookup_weapon(entity_or_id) or self.lookup_accessory(entity_or_id)
            if not info:
                for b in self._boss_remembrances:
                    if b.get("id") == entity_or_id or b.get("boss") == entity_or_id:
                        info = b
                        break
                if not info:
                    for c in (self._discovered_chests or self._chests):
                        if c.get("id") == entity_or_id or str(c.get("lotParamId")) == entity_or_id:
                            info = c
                            break
                if not info:
                    for e in self._elite_enemies:
                        if e.get("id") == entity_or_id or str(e.get("lotParamId")) == entity_or_id:
                            info = e
                            break
                if not info:
                    for m in self._merchants:
                        if m.get("id") == entity_or_id or str(m.get("shopId")) == entity_or_id:
                            info = m
                            break

        if info:
            if "progressionTier" in info:
                val = int(info["progressionTier"])
                if val in (1, 2, 3, 4):
                    return ProgressionTier(val)
            if "targetSourceId" in info and info["targetSourceId"] != entity_or_id:
                return self.get_progression_tier(info["targetSourceId"])
            name_lower = (info.get("name", "") + " " + info.get("location", "") + " " + info.get("description", "")).lower()
        else:
            name_lower = str(entity_or_id).lower()

        if any(w in name_lower for w in ["haligtree", "malenia", "farum", "azula", "maliketh", "mohg", "placidusax", "elden beast", "elden throne", "snowfield", "mountaintop", "sol"]):
            return ProgressionTier.ENDGAME
        if any(w in name_lower for w in ["altus", "leyndell", "volcano", "gelmir", "rykard", "godfrey", "crucible", "ordovis", "vyke", "vargram"]):
            return ProgressionTier.LATE
        if any(w in name_lower for w in ["liurnia", "raya lucaria", "caria", "rennala", "radahn", "caelid", "redmane", "makar", "siofra", "ainsel", "moonveil"]):
            return ProgressionTier.MID
        if any(w in name_lower for w in ["stormveil", "limgrave", "weeping", "gatefront", "morne", "godrick", "margit", "darriwil", "kale", "elleh"]):
            return ProgressionTier.EARLY

        return ProgressionTier.MID

    def get_progression_tier_for_spec(self, spec: Dict[str, Any]) -> ProgressionTier:
        for ep in spec.get("equip_params", []):
            base_clone_id = ep.get("base_clone_id")
            if base_clone_id:
                return self.get_progression_tier(str(base_clone_id))
        return self.get_progression_tier(spec.get("set_id", ""))

    def get_chest_after_boss(self, boss_id: str) -> Optional[Dict[str, Any]]:
        all_chests = (self._chests or []) + (self._discovered_chests or [])
        for b in self._boss_remembrances:
            if b.get("id") == boss_id or b.get("boss") == boss_id:
                chest_id = b.get("chestAfterBossId")
                if chest_id:
                    for c in all_chests:
                        if c.get("id") == chest_id:
                            return dict(c)
        for c in all_chests:
            if c.get("afterBoss") == boss_id:
                return dict(c)
        return None

    def list_chests(self, tier: Optional[ProgressionTier] = None) -> List[Dict[str, Any]]:
        chests = self._discovered_chests if self._discovered_chests else self._chests
        if tier is None or not chests:
            return list(chests)
        filtered = [c for c in chests if c.get("progressionTier") == tier.value]
        return filtered if filtered else list(chests)

    def list_boss_remembrances(self, tier: Optional[ProgressionTier] = None) -> List[Dict[str, Any]]:
        if tier is None:
            return list(self._boss_remembrances)
        filtered = [b for b in self._boss_remembrances if b.get("progressionTier") == tier.value]
        return filtered if filtered else list(self._boss_remembrances)

    def list_elite_enemies(self, tier: Optional[ProgressionTier] = None) -> List[Dict[str, Any]]:
        if tier is None:
            return list(self._elite_enemies)
        filtered = [e for e in self._elite_enemies if e.get("progressionTier") == tier.value]
        return filtered if filtered else list(self._elite_enemies)

    def list_merchants(self, tier: Optional[ProgressionTier] = None) -> List[Dict[str, Any]]:
        if tier is None:
            return list(self._merchants)
        filtered = [m for m in self._merchants if m.get("progressionTier") == tier.value]
        return filtered if filtered else list(self._merchants)

    def get_enemy_lot_id(self, enemy_id: str) -> Optional[int]:
        for e in self._elite_enemies:
            if e.get("id") == enemy_id:
                return e.get("lotParamId")
        for e in self._enemies:
            if e.get("id") == enemy_id:
                return e.get("lotParamId")
        return None

    def list_enemies(self) -> List[Dict[str, Any]]:
        return list(self._enemies)

    def get_diablo_distribution_pools(self) -> Dict[str, List[Dict[str, Any]]]:
        """Returns game-wide loot targets for procedural Diablo loot distribution."""
        chests = list(self._discovered_chests) if self._discovered_chests else list(self._chests)
        if not chests:
            chests = [
                {"id": "gatefront_ruins_chest", "name": "Gatefront Ruins Chest (Limgrave)", "lotParamId": 102100, "progressionTier": 1},
                {"id": "castle_sol_medallion", "name": "Castle Sol Secret Chest (Mountaintops)", "lotParamId": 102800, "progressionTier": 4},
                {"id": "morne_tunnel_cache", "name": "Morne Tunnel Hidden Cache (Weeping Peninsula)", "lotParamId": 20600, "progressionTier": 1},
                {"id": "alexander_warrior_remains", "name": "Alexander Warrior Jar Treasure (Farum Azula)", "lotParamId": 101740, "progressionTier": 4},
                {"id": "patches_leather_cache", "name": "Patches' Murkwater Cave Cache (Limgrave)", "lotParamId": 101840, "progressionTier": 1},
                {"id": "yura_ronin_cache", "name": "Yura's Zamor Ruins Cache (Mountaintops)", "lotParamId": 101640, "progressionTier": 4},
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

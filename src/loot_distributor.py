"""Loot distribution engine for LootForge.

Implements distribution algorithms, Enums (AdditionType, AntiDup),
set cohesion invariance, boss rotation with cascading fallback, and drop rate scaling.
"""

import random
from typing import Dict, Optional, Set
from src.models import (
    AdditionType, AntiDup, LootDistributionType, LootTarget,
    DetectedModSet, ItemDropConfig
)
from src.knowledge_base import VanillaKnowledgeBase
from src.logger import system_logger


class LootDistributor:
    """Orchestrates loot distribution according to AdditionType and AntiDup rules."""

    def __init__(self, knowledge_base: VanillaKnowledgeBase):
        self._kb = knowledge_base
        self._assigned_bosses: Set[str] = set()
        self._global_spoil_enabled: bool = False
        self._item_configs: Dict[str, ItemDropConfig] = {}
        self._test_mode_index: int = 0

    @property
    def global_spoil_enabled(self) -> bool:
        """Returns True if spoiler protection is disabled globally."""
        return self._global_spoil_enabled

    @global_spoil_enabled.setter
    def global_spoil_enabled(self, val: bool) -> None:
        self._global_spoil_enabled = bool(val)

    def reset_rotation_state(self) -> None:
        """Clears boss assignment ledger and test mode index for a fresh run."""
        self._assigned_bosses.clear()
        self._test_mode_index = 0

    def distribute_set(
        self,
        mod_set: DetectedModSet,
        addition_type: AdditionType = AdditionType.STANDARD_ADDITION,
        anti_dup: AntiDup = AntiDup.BOSS_ROTATION,
        global_rate_multiplier_percent: float = 100.0
    ) -> LootTarget:
        """Calculates the single unified loot target for an entire mod set."""
        model_id = mod_set.target_model_id
        is_weapon = mod_set.is_weapon

        if is_weapon:
            system_logger.info(
                f"Custom weapon '{mod_set.set_id}': using standalone fallback definition.",
                source="LootDistributor"
            )

        vanilla_info = (
            self._kb.lookup_weapon(model_id)
            if is_weapon
            else self._kb.lookup_protector(model_id)
        )

        is_not_dropped = False
        is_100_percent_boss = False
        default_route = "enemy_drop"
        source_id = ""
        source_name = ""

        if vanilla_info:
            default_route = vanilla_info.get("defaultRoute", "enemy_drop")
            source_id = vanilla_info.get("targetSourceId", "")
            source_name = vanilla_info.get("defaultEnemyName", "")
            if default_route in ("boss_remembrance", "merchant_shop"):
                is_not_dropped = True
                if default_route == "boss_remembrance":
                    is_100_percent_boss = True

        if not source_name:
            all_enemies = self._kb.list_elite_enemies()
            if all_enemies:
                fallback = random.choice(all_enemies)
                source_id, source_name, default_route = fallback["id"], fallback["name"], "enemy_drop"
                system_logger.info(
                    f"Model '{model_id}' not in knowledge base, assigned to: {source_name}",
                    source="LootDistributor"
                )
            else:
                source_name = "Wandering Enemy (Uncharted)"

        # 0. Test Mode: cycles across Bosses, Mobs, Shops
        if addition_type == AdditionType.TEST_MODE:
            target = self._test_mode_placement()
            mod_set.loot_target = target
            return target

        # 1. Anti-Dup Handling for 100% Boss Drops
        if is_100_percent_boss:
            if anti_dup == AntiDup.BOSS_ROTATION:
                target = self._rotate_boss_drop(source_id, source_name)
            elif anti_dup == AntiDup.EVERYTHING_IN_THE_WILD:
                target = self._place_in_wild(source_name)
            else:
                target = self._standard_placement(default_route, source_id, source_name)
            mod_set.loot_target = target
            return target

        # 2. Addition Type Routing
        if addition_type == AdditionType.RANDOM_ADDITION:
            target = self._random_boss_shop_or_transfusion() if is_not_dropped else self._random_mob_drop()
        else:
            target = self._standard_placement(default_route, source_id, source_name)

        mod_set.loot_target = target
        return target

    def _test_mode_placement(self) -> LootTarget:
        """Cycles items across all 3 major loot pools for test verification."""
        pool_type, idx = self._test_mode_index % 3, self._test_mode_index // 3
        self._test_mode_index += 1

        if pool_type == 0:
            bosses = self._kb.list_boss_remembrances()
            if bosses:
                chosen = bosses[idx % len(bosses)]
                system_logger.info(f"Test Mode: Routed to Boss Remembrance -> '{chosen['name']}'", source="LootDistributor")
                return LootTarget(LootDistributionType.BOSS_REMEMBRANCE, chosen["id"], f"[Test: Boss] {chosen['name']}", float(chosen.get("defaultCost", 1000.0)))
        elif pool_type == 1:
            test_mobs = [
                {"id": "431100000", "name": "Godrick Soldier (Gatefront / Limgrave)"},
                {"id": "430000000", "name": "Wandering Noble (Church of Elleh Road)"},
                {"id": "435100000", "name": "Godrick Knight (Gatefront Ruins)"},
            ]
            chosen = test_mobs[idx % len(test_mobs)]
            system_logger.info(f"Test Mode: Routed to Enemy Drop -> '{chosen['name']}' (100% drop)", source="LootDistributor")
            return LootTarget(LootDistributionType.ENEMY_DROP, chosen["id"], f"[Test: Mob 100%] {chosen['name']}", 100.0)
        else:
            merchants = self._kb.list_merchants()
            if merchants:
                chosen = merchants[idx % len(merchants)]
                system_logger.info(f"Test Mode: Routed to Merchant Shop -> '{chosen['name']}'", source="LootDistributor")
                return LootTarget(LootDistributionType.MERCHANT_SHOP, chosen["id"], f"[Test: Shop] {chosen['name']}", float(chosen.get("defaultRuneCost", 100.0)))

        return LootTarget(LootDistributionType.ENEMY_DROP, "431100000", "[Test: Mob 100%] Godrick Soldier", 100.0)

    def _rotate_boss_drop(self, original_boss_id: str, original_boss_name: str) -> LootTarget:
        """AntiDup Option 1: Boss Rotation with cascading fallbacks."""
        bosses = self._kb.list_boss_remembrances()
        available = [b for b in bosses if b["id"] != original_boss_id and b["id"] not in self._assigned_bosses]

        if available:
            chosen = random.choice(available)
            self._assigned_bosses.add(chosen["id"])
            system_logger.info(f"Boss Rotation: Rotated from '{original_boss_name}' to '{chosen['name']}'", source="LootDistributor")
            return LootTarget(LootDistributionType.BOSS_REMEMBRANCE, chosen["id"], chosen["name"], float(chosen.get("defaultCost", 30000)))

        # Fallback 1: Mini-bosses
        mini_bosses = [
            e for e in self._kb.list_elite_enemies()
            if any(k in e["name"].lower() for k in ["sentinel", "knight", "cavalry", "assassin", "darriwil"])
            and e["id"] not in self._assigned_bosses
        ]
        if mini_bosses:
            chosen_mini = random.choice(mini_bosses)
            self._assigned_bosses.add(chosen_mini["id"])
            system_logger.info(f"Boss Rotation: Cascaded to Mini-Boss '{chosen_mini['name']}'", source="LootDistributor")
            return LootTarget(LootDistributionType.ENEMY_DROP, chosen_mini["id"], chosen_mini["name"], float(chosen_mini.get("defaultDropChance", 25.0)))

        # Fallback 2: Wild enemies
        return self._place_in_wild(original_boss_name)

    def _place_in_wild(self, original_name: str) -> LootTarget:
        """Places item into the wild on stronger enemies at normal drop rates."""
        all_enemies = self._kb.list_elite_enemies()
        chosen = random.choice(all_enemies) if all_enemies else {"id": "wild_enemy", "name": "Strong Wild Foe", "defaultDropChance": 20.0}
        system_logger.info(f"Placed in wild on: '{chosen['name']}' ({chosen.get('defaultDropChance', 20.0)}%)", source="LootDistributor")
        return LootTarget(LootDistributionType.ENEMY_DROP, chosen["id"], chosen["name"], float(chosen.get("defaultDropChance", 20.0)))

    def _random_boss_shop_or_transfusion(self) -> LootTarget:
        """Places non-dropped items randomly across bosses, shops, or transfusions."""
        pool = [
            {"type": LootDistributionType.BOSS_REMEMBRANCE, "id": b["id"], "name": b["name"], "cost": float(b.get("defaultCost", 30000))}
            for b in self._kb.list_boss_remembrances()
        ] + [
            {"type": LootDistributionType.MERCHANT_SHOP, "id": m["id"], "name": m["name"], "cost": float(m.get("defaultRuneCost", 10000))}
            for m in self._kb.list_merchants()
        ]
        chosen = random.choice(pool) if pool else {"type": LootDistributionType.MERCHANT_SHOP, "id": "kale", "name": "Merchant Kalé", "cost": 5000.0}
        return LootTarget(chosen["type"], chosen["id"], chosen["name"], chosen["cost"])

    def _random_mob_drop(self) -> LootTarget:
        """Places normal items randomly onto wild mobs."""
        enemies = self._kb.list_elite_enemies()
        chosen = random.choice(enemies) if enemies else {"id": "mob_default", "name": "Roaming Enemy", "defaultDropChance": 20.0}
        return LootTarget(LootDistributionType.ENEMY_DROP, chosen["id"], chosen["name"], float(chosen.get("defaultDropChance", 20.0)))

    def _standard_placement(self, default_route: str, source_id: str, source_name: str) -> LootTarget:
        """Standard thematic placement."""
        route_map = {
            "boss_remembrance": (LootDistributionType.BOSS_REMEMBRANCE, 30000.0),
            "merchant_shop": (LootDistributionType.MERCHANT_SHOP, 10000.0),
        }
        route, cost = route_map.get(default_route, (LootDistributionType.ENEMY_DROP, 20.0))
        return LootTarget(route, source_id, source_name, cost)

    @staticmethod
    def calculate_final_rate(user_rate: float, global_multiplier_percent: float) -> float:
        """Calculates final drop rate: user_rate * (global_multiplier / 100.0)."""
        return round(user_rate * (global_multiplier_percent / 100.0), 2)

    @staticmethod
    def get_rate_color_status(final_rate: float, vanilla_rate: float) -> str:
        """Returns 'green' if higher, 'red' if lower, 'grey' if equal."""
        if abs(final_rate - vanilla_rate) < 0.01:
            return "grey"
        return "green" if final_rate > vanilla_rate else "red"

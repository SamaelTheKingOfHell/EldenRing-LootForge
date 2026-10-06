"""
Loot distribution engine for LootForge.

Implements the user-specified distribution algorithms, Enums (AdditionType, AntiDup),
set cohesion invariance, boss rotation with cascading fallback, and drop rate scaling.
"""

import random
from typing import List, Dict, Any, Optional, Set
from src.models import (
    AdditionType, AntiDup, LootDistributionType, LootTarget,
    DetectedModSet, ItemDropConfig
)
from src.knowledge_base import VanillaKnowledgeBase
from src.logger import system_logger


class LootDistributor:
    """
    Orchestrates loot distribution according to AdditionType and AntiDup rules.
    
    Why:
        Enforces game balance, preserves set cohesion (pieces from the same mod
        always drop from the exact same mob), and handles 100% boss drop rotation.
        
    Example:
    ```python
    distributor = LootDistributor(knowledge_base)
    target = distributor.distribute_set(
        mod_set,
        addition_type=AdditionType.RANDOM_ADDITION,
        anti_dup=AntiDup.BOSS_ROTATION
    )
    ```
    """

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
        """Clears boss assignment ledger and test mode index for a fresh distribution run."""
        self._assigned_bosses.clear()
        self._test_mode_index = 0

    def distribute_set(
        self,
        mod_set: DetectedModSet,
        addition_type: AdditionType = AdditionType.STANDARD_ADDITION,
        anti_dup: AntiDup = AntiDup.BOSS_ROTATION,
        global_rate_multiplier_percent: float = 100.0
    ) -> LootTarget:
        """
        Calculates the single unified loot target for an entire mod set.
        
        Rule: In ALL cases, sets from the same mod always drop from the same mob/boss.
        """
        model_id = mod_set.target_model_id
        is_weapon = mod_set.is_weapon

        # If custom weapon, use standalone fallback
        if is_weapon:
            system_logger.info(
                f"Custom weapon '{mod_set.set_id}': using standalone fallback definition.",
                source="LootDistributor"
            )

        # Lookup vanilla info
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

        # Fallback: if model not in KB or name missing, assign to a random known entity
        if not source_name:
            all_enemies = self._kb.list_elite_enemies()
            if all_enemies:
                fallback = random.choice(all_enemies)
                source_id = fallback["id"]
                source_name = fallback["name"]
                default_route = "enemy_drop"
                system_logger.info(
                    f"Model '{model_id}' not in knowledge base, assigned to: {source_name}",
                    source="LootDistributor"
                )
            else:
                source_name = "Wandering Enemy (Uncharted)"

        # =========================================================================
        # 0. TEST MODE ROUTING (ADDITION TYPE 3: CYCLES ACROSS ALL LOOT POOLS)
        # =========================================================================
        if addition_type == AdditionType.TEST_MODE:
            target = self._test_mode_placement()
            mod_set.loot_target = target
            return target

        # =========================================================================
        # 1. ANTI-DUP HANDLING FOR 100% BOSS DROPS
        # =========================================================================
        if is_100_percent_boss:
            if anti_dup == AntiDup.BOSS_ROTATION:
                target = self._rotate_boss_drop(source_id, source_name)
                mod_set.loot_target = target
                return target
            elif anti_dup == AntiDup.EVERYTHING_IN_THE_WILD:
                target = self._place_in_wild(source_name)
                mod_set.loot_target = target
                return target

        # =========================================================================
        # 2. ADDITION TYPE ROUTING
        # =========================================================================
        if addition_type == AdditionType.RANDOM_ADDITION:
            if is_not_dropped:
                # Items that are not dropped in vanilla are added randomly to bosses, shops, and transfusions
                target = self._random_boss_shop_or_transfusion()
            else:
                # Normal dropped items are placed on mobs randomly
                target = self._random_mob_drop()
        else:
            # STANDARD ADDITION: places on the same expected drop list, shop or boss weapon transfusion
            target = self._standard_placement(default_route, source_id, source_name)

        mod_set.loot_target = target
        return target

    def _test_mode_placement(self) -> LootTarget:
        """
        AdditionType.TEST_MODE (Option 3):
        Cycles items sequentially across all 3 major loot pools:
          1. Boss Remembrances (ShopLineupParam / Finger Reader Enia)
          2. Enemy Drops (ItemLotParam_enemy / 100% drop rate for testing)
          3. Merchant Shops (ShopLineupParam / Kalé & Roundtable merchants)
        Ensures each pool receives test injection to verify the full pipeline.
        """
        pool_type = self._test_mode_index % 3
        idx = self._test_mode_index // 3
        self._test_mode_index += 1

        if pool_type == 0:
            # Pool 1: Boss Remembrances
            bosses = self._kb.list_boss_remembrances()
            if bosses:
                chosen = bosses[idx % len(bosses)]
                system_logger.info(
                    f"Test Mode: Routed to Boss Remembrance -> '{chosen['name']}'",
                    source="LootDistributor"
                )
                return LootTarget(
                    route_type=LootDistributionType.BOSS_REMEMBRANCE,
                    target_id=chosen["id"],
                    display_name=f"[Test: Boss] {chosen['name']}",
                    chance_or_cost=float(chosen.get("defaultCost", 1000.0))
                )
        elif pool_type == 1:
            # Pool 2: Enemy Drops (100% drop rate for quick in-game verification)
            enemies = self._kb.list_elite_enemies()
            if enemies:
                chosen = enemies[idx % len(enemies)]
                system_logger.info(
                    f"Test Mode: Routed to Enemy Drop -> '{chosen['name']}' (100% drop)",
                    source="LootDistributor"
                )
                return LootTarget(
                    route_type=LootDistributionType.ENEMY_DROP,
                    target_id=chosen["id"],
                    display_name=f"[Test: Mob 100%] {chosen['name']}",
                    chance_or_cost=100.0
                )
        else:
            # Pool 3: Merchant Shops (100 Runes test price)
            merchants = self._kb.list_merchants()
            if merchants:
                chosen = merchants[idx % len(merchants)]
                system_logger.info(
                    f"Test Mode: Routed to Merchant Shop -> '{chosen['name']}'",
                    source="LootDistributor"
                )
                return LootTarget(
                    route_type=LootDistributionType.MERCHANT_SHOP,
                    target_id=chosen["id"],
                    display_name=f"[Test: Shop] {chosen['name']}",
                    chance_or_cost=float(chosen.get("defaultRuneCost", 100.0))
                )

        return LootTarget(
            route_type=LootDistributionType.ENEMY_DROP,
            target_id="test_enemy",
            display_name="[Test: Mob 100%] Roaming Enemy",
            chance_or_cost=100.0
        )

    def _rotate_boss_drop(self, original_boss_id: str, original_boss_name: str) -> LootTarget:
        """
        AntiDup Option 1: Boss Rotation.
        Adds item to a different boss (limit 1 set per boss).
        If bosses exhausted -> distribute to mini-bosses.
        If mini-bosses exhausted -> distribute to wild enemies at normal drop rate.
        """
        bosses = self._kb.list_boss_remembrances()
        # Find candidate bosses different from original and not yet assigned
        available_bosses = [
            b for b in bosses
            if b["id"] != original_boss_id and b["id"] not in self._assigned_bosses
        ]

        if available_bosses:
            chosen = random.choice(available_bosses)
            self._assigned_bosses.add(chosen["id"])
            system_logger.info(
                f"Boss Rotation: Rotated from '{original_boss_name}' to '{chosen['name']}'",
                source="LootDistributor"
            )
            return LootTarget(
                route_type=LootDistributionType.BOSS_REMEMBRANCE,
                target_id=chosen["id"],
                display_name=chosen["name"],
                chance_or_cost=float(chosen.get("defaultCost", 30000))
            )

        # Fallback 1: Distribute to mini-bosses
        mini_bosses = [
            e for e in self._kb.list_elite_enemies()
            if any(k in e["name"].lower() for k in ["sentinel", "knight", "cavalry", "assassin", "darriwil"])
            and e["id"] not in self._assigned_bosses
        ]

        if mini_bosses:
            chosen_mini = random.choice(mini_bosses)
            self._assigned_bosses.add(chosen_mini["id"])
            system_logger.info(
                f"Boss Rotation (Bosses Exhausted): Cascaded to Mini-Boss '{chosen_mini['name']}'",
                source="LootDistributor"
            )
            return LootTarget(
                route_type=LootDistributionType.ENEMY_DROP,
                target_id=chosen_mini["id"],
                display_name=chosen_mini["name"],
                chance_or_cost=float(chosen_mini.get("defaultDropChance", 25.0))
            )

        # Fallback 2: Distribute to stronger enemies in the wild at normal drop rate
        return self._place_in_wild(original_boss_name)

    def _place_in_wild(self, original_name: str) -> LootTarget:
        """Places item into the wild on stronger enemies at normal drop rates."""
        all_enemies = self._kb.list_elite_enemies()
        chosen = random.choice(all_enemies) if all_enemies else {
            "id": "wild_enemy", "name": "Strong Wild Foe", "defaultDropChance": 20.0
        }
        system_logger.info(
            f"Placed in wild on: '{chosen['name']}' at normal drop rate ({chosen.get('defaultDropChance', 20.0)}%)",
            source="LootDistributor"
        )
        return LootTarget(
            route_type=LootDistributionType.ENEMY_DROP,
            target_id=chosen["id"],
            display_name=chosen["name"],
            chance_or_cost=float(chosen.get("defaultDropChance", 20.0))
        )

    def _random_boss_shop_or_transfusion(self) -> LootTarget:
        """Places non-dropped items randomly across bosses, shops, or transfusions."""
        pool = []
        for b in self._kb.list_boss_remembrances():
            pool.append({
                "type": LootDistributionType.BOSS_REMEMBRANCE,
                "id": b["id"],
                "name": b["name"],
                "cost": float(b.get("defaultCost", 30000))
            })
        for m in self._kb.list_merchants():
            pool.append({
                "type": LootDistributionType.MERCHANT_SHOP,
                "id": m["id"],
                "name": m["name"],
                "cost": float(m.get("defaultRuneCost", 10000))
            })

        chosen = random.choice(pool) if pool else {
            "type": LootDistributionType.MERCHANT_SHOP,
            "id": "kale", "name": "Merchant Kalé", "cost": 5000.0
        }
        return LootTarget(
            route_type=chosen["type"],
            target_id=chosen["id"],
            display_name=chosen["name"],
            chance_or_cost=chosen["cost"]
        )

    def _random_mob_drop(self) -> LootTarget:
        """Places normal items randomly onto wild mobs."""
        enemies = self._kb.list_elite_enemies()
        chosen = random.choice(enemies) if enemies else {
            "id": "mob_default", "name": "Roaming Enemy", "defaultDropChance": 20.0
        }
        return LootTarget(
            route_type=LootDistributionType.ENEMY_DROP,
            target_id=chosen["id"],
            display_name=chosen["name"],
            chance_or_cost=float(chosen.get("defaultDropChance", 20.0))
        )

    def _standard_placement(self, default_route: str, source_id: str, source_name: str) -> LootTarget:
        """Standard thematic placement."""
        if default_route == "boss_remembrance":
            return LootTarget(
                route_type=LootDistributionType.BOSS_REMEMBRANCE,
                target_id=source_id,
                display_name=source_name,
                chance_or_cost=30000.0
            )
        elif default_route == "merchant_shop":
            return LootTarget(
                route_type=LootDistributionType.MERCHANT_SHOP,
                target_id=source_id,
                display_name=source_name,
                chance_or_cost=10000.0
            )
        else:
            return LootTarget(
                route_type=LootDistributionType.ENEMY_DROP,
                target_id=source_id,
                display_name=source_name,
                chance_or_cost=20.0
            )

    @staticmethod
    def calculate_final_rate(user_rate: float, global_multiplier_percent: float) -> float:
        """
        Calculates final drop rate: user_rate * (global_multiplier / 100.0).
        """
        return round(user_rate * (global_multiplier_percent / 100.0), 2)

    @staticmethod
    def get_rate_color_status(final_rate: float, vanilla_rate: float) -> str:
        """
        Returns 'green' if higher, 'red' if lower, 'grey' if equal.
        """
        if abs(final_rate - vanilla_rate) < 0.01:
            return "grey"
        elif final_rate > vanilla_rate:
            return "green"
        else:
            return "red"

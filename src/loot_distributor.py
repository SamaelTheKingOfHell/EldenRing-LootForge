"""Loot distribution engine for LootForge.

Implements distribution algorithms, Enums (AdditionType, AntiDup),
set cohesion invariance, boss rotation with cascading fallback, and drop rate scaling.
"""

import random
from typing import Dict, Optional, Set
from src.models import (
    AdditionType, AntiDup, LootDistributionType, LootTarget,
    DetectedModSet, ItemDropConfig, ProgressionTier
)
from src.knowledge_base import VanillaKnowledgeBase

from src.logger import system_logger


class LootDistributor:
    """Orchestrates loot distribution according to AdditionType and AntiDup rules."""

    def __init__(self, knowledge_base: VanillaKnowledgeBase, max_shop_capacity: int = 15):
        self._kb = knowledge_base
        self._assigned_bosses: Set[str] = set()
        self._assigned_chests: Set[str] = set()
        self._global_spoil_enabled: bool = False
        self._item_configs: Dict[str, ItemDropConfig] = {}
        self._test_mode_index: int = 0
        self._shop_allocations: Dict[str, int] = {}
        self.max_shop_capacity: int = max_shop_capacity

    @property
    def global_spoil_enabled(self) -> bool:
        """Returns True if spoiler protection is disabled globally."""
        return self._global_spoil_enabled

    @global_spoil_enabled.setter
    def global_spoil_enabled(self, val: bool) -> None:
        self._global_spoil_enabled = bool(val)

    def reset_rotation_state(self) -> None:
        """Clears boss and chest ledgers, shop counts, and test mode index for a fresh run."""
        self._assigned_bosses.clear()
        self._assigned_chests.clear()
        self._shop_allocations.clear()
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
        vanilla_info = (
            self._kb.lookup_weapon(model_id)
            if is_weapon
            else self._kb.lookup_protector(model_id)
        )

        if not vanilla_info:
            system_logger.info(
                f"Mod '{mod_set.set_id}' (model {model_id}): not in knowledge base, using thematic fallback.",
                source="LootDistributor"
            )
        else:
            system_logger.debug(
                f"Mod '{mod_set.set_id}' (model {model_id}): matched vanilla item '{vanilla_info.get('name')}'",
                source="LootDistributor"
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
            fallback = random.choice(all_enemies) if all_enemies else {"id": "mob_default", "name": "Wandering Enemy"}
            source_id, source_name, default_route = fallback["id"], fallback["name"], "enemy_drop"

        tier = self._kb.get_progression_tier(vanilla_info or mod_set.target_model_id)

        # 0. Test Mode: cycles across Bosses, Mobs, Shops
        if addition_type == AdditionType.TEST_MODE:
            target = self._test_mode_placement()
            mod_set.loot_target = target
            return target

        # 1. Anti-Dup Handling for 100% Boss Drops
        if is_100_percent_boss:
            if anti_dup == AntiDup.CHEST_AFTER_BOSS:
                target = self._route_chest_after_boss(source_id, source_name, tier=tier)
            elif anti_dup == AntiDup.BOSS_ROTATION:
                target = self._rotate_boss_drop(source_id, source_name, tier=tier)
            elif anti_dup == AntiDup.EVERYTHING_IN_THE_WILD:
                target = self._place_in_wild(source_name, tier=tier)
            else:
                target = self._standard_placement(default_route, source_id, source_name)
            mod_set.loot_target = target
            return target

        # 2. Addition Type Routing
        if addition_type == AdditionType.RANDOM_ADDITION:
            target = self._random_boss_shop_or_transfusion(tier=tier) if is_not_dropped else self._random_mob_drop(tier=tier)
        elif not is_weapon:
            chests = self._kb.list_chests(tier=tier) or self._kb.list_chests()
            if chests:
                unassigned = [c for c in chests if str(c.get("lotParamId", c.get("id"))) not in self._assigned_chests]
                chosen = unassigned[0] if unassigned else chests[len(self._assigned_chests) % len(chests)]
                lot_id = chosen.get("lotParamId", 102100)
                self._assigned_chests.add(str(lot_id))
                target = LootTarget(LootDistributionType.MAP_PICKUP, str(lot_id), chosen.get("name", f"Chest {lot_id}"), 100.0)
            else:
                target = self._standard_placement(default_route, source_id, source_name)
        else:
            target = self._standard_placement(default_route, source_id, source_name)

        mod_set.loot_target = target
        return target

    def _test_mode_placement(self) -> LootTarget:
        """Cycles items across all 3 major loot pools for test verification with shop overflow protection."""
        pool_type, idx = self._test_mode_index % 3, self._test_mode_index // 3
        self._test_mode_index += 1

        if pool_type == 0:
            bosses = self._kb.list_boss_remembrances()
            if bosses:
                available_bosses = [b for b in bosses if self._shop_allocations.get(b["id"], 0) < self.max_shop_capacity]
                if available_bosses:
                    chosen = available_bosses[idx % len(available_bosses)]
                    self._shop_allocations[chosen["id"]] = self._shop_allocations.get(chosen["id"], 0) + 1
                    system_logger.info(f"Test Mode: Routed to Boss Remembrance -> '{chosen['name']}'", source="LootDistributor")
                    return LootTarget(LootDistributionType.BOSS_REMEMBRANCE, chosen["id"], f"[Test: Boss] {chosen['name']}", float(chosen.get("defaultCost", 1000.0)))
        elif pool_type == 2:
            merchants = self._kb.list_merchants()
            if merchants:
                available_merchants = [m for m in merchants if self._shop_allocations.get(m["id"], 0) < self.max_shop_capacity]
                if available_merchants:
                    chosen = available_merchants[idx % len(available_merchants)]
                    self._shop_allocations[chosen["id"]] = self._shop_allocations.get(chosen["id"], 0) + 1
                    system_logger.info(f"Test Mode: Routed to Merchant Shop -> '{chosen['name']}'", source="LootDistributor")
                    return LootTarget(LootDistributionType.MERCHANT_SHOP, chosen["id"], f"[Test: Shop] {chosen['name']}", float(chosen.get("defaultRuneCost", 100.0)))

        # Fallback to enemy drop pool when shop rows are full or pool_type == 1
        test_mobs = self._kb.list_elite_enemies() or self._kb.list_enemies()
        if test_mobs:
            chosen = test_mobs[idx % len(test_mobs)]
            chosen_id = str(chosen.get("id", "generic_mob"))
            chosen_name = str(chosen.get("name", "Roaming Foe"))
            system_logger.info(f"Test Mode: Routed to Enemy Drop -> '{chosen_name}' (100% drop)", source="LootDistributor")
            return LootTarget(LootDistributionType.ENEMY_DROP, chosen_id, f"[Test: Mob 100%] {chosen_name}", 100.0)
        return LootTarget(LootDistributionType.ENEMY_DROP, "roaming_mob", "[Test: Mob 100%] Roaming Enemy", 100.0)

    def _rotate_boss_drop(self, original_boss_id: str, original_boss_name: str, tier: Optional[ProgressionTier] = None) -> LootTarget:
        """
        AntiDup Option 1: Boss Rotation with progression matching and cascade to Chest After Boss.
        1. Rotates to another major boss strictly within the matching progression tier (max 1 set per boss).
        2. If all bosses in that tier are filled, cascades directly to high-value Chests After Boss in that tier.
        3. If chests in that tier are exhausted, cascades to elite enemies in that tier.
        """
        tier_bosses = self._kb.list_boss_remembrances(tier=tier)
        available = [
            b for b in tier_bosses
            if b["id"] != original_boss_id and b["id"] not in self._assigned_bosses and self._shop_allocations.get(b["id"], 0) < 1
        ]

        if available:
            chosen = random.choice(available)
            self._assigned_bosses.add(chosen["id"])
            self._shop_allocations[chosen["id"]] = self._shop_allocations.get(chosen["id"], 0) + 1
            system_logger.info(f"Boss Rotation ({tier.name if tier else 'ALL'}): Rotated from '{original_boss_name}' to '{chosen['name']}'", source="LootDistributor")
            return LootTarget(LootDistributionType.BOSS_REMEMBRANCE, chosen["id"], chosen["name"], float(chosen.get("defaultCost", 30000)))

        # Fallback 1: High-value Chests After Boss in the matching progression tier
        tier_chests = self._kb.list_chests(tier=tier)
        post_boss = [c for c in tier_chests if c.get("afterBoss")]
        cands = post_boss if post_boss else tier_chests
        avail = [c for c in cands if str(c.get("lotParamId", 102100)) not in self._assigned_chests]
        if avail:
            chosen_chest = random.choice(avail)
            self._assigned_chests.add(str(chosen_chest.get("lotParamId", 102100)))
            system_logger.info(f"Boss Rotation: Cascaded to Chest '{chosen_chest['name']}'", source="LootDistributor")
            return LootTarget(LootDistributionType.MAP_PICKUP, str(chosen_chest.get("lotParamId", 102100)), f"[Chest After Boss] {chosen_chest['name']}", 100.0)

        # Fallback 2: Elite enemies / mini-bosses in matching progression tier
        tier_elites = self._kb.list_elite_enemies(tier=tier)
        if tier_elites:
            chosen_mini = random.choice(tier_elites)
            system_logger.info(f"Boss Rotation: Cascaded to Mini-Boss '{chosen_mini['name']}'", source="LootDistributor")
            return LootTarget(LootDistributionType.ENEMY_DROP, chosen_mini["id"], chosen_mini["name"], float(chosen_mini.get("defaultDropChance", 25.0)))

        return self._place_in_wild(original_boss_name, tier=tier)

    def _route_chest_after_boss(self, boss_id: str, boss_name: str, tier: Optional[ProgressionTier] = None) -> LootTarget:
        """AntiDup Option 3: Guaranteed Chest After Boss without duplication."""
        chest = self._kb.get_chest_after_boss(boss_id)
        if chest and str(chest.get("lotParamId", 102100)) in self._assigned_chests:
            chest = None
        if not chest:
            tier_chests = self._kb.list_chests(tier=tier)
            post_boss = [c for c in tier_chests if c.get("afterBoss")]
            cands = post_boss if post_boss else tier_chests
            avail = [c for c in cands if str(c.get("lotParamId", 102100)) not in self._assigned_chests]
            if avail:
                chest = random.choice(avail)

        if chest:
            self._assigned_chests.add(str(chest.get("lotParamId", 102100)))
            system_logger.info(f"AntiDup: Routed directly to Chest '{chest['name']}'", source="LootDistributor")
            return LootTarget(LootDistributionType.MAP_PICKUP, str(chest.get("lotParamId", 102100)), f"[Chest After Boss] {chest['name']}", 100.0)

        return self._place_in_wild(boss_name, tier=tier)

    def _place_in_wild(self, original_name: str, tier: Optional[ProgressionTier] = None) -> LootTarget:
        """Places item into the wild on enemies strictly within matching progression tier."""
        tier_enemies = self._kb.list_elite_enemies(tier=tier)
        chosen = random.choice(tier_enemies) if tier_enemies else {"id": "wild_enemy", "name": "Strong Wild Foe", "defaultDropChance": 20.0}
        system_logger.info(f"Placed in wild ({tier.name if tier else 'ALL'}): '{chosen['name']}' ({chosen.get('defaultDropChance', 20.0)}%)", source="LootDistributor")
        return LootTarget(LootDistributionType.ENEMY_DROP, chosen["id"], chosen["name"], float(chosen.get("defaultDropChance", 20.0)))

    def _random_boss_shop_or_transfusion(self, tier: Optional[ProgressionTier] = None) -> LootTarget:
        """Places non-dropped items randomly across bosses, shops, or transfusions with capacity checking."""
        tier_bosses = self._kb.list_boss_remembrances(tier=tier)
        tier_merchants = self._kb.list_merchants(tier=tier)
        pool = [
            {"type": LootDistributionType.BOSS_REMEMBRANCE, "id": b["id"], "name": b["name"], "cost": float(b.get("defaultCost", 30000))}
            for b in tier_bosses
            if self._shop_allocations.get(b["id"], 0) < self.max_shop_capacity
        ] + [
            {"type": LootDistributionType.MERCHANT_SHOP, "id": m["id"], "name": m["name"], "cost": float(m.get("defaultRuneCost", 10000))}
            for m in tier_merchants
            if self._shop_allocations.get(m["id"], 0) < self.max_shop_capacity
        ]
        if pool:
            chosen = random.choice(pool)
            self._shop_allocations[chosen["id"]] = self._shop_allocations.get(chosen["id"], 0) + 1
            return LootTarget(chosen["type"], chosen["id"], chosen["name"], chosen["cost"])

        # When all shops/bosses in tier hit row limit, rotate overflowed item to chests in tier first (Bosses -> Chests -> The Rest)
        tier_chests = self._kb.list_chests(tier=tier)
        if tier_chests:
            chosen_chest = random.choice(tier_chests)
            system_logger.info(f"Shop limits reached. Rotating overflowed item to Chest '{chosen_chest['name']}'.", source="LootDistributor")
            return LootTarget(LootDistributionType.MAP_PICKUP, str(chosen_chest.get("lotParamId", 102100)), chosen_chest["name"], 100.0)

        system_logger.info("Shop row limits reached for merchants/bosses. Rotating overflowed item to wild enemies.", source="LootDistributor")
        return self._place_in_wild(original_name="Overflowed Mod Item", tier=tier)

    def _random_mob_drop(self, tier: Optional[ProgressionTier] = None) -> LootTarget:
        """Places normal items randomly onto wild mobs in matching progression tier."""
        enemies = self._kb.list_elite_enemies(tier=tier)
        chosen = random.choice(enemies) if enemies else {"id": "mob_default", "name": "Roaming Enemy", "defaultDropChance": 20.0}
        return LootTarget(LootDistributionType.ENEMY_DROP, chosen["id"], chosen["name"], float(chosen.get("defaultDropChance", 20.0)))


    def _standard_placement(self, default_route: str, source_id: str, source_name: str) -> LootTarget:
        """Standard thematic placement with shop capacity overflow checks."""
        if default_route in ("boss_remembrance", "merchant_shop"):
            if self._shop_allocations.get(source_id, 0) >= self.max_shop_capacity:
                system_logger.info(
                    f"Shop param row limit reached for '{source_name}'. Rotating overflowed item to wild enemy drop.",
                    source="LootDistributor"
                )
                return self._place_in_wild(source_name)
            self._shop_allocations[source_id] = self._shop_allocations.get(source_id, 0) + 1

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

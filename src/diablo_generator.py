"""
Diablo-style procedural loot variant generator for LootForge.

Rolls random rarity tiers, prefixes, and suffixes, applying authentic stat modifiers,
SpEffectParam passive buffs, dynamic item naming, and detailed Diablo-style lore captions.
"""

import random
from typing import List, Dict, Any, Optional, Union, Set
from src.models import ProgressionTier
from src.diablo_affixes import (
    RarityTier, AffixType, AffixDefinition, AFFIX_POOL,
    WeaponSkill, WEAPON_SKILL_POOL
)
from src.logger import system_logger
from src.diablo_text_formatter import DiabloTextFormatter
from src.diablo_variant_builder import DiabloVariantBuilder
from src.diablo_vanilla_base_distributor import VanillaBaseDistributor
from src.diablo_vanilla_stat_injector import VanillaStatInjector
from src.diablo_equipment_modifier import DiabloEquipmentModifier
from src.diablo_affix_roller import DiabloAffixRoller


class DiabloLootGenerator:
    """
    Generates multi-tier Diablo-style loot variants with dynamic affixes.

    Why:
        Enables rich, repeatable ARPG-style item progression in Elden Ring,
        turning standalone mod items into thousands of uniquely-rolled relics.
    """

    DEFAULT_MAX_SHOP_PER_MERCHANT = 15
    DEFAULT_MAX_ENIA_SHOP_ROWS = 30
    DEFAULT_MAX_TOTAL_SHOP_ROWS = 80

    RARITY_WEIGHTS = {
        RarityTier.COMMON: 25,
        RarityTier.MAGIC: 40,
        RarityTier.RARE: 25,
        RarityTier.LEGENDARY: 8,
        RarityTier.MYTHIC: 2
    }

    BOSS_RARITY_WEIGHTS = {
        RarityTier.LEGENDARY: 65,
        RarityTier.MYTHIC: 35
    }

    def __init__(
        self,
        seed: Optional[int] = None,
        knowledge_base: Optional[Any] = None,
        max_shop_per_merchant: int = DEFAULT_MAX_SHOP_PER_MERCHANT,
        max_enia_rows: int = DEFAULT_MAX_ENIA_SHOP_ROWS,
        max_total_shop_rows: int = DEFAULT_MAX_TOTAL_SHOP_ROWS,
        randomize_weapon_skills: bool = False,
        balance_weapon_skills_by_progression: bool = True,
        weapon_skills_pool: Optional[List[WeaponSkill]] = None,
        pricing_engine: Optional[Any] = None,
        stats_multiplier: float = 1.0,
        price_multiplier: float = 1.0
    ):
        self._rng = random.Random(seed)
        self._knowledge_base = knowledge_base
        self.max_shop_per_merchant = max_shop_per_merchant
        self.max_enia_rows = max_enia_rows
        self.max_total_shop_rows = max_total_shop_rows
        self.randomize_weapon_skills = randomize_weapon_skills
        self.balance_weapon_skills_by_progression = balance_weapon_skills_by_progression
        self._weapon_skills_pool = list(weapon_skills_pool or WEAPON_SKILL_POOL)
        self._shop_allocations: Dict[str, int] = {}
        self._total_shop_allocations: int = 0
        self._assigned_chests: Set[int] = set()
        self._assigned_bosses: Set[str] = set()
        self._chest_cursor: int = 0
        self._boss_cursor: int = 0
        self.stats_multiplier = max(0.0, float(stats_multiplier))
        self.price_multiplier = max(0.0, float(price_multiplier))
        from src.pricing_engine import PricingEngine
        self.pricing_engine = pricing_engine if pricing_engine is not None else PricingEngine(price_multiplier=self.price_multiplier)

    def roll_weapon_skill(self, tier: Optional[Union[ProgressionTier, int]] = None) -> WeaponSkill:
        """Rolls an authentic Ash of War or weapon skill from the weapon skill pool."""
        return DiabloAffixRoller.roll_weapon_skill(
            rng=self._rng,
            weapon_skills_pool=self._weapon_skills_pool,
            balance_weapon_skills_by_progression=self.balance_weapon_skills_by_progression,
            tier=tier
        )

    def apply_affixes_to_equipment(
        *args,
        is_weapon: bool = False,
        is_accessory: bool = False,
        stats_multiplier: Optional[float] = None,
        **kwargs
    ) -> None:
        """Applies affix modifiers to equip param dictionary with stats multiplier scaling."""
        if len(args) >= 1 and isinstance(args[0], DiabloLootGenerator):
            gen = args[0]
            field_updates = args[1]
            affixes = args[2] if len(args) > 2 else kwargs.get("affixes", [])
            wep = args[3] if len(args) > 3 else kwargs.get("is_weapon", is_weapon)
            acc = args[4] if len(args) > 4 else kwargs.get("is_accessory", is_accessory)
            mult = gen.stats_multiplier if stats_multiplier is None else stats_multiplier
        else:
            field_updates = args[0] if len(args) > 0 else kwargs.get("field_updates", {})
            affixes = args[1] if len(args) > 1 else kwargs.get("affixes", [])
            wep = args[2] if len(args) > 2 else kwargs.get("is_weapon", is_weapon)
            acc = args[3] if len(args) > 3 else kwargs.get("is_accessory", is_accessory)
            mult = 1.0 if stats_multiplier is None else stats_multiplier

        DiabloEquipmentModifier.apply_affixes_to_equipment(
            field_updates=field_updates,
            affixes=affixes,
            is_weapon=bool(wep),
            is_accessory=bool(acc),
            stats_multiplier=mult
        )

    def is_shop_capacity_exceeded(self, shop_id: str, is_enia: bool = False) -> bool:
        """Checks whether a merchant, Enia, or total ShopLineupParam has reached capacity."""
        if self._total_shop_allocations >= self.max_total_shop_rows:
            return True
        if is_enia:
            enia_total = self._shop_allocations.get("finger_reader_enia", 0)
            return enia_total >= self.max_enia_rows
        return self._shop_allocations.get(shop_id, 0) >= self.max_shop_per_merchant

    def record_shop_allocation(self, shop_id: str, is_enia: bool = False) -> None:
        """Records an allocation into ShopLineupParam."""
        if is_enia:
            self._shop_allocations["finger_reader_enia"] = self._shop_allocations.get("finger_reader_enia", 0) + 1
            self._shop_allocations[shop_id] = self._shop_allocations.get(shop_id, 0) + 1
        else:
            self._shop_allocations[shop_id] = self._shop_allocations.get(shop_id, 0) + 1
        self._total_shop_allocations += 1

    def get_next_chest(self, candidate_chests: List[Dict[str, Any]], excluded_ids: Optional[Set[int]] = None) -> Optional[Dict[str, Any]]:
        """Selects next available chest, prioritizing unassigned chests without repeating."""
        if not candidate_chests:
            return None
        excluded = excluded_ids or set()
        unassigned = [c for c in candidate_chests if c.get("lotParamId", 0) not in self._assigned_chests and c.get("lotParamId", 0) not in excluded]
        if unassigned:
            chosen = unassigned[self._chest_cursor % len(unassigned)]
            self._chest_cursor += 1
            return chosen
        available = [c for c in candidate_chests if c.get("lotParamId", 0) not in excluded]
        if available:
            chosen = available[self._chest_cursor % len(available)]
            self._chest_cursor += 1
            return chosen
        chosen = candidate_chests[self._chest_cursor % len(candidate_chests)]
        self._chest_cursor += 1
        return chosen

    def get_next_boss(self, candidate_bosses: List[Dict[str, Any]], excluded_ids: Optional[Set[str]] = None) -> Optional[Dict[str, Any]]:
        """Selects next available boss, prioritizing unassigned bosses with shop capacity."""
        if not candidate_bosses:
            return None
        excluded = excluded_ids or set()
        eligible = [b for b in candidate_bosses if not self.is_shop_capacity_exceeded(b["id"], is_enia=True) and b["id"] not in excluded]
        if not eligible:
            return None
        unassigned = [b for b in eligible if b["id"] not in self._assigned_bosses]
        if unassigned:
            chosen = unassigned[self._boss_cursor % len(unassigned)]
            self._boss_cursor += 1
            return chosen
        chosen = eligible[self._boss_cursor % len(eligible)]
        self._boss_cursor += 1
        return chosen

    def is_chest_assigned(self, lot_id: int) -> bool:
        """Checks if a chest has already been assigned in this distribution run."""
        return lot_id in self._assigned_chests

    def record_chest_assignment(self, lot_id: int) -> None:
        """Records a chest assignment to ensure no duplicate chest loot."""
        self._assigned_chests.add(lot_id)

    def is_boss_assigned(self, boss_id: str) -> bool:
        """Checks if a boss has already been assigned in this distribution run."""
        return boss_id in self._assigned_bosses

    def record_boss_assignment(self, boss_id: str) -> None:
        """Records a boss assignment to ensure no duplicate boss loot."""
        self._assigned_bosses.add(boss_id)

    def reset_distribution_state(self) -> None:
        """Resets all tracked assignments across chests, bosses, and shops."""
        self._assigned_chests.clear()
        self._assigned_bosses.clear()
        self._chest_cursor = 0
        self._boss_cursor = 0
        self.reset_shop_allocations()

    def reset_shop_allocations(self) -> None:
        """Resets tracked shop allocations."""
        self._shop_allocations.clear()
        self._total_shop_allocations = 0

    def roll_rarity(self, is_boss: bool = False, is_chest: bool = False) -> RarityTier:
        """Selects a rarity tier using drop weights. Bosses and Chests are guaranteed high tier (Legendary or Mythic)."""
        return DiabloAffixRoller.roll_rarity(self._rng, is_boss=is_boss, is_chest=is_chest)

    def roll_affixes(
        self,
        rarity: RarityTier,
        is_weapon: bool,
        is_accessory: bool = False,
        is_boss: bool = False
    ) -> List[AffixDefinition]:
        """Rolls a balanced combination of prefixes and suffixes for the rarity tier."""
        return DiabloAffixRoller.roll_affixes(
            rng=self._rng,
            rarity=rarity,
            is_weapon=is_weapon,
            is_accessory=is_accessory,
            is_boss=is_boss
        )

    def build_item_name(
        self,
        base_name: str,
        rarity: RarityTier,
        affixes: List[AffixDefinition],
        marker_tag: str = "[LootForge]",
        is_boss: bool = False
    ) -> str:
        """Formats dynamic Diablo item name: [Tag] [Rarity] Prefix BaseName Suffix."""
        return DiabloTextFormatter.build_item_name(base_name, rarity, affixes, marker_tag=marker_tag, is_boss=is_boss)

    def build_caption_with_affixes(
        self,
        base_caption: str,
        rarity: RarityTier,
        affixes: List[AffixDefinition],
        boss_name: Optional[str] = None,
        skill: Optional[WeaponSkill] = None,
        pricing: Optional[Dict[str, Any]] = None
    ) -> str:
        """Appends formatted rarity, skill, and affix breakdown to item description."""
        return DiabloTextFormatter.build_caption_with_affixes(
            base_caption, rarity, affixes, boss_name=boss_name, skill=skill, pricing=pricing,
            stats_multiplier=self.stats_multiplier
        )

    def generate_variants_for_spec(
        self,
        base_spec: Dict[str, Any],
        variants_per_item: int = 3,
        knowledge_base: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Generates N Diablo-rolled variants for a given patch specification,
        organically distributed across the entire game (Bosses, Merchants, Chests, Mobs).
        """
        return DiabloVariantBuilder.generate_variants(
            generator=self,
            base_spec=base_spec,
            variants_per_item=variants_per_item,
            knowledge_base=knowledge_base
        )

    def generate_vanilla_stat_injections(
        self,
        knowledge_base: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Generates procedural Diablo-style stat and affix infusions directly for vanilla items.
        """
        return VanillaStatInjector.generate_injections(self, knowledge_base=knowledge_base)

    def generate_vanilla_base_distribution_specs(
        self,
        knowledge_base: Optional[Any] = None,
        id_allocator: Optional[Any] = None,
        variants_per_item: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Uses cataloged vanilla weapons and armor sets as base items to create
        standalone procedural relics and distribute them across bosses, merchants, chests, and enemies.
        """
        return VanillaBaseDistributor.generate_distribution_specs(
            knowledge_base=knowledge_base or self._knowledge_base,
            id_allocator=id_allocator,
            variants_per_item=variants_per_item,
            variant_generator_fn=lambda spec, variants, kb: self.generate_variants_for_spec(spec, variants, kb)
        )

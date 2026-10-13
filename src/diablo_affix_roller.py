"""
Diablo affix, skill, and rarity rolling service for LootForge.
Extracts procedural dice rolls from DiabloLootGenerator to maintain modular granularity.
Complies with [CS-MODULAR] and [CS-GRANULARITY] (<= 300 lines).
"""

import random
from typing import List, Dict, Any, Optional, Union
from src.models import ProgressionTier
from src.diablo_affixes import (
    RarityTier, AffixType, AffixDefinition, AFFIX_POOL,
    WeaponSkill, WEAPON_SKILL_POOL
)


class DiabloAffixRoller:
    """
    Handles random rolls for rarity, affixes (prefixes/suffixes), and progression-balanced weapon skills.
    """

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

    @classmethod
    def roll_rarity(cls, rng: random.Random, is_boss: bool = False, is_chest: bool = False) -> RarityTier:
        """Selects a rarity tier using drop weights. Bosses and Chests guarantee Legendary or Mythic."""
        weights_dict = cls.BOSS_RARITY_WEIGHTS if (is_boss or is_chest) else cls.RARITY_WEIGHTS
        tiers = list(weights_dict.keys())
        weights = list(weights_dict.values())
        return rng.choices(tiers, weights=weights, k=1)[0]

    @classmethod
    def roll_affixes(
        cls,
        rng: random.Random,
        rarity: RarityTier,
        is_weapon: bool,
        is_accessory: bool = False,
        is_boss: bool = False
    ) -> List[AffixDefinition]:
        """Rolls a balanced combination of prefixes and suffixes for the specified rarity tier."""
        if rarity == RarityTier.COMMON and not is_boss:
            return []

        if is_accessory:
            available_prefixes = [
                a for a in AFFIX_POOL
                if a.affix_type == AffixType.PREFIX and getattr(a, "applies_to_accessory", False)
            ]
            available_suffixes = [
                a for a in AFFIX_POOL
                if a.affix_type == AffixType.SUFFIX and getattr(a, "applies_to_accessory", False)
            ]
        elif is_weapon:
            available_prefixes = [
                a for a in AFFIX_POOL
                if a.affix_type == AffixType.PREFIX and a.applies_to_weapon
            ]
            available_suffixes = [
                a for a in AFFIX_POOL
                if a.affix_type == AffixType.SUFFIX and a.applies_to_weapon
            ]
        else:
            available_prefixes = [
                a for a in AFFIX_POOL
                if a.affix_type == AffixType.PREFIX and a.applies_to_armor
            ]
            available_suffixes = [
                a for a in AFFIX_POOL
                if a.affix_type == AffixType.SUFFIX and a.applies_to_armor
            ]

        rolled: List[AffixDefinition] = []

        if rarity == RarityTier.MAGIC:
            pool = available_prefixes + available_suffixes
            if pool:
                rolled.append(rng.choice(pool))

        elif rarity == RarityTier.RARE:
            if available_prefixes:
                rolled.append(rng.choice(available_prefixes))
            if available_suffixes:
                rolled.append(rng.choice(available_suffixes))

        elif rarity == RarityTier.LEGENDARY:
            pref_count = min(2, len(available_prefixes))
            suff_count = min(2 if is_boss else 1, len(available_suffixes))
            if available_prefixes:
                rolled.extend(rng.sample(available_prefixes, pref_count))
            if available_suffixes:
                rolled.extend(rng.sample(available_suffixes, suff_count))

        elif rarity == RarityTier.MYTHIC:
            pref_count = min(2, len(available_prefixes))
            suff_count = min(2, len(available_suffixes))
            if available_prefixes:
                rolled.extend(rng.sample(available_prefixes, pref_count))
            if available_suffixes:
                rolled.extend(rng.sample(available_suffixes, suff_count))

        # Guarantee at least one passive SpEffect on boss drops
        if is_boss and not any(a.sp_effect_id for a in rolled):
            sp_affixes = [a for a in (available_prefixes + available_suffixes) if a.sp_effect_id]
            if sp_affixes:
                if rolled:
                    rolled[0] = rng.choice(sp_affixes)
                else:
                    rolled.append(rng.choice(sp_affixes))

        return rolled

    @classmethod
    def roll_weapon_skill(
        cls,
        rng: random.Random,
        weapon_skills_pool: List[WeaponSkill],
        balance_weapon_skills_by_progression: bool = True,
        tier: Optional[Union[ProgressionTier, int]] = None
    ) -> WeaponSkill:
        """
        Rolls an authentic Ash of War or weapon skill from the weapon skill pool.
        Optionally balances skill selection by progression tier.
        """
        if not balance_weapon_skills_by_progression or tier is None:
            return rng.choice(weapon_skills_pool)

        if isinstance(tier, int) and not isinstance(tier, ProgressionTier):
            try:
                tier = ProgressionTier(tier)
            except ValueError:
                return rng.choice(weapon_skills_pool)

        tier_map: Dict[ProgressionTier, List[WeaponSkill]] = {
            t: [s for s in weapon_skills_pool if s.tier == t]
            for t in ProgressionTier
        }

        tier_weights = {
            ProgressionTier.EARLY: {ProgressionTier.EARLY: 1.0},
            ProgressionTier.MID: {ProgressionTier.MID: 0.75, ProgressionTier.EARLY: 0.25},
            ProgressionTier.LATE: {ProgressionTier.LATE: 0.70, ProgressionTier.MID: 0.20, ProgressionTier.EARLY: 0.10},
            ProgressionTier.ENDGAME: {ProgressionTier.ENDGAME: 0.65, ProgressionTier.LATE: 0.20, ProgressionTier.MID: 0.10, ProgressionTier.EARLY: 0.05},
        }

        weights_for_target = tier_weights.get(tier, {tier: 1.0})
        active_tiers = [t for t in weights_for_target if tier_map.get(t)]
        if not active_tiers:
            eligible = [s for s in weapon_skills_pool if s.tier.value <= tier.value]
            return rng.choice(eligible) if eligible else rng.choice(weapon_skills_pool)

        active_weights = [weights_for_target[t] for t in active_tiers]
        chosen_tier = rng.choices(active_tiers, weights=active_weights, k=1)[0]
        return rng.choice(tier_map[chosen_tier])

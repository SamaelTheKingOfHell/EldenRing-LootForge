"""
Diablo-style procedural loot variant generator for LootForge.

Rolls random rarity tiers, prefixes, and suffixes, applying authentic stat modifiers,
SpEffectParam passive buffs, dynamic item naming, and detailed Diablo-style lore captions.
"""

import copy
import random
from typing import List, Dict, Any, Optional, Union
from src.models import ProgressionTier
from src.diablo_affixes import (
    RarityTier, AffixType, AffixDefinition, AFFIX_POOL,
    WeaponSkill, WEAPON_SKILL_POOL
)
from src.logger import system_logger


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
        pricing_engine: Optional[Any] = None
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
        from src.pricing_engine import PricingEngine
        self.pricing_engine = pricing_engine if pricing_engine is not None else PricingEngine()

    def roll_weapon_skill(self, tier: Optional[Union[ProgressionTier, int]] = None) -> WeaponSkill:
        """
        Rolls an authentic Ash of War or weapon skill from the weapon skill pool.

        If balance_weapon_skills_by_progression is True and tier is provided:
        Restricts and weights the selection by progression tier so early game regions/drops
        only receive early game skills, preventing overpowered end-game/boss weapon skills
        from dropping in early regions.

        If balance_weapon_skills_by_progression is False (or tier is None):
        Performs pure random selection across all weapon skills without progression restrictions.
        """
        if not self.balance_weapon_skills_by_progression or tier is None:
            return self._rng.choice(self._weapon_skills_pool)

        if isinstance(tier, int) and not isinstance(tier, ProgressionTier):
            try:
                tier = ProgressionTier(tier)
            except ValueError:
                return self._rng.choice(self._weapon_skills_pool)

        tier_map: Dict[ProgressionTier, List[WeaponSkill]] = {
            t: [s for s in self._weapon_skills_pool if s.tier == t]
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
            eligible = [s for s in self._weapon_skills_pool if s.tier.value <= tier.value]
            return self._rng.choice(eligible) if eligible else self._rng.choice(self._weapon_skills_pool)

        active_weights = [weights_for_target[t] for t in active_tiers]
        chosen_tier = self._rng.choices(active_tiers, weights=active_weights, k=1)[0]
        return self._rng.choice(tier_map[chosen_tier])

    @staticmethod
    def apply_affixes_to_equipment(
        field_updates: Dict[str, Any],
        affixes: List[AffixDefinition],
        is_weapon: bool,
        is_accessory: bool = False
    ) -> None:
        """
        Applies affix modifiers to equip param dictionary.
        Routes status buildups to spEffectBehaviorId0..2 and WeaponEffect UI slots spEffectMsgId0..2.
        Routes resident passives to residentSpEffectId / residentSpEffectId1 / residentSpEffectId2 for weapons,
        residentSpEffectId / residentSpEffectId2 / residentSpEffectId3 for protectors,
        and residentSpEffectId1..4 and refId for accessories (EquipParamAccessory).
        """
        wep_behavior_slot = 0
        wep_resident_slot = 0
        wep_msg_slot = 0
        armor_resident_slot = 0
        acc_resident_slot = 1

        for aff in affixes:
            for field_name, delta in aff.field_modifiers.items():
                field_updates[field_name] = field_updates.get(field_name, 0) + delta

            if aff.sp_effect_id:
                if is_accessory:
                    if acc_resident_slot <= 4:
                        field_updates[f"residentSpEffectId{acc_resident_slot}"] = aff.sp_effect_id
                        acc_resident_slot += 1
                    if "refId" not in field_updates:
                        field_updates["refId"] = aff.sp_effect_id
                elif is_weapon:
                    if getattr(aff, "is_on_hit_effect", False):
                        if wep_behavior_slot < 3:
                            field_updates[f"spEffectBehaviorId{wep_behavior_slot}"] = aff.sp_effect_id
                            wep_behavior_slot += 1
                    else:
                        if wep_resident_slot < 3:
                            key = "residentSpEffectId" if wep_resident_slot == 0 else f"residentSpEffectId{wep_resident_slot}"
                            field_updates[key] = aff.sp_effect_id
                            wep_resident_slot += 1
                else:
                    if armor_resident_slot < 3:
                        key = "residentSpEffectId" if armor_resident_slot == 0 else f"residentSpEffectId{armor_resident_slot + 1}"
                        field_updates[key] = aff.sp_effect_id
                        armor_resident_slot += 1

            if is_weapon and getattr(aff, "sp_effect_msg_id", None) and wep_msg_slot < 3:
                field_updates[f"spEffectMsgId{wep_msg_slot}"] = aff.sp_effect_msg_id
                wep_msg_slot += 1

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

    def reset_shop_allocations(self) -> None:
        """Resets tracked shop allocations."""
        self._shop_allocations.clear()
        self._total_shop_allocations = 0

    def roll_rarity(self, is_boss: bool = False, is_chest: bool = False) -> RarityTier:
        """Selects a rarity tier using drop weights. Bosses and Chests are guaranteed high tier (Legendary or Mythic)."""
        weights_dict = self.BOSS_RARITY_WEIGHTS if (is_boss or is_chest) else self.RARITY_WEIGHTS
        tiers = list(weights_dict.keys())
        weights = list(weights_dict.values())
        return self._rng.choices(tiers, weights=weights, k=1)[0]


    def roll_affixes(
        self,
        rarity: RarityTier,
        is_weapon: bool,
        is_accessory: bool = False,
        is_boss: bool = False
    ) -> List[AffixDefinition]:
        """Rolls a balanced combination of prefixes and suffixes for the rarity tier."""
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
                rolled.append(self._rng.choice(pool))

        elif rarity == RarityTier.RARE:
            if available_prefixes:
                rolled.append(self._rng.choice(available_prefixes))
            if available_suffixes:
                rolled.append(self._rng.choice(available_suffixes))

        elif rarity == RarityTier.LEGENDARY:
            pref_count = min(2, len(available_prefixes))
            suff_count = min(2 if is_boss else 1, len(available_suffixes))
            if available_prefixes:
                rolled.extend(self._rng.sample(available_prefixes, pref_count))
            if available_suffixes:
                rolled.extend(self._rng.sample(available_suffixes, suff_count))

        elif rarity == RarityTier.MYTHIC:
            pref_count = min(2, len(available_prefixes))
            suff_count = min(2, len(available_suffixes))
            if available_prefixes:
                rolled.extend(self._rng.sample(available_prefixes, pref_count))
            if available_suffixes:
                rolled.extend(self._rng.sample(available_suffixes, suff_count))

        # Guarantee at least one passive SpEffect on boss drops
        if is_boss and not any(a.sp_effect_id for a in rolled):
            sp_affixes = [a for a in (available_prefixes + available_suffixes) if a.sp_effect_id]
            if sp_affixes:
                if rolled:
                    rolled[0] = self._rng.choice(sp_affixes)
                else:
                    rolled.append(self._rng.choice(sp_affixes))

        return rolled

    def build_item_name(
        self,
        base_name: str,
        rarity: RarityTier,
        affixes: List[AffixDefinition],
        marker_tag: str = "[LootForge]",
        is_boss: bool = False
    ) -> str:
        """Formats dynamic Diablo item name: [Tag] [Rarity] Prefix BaseName Suffix."""
        prefixes = [a.name for a in affixes if a.affix_type == AffixType.PREFIX]
        suffixes = [a.name for a in affixes if a.affix_type == AffixType.SUFFIX]

        prefix_str = f"{' '.join(prefixes)} " if prefixes else ""
        suffix_str = f" {' '.join(suffixes)}" if suffixes else ""

        clean_base = base_name
        for prefix_tag in ["[LootForge]", "✦", "▪", "★"]:
            clean_base = clean_base.replace(prefix_tag, "").strip()

        if is_boss:
            rarity_tag = f"[Giga {rarity.display_name}] "
        else:
            rarity_tag = f"[{rarity.display_name}] " if rarity != RarityTier.COMMON else ""
        return f"{marker_tag} {rarity_tag}{prefix_str}{clean_base}{suffix_str}".strip()

    def build_caption_with_affixes(
        self,
        base_caption: str,
        rarity: RarityTier,
        affixes: List[AffixDefinition],
        boss_name: Optional[str] = None,
        skill: Optional[WeaponSkill] = None,
        pricing: Optional[Dict[str, Any]] = None
    ) -> str:
        """Appends formatted rarity, skill, and affix breakdown to the bottom of item description."""
        lines = [base_caption.rstrip(), ""]
        lines.append("----------------------------------------")
        tier_title = f"GIGA {rarity.display_name.upper()}" if boss_name else rarity.display_name.upper()
        lines.append(f"RARITY: {tier_title} {rarity.stars}")

        if skill:
            lines.append(f"SKILL: {skill.name}")

        if boss_name:
            lines.append(f"[BOSS TROPHY] Claimed from {boss_name}")

        if pricing and pricing.get("buy_price"):
            lines.append(f"VALUE: {pricing['buy_price']:,} Runes (Sell: {pricing.get('sell_price', 0):,})")

        if affixes:
            lines.append("----------------------------------------")
            lines.append("DIABLO AFFIXES:")
            for aff in affixes:
                aff_type_str = "Prefix" if aff.affix_type == AffixType.PREFIX else "Suffix"
                lines.append(f"- [{aff_type_str}] {aff.name}: {aff.description}")
        else:
            lines.append("----------------------------------------")
            lines.append("- Standard Mundane Quality (No Magical Affixes)")

        lines.append("----------------------------------------")
        return "\n".join(lines)

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
        if variants_per_item <= 1:
            return [base_spec]

        kb = knowledge_base or self._knowledge_base
        pools = kb.get_diablo_distribution_pools() if (kb and hasattr(kb, "get_diablo_distribution_pools")) else None

        variant_specs: List[Dict[str, Any]] = []

        tier = base_spec.get("tier")
        if tier is None and kb and hasattr(kb, "get_progression_tier_for_spec"):
            tier = kb.get_progression_tier_for_spec(base_spec)

        for v_idx in range(variants_per_item):
            spec_copy = copy.deepcopy(base_spec)
            spec_copy["set_id"] = f"{base_spec['set_id']}_v{v_idx + 1}"

            # 1. Determine distribution destination across whole game with progression locking
            is_boss = False
            boss_name: Optional[str] = None
            loot_spec: Optional[Dict[str, Any]] = None

            if pools:
                raw_bosses = pools.get("bosses", [])
                raw_merchants = pools.get("merchants", [])
                raw_chests = pools.get("chests", [])
                raw_elites = pools.get("elites", [])
                raw_roaming = pools.get("roaming", [])

                # Filter pools strictly by progression tier to prevent late-game gear in early regions
                if tier and kb and hasattr(kb, "get_progression_tier"):
                    boss_pool = [b for b in raw_bosses if kb.get_progression_tier(b) == tier] or raw_bosses
                    chest_pool = [c for c in raw_chests if kb.get_progression_tier(c) == tier] or raw_chests
                    merchant_pool = [m for m in raw_merchants if kb.get_progression_tier(m) == tier] or raw_merchants
                    elites = [e for e in raw_elites if kb.get_progression_tier(e) == tier] or raw_elites
                    roaming = [r for r in raw_roaming if kb.get_progression_tier(r) == tier] or raw_roaming
                else:
                    boss_pool = raw_bosses
                    chest_pool = raw_chests
                    merchant_pool = raw_merchants
                    elites = raw_elites
                    roaming = raw_roaming

                enemy_pool = (elites + roaming) if (elites or roaming) else []

                # Rotation strictly prioritizes: Bosses (0) > Chests (1) > The Rest (2: Merchants, Elites, Roaming Mobs)
                mod_bucket = v_idx % 3
                if mod_bucket == 0 and boss_pool:
                    boss = boss_pool[(v_idx // 3) % len(boss_pool)]
                    shop_id = boss["id"]
                    if not self.is_shop_capacity_exceeded(shop_id, is_enia=True):
                        is_boss = True
                        boss_name = boss.get("name", "Great Enemy")
                        loot_spec = {
                            "type": "shop_lineup",
                            "shop_type": "finger_reader_enia",
                            "target_id": boss["id"],
                            "display_name": f"[Boss Remembrance] {boss_name}",
                            "cost_or_remembrance": float(boss.get("defaultCost", 30000))
                        }
                        self.record_shop_allocation(shop_id, is_enia=True)
                    else:
                        system_logger.info(
                            f"Shop param row limit reached for Enia remembrance '{boss.get('name')}'. "
                            f"Cascading to Chests (Bosses -> Chests -> The Rest).",
                            source="DiabloGenerator"
                        )
                        # Boss capacity limit reached: cascade to Chests
                        if chest_pool:
                            chest = chest_pool[(v_idx // 3) % len(chest_pool)]
                            loot_spec = {
                                "type": "map_pickup",
                                "lot_id": chest["lotParamId"],
                                "target_id": str(chest["lotParamId"]),
                                "display_name": f"[Chest After Boss] {chest['name']}",
                                "drop_rate_percent": 100.0
                            }

                elif mod_bucket == 1 and chest_pool:
                    chest = chest_pool[(v_idx // 3) % len(chest_pool)]
                    loot_spec = {
                        "type": "map_pickup",
                        "lot_id": chest["lotParamId"],
                        "target_id": str(chest["lotParamId"]),
                        "display_name": f"[Chest Discovery] {chest['name']}",
                        "drop_rate_percent": 100.0
                    }

                # If mod_bucket == 2 OR if boss/chest was unavailable: cascade to The Rest (Merchants, Elites, Roaming Mobs)
                if loot_spec is None:
                    rest_cycle = (v_idx // 3) % 3
                    if rest_cycle == 0 and merchant_pool:
                        merch = merchant_pool[(v_idx // 3) % len(merchant_pool)]
                        shop_id = merch["id"]
                        if not self.is_shop_capacity_exceeded(shop_id, is_enia=False):
                            loot_spec = {
                                "type": "merchant_shop",
                                "shop_id": merch["id"],
                                "target_id": merch["id"],
                                "display_name": f"[Merchant Shop] {merch['name']}",
                                "merchant_name": merch["name"],
                                "cost_or_remembrance": float(merch.get("defaultRuneCost", 8000)),
                                "rune_cost": int(merch.get("defaultRuneCost", 8000))
                            }
                            self.record_shop_allocation(shop_id)

                    if loot_spec is None:
                        if elites:
                            elite = elites[(v_idx // 2) % len(elites)]
                            lot_id = elite.get("lotParamId", 380000000)
                            loot_spec = {
                                "type": "enemy_drop",
                                "lot_id": lot_id,
                                "target_id": str(elite.get("id", lot_id)),
                                "target_enemy": elite["name"],
                                "display_name": elite["name"],
                                "drop_rate_percent": float(elite.get("defaultDropChance", 25.0))
                            }
                        elif enemy_pool:
                            enemy = enemy_pool[v_idx % len(enemy_pool)]
                            lot_id = enemy.get("lotParamId", 431100000)
                            loot_spec = {
                                "type": "enemy_drop",
                                "lot_id": lot_id,
                                "target_id": str(enemy.get("id", lot_id)),
                                "target_enemy": enemy["name"],
                                "display_name": enemy["name"],
                                "drop_rate_percent": float(enemy.get("defaultDropChance", 20.0))
                            }

            is_chest_drop = loot_spec is not None and loot_spec.get("type") in ("map_pickup", "world_chest")

            # 2. Modify Equip Params and FMG texts with rolled affixes (Chests are highly valuable: guaranteed high rarity)
            variant_new_ids: List[int] = []
            variant_item_prices: Dict[str, int] = {}

            for ep in spec_copy.get("equip_params", []):
                old_id = ep["new_param_id"]
                new_id = old_id + ((v_idx + 1) * 100)
                ep["new_param_id"] = new_id
                variant_new_ids.append(new_id)

                is_weapon = ep.get("param_table") == "EquipParamWeapon"
                is_accessory = ep.get("param_table") == "EquipParamAccessory"
                rarity = self.roll_rarity(is_boss=is_boss, is_chest=is_chest_drop)
                affixes = self.roll_affixes(rarity, is_weapon=is_weapon, is_accessory=is_accessory, is_boss=is_boss or is_chest_drop)

                field_updates = ep.setdefault("field_updates", {})
                field_updates["sortId"] = new_id

                rolled_skill: Optional[WeaponSkill] = None
                effective_tier = tier
                if is_weapon and self.randomize_weapon_skills:
                    if not effective_tier and loot_spec and kb and hasattr(kb, "get_progression_tier"):
                        target_id = loot_spec.get("target_id") or loot_spec.get("shop_id") or loot_spec.get("lot_id")
                        if target_id:
                            effective_tier = kb.get_progression_tier(str(target_id))
                    if not effective_tier and kb and hasattr(kb, "get_progression_tier_for_spec"):
                        effective_tier = kb.get_progression_tier_for_spec(spec_copy)
                    rolled_skill = self.roll_weapon_skill(tier=effective_tier)
                    field_updates["swordArtsParamId"] = rolled_skill.id

                self.apply_affixes_to_equipment(field_updates, affixes, is_weapon=is_weapon, is_accessory=is_accessory)

                pricing = self.pricing_engine.calculate_item_prices(
                    slot=ep.get("slot"),
                    tier=effective_tier or tier or 1,
                    rarity=rarity,
                    affixes=affixes,
                    weapon_skill=rolled_skill,
                    is_weapon=is_weapon,
                    is_accessory=is_accessory,
                    is_boss=is_boss
                )
                field_updates["sellValue"] = pricing["sell_price"]
                field_updates["saleValue"] = pricing["buy_price"]
                if not is_weapon:
                    field_updates["basicPrice"] = pricing["buy_price"]
                variant_item_prices[str(new_id)] = pricing["buy_price"]

                for fmg in spec_copy.get("fmg_texts", []):
                    fmg_id = fmg.get("item_id", fmg.get("param_id"))
                    if fmg_id == old_id:
                        if "item_id" in fmg:
                            fmg["item_id"] = new_id
                        if "param_id" in fmg:
                            fmg["param_id"] = new_id
                        fmg["is_accessory"] = is_accessory
                        fmg["name"] = self.build_item_name(fmg["name"], rarity, affixes, is_boss=is_boss)
                        fmg["caption"] = self.build_caption_with_affixes(
                            fmg["caption"], rarity, affixes, boss_name=boss_name, skill=rolled_skill, pricing=pricing
                        )

            # Multi-drop for Bosses and Chests: award multiple drops
            # Chests are highly valuable and always contain multiple extra injections (at least 2 companion accessories)
            if (is_boss or is_chest_drop) and kb and variant_new_ids:
                acc_catalog = kb.list_all_vanilla_accessories(tier=tier) if hasattr(kb, "list_all_vanilla_accessories") else {}
                if not acc_catalog and hasattr(kb, "list_all_vanilla_accessories"):
                    acc_catalog = kb.list_all_vanilla_accessories()

                if acc_catalog:
                    acc_keys = list(acc_catalog.keys())
                    num_extra = 2 if is_chest_drop else 1

                    for extra_idx in range(num_extra):
                        comp_key = acc_keys[(v_idx + len(variant_new_ids) + extra_idx) % len(acc_keys)]
                        comp_info = acc_catalog[comp_key]
                        comp_base_id = comp_info.get("baseParamId", 1000)
                        comp_name = comp_info.get("name", "Talisman")

                        comp_param_id = variant_new_ids[0] + 50 + extra_idx
                        if comp_param_id not in variant_new_ids:
                            comp_rarity = self.roll_rarity(is_boss=is_boss, is_chest=is_chest_drop)
                            comp_affixes = self.roll_affixes(comp_rarity, is_weapon=False, is_accessory=True, is_boss=is_boss or is_chest_drop)
                            comp_field_updates = {"sortId": comp_param_id, "isDeposit": 1}
                            self.apply_affixes_to_equipment(comp_field_updates, comp_affixes, is_weapon=False, is_accessory=True)

                            comp_pricing = self.pricing_engine.calculate_item_prices(
                                slot="accessory",
                                tier=tier or 1,
                                rarity=comp_rarity,
                                affixes=comp_affixes,
                                is_accessory=True,
                                is_boss=is_boss or is_chest_drop
                            )
                            comp_field_updates["sellValue"] = comp_pricing["sell_price"]
                            comp_field_updates["saleValue"] = comp_pricing["buy_price"]
                            comp_field_updates["basicPrice"] = comp_pricing["buy_price"]
                            variant_item_prices[str(comp_param_id)] = comp_pricing["buy_price"]

                            chest_tag = "Chest Discovery" if is_chest_drop else "Encounter Trophy"
                            comp_fmg_name = self.build_item_name(f"[LootForge] {comp_name}", comp_rarity, comp_affixes, is_boss=is_boss or is_chest_drop)
                            comp_fmg_caption = self.build_caption_with_affixes(
                                f"Extra treasure ({chest_tag}) awarded with {spec_copy.get('set_id')}.",
                                comp_rarity, comp_affixes, boss_name=boss_name, pricing=comp_pricing
                            )

                            spec_copy.setdefault("equip_params", []).append({
                                "param_table": "EquipParamAccessory",
                                "new_param_id": comp_param_id,
                                "base_clone_id": comp_base_id,
                                "slot": "accessory",
                                "slot_offset": 50 + extra_idx,
                                "row_name": f"[LootForge] {comp_name}",
                                "field_updates": comp_field_updates
                            })

                            spec_copy.setdefault("fmg_texts", []).append({
                                "item_id": comp_param_id,
                                "vanilla_source_id": comp_base_id,
                                "slot": "accessory",
                                "slot_offset": 50 + extra_idx,
                                "is_weapon": False,
                                "is_accessory": True,
                                "name": comp_fmg_name,
                                "caption": comp_fmg_caption,
                                "info": f"Origin: Vanilla {comp_name} ({chest_tag})"
                            })

                            variant_new_ids.append(comp_param_id)

            # 3. Synchronize loot distribution
            if loot_spec:
                loot_spec["awarded_items"] = variant_new_ids
                loot_spec["item_prices"] = variant_item_prices
                if loot_spec.get("type") in ("merchant_shop", "shop_lineup") and variant_item_prices:
                    avg_cost = int(sum(variant_item_prices.values()) / max(1, len(variant_item_prices)))
                    loot_spec["cost_or_remembrance"] = float(avg_cost)
                    if "rune_cost" in loot_spec:
                        loot_spec["rune_cost"] = avg_cost
                spec_copy["loot_distribution"] = loot_spec
            elif "loot_distribution" in spec_copy and spec_copy["loot_distribution"]:
                spec_copy["loot_distribution"]["awarded_items"] = variant_new_ids
                spec_copy["loot_distribution"]["item_prices"] = variant_item_prices

            variant_specs.append(spec_copy)


        return variant_specs

    def generate_vanilla_stat_injections(
        self,
        knowledge_base: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Generates procedural Diablo-style stat and affix infusions directly for vanilla items.
        Injects into existing vanilla EquipParamWeapon and EquipParamProtector rows,
        and enriches their FMG text descriptions with Diablo rarity and affix breakdowns.
        """
        kb = knowledge_base or self._knowledge_base
        if not kb:
            return []

        specs: List[Dict[str, Any]] = []

        # 1. Vanilla weapons
        weapons = kb.list_all_vanilla_weapons() if hasattr(kb, "list_all_vanilla_weapons") else getattr(kb, "_weapons", {})
        for model_id, w_info in weapons.items():
            base_param_id = w_info.get("baseParamId")
            if not base_param_id:
                continue

            rarity = self.roll_rarity(is_boss=False)
            affixes = self.roll_affixes(rarity, is_weapon=True, is_boss=False)

            field_updates: Dict[str, Any] = {}
            rolled_skill: Optional[WeaponSkill] = None
            w_tier = kb.get_progression_tier(w_info) if (kb and hasattr(kb, "get_progression_tier")) else None
            if self.randomize_weapon_skills:
                rolled_skill = self.roll_weapon_skill(tier=w_tier)
                field_updates["swordArtsParamId"] = rolled_skill.id

            self.apply_affixes_to_equipment(field_updates, affixes, is_weapon=True)

            pricing = self.pricing_engine.calculate_item_prices(
                slot="weapon",
                tier=w_tier or 1,
                rarity=rarity,
                affixes=affixes,
                weapon_skill=rolled_skill,
                is_weapon=True,
                is_boss=False
            )
            field_updates["sellValue"] = pricing["sell_price"]
            field_updates["saleValue"] = pricing["buy_price"]

            clean_name = w_info.get("name", "Weapon")
            clean_desc = w_info.get("description", "")
            fmg_name = f"[{rarity.display_name}] {clean_name}" if rarity != RarityTier.COMMON else clean_name
            fmg_caption = self.build_caption_with_affixes(clean_desc, rarity, affixes, skill=rolled_skill, pricing=pricing)

            specs.append({
                "set_id": f"vanilla_weapon_inject_{base_param_id}",
                "equip_params": [{
                    "param_table": "EquipParamWeapon",
                    "new_param_id": base_param_id,
                    "update_existing": True,
                    "field_updates": field_updates,
                    "row_name": f"[Vanilla Infused] {clean_name}"
                }],
                "fmg_texts": [{
                    "item_id": base_param_id,
                    "is_weapon": True,
                    "name": fmg_name,
                    "caption": fmg_caption,
                    "info": f"Origin: Vanilla Elden Ring (Diablo Infused)"
                }],
                "loot_distribution": None
            })

        # 2. Vanilla protectors (armor sets: head, body, arms, legs)
        protectors = kb.list_all_vanilla_protectors() if hasattr(kb, "list_all_vanilla_protectors") else getattr(kb, "_protectors", {})
        for model_id, p_info in protectors.items():
            base_param_id = p_info.get("baseParamId")
            if not base_param_id:
                continue

            clean_set_name = p_info.get("name", "Armor Set")
            clean_desc = p_info.get("description", "")
            p_tier = kb.get_progression_tier(p_info) if (kb and hasattr(kb, "get_progression_tier")) else None

            rarity = self.roll_rarity(is_boss=False)
            affixes = self.roll_affixes(rarity, is_weapon=False, is_boss=False)

            field_updates: Dict[str, Any] = {}
            self.apply_affixes_to_equipment(field_updates, affixes, is_weapon=False)

            explicit_pieces = p_info.get("pieces")
            if explicit_pieces and isinstance(explicit_pieces, dict):
                pieces_to_process = [(pid, sname) for sname, pid in explicit_pieces.items()]
            else:
                pieces_to_process = [
                    (base_param_id + slot_offset, slot_name)
                    for slot_offset, slot_name in [(0, "Helm"), (100, "Armor"), (200, "Gauntlets"), (300, "Greaves")]
                ]

            for piece_id, slot_name in pieces_to_process:
                slot_key = {
                    "Helm": "head",
                    "Armor": "body",
                    "Gauntlets": "arms",
                    "Greaves": "legs"
                }.get(slot_name, slot_name.lower())

                piece_pricing = self.pricing_engine.calculate_item_prices(
                    slot=slot_key,
                    tier=p_tier or 1,
                    rarity=rarity,
                    affixes=affixes,
                    is_weapon=False,
                    is_boss=False
                )
                piece_field_updates = dict(field_updates)
                piece_field_updates["sellValue"] = piece_pricing["sell_price"]
                piece_field_updates["saleValue"] = piece_pricing["buy_price"]
                piece_field_updates["basicPrice"] = piece_pricing["buy_price"]

                piece_fmg_caption = self.build_caption_with_affixes(clean_desc, rarity, affixes, pricing=piece_pricing)
                piece_name = f"[{rarity.display_name}] {clean_set_name} ({slot_name})" if rarity != RarityTier.COMMON else f"{clean_set_name} ({slot_name})"

                specs.append({
                    "set_id": f"vanilla_protector_inject_{piece_id}",
                    "equip_params": [{
                        "param_table": "EquipParamProtector",
                        "new_param_id": piece_id,
                        "update_existing": True,
                        "field_updates": piece_field_updates,
                        "row_name": f"[Vanilla Infused] {clean_set_name} ({slot_name})"
                    }],
                    "fmg_texts": [{
                        "item_id": piece_id,
                        "is_weapon": False,
                        "name": piece_name,
                        "caption": piece_fmg_caption,
                        "info": f"Origin: Vanilla Elden Ring (Diablo Infused)"
                    }],
                    "loot_distribution": None
                })

        # 3. Vanilla accessories (talismans)
        accessories = kb.list_all_vanilla_accessories() if hasattr(kb, "list_all_vanilla_accessories") else getattr(kb, "_accessories", {})
        for model_id, a_info in accessories.items():
            base_param_id = a_info.get("baseParamId")
            if not base_param_id:
                continue

            clean_name = a_info.get("name", "Talisman")
            clean_desc = a_info.get("description", "")
            a_tier = kb.get_progression_tier(a_info) if (kb and hasattr(kb, "get_progression_tier")) else None

            rarity = self.roll_rarity(is_boss=False)
            affixes = self.roll_affixes(rarity, is_weapon=False, is_accessory=True, is_boss=False)

            field_updates: Dict[str, Any] = {}
            self.apply_affixes_to_equipment(field_updates, affixes, is_weapon=False, is_accessory=True)

            pricing = self.pricing_engine.calculate_item_prices(
                slot="accessory",
                tier=a_tier or 1,
                rarity=rarity,
                affixes=affixes,
                is_accessory=True,
                is_boss=False
            )
            field_updates["sellValue"] = pricing["sell_price"]
            field_updates["saleValue"] = pricing["buy_price"]
            field_updates["basicPrice"] = pricing["buy_price"]

            fmg_name = f"[{rarity.display_name}] {clean_name}" if rarity != RarityTier.COMMON else clean_name
            fmg_caption = self.build_caption_with_affixes(clean_desc, rarity, affixes, pricing=pricing)

            specs.append({
                "set_id": f"vanilla_accessory_inject_{base_param_id}",
                "equip_params": [{
                    "param_table": "EquipParamAccessory",
                    "new_param_id": base_param_id,
                    "update_existing": True,
                    "field_updates": field_updates,
                    "row_name": f"[Vanilla Infused] {clean_name}"
                }],
                "fmg_texts": [{
                    "item_id": base_param_id,
                    "is_weapon": False,
                    "is_accessory": True,
                    "name": fmg_name,
                    "caption": fmg_caption,
                    "info": "Origin: Vanilla Elden Ring (Diablo Infused)"
                }],
                "loot_distribution": None
            })

        return specs

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
        kb = knowledge_base or self._knowledge_base
        if not kb or not id_allocator:
            return []

        all_specs: List[Dict[str, Any]] = []

        # 1. Vanilla weapons
        weapons = kb.list_all_vanilla_weapons() if hasattr(kb, "list_all_vanilla_weapons") else getattr(kb, "_weapons", {})
        for model_id, w_info in weapons.items():
            base_clone_id = w_info.get("baseParamId")
            if not base_clone_id:
                continue

            set_id = f"vanilla_base_weapon_{model_id}"
            alloc = id_allocator.allocate(set_id)
            clean_name = w_info.get("name", "Weapon")
            clean_desc = w_info.get("description", "A classic weapon of the Lands Between.")

            base_spec = {
                "set_id": set_id,
                "equip_params": [{
                    "param_table": "EquipParamWeapon",
                    "new_param_id": alloc.new_equip_param_id,
                    "base_clone_id": base_clone_id,
                    "target_model_id": int(model_id) if model_id.isdigit() else 0,
                    "slot": "weapon",
                    "slot_offset": 0,
                    "row_name": f"[LootForge] {clean_name}",
                    "field_updates": {
                        "sortId": alloc.new_equip_param_id,
                        "isDeposit": 1,
                        "equipModelId": int(model_id) if model_id.isdigit() else 0
                    }
                }],
                "fmg_texts": [{
                    "item_id": alloc.new_equip_param_id,
                    "vanilla_source_id": base_clone_id,
                    "target_model_id": int(model_id) if model_id.isdigit() else 0,
                    "slot": "weapon",
                    "slot_offset": 0,
                    "is_weapon": True,
                    "name": f"[LootForge] {clean_name}",
                    "caption": f"Standalone relic forged by LootForge from vanilla {clean_name}.\n\n{clean_desc}",
                    "info": f"Origin: Vanilla {clean_name}"
                }],
                "loot_distribution": {
                    "type": "enemy_drop",
                    "lot_id": alloc.new_item_lot_id,
                    "target_id": str(alloc.new_item_lot_id),
                    "drop_rate_percent": 20.0,
                    "awarded_items": [alloc.new_equip_param_id]
                }
            }

            if variants_per_item > 1:
                variants = self.generate_variants_for_spec(base_spec, variants_per_item=variants_per_item, knowledge_base=kb)
                all_specs.extend(variants)
            else:
                all_specs.append(base_spec)

        # 2. Vanilla protectors (armor sets)
        protectors = kb.list_all_vanilla_protectors() if hasattr(kb, "list_all_vanilla_protectors") else getattr(kb, "_protectors", {})
        for model_id, p_info in protectors.items():
            base_clone_id = p_info.get("baseParamId")
            if not base_clone_id:
                continue

            set_id = f"vanilla_base_armor_{model_id}"
            alloc = id_allocator.allocate(set_id)
            clean_set_name = p_info.get("name", "Armor Set")
            clean_desc = p_info.get("description", "Authentic armor of the Lands Between.")

            equip_params = []
            fmg_texts = []
            awarded_ids = []

            explicit_pieces = p_info.get("pieces")
            slot_config = [
                (0, "Helm", "head", "headEquipModelId"),
                (100, "Armor", "body", "bodyEquipModelId"),
                (200, "Gauntlets", "arms", "armEquipModelId"),
                (300, "Greaves", "legs", "legEquipModelId")
            ]
            if explicit_pieces and isinstance(explicit_pieces, dict):
                slot_config = [
                    (s_offset, s_name, s_key, f_name)
                    for s_offset, s_name, s_key, f_name in slot_config
                    if s_name in explicit_pieces
                ]

            for slot_offset, slot_name, slot_key, field_name in slot_config:
                item_id = alloc.new_equip_param_id + slot_offset
                awarded_ids.append(item_id)
                model_int = int(model_id) if model_id.isdigit() else 0
                clone_id = explicit_pieces[slot_name] if (explicit_pieces and slot_name in explicit_pieces) else (base_clone_id + slot_offset)

                equip_params.append({
                    "param_table": "EquipParamProtector",
                    "new_param_id": item_id,
                    "base_clone_id": clone_id,
                    "target_model_id": model_int,
                    "slot": slot_key,
                    "slot_offset": slot_offset,
                    "row_name": f"[LootForge] {clean_set_name} ({slot_name})",
                    "field_updates": {
                        "sortId": item_id,
                        "isDeposit": 1,
                        field_name: model_int,
                        "equipModelId": model_int
                    }
                })

                fmg_texts.append({
                    "item_id": item_id,
                    "vanilla_source_id": clone_id,
                    "target_model_id": model_int,
                    "slot": slot_key,
                    "slot_offset": slot_offset,
                    "is_weapon": False,
                    "name": f"[LootForge] {clean_set_name} ({slot_name})",
                    "caption": f"Standalone relic forged by LootForge from vanilla {clean_set_name}.\n\n{clean_desc}",
                    "info": f"Origin: Vanilla {clean_set_name}"
                })

            base_spec = {
                "set_id": set_id,
                "equip_params": equip_params,
                "fmg_texts": fmg_texts,
                "loot_distribution": {
                    "type": "enemy_drop",
                    "lot_id": alloc.new_item_lot_id,
                    "target_id": str(alloc.new_item_lot_id),
                    "drop_rate_percent": 20.0,
                    "awarded_items": awarded_ids
                }
            }

            if variants_per_item > 1:
                variants = self.generate_variants_for_spec(base_spec, variants_per_item=variants_per_item, knowledge_base=kb)
                all_specs.extend(variants)
            else:
                all_specs.append(base_spec)

        # 3. Vanilla accessories (talismans)
        accessories = kb.list_all_vanilla_accessories() if hasattr(kb, "list_all_vanilla_accessories") else getattr(kb, "_accessories", {})
        for model_id, a_info in accessories.items():
            base_clone_id = a_info.get("baseParamId")
            if not base_clone_id:
                continue

            set_id = f"vanilla_base_accessory_{model_id}"
            alloc = id_allocator.allocate(set_id)
            clean_name = a_info.get("name", "Talisman")
            clean_desc = a_info.get("description", "A classic talisman of the Lands Between.")

            base_spec = {
                "set_id": set_id,
                "equip_params": [{
                    "param_table": "EquipParamAccessory",
                    "new_param_id": alloc.new_equip_param_id,
                    "base_clone_id": base_clone_id,
                    "target_model_id": int(model_id) if model_id.isdigit() else 0,
                    "slot": "accessory",
                    "slot_offset": 0,
                    "row_name": f"[LootForge] {clean_name}",
                    "field_updates": {
                        "sortId": alloc.new_equip_param_id,
                        "isDeposit": 1
                    }
                }],
                "fmg_texts": [{
                    "item_id": alloc.new_equip_param_id,
                    "vanilla_source_id": base_clone_id,
                    "slot": "accessory",
                    "slot_offset": 0,
                    "is_weapon": False,
                    "is_accessory": True,
                    "name": f"[LootForge] {clean_name}",
                    "caption": f"Standalone relic forged by LootForge from vanilla {clean_name}.\n\n{clean_desc}",
                    "info": f"Origin: Vanilla {clean_name}"
                }],
                "loot_distribution": {
                    "type": "map_pickup",
                    "lot_id": 102100,
                    "target_id": "102100",
                    "drop_rate_percent": 100.0,
                    "awarded_items": [alloc.new_equip_param_id]
                }
            }

            if variants_per_item > 1:
                variants = self.generate_variants_for_spec(base_spec, variants_per_item=variants_per_item, knowledge_base=kb)
                all_specs.extend(variants)
            else:
                all_specs.append(base_spec)

        return all_specs

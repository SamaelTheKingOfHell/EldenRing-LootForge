"""
Diablo-style procedural loot variant generator for LootForge.

Rolls random rarity tiers, prefixes, and suffixes, applying authentic stat modifiers,
SpEffectParam passive buffs, dynamic item naming, and detailed Diablo-style lore captions.
"""

import copy
import random
from typing import List, Dict, Any, Optional
from src.diablo_affixes import RarityTier, AffixType, AffixDefinition, AFFIX_POOL


class DiabloLootGenerator:
    """
    Generates multi-tier Diablo-style loot variants with dynamic affixes.

    Why:
        Enables rich, repeatable ARPG-style item progression in Elden Ring,
        turning standalone mod items into thousands of uniquely-rolled relics.
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

    def __init__(self, seed: Optional[int] = None, knowledge_base: Optional[Any] = None):
        self._rng = random.Random(seed)
        self._knowledge_base = knowledge_base

    def roll_rarity(self, is_boss: bool = False) -> RarityTier:
        """Selects a rarity tier using drop weights. Bosses are guaranteed Giga Legendary or Mythic."""
        weights_dict = self.BOSS_RARITY_WEIGHTS if is_boss else self.RARITY_WEIGHTS
        tiers = list(weights_dict.keys())
        weights = list(weights_dict.values())
        return self._rng.choices(tiers, weights=weights, k=1)[0]

    def roll_affixes(
        self,
        rarity: RarityTier,
        is_weapon: bool,
        is_boss: bool = False
    ) -> List[AffixDefinition]:
        """Rolls a balanced combination of prefixes and suffixes for the rarity tier."""
        if rarity == RarityTier.COMMON and not is_boss:
            return []

        available_prefixes = [
            a for a in AFFIX_POOL
            if a.affix_type == AffixType.PREFIX and
            (a.applies_to_weapon if is_weapon else a.applies_to_armor)
        ]
        available_suffixes = [
            a for a in AFFIX_POOL
            if a.affix_type == AffixType.SUFFIX and
            (a.applies_to_weapon if is_weapon else a.applies_to_armor)
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
        boss_name: Optional[str] = None
    ) -> str:
        """Appends formatted rarity and affix breakdown to the bottom of item description."""
        lines = [base_caption.rstrip(), ""]
        lines.append("----------------------------------------")
        tier_title = f"GIGA {rarity.display_name.upper()}" if boss_name else rarity.display_name.upper()
        lines.append(f"RARITY: {tier_title} {rarity.stars}")

        if boss_name:
            lines.append(f"[BOSS TROPHY] Claimed from {boss_name}")

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

        for v_idx in range(variants_per_item):
            spec_copy = copy.deepcopy(base_spec)
            spec_copy["set_id"] = f"{base_spec['set_id']}_v{v_idx + 1}"

            # 1. Determine distribution destination across whole game
            is_boss = False
            boss_name: Optional[str] = None
            loot_spec: Optional[Dict[str, Any]] = None

            if pools:
                boss_pool = pools.get("bosses", [])
                merchant_pool = pools.get("merchants", [])
                chest_pool = pools.get("chests", [])
                elites = pools.get("elites", [])
                roaming = pools.get("roaming", [])
                enemy_pool = (elites + roaming) if (elites or roaming) else []

                mod_bucket = v_idx % 5
                if mod_bucket == 0 and boss_pool:
                    boss = boss_pool[(v_idx // 5) % len(boss_pool)]
                    is_boss = True
                    boss_name = boss.get("name", "Great Enemy")
                    loot_spec = {
                        "type": "shop_lineup",
                        "shop_type": "finger_reader_enia",
                        "target_id": boss["id"],
                        "display_name": f"[Boss Remembrance] {boss_name}",
                        "cost_or_remembrance": float(boss.get("defaultCost", 30000))
                    }
                elif mod_bucket == 1 and merchant_pool:
                    merch = merchant_pool[(v_idx // 5) % len(merchant_pool)]
                    loot_spec = {
                        "type": "merchant_shop",
                        "shop_id": merch["id"],
                        "target_id": merch["id"],
                        "display_name": f"[Merchant Shop] {merch['name']}",
                        "merchant_name": merch["name"],
                        "cost_or_remembrance": float(merch.get("defaultRuneCost", 8000)),
                        "rune_cost": int(merch.get("defaultRuneCost", 8000))
                    }
                elif mod_bucket == 2 and chest_pool:
                    chest = chest_pool[(v_idx // 5) % len(chest_pool)]
                    loot_spec = {
                        "type": "map_pickup",
                        "lot_id": chest["lotParamId"],
                        "target_id": str(chest["lotParamId"]),
                        "display_name": f"[World Discovery] {chest['name']}",
                        "drop_rate_percent": 100.0
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

            # 2. Modify Equip Params and FMG texts with rolled affixes
            variant_new_ids: List[int] = []

            for ep in spec_copy.get("equip_params", []):
                old_id = ep["new_param_id"]
                new_id = old_id + ((v_idx + 1) * 100)
                ep["new_param_id"] = new_id
                variant_new_ids.append(new_id)

                is_weapon = ep.get("param_table") == "EquipParamWeapon"
                rarity = self.roll_rarity(is_boss=is_boss)
                affixes = self.roll_affixes(rarity, is_weapon=is_weapon, is_boss=is_boss)

                field_updates = ep.setdefault("field_updates", {})
                field_updates["sortId"] = new_id

                sp_effect_slot = 0
                for aff in affixes:
                    for field_name, delta in aff.field_modifiers.items():
                        current_val = field_updates.get(field_name, 0)
                        field_updates[field_name] = current_val + delta

                    if aff.sp_effect_id:
                        if is_weapon and sp_effect_slot < 3:
                            field_updates[f"spEffectId{sp_effect_slot}"] = aff.sp_effect_id
                            sp_effect_slot += 1
                        elif not is_weapon and sp_effect_slot < 3:
                            key = "residentSpEffectId" if sp_effect_slot == 0 else f"residentSpEffectId{sp_effect_slot + 1}"
                            field_updates[key] = aff.sp_effect_id
                            sp_effect_slot += 1

                for fmg in spec_copy.get("fmg_texts", []):
                    if fmg["item_id"] == old_id:
                        fmg["item_id"] = new_id
                        fmg["name"] = self.build_item_name(fmg["name"], rarity, affixes, is_boss=is_boss)
                        fmg["caption"] = self.build_caption_with_affixes(fmg["caption"], rarity, affixes, boss_name=boss_name)

            # 3. Synchronize loot distribution
            if loot_spec:
                loot_spec["awarded_items"] = variant_new_ids
                spec_copy["loot_distribution"] = loot_spec
            elif "loot_distribution" in spec_copy and "awarded_items" in spec_copy["loot_distribution"]:
                spec_copy["loot_distribution"]["awarded_items"] = variant_new_ids

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
            sp_effect_slot = 0
            for aff in affixes:
                for field_name, delta in aff.field_modifiers.items():
                    field_updates[field_name] = field_updates.get(field_name, 0) + delta

                if aff.sp_effect_id and sp_effect_slot < 3:
                    field_updates[f"spEffectId{sp_effect_slot}"] = aff.sp_effect_id
                    sp_effect_slot += 1

            clean_name = w_info.get("name", "Weapon")
            clean_desc = w_info.get("description", "")
            fmg_name = f"[{rarity.display_name}] {clean_name}" if rarity != RarityTier.COMMON else clean_name
            fmg_caption = self.build_caption_with_affixes(clean_desc, rarity, affixes)

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

            rarity = self.roll_rarity(is_boss=False)
            affixes = self.roll_affixes(rarity, is_weapon=False, is_boss=False)

            field_updates: Dict[str, Any] = {}
            sp_effect_slot = 0
            for aff in affixes:
                for field_name, delta in aff.field_modifiers.items():
                    field_updates[field_name] = field_updates.get(field_name, 0) + delta

                if aff.sp_effect_id and sp_effect_slot < 3:
                    key = "residentSpEffectId" if sp_effect_slot == 0 else f"residentSpEffectId{sp_effect_slot + 1}"
                    field_updates[key] = aff.sp_effect_id
                    sp_effect_slot += 1

            fmg_caption = self.build_caption_with_affixes(clean_desc, rarity, affixes)

            for slot_offset, slot_name in [(0, "Helm"), (100, "Armor"), (200, "Gauntlets"), (300, "Greaves")]:
                piece_id = base_param_id + slot_offset
                piece_name = f"[{rarity.display_name}] {clean_set_name} ({slot_name})" if rarity != RarityTier.COMMON else f"{clean_set_name} ({slot_name})"

                specs.append({
                    "set_id": f"vanilla_protector_inject_{piece_id}",
                    "equip_params": [{
                        "param_table": "EquipParamProtector",
                        "new_param_id": piece_id,
                        "update_existing": True,
                        "field_updates": dict(field_updates),
                        "row_name": f"[Vanilla Infused] {clean_set_name} ({slot_name})"
                    }],
                    "fmg_texts": [{
                        "item_id": piece_id,
                        "is_weapon": False,
                        "name": piece_name,
                        "caption": fmg_caption,
                        "info": f"Origin: Vanilla Elden Ring (Diablo Infused)"
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

            for slot_offset, slot_name, slot_key, field_name in [
                (0, "Helm", "head", "headEquipModelId"),
                (100, "Armor", "body", "bodyEquipModelId"),
                (200, "Gauntlets", "arms", "armEquipModelId"),
                (300, "Greaves", "legs", "legEquipModelId")
            ]:
                item_id = alloc.new_equip_param_id + slot_offset
                awarded_ids.append(item_id)
                model_int = int(model_id) if model_id.isdigit() else 0

                equip_params.append({
                    "param_table": "EquipParamProtector",
                    "new_param_id": item_id,
                    "base_clone_id": base_clone_id + slot_offset,
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
                    "vanilla_source_id": base_clone_id + slot_offset,
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

        return all_specs

"""
Vanilla gear stat and affix injector for LootForge.
Generates in-place procedural stat modifications and FMG text for vanilla items.
Complies with [CS-MODULAR] and [CS-GRANULARITY] (<= 300 lines).
"""

from typing import List, Dict, Any, Optional
from src.diablo_affixes import RarityTier, WeaponSkill


class VanillaStatInjector:
    """
    Generates procedural Diablo-style stat and affix infusions directly for vanilla items.
    """

    @staticmethod
    def generate_injections(generator: Any, knowledge_base: Optional[Any] = None) -> List[Dict[str, Any]]:
        kb = knowledge_base or generator._knowledge_base
        if not kb:
            return []

        specs: List[Dict[str, Any]] = []

        # 1. Vanilla weapons
        weapons = VanillaStatInjector.catalog(kb, "weapons")
        for model_id, w_info in weapons.items():
            base_param_id = w_info.get("baseParamId")
            if not base_param_id:
                continue

            w_tier = kb.get_progression_tier(w_info) if hasattr(kb, "get_progression_tier") else None
            rarity = generator.roll_rarity(is_boss=False, tier=w_tier)
            affixes = generator.roll_affixes(rarity, is_weapon=True, is_boss=False, tier=w_tier,
                is_shield=w_info.get("wepType") in (65, 67, 69) or "shield" in w_info.get("name", "").lower())

            field_updates: Dict[str, Any] = {}
            rolled_skill: Optional[WeaponSkill] = None
            if generator.randomize_weapon_skills:
                gem_mount = w_info.get("gemMountType", 1)
                is_unarmed = base_param_id == 110000 or base_param_id < 1000000
                if gem_mount > 0 and not is_unarmed:
                    rolled_skill = generator.roll_weapon_skill(tier=w_tier)
                    field_updates["swordArtsParamId"] = rolled_skill.id

            generator.apply_affixes_to_equipment(field_updates, affixes, is_weapon=True)
            VanillaStatInjector.power(generator, field_updates, rarity, w_tier)

            pricing = generator.pricing_engine.calculate_item_prices(
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
            fmg_caption = generator.build_caption_with_affixes(clean_desc, rarity, affixes, skill=rolled_skill, pricing=pricing)

            specs.append({
                "set_id": f"vanilla_weapon_inject_{base_param_id}",
                "equip_params": [{
                    "param_table": "EquipParamWeapon",
                    "new_param_id": base_param_id,
                    "update_existing": True,
                    "diablo_infusion_family": True,
                    "field_updates": field_updates,
                    "row_name": f"[Vanilla Infused] {clean_name}"
                }],
                "fmg_texts": [{
                    "item_id": base_param_id,
                    "is_weapon": True,
                    "name": fmg_name,
                    "caption": fmg_caption,
                    "info": "Origin: Vanilla Elden Ring (Diablo Infused)"
                }],
                "loot_distribution": None
            })

        # 2. Vanilla protectors (armor sets: head, body, arms, legs)
        protectors = VanillaStatInjector.catalog(kb, "protectors")
        for model_id, p_info in protectors.items():
            base_param_id = p_info.get("baseParamId")
            if not base_param_id:
                continue

            clean_set_name = p_info.get("name", "Armor Set")
            clean_desc = p_info.get("description", "")
            p_tier = kb.get_progression_tier(p_info) if (kb and hasattr(kb, "get_progression_tier")) else None

            rarity = generator.roll_rarity(is_boss=False, tier=p_tier)
            affixes = generator.roll_affixes(rarity, is_weapon=False, is_boss=False, tier=p_tier)

            field_updates: Dict[str, Any] = {}
            generator.apply_affixes_to_equipment(field_updates, affixes, is_weapon=False)
            VanillaStatInjector.power(generator, field_updates, rarity, p_tier)

            explicit_pieces = p_info.get("pieces")
            if p_info.get("_individual_piece"):
                pieces_to_process = [(base_param_id, "Armor")]
            elif explicit_pieces and isinstance(explicit_pieces, dict):
                pieces_to_process = [(pid, sname) for sname, pid in explicit_pieces.items()]
            elif base_param_id % 10000 == 0:
                pieces_to_process = [
                    (base_param_id + slot_offset, slot_name)
                    for slot_offset, slot_name in [(0, "Helm"), (100, "Armor"), (200, "Gauntlets"), (300, "Greaves")]
                ]
            else:
                pieces_to_process = [(base_param_id, "Armor")]

            for piece_id, slot_name in pieces_to_process:
                slot_key = {
                    "Helm": "head",
                    "Armor": "body",
                    "Gauntlets": "arms",
                    "Greaves": "legs"
                }.get(slot_name, slot_name.lower())

                piece_pricing = generator.pricing_engine.calculate_item_prices(
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

                piece_fmg_caption = generator.build_caption_with_affixes(clean_desc, rarity, affixes, pricing=piece_pricing)
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
                        "info": "Origin: Vanilla Elden Ring (Diablo Infused)"
                    }],
                    "loot_distribution": None
                })

        # 3. Vanilla accessories (talismans)
        accessories = VanillaStatInjector.catalog(kb, "accessories")
        for model_id, a_info in accessories.items():
            base_param_id = a_info.get("baseParamId")
            if not base_param_id:
                continue

            clean_name = a_info.get("name", "Talisman")
            clean_desc = a_info.get("description", "")
            a_tier = kb.get_progression_tier(a_info) if (kb and hasattr(kb, "get_progression_tier")) else None

            rarity = generator.roll_rarity(is_boss=False, tier=a_tier)
            affixes = generator.roll_affixes(rarity, is_weapon=False, is_accessory=True, is_boss=False, tier=a_tier)

            field_updates: Dict[str, Any] = {}
            generator.apply_affixes_to_equipment(field_updates, affixes, is_weapon=False, is_accessory=True)

            pricing = generator.pricing_engine.calculate_item_prices(
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
            fmg_caption = generator.build_caption_with_affixes(clean_desc, rarity, affixes, pricing=pricing)

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

    @staticmethod
    def catalog(kb, kind):
        discovery = getattr(kb, "list_all_discovered_" + kind, None)
        discovered = discovery() if discovery else {}
        if hasattr(kb, "_discovered_" + kind) and not getattr(kb, "_discovered_" + kind):
            discovered = {}
        if not discovered:
            getter = getattr(kb, "list_all_vanilla_" + kind, None)
            return getter() if getter else getattr(kb, "_" + kind, {})
        result = {}
        for info in discovered.values():
            item_id = info.get("baseParamId", 0)
            if not item_id or item_id >= 90000000 or (kind == "weapons" and item_id < 1000000):
                continue
            key = info.get("familyId", item_id) if kind == "weapons" else item_id
            if key not in result or item_id == key:
                result[key] = dict(info, _individual_piece=(kind == "protectors"))
        return result

    @staticmethod
    def power(generator, fields, rarity, tier):
        if generator.progression_scaling:
            from src.diablo_power import REGION_POWER, RARITY_POWER, RARITIES, tier_value
            fields["_lf_diablo_tier"] = tier_value(tier)
            fields["_lf_diablo_power"] = round(REGION_POWER[tier_value(tier)-1] *
                RARITY_POWER[RARITIES.index(rarity)] * generator.stats_multiplier, 4)

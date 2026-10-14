"""
Diablo variant builder service for LootForge.
Generates multi-tier Diablo-rolled variants for patch specifications,
organically distributed across Bosses, Merchants, Chests, and Elite Mobs.
Complies with [CS-MODULAR] and [CS-GRANULARITY] (<= 300 lines).
"""

import copy
from typing import List, Dict, Any, Optional, Set
from src.diablo_affixes import RarityTier, WeaponSkill
from src.logger import system_logger


class DiabloVariantBuilder:
    """
    Builds procedurally-rolled variants for equipment patch specifications.
    """

    @staticmethod
    def generate_variants(
        generator: Any,
        base_spec: Dict[str, Any],
        variants_per_item: int = 3,
        knowledge_base: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        if variants_per_item <= 1:
            return [base_spec]

        kb = knowledge_base or generator._knowledge_base
        pools = kb.get_diablo_distribution_pools() if (kb and hasattr(kb, "get_diablo_distribution_pools")) else None

        variant_specs: List[Dict[str, Any]] = []

        tier = base_spec.get("tier")
        if tier is None and kb and hasattr(kb, "get_progression_tier_for_spec"):
            tier = kb.get_progression_tier_for_spec(base_spec)

        item_assigned_chests: Set[int] = set()
        item_assigned_bosses: Set[str] = set()

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

                if tier and kb and hasattr(kb, "get_progression_tier"):
                    boss_pool = [b for b in raw_bosses if kb.get_progression_tier(b) == tier] or raw_bosses
                    chest_pool = [c for c in raw_chests if kb.get_progression_tier(c) == tier] or raw_chests
                    merchant_pool = [m for m in raw_merchants if kb.get_progression_tier(m) == tier] or raw_merchants
                    elites = [e for e in raw_elites if kb.get_progression_tier(e) == tier] or raw_elites
                    roaming = [r for r in raw_roaming if kb.get_progression_tier(r) == tier] or raw_roaming
                else:
                    boss_pool, chest_pool, merchant_pool = raw_bosses, raw_chests, raw_merchants
                    elites, roaming = raw_elites, raw_roaming

                enemy_pool = (elites + roaming) if (elites or roaming) else []

                mod_bucket = v_idx % 3
                if mod_bucket == 0 and boss_pool:
                    boss = generator.get_next_boss(boss_pool, excluded_ids=item_assigned_bosses) if hasattr(generator, "get_next_boss") else None
                    if not boss and raw_bosses and hasattr(generator, "get_next_boss"):
                        boss = generator.get_next_boss(raw_bosses, excluded_ids=item_assigned_bosses)
                    if boss:
                        generator.record_boss_assignment(boss["id"])
                        generator.record_shop_allocation(boss["id"], is_enia=True)
                        item_assigned_bosses.add(boss["id"])
                        is_boss, boss_name = True, boss.get("name", "Great Enemy")
                        loot_spec = {
                            "type": "shop_lineup",
                            "shop_type": "finger_reader_enia",
                            "target_id": boss["id"],
                            "display_name": f"[Boss Remembrance] {boss_name}",
                            "cost_or_remembrance": float(boss.get("defaultCost", 30000))
                        }
                    else:
                        chest = generator.get_next_chest(chest_pool, excluded_ids=item_assigned_chests) if hasattr(generator, "get_next_chest") else (chest_pool[0] if chest_pool else None)
                        if not chest and raw_chests and hasattr(generator, "get_next_chest"):
                            chest = generator.get_next_chest(raw_chests, excluded_ids=item_assigned_chests)
                        if chest:
                            generator.record_chest_assignment(chest.get("lotParamId", 0))
                            item_assigned_chests.add(chest.get("lotParamId", 0))
                            loot_spec = {
                                "type": "map_pickup",
                                "lot_id": chest["lotParamId"],
                                "target_id": str(chest["lotParamId"]),
                                "display_name": f"[Chest After Boss] {chest['name']}",
                                "drop_rate_percent": 100.0
                            }

                elif mod_bucket == 1 and chest_pool:
                    chest = generator.get_next_chest(chest_pool, excluded_ids=item_assigned_chests) if hasattr(generator, "get_next_chest") else (chest_pool[0] if chest_pool else None)
                    if not chest and raw_chests and hasattr(generator, "get_next_chest"):
                        chest = generator.get_next_chest(raw_chests, excluded_ids=item_assigned_chests)
                    if chest:
                        generator.record_chest_assignment(chest.get("lotParamId", 0))
                        item_assigned_chests.add(chest.get("lotParamId", 0))
                        loot_spec = {
                            "type": "map_pickup",
                            "lot_id": chest["lotParamId"],
                            "target_id": str(chest["lotParamId"]),
                            "display_name": f"[Chest Discovery] {chest['name']}",
                            "drop_rate_percent": 100.0
                        }

                if loot_spec is None:
                    rest_cycle = (v_idx // 3) % 3
                    if rest_cycle == 0 and merchant_pool:
                        merch = merchant_pool[(v_idx // 3) % len(merchant_pool)]
                        shop_id = merch["id"]
                        if not generator.is_shop_capacity_exceeded(shop_id, is_enia=False):
                            generator.record_shop_allocation(shop_id, is_enia=False)
                            loot_spec = {
                                "type": "merchant_shop",
                                "shop_id": merch["id"],
                                "target_id": merch["id"],
                                "display_name": f"[Merchant Shop] {merch['name']}",
                                "merchant_name": merch["name"],
                                "cost_or_remembrance": float(merch.get("defaultRuneCost", 8000)),
                                "rune_cost": int(merch.get("defaultRuneCost", 8000))
                            }

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

            if loot_spec is None and spec_copy.get("loot_distribution"):
                loot_spec = copy.deepcopy(spec_copy["loot_distribution"])

            is_chest_drop = loot_spec is not None and loot_spec.get("type") in ("map_pickup", "world_chest", "chest_drop")
            is_boss = is_boss or (loot_spec is not None and loot_spec.get("type") == "boss_remembrance")

            # 2. Modify Equip Params and FMG texts with rolled affixes
            variant_new_ids: List[int] = []
            variant_item_prices: Dict[str, int] = {}

            for ep in spec_copy.get("equip_params", []):
                old_id = ep["new_param_id"]
                new_id = old_id + ((v_idx + 1) * 100)
                ep["new_param_id"] = new_id
                variant_new_ids.append(new_id)

                is_weapon = ep.get("param_table") == "EquipParamWeapon"
                is_accessory = ep.get("param_table") == "EquipParamAccessory"
                rarity = generator.roll_rarity(is_boss=is_boss, is_chest=is_chest_drop)
                affixes = generator.roll_affixes(rarity, is_weapon=is_weapon, is_accessory=is_accessory, is_boss=is_boss or is_chest_drop)

                field_updates = ep.setdefault("field_updates", {})
                field_updates["sortId"] = new_id

                rolled_skill: Optional[WeaponSkill] = None
                effective_tier = tier
                if is_weapon and generator.randomize_weapon_skills:
                    if not effective_tier and loot_spec and kb and hasattr(kb, "get_progression_tier"):
                        target_id = loot_spec.get("target_id") or loot_spec.get("shop_id") or loot_spec.get("lot_id")
                        if target_id:
                            effective_tier = kb.get_progression_tier(str(target_id))
                    if not effective_tier and kb and hasattr(kb, "get_progression_tier_for_spec"):
                        effective_tier = kb.get_progression_tier_for_spec(spec_copy)
                    rolled_skill = generator.roll_weapon_skill(tier=effective_tier)
                    field_updates["swordArtsParamId"] = rolled_skill.id

                generator.apply_affixes_to_equipment(field_updates, affixes, is_weapon=is_weapon, is_accessory=is_accessory)

                pricing = generator.pricing_engine.calculate_item_prices(
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
                        fmg["name"] = generator.build_item_name(fmg["name"], rarity, affixes, is_boss=is_boss)
                        fmg["caption"] = generator.build_caption_with_affixes(
                            fmg["caption"], rarity, affixes, boss_name=boss_name, skill=rolled_skill, pricing=pricing
                        )

            # Multi-drop for Bosses and Chests (companion accessories)
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
                            comp_rarity = generator.roll_rarity(is_boss=is_boss, is_chest=is_chest_drop)
                            comp_affixes = generator.roll_affixes(comp_rarity, is_weapon=False, is_accessory=True, is_boss=is_boss or is_chest_drop)
                            comp_field_updates = {
                                "sortId": comp_param_id,
                                "isDeposit": 1,
                                "iconId": comp_info.get("iconId", 18000)
                            }
                            generator.apply_affixes_to_equipment(comp_field_updates, comp_affixes, is_weapon=False, is_accessory=True)

                            comp_pricing = generator.pricing_engine.calculate_item_prices(
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
                            comp_fmg_name = generator.build_item_name(f"[LootForge] {comp_name}", comp_rarity, comp_affixes, is_boss=is_boss or is_chest_drop)
                            comp_fmg_caption = generator.build_caption_with_affixes(
                                f"Extra treasure ({chest_tag}) awarded with {spec_copy.get('set_id')}.",
                                comp_rarity, comp_affixes, boss_name=boss_name, pricing=comp_pricing
                            )

                            spec_copy.setdefault("equip_params", []).append({
                                "param_table": "EquipParamAccessory", "new_param_id": comp_param_id, "base_clone_id": comp_base_id,
                                "slot": "accessory", "slot_offset": 50 + extra_idx, "row_name": f"[LootForge] {comp_name}",
                                "field_updates": comp_field_updates
                            })
                            spec_copy.setdefault("fmg_texts", []).append({
                                "item_id": comp_param_id, "vanilla_source_id": comp_base_id, "slot": "accessory",
                                "slot_offset": 50 + extra_idx, "is_weapon": False, "is_accessory": True,
                                "name": comp_fmg_name, "caption": comp_fmg_caption, "info": f"Origin: Vanilla {comp_name} ({chest_tag})"
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

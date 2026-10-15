"""
Vanilla base item distributor for LootForge.
Uses curated vanilla weapons, armors, and accessories to forge standalone procedural relics
and route them organically across bosses, merchants, and chests.
Complies with [CS-MODULAR] and [CS-GRANULARITY] (<= 300 lines).
"""

from typing import List, Dict, Any, Optional, Callable


class VanillaBaseDistributor:
    """
    Constructs standalone procedural relics from curated vanilla base gear.
    """

    @staticmethod
    def generate_distribution_specs(
        knowledge_base: Any,
        id_allocator: Any,
        variants_per_item: int,
        variant_generator_fn: Callable[[Dict[str, Any], int, Any], List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """
        Uses cataloged vanilla base items to create standalone distributed relics.
        """
        kb = knowledge_base
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
            alloc = id_allocator.allocate_virtual(set_id)
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
                variants = variant_generator_fn(base_spec, variants_per_item, kb)
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
            alloc = id_allocator.allocate_virtual(set_id)
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
                variants = variant_generator_fn(base_spec, variants_per_item, kb)
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
            alloc = id_allocator.allocate_virtual(set_id)
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
                        "isDeposit": 1,
                        "iconId": a_info.get("iconId", 18000)
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
                variants = variant_generator_fn(base_spec, variants_per_item, kb)
                all_specs.extend(variants)
            else:
                all_specs.append(base_spec)

        return all_specs

"""
Parameter patch builder for LootForge.

Generates structured parameter and text modification specifications for EquipParamProtector,
EquipParamWeapon, ItemLotParam_enemy, ShopLineupParam, and FMG item text.
"""

from typing import Dict, Any, List, Optional
from src.models import DetectedModSet, LootDistributionType, EquipmentSlot
from src.logger import system_logger


def _clean_mod_folder_name(folder_name: str) -> str:
    """Strips Nexus version suffixes and formats folder name for display."""
    import re as _re
    cleaned = _re.sub(r'-\d{2,}-[\d-]+$', '', folder_name)
    cleaned = cleaned.replace('_', ' ').replace('-', ' ')
    cleaned = _re.sub(r'\s+', ' ', cleaned).strip()
    if cleaned == cleaned.lower():
        cleaned = cleaned.title()
    return cleaned


class ParamBuilder:
    """
    Constructs patch specifications for Elden Ring game parameters and localization.
    
    Why:
        Translates user-selected loot configurations and standalone model allocations
        into concrete parameter rows compatible with regulation.bin.
        
    Example:
    ```python
    builder = ParamBuilder()
    spec = builder.build_patch_spec(mod_set)
    print(spec["equip_params"][0]["new_param_id"])
    ```
    """

    SLOT_MODEL_FIELD = {
        EquipmentSlot.HEAD: "headEquipModelId",
        EquipmentSlot.BODY: "bodyEquipModelId",
        EquipmentSlot.ARMS: "armEquipModelId",
        EquipmentSlot.LEGS: "legEquipModelId"
    }

    SLOT_ID_OFFSET = {
        EquipmentSlot.HEAD: 10000,
        EquipmentSlot.BODY: 20000,
        EquipmentSlot.ARMS: 30000,
        EquipmentSlot.LEGS: 40000,
        EquipmentSlot.WEAPON: 0
    }

    # Vanilla EquipParam row ID = model_id * multiplier + offset
    # Protectors: model*100 + (0=head, 100=body, 200=arms, 300=legs)
    # Weapons:    model*10000
    VANILLA_CLONE_OFFSETS = {
        EquipmentSlot.HEAD: (100, 0),
        EquipmentSlot.BODY: (100, 100),
        EquipmentSlot.ARMS: (100, 200),
        EquipmentSlot.LEGS: (100, 300),
        EquipmentSlot.WEAPON: (10000, 0),
    }

    def __init__(self, knowledge_base: Optional[Any] = None):
        self.kb = knowledge_base


    def build_patch_spec(self, mod_set: DetectedModSet) -> Dict[str, Any]:
        """
        Builds the complete parameter and loot patch dictionary for a mod set.
        """
        if not mod_set.allocation or not mod_set.loot_target:
            raise ValueError(f"ModSet '{mod_set.set_id}' is missing allocation or loot target.")

        alloc = mod_set.allocation
        new_model_id_int = int(alloc.new_model_id)
        base_param_id = alloc.new_equip_param_id

        equip_params: List[Dict[str, Any]] = []
        fmg_texts: List[Dict[str, Any]] = []

        # Determine slots present in the mod set
        slots_present = {part.slot for part in mod_set.parts}

        # Determine gender restriction (only female-exclusive sets are restricted)
        gender_res = getattr(mod_set, "gender_restriction", None)
        gender_tag = ""
        gender_caption = ""
        if gender_res == "female":
            gender_tag = "[Female Only] "
            gender_caption = "[RESTRICTION: Female Only] Tailored exclusively for Type B (Female) bodies. Attempting to equip on Type A (Male) characters is unsupported.\n\n"

        for slot in slots_present:
            slot_offset = self.SLOT_ID_OFFSET.get(slot, 0)
            item_id = base_param_id + slot_offset
            slot_name = slot.value.capitalize()

            # Compute the correct vanilla EquipParam row ID for cloning
            multiplier, vanilla_offset = self.VANILLA_CLONE_OFFSETS.get(slot, (100, 0))
            base_clone_id = int(mod_set.target_model_id) * multiplier + vanilla_offset

            # Item display name with marker tag (only female-exclusive gear gets restriction tag)
            cleaned_title = _clean_mod_folder_name(mod_set.folder_or_archive_name)
            item_display_name = f"{alloc.marker_tag} {gender_tag}{cleaned_title} ({slot_name})".strip()

            # Field updates for EquipParam
            field_updates: Dict[str, Any] = {
                "sortId": item_id,
                "isDeposit": 1,
            }

            if not mod_set.is_weapon and gender_res == "female":
                field_updates["equipModelGender"] = 2

            model_field = self.SLOT_MODEL_FIELD.get(slot)
            if model_field:
                field_updates[model_field] = new_model_id_int

            equip_params.append({
                "param_table": "EquipParamWeapon" if mod_set.is_weapon else "EquipParamProtector",
                "new_param_id": item_id,
                "base_clone_id": base_clone_id,
                "target_model_id": int(mod_set.target_model_id) if mod_set.target_model_id.isdigit() else 0,
                "slot": slot.value,
                "slot_offset": vanilla_offset,
                "row_name": f"[LootForge] {mod_set.set_id} ({slot_name})",
                "field_updates": field_updates
            })

            # FMG text specification — vanilla_source_id lets RegTool copy
            # authentic names/descriptions from the vanilla item being replaced
            fmg_texts.append({
                "item_id": item_id,
                "vanilla_source_id": base_clone_id,
                "target_model_id": int(mod_set.target_model_id) if mod_set.target_model_id.isdigit() else 0,
                "slot": slot.value,
                "slot_offset": vanilla_offset,
                "is_weapon": mod_set.is_weapon,
                "name": item_display_name,
                "caption": f"{gender_caption}Standalone relic forged by LootForge. Preserves authentic vanilla gear while offering unique drops.",
                "info": f"Origin: {mod_set.folder_or_archive_name}"
            })

        # Loot routing specification
        loot_spec: Dict[str, Any] = {}
        target = mod_set.loot_target

        if target.route_type == LootDistributionType.BOSS_REMEMBRANCE:
            loot_spec = {
                "type": "shop_lineup",
                "shop_type": "finger_reader_enia",
                "target_id": target.target_id,
                "display_name": target.display_name,
                "cost_or_remembrance": target.chance_or_cost,
                "awarded_items": [ep["new_param_id"] for ep in equip_params]
            }
        elif target.route_type == LootDistributionType.ENEMY_DROP:
            resolved_lot = self.kb.get_enemy_lot_id(str(target.target_id)) if self.kb else None
            lot_id = resolved_lot if resolved_lot else (int(target.target_id) if str(target.target_id).isdigit() else alloc.new_item_lot_id)
            loot_spec = {
                "type": "enemy_drop",
                "lot_id": lot_id,
                "target_id": str(target.target_id),
                "target_enemy": target.display_name,
                "drop_rate_percent": target.chance_or_cost,
                "awarded_items": [ep["new_param_id"] for ep in equip_params]
            }
        else:
            loot_spec = {
                "type": "merchant_shop",
                "shop_id": target.target_id,
                "target_id": target.target_id,
                "display_name": target.display_name,
                "merchant_name": target.display_name,
                "cost_or_remembrance": target.chance_or_cost,
                "rune_cost": int(target.chance_or_cost),
                "awarded_items": [ep["new_param_id"] for ep in equip_params]
            }

        system_logger.info(
            f"Built patch spec for '{mod_set.set_id}': {len(equip_params)} item(s) routed to {target.display_name}",
            source="ParamBuilder"
        )

        return {
            "set_id": mod_set.set_id,
            "equip_params": equip_params,
            "fmg_texts": fmg_texts,
            "loot_distribution": loot_spec
        }

    def build_diablo_patch_specs(
        self,
        mod_set: DetectedModSet,
        variants_count: int = 3,
        seed: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Builds multiple procedural Diablo-style patch specifications for a mod set.
        """
        base_spec = self.build_patch_spec(mod_set)
        from src.diablo_generator import DiabloLootGenerator
        generator = DiabloLootGenerator(seed=seed, knowledge_base=self.kb)
        return generator.generate_variants_for_spec(base_spec, variants_per_item=variants_count)

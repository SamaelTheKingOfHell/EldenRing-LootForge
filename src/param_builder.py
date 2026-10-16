"""
Parameter patch builder for LootForge.

Generates structured parameter and text modification specifications for EquipParamProtector,
EquipParamWeapon, ItemLotParam_enemy, ShopLineupParam, and FMG item text.
"""

from typing import Dict, Any, List, Optional
from src.models import DetectedModSet, LootDistributionType, EquipmentSlot
from src.logger import system_logger
from src.pricing_engine import PricingEngine


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
    # Weapons:    model*1000 (e.g. 9000*1000 = 9000000 for Uchigatana, NOT 90000000 knife)
    VANILLA_CLONE_OFFSETS = {
        EquipmentSlot.HEAD: (100, 0),
        EquipmentSlot.BODY: (100, 100),
        EquipmentSlot.ARMS: (100, 200),
        EquipmentSlot.LEGS: (100, 300),
        EquipmentSlot.WEAPON: (1000, 0),
    }

    def __init__(self, knowledge_base: Optional[Any] = None, pricing_engine: Optional[Any] = None):
        self.kb = knowledge_base
        self.pricing_engine = pricing_engine if pricing_engine is not None else PricingEngine()


    def build_patch_spec(self, mod_set: DetectedModSet, include_custom_art: bool = True) -> Dict[str, Any]:
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
        item_prices: Dict[str, int] = {}

        # Determine slots and gender coverage present in the mod set
        slots_present = {part.slot for part in mod_set.parts}
        genders_in_set = {p.gender_variant.lower() for p in mod_set.parts if not mod_set.is_weapon}
        has_male_files = "m" in genders_in_set
        has_female_files = "f" in genders_in_set
        # If both genders are present the cross-mirror is redundant; if only one is present
        # the cross-mirror in PartsDeployer/AssetRenumberer creates the missing file.
        # We also emit a vanilla fallback model ID as a secondary safety net — if the
        # cross-mirrored file somehow fails to reach the game (e.g. wrong Mod Engine path),
        # EquipInjector uses this ID to point the missing gender to a vanilla model that already
        # ships both bd_m_XXXX and bd_f_XXXX in the base game, preventing invisible body parts.
        #
        # Vanilla fallback: Commoner's Garb set (model 220) — ships all four slots
        # with both gender variants in every Elden Ring version including DLC.
        VANILLA_FALLBACK_MODEL_ID = 220

        is_boss_route = (mod_set.loot_target.route_type == LootDistributionType.BOSS_REMEMBRANCE) if mod_set.loot_target else False
        prog_tier = 1
        if self.kb and hasattr(self.kb, "get_progression_tier"):
            prog_tier = self.kb.get_progression_tier(str(mod_set.target_model_id)) or 1

        for slot in slots_present:
            slot_offset = self.SLOT_ID_OFFSET.get(slot, 0)
            item_id = base_param_id + slot_offset
            slot_name = slot.value.capitalize()

            multiplier, vanilla_offset = self.VANILLA_CLONE_OFFSETS.get(
                slot, (1000, 0) if mod_set.is_weapon else (100, 0)
            )

            # Compute the correct vanilla EquipParam row ID for cloning
            base_clone_id = None
            if self.kb:
                if mod_set.is_weapon:
                    wep = self.kb.lookup_weapon(str(mod_set.target_model_id))
                    if wep and wep.get("baseParamId"):
                        base_clone_id = wep["baseParamId"]
                else:
                    prot = self.kb.lookup_protector(str(mod_set.target_model_id))
                    if prot:
                        pieces = prot.get("pieces", {})
                        if slot_name in pieces:
                            base_clone_id = pieces[slot_name]
                        elif prot.get("baseParamId"):
                            base_clone_id = prot["baseParamId"] + vanilla_offset

            if base_clone_id is None:
                if mod_set.target_model_id.isdigit():
                    base_clone_id = int(mod_set.target_model_id) * multiplier + vanilla_offset
                else:
                    base_clone_id = 0

            # Item display name with marker tag
            if mod_set.souls_port_meta:
                from src.souls_port_adapter import SoulsPortAdapter
                item_display_name = SoulsPortAdapter.resolve_piece_name(mod_set, slot, marker=alloc.marker_tag)
            else:
                cleaned_title = _clean_mod_folder_name(mod_set.folder_or_archive_name)
                item_display_name = f"{alloc.marker_tag} {cleaned_title} ({slot_name})".strip()

            # Dynamic power-based buy and sell pricing
            pricing = self.pricing_engine.calculate_item_prices(
                slot=slot.value,
                tier=prog_tier,
                is_weapon=mod_set.is_weapon,
                is_boss=is_boss_route
            )
            item_prices[str(item_id)] = pricing["buy_price"]

            # Field updates for EquipParam (equipModelGender = 0: unisex for both Type A and Type B)
            field_updates: Dict[str, Any] = {
                "sortId": item_id,
                "isDeposit": 1,
                "sellValue": pricing["sell_price"],
                "saleValue": pricing["buy_price"],
            }

            if not mod_set.is_weapon:
                field_updates["basicPrice"] = pricing["buy_price"]
                field_updates["equipModelGender"] = 0
                # Emit gender coverage flags so EquipInjector knows which file variant
                # the mod actually provides. When only one gender is present the injector
                # can fall back to a vanilla model for the missing gender rather than
                # leaving the body slot invisible.
                field_updates["_lf_hasMaleFiles"] = 1 if has_male_files else 0
                field_updates["_lf_hasFemaleFiles"] = 1 if has_female_files else 0
                field_updates["_lf_fallbackModelId"] = VANILLA_FALLBACK_MODEL_ID
                if mod_set.souls_port_meta:
                    from src.souls_port_adapter import SoulsPortAdapter
                    field_updates.update(SoulsPortAdapter.get_er_field_updates(mod_set, slot))
            else:
                # If weapon has custom skill or moveset metadata, apply it
                if include_custom_art and getattr(mod_set, "import_custom_moveset", True) and mod_set.skill_moveset:
                    if not mod_set.skill_moveset.is_deep_introspected and mod_set.skill_moveset.regulation_path:
                        try:
                            from src.skill_moveset_importer import SkillMovesetImporter
                            reg_p = Path(mod_set.skill_moveset.regulation_path)
                            importer = SkillMovesetImporter(Path(__file__).resolve().parents[1])
                            importer.ensure_deep_introspected(mod_set)
                        except Exception:
                            pass
                    sm = mod_set.skill_moveset
                    if sm.has_custom_skill and sm.skill_id > 0:
                        field_updates["swordArtsParamId"] = sm.skill_id
                    if sm.behavior_variation_id > 0:
                        field_updates["behaviorVariationId"] = sm.behavior_variation_id
                    if sm.wepmotion_category > 0:
                        field_updates["wepmotionCategory"] = sm.wepmotion_category
                    if sm.wepmotion_one_hand_id > 0:
                        field_updates["wepmotionOneHandId"] = sm.wepmotion_one_hand_id
                    if sm.wepmotion_both_hand_id > 0:
                        field_updates["wepmotionBothHandId"] = sm.wepmotion_both_hand_id
                    if sm.sp_atk_category > 0:
                        field_updates["spAtkCategory"] = sm.sp_atk_category

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
            caption_text = (
                SoulsPortAdapter.resolve_piece_caption(mod_set, slot)
                if mod_set.souls_port_meta
                else "Standalone relic forged by LootForge. Preserves authentic vanilla gear while offering unique drops."
            )

            fmg_texts.append({
                "item_id": item_id,
                "vanilla_source_id": base_clone_id,
                "target_model_id": int(mod_set.target_model_id) if mod_set.target_model_id.isdigit() else 0,
                "slot": slot.value,
                "slot_offset": vanilla_offset,
                "is_weapon": mod_set.is_weapon,
                "name": item_display_name,
                "caption": caption_text,
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
                "awarded_items": [ep["new_param_id"] for ep in equip_params],
                "item_prices": item_prices
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
        elif target.route_type == LootDistributionType.MAP_PICKUP:
            lot_id = int(target.target_id) if str(target.target_id).isdigit() else alloc.new_item_lot_id
            awarded = [ep["new_param_id"] for ep in equip_params]

            loot_spec = {
                "type": "map_pickup",
                "lot_id": lot_id,
                "target_id": str(target.target_id),
                "display_name": target.display_name,
                "drop_rate_percent": float(target.chance_or_cost or 100.0),
                "awarded_items": awarded,
                "item_prices": item_prices
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
                "awarded_items": [ep["new_param_id"] for ep in equip_params],
                "item_prices": item_prices
            }

        if include_custom_art:
            system_logger.info(
                f"Built patch spec for '{mod_set.set_id}': {len(equip_params)} item(s) routed to {target.display_name}",
                source="ParamBuilder"
            )

        patch_spec = {
            "set_id": mod_set.set_id,
            "equip_params": equip_params,
            "fmg_texts": fmg_texts,
            "loot_distribution": loot_spec
        }

        if include_custom_art and mod_set.is_weapon and getattr(mod_set, "import_custom_moveset", True) and mod_set.skill_moveset:
            sm = mod_set.skill_moveset
            if sm.custom_skills_spec:
                patch_spec["custom_skills"] = sm.custom_skills_spec
            if sm.custom_behaviors_spec:
                patch_spec["custom_behaviors"] = sm.custom_behaviors_spec
            if sm.custom_attacks_spec:
                patch_spec["custom_attacks"] = sm.custom_attacks_spec

        return patch_spec

    def build_diablo_patch_specs(
        self,
        mod_set: DetectedModSet,
        variants_count: int = 3,
        seed: Optional[int] = None,
        randomize_weapon_skills: bool = False,
        balance_weapon_skills_by_progression: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Builds multiple procedural Diablo-style patch specifications for a mod set.
        """
        base_spec = self.build_patch_spec(mod_set)
        from src.diablo_generator import DiabloLootGenerator
        generator = DiabloLootGenerator(
            seed=seed,
            knowledge_base=self.kb,
            randomize_weapon_skills=randomize_weapon_skills,
            balance_weapon_skills_by_progression=balance_weapon_skills_by_progression
        )
        return generator.generate_variants_for_spec(base_spec, variants_per_item=variants_count)

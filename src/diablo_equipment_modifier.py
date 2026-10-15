"""
Equipment affix modifier service for LootForge.
Applies stat deltas and SpEffect passive buffs to parameter update dictionaries.
Complies with [CS-MODULAR] and [CS-GRANULARITY] (<= 300 lines).
"""

from typing import List, Dict, Any
from src.diablo_affixes import AffixDefinition


class DiabloEquipmentModifier:
    """
    Applies rolled Diablo affix stat deltas and SpEffect IDs into equipment field dictionaries.
    """

    @staticmethod
    def apply_affixes_to_equipment(
        field_updates: Dict[str, Any],
        affixes: List[AffixDefinition],
        is_weapon: bool,
        is_accessory: bool = False,
        stats_multiplier: float = 1.0,
        native_stat_deltas: bool = False
    ) -> None:
        """Applies stat deltas and routes SpEffect passive buffs to appropriate slots."""
        wep_behavior_slot = 0
        wep_resident_slot = 0
        wep_msg_slot = 0
        armor_resident_slot = 0
        acc_resident_slot = 1

        mult = max(0.0, float(stats_multiplier))
        native = {}
        passive_scales = {}
        stat_deltas = {}
        for aff in affixes:
            for key, value in aff.native_fields.items():
                if key.endswith("Rate"):
                    native[key] = round(1 + (value - 1) * mult, 5)
                else:
                    native[key] = int(round(value * mult))
            if aff.proc_kind and mult > 0:
                field_updates["_lf_diablo_proc"] = {
                    "kind": aff.proc_kind, "power": round(aff.power_scale * mult, 3)}
            for field_name, delta in aff.field_modifiers.items():
                if isinstance(delta, (int, float)):
                    scaled_delta = delta * mult
                    if isinstance(delta, int):
                        scaled_delta = int(round(scaled_delta))
                else:
                    scaled_delta = delta
                field_updates[field_name] = field_updates.get(field_name, 0) + scaled_delta
                stat_deltas[field_name] = stat_deltas.get(field_name, 0) + scaled_delta

            if aff.sp_effect_id:
                if aff.power_scale != 1.0:
                    passive_scales[str(aff.sp_effect_id)] = max(0.0, round(aff.power_scale * mult * 4) / 4)
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
        if native:
            field_updates["_lf_diablo_passives"] = native
        if passive_scales:
            field_updates["_lf_diablo_passive_scales"] = passive_scales
        if native_stat_deltas and stat_deltas:
            field_updates["_lf_diablo_stat_deltas"] = stat_deltas

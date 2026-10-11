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

    def __init__(self, seed: Optional[int] = None):
        self._rng = random.Random(seed)

    def roll_rarity(self) -> RarityTier:
        """Selects a rarity tier using Diablo-authentic drop weights."""
        tiers = list(self.RARITY_WEIGHTS.keys())
        weights = list(self.RARITY_WEIGHTS.values())
        return self._rng.choices(tiers, weights=weights, k=1)[0]

    def roll_affixes(self, rarity: RarityTier, is_weapon: bool) -> List[AffixDefinition]:
        """Rolls a balanced combination of prefixes and suffixes for the rarity tier."""
        if rarity == RarityTier.COMMON:
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
            suff_count = min(1, len(available_suffixes))
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

        return rolled

    def build_item_name(
        self,
        base_name: str,
        rarity: RarityTier,
        affixes: List[AffixDefinition],
        marker_tag: str = "✦ [LootForge]"
    ) -> str:
        """Formats dynamic Diablo item name: [Tag] [Rarity] Prefix BaseName Suffix."""
        prefixes = [a.name for a in affixes if a.affix_type == AffixType.PREFIX]
        suffixes = [a.name for a in affixes if a.affix_type == AffixType.SUFFIX]

        prefix_str = f"{' '.join(prefixes)} " if prefixes else ""
        suffix_str = f" {' '.join(suffixes)}" if suffixes else ""

        # Strip existing tag if present in base_name
        clean_base = base_name
        for prefix_tag in ["[LootForge]", "✦", "▪", "★"]:
            clean_base = clean_base.replace(prefix_tag, "").strip()

        rarity_tag = f"[{rarity.display_name}] " if rarity != RarityTier.COMMON else ""
        return f"{marker_tag} {rarity_tag}{prefix_str}{clean_base}{suffix_str}".strip()

    def build_caption_with_affixes(
        self,
        base_caption: str,
        rarity: RarityTier,
        affixes: List[AffixDefinition]
    ) -> str:
        """Appends formatted rarity and affix breakdown to the bottom of item description."""
        lines = [base_caption.rstrip(), ""]
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"◆ RARITY: {rarity.display_name.upper()} {rarity.stars}")

        if affixes:
            lines.append("----------------------------------------")
            lines.append("✦ DIABLO AFFIXES:")
            for aff in affixes:
                aff_type_str = "Prefix" if aff.affix_type == AffixType.PREFIX else "Suffix"
                lines.append(f"• [{aff_type_str}] {aff.name}: {aff.description}")
        else:
            lines.append("----------------------------------------")
            lines.append("✦ Standard Mundane Quality (No Magical Affixes)")

        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)

    def generate_variants_for_spec(
        self,
        base_spec: Dict[str, Any],
        variants_per_item: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Generates N Diablo-rolled variants for a given patch specification.
        """
        if variants_per_item <= 1:
            return [base_spec]

        variant_specs: List[Dict[str, Any]] = []

        for v_idx in range(variants_per_item):
            spec_copy = copy.deepcopy(base_spec)
            spec_copy["set_id"] = f"{base_spec['set_id']}_v{v_idx + 1}"

            # Modify Equip Params
            for ep in spec_copy.get("equip_params", []):
                old_id = ep["new_param_id"]
                # ID offset for variant instance
                new_id = old_id + ((v_idx + 1) * 100)
                ep["new_param_id"] = new_id

                is_weapon = ep.get("param_table") == "EquipParamWeapon"
                rarity = self.roll_rarity()
                affixes = self.roll_affixes(rarity, is_weapon=is_weapon)

                field_updates = ep.setdefault("field_updates", {})
                field_updates["sortId"] = new_id

                # Apply stat modifications from affixes
                sp_effect_slot = 0
                for aff in affixes:
                    for field_name, delta in aff.field_modifiers.items():
                        current_val = field_updates.get(field_name, 0)
                        field_updates[field_name] = current_val + delta

                    if aff.sp_effect_id:
                        if is_weapon and sp_effect_slot < 3:
                            field_updates[f"spEffectId{sp_effect_slot}"] = aff.sp_effect_id
                            sp_effect_slot += 1
                        elif not is_weapon:
                            key = "residentSpEffectId" if sp_effect_slot == 0 else f"residentSpEffectId{sp_effect_slot + 1}"
                            if sp_effect_slot < 3:
                                field_updates[key] = aff.sp_effect_id
                                sp_effect_slot += 1

                # Update matching FMG text for this item
                for fmg in spec_copy.get("fmg_texts", []):
                    if fmg["item_id"] == old_id:
                        fmg["item_id"] = new_id
                        fmg["name"] = self.build_item_name(fmg["name"], rarity, affixes)
                        fmg["caption"] = self.build_caption_with_affixes(fmg["caption"], rarity, affixes)

            variant_specs.append(spec_copy)

        return variant_specs

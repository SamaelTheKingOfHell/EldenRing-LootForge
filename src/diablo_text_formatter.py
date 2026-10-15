"""
Diablo-style text and caption formatting engine for LootForge.
Formats item names, affixes, pricing, and lore breakdowns for FMG display.
Complies with [CS-MODULAR] and [CS-GRANULARITY] (<= 300 lines).
"""

from typing import List, Dict, Any, Optional
from src.diablo_affixes import (
    RarityTier, AffixType, AffixDefinition, WeaponSkill
)


class DiabloTextFormatter:
    """
    Builds localized FMG item names and lore captions enriched with Diablo ARPG affixes.
    """

    @staticmethod
    def build_item_name(
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

    @staticmethod
    def build_caption_with_affixes(
        base_caption: str,
        rarity: RarityTier,
        affixes: List[AffixDefinition],
        boss_name: Optional[str] = None,
        skill: Optional[WeaponSkill] = None,
        pricing: Optional[Dict[str, Any]] = None,
        stats_multiplier: float = 1.0
    ) -> str:
        """Appends formatted rarity, skill, pricing, and affix breakdown to the bottom of item description."""
        lines = [base_caption.rstrip(), ""]
        lines.append("----------------------------------------")
        tier_title = f"GIGA {rarity.display_name.upper()}" if boss_name else rarity.display_name.upper()
        mult_tag = f" (Stats x{stats_multiplier:g})" if stats_multiplier != 1.0 else ""
        lines.append(f"RARITY: {tier_title} {rarity.stars}{mult_tag}")

        if skill:
            lines.append(f"SKILL: {skill.name}")

        if boss_name:
            lines.append(f"[BOSS TROPHY] Claimed from {boss_name}")

        if pricing and pricing.get("buy_price"):
            lines.append(f"VALUE: {pricing['buy_price']:,} Runes (Sell: {pricing.get('sell_price', 0):,})")

        if affixes:
            lines.append("----------------------------------------")
            header = "DIABLO AFFIXES:"
            if stats_multiplier != 1.0:
                header += f" (Potency x{stats_multiplier:g})"
            lines.append(header)
            for aff in affixes:
                aff_type_str = "Prefix" if aff.affix_type == AffixType.PREFIX else "Suffix"
                desc = aff.description
                if aff.sp_effect_id and aff.power_scale != 1.0:
                    potency = max(0.0, round(aff.power_scale * stats_multiplier * 4) / 4)
                    desc += f" [Base passive; rolled potency x{potency:g}]"
                if stats_multiplier != 1.0 and aff.field_modifiers:
                    for delta in aff.field_modifiers.values():
                        if isinstance(delta, (int, float)) and delta != 0:
                            scaled = int(round(delta * stats_multiplier)) if isinstance(delta, int) else round(delta * stats_multiplier, 1)
                            desc = desc.replace(f"+{delta}", f"+{scaled}").replace(f"{delta}%", f"{scaled}%")
                if aff.native_fields and stats_multiplier != 1.0:
                    for key, value in aff.native_fields.items():
                        old = round(abs((value - 1) * 100 if key.endswith("Rate") else value), 2)
                        new = round(old * stats_multiplier, 2) if key.endswith("Rate") else abs(int(round(value * stats_multiplier)))
                        desc = desc.replace(f"{old:g}", f"{new:g}")
                lines.append(f"- [{aff_type_str}] {aff.name}: {desc}")
        else:
            lines.append("----------------------------------------")
            lines.append("- Standard Mundane Quality (No Magical Affixes)")

        lines.append("----------------------------------------")
        return "\n".join(lines)

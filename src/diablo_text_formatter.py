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
        pricing: Optional[Dict[str, Any]] = None
    ) -> str:
        """Appends formatted rarity, skill, pricing, and affix breakdown to the bottom of item description."""
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

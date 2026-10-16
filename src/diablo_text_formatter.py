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
        import textwrap
        labels = {"attackBasePhysics": "Physical", "attackBaseMagic": "Magic", "attackBaseFire": "Fire",
                  "attackBaseThunder": "Lightning", "attackBaseDark": "Holy", "correctStrength": "STR scaling",
                  "correctAgility": "DEX scaling", "correctMagic": "INT scaling", "correctFaith": "FAI scaling",
                  "defensePhysics": "Defense", "defenseMagic": "Magic defense", "defenseFire": "Fire defense",
                  "defenseThunder": "Lightning defense", "defenseDark": "Holy defense", "toughnessCorrectRate": "Poise"}
        native_labels = {"maxHpRate": "HP", "maxMpRate": "FP", "maxStaminaRate": "Stamina",
                         "staminaRecoverChangeSpeed": "Stamina recovery", "changeHpPoint": "HP/s",
                         "physicsDiffenceRate": "Physical ward"}
        triggers = {"attack_cast": "Attack casts magic (6s)", "guard_cast": "Guard casts magic (10s)",
                    "guard_heal": "Guard heals (10s)", "thorns": "Hit: magic burst (8s)", "hurt_heal": "Hit: heal (12s)"}
        bonuses = []
        for aff in affixes:
            for field, delta in aff.field_modifiers.items():
                value = round(delta * stats_multiplier, 2)
                if field.startswith("defense"):
                    bonuses.append(f"{labels.get(field, field)} negation {value / 10:+g}%")
                else:
                    bonuses.append(f"{labels.get(field, field)} {value:+g}")
            if aff.sp_effect_id:
                power = max(0.5, round(aff.power_scale * stats_multiplier * 4) / 4) if stats_multiplier > 0 else 0
                bonuses.append(f"{aff.name.removeprefix('of ')} x{power:g}")
            for field, value in aff.native_fields.items():
                rate = field.endswith("Rate")
                amount = (value - 1) * 100 * stats_multiplier if rate else round(value * stats_multiplier)
                if field in ("changeHpPoint", "physicsDiffenceRate"):
                    amount = abs(amount)
                bonuses.append(f"{native_labels.get(field, field)} {amount:+g}{'%' if rate else ''}")
            if aff.proc_kind:
                bonuses.append(triggers[aff.proc_kind])
        title = f"RARITY: {'GIGA ' if boss_name else ''}{rarity.display_name.upper()}"
        if stats_multiplier != 1:
            title += f" (Stats x{stats_multiplier:g})"
        # The game adds its own skill panel underneath WeaponCaption. Long lore
        # plus a second skill/economy panel overlaps that fixed layout.
        summary = "; ".join(bonuses) if bonuses else "No additional magical effects."
        effect_lines = textwrap.wrap(summary, width=54, break_long_words=False, break_on_hyphens=False)
        lore = " ".join(base_caption.split())
        if lore.startswith("Standalone relic forged") or lore.startswith("Extra treasure"):
            lore = ""
        lines = [title]
        if lore and len(effect_lines) <= 3:
            lines += textwrap.wrap(lore[:100], width=54)[:2]
        lines += effect_lines
        return "\n".join(lines[:6])

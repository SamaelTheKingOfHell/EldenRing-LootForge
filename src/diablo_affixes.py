"""
Diablo-style affix definitions and pool for LootForge.

Defines rarity tiers, affix types (prefixes and suffixes), elemental damage bonuses,
defense augmentations, and authentic Elden Ring SpEffectParam passive buffs.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, List


class RarityTier(Enum):
    """Diablo rarity tiers with corresponding star ratings and affix counts."""
    COMMON = ("Common", "[*----]", 0, 0)
    MAGIC = ("Magic", "[**---]", 1, 1)
    RARE = ("Rare", "[***--]", 1, 2)
    LEGENDARY = ("Legendary", "[****-]", 2, 2)
    MYTHIC = ("Mythic", "[*****]", 2, 3)

    def __init__(self, display_name: str, stars: str, min_affixes: int, max_affixes: int):
        self.display_name = display_name
        self.stars = stars
        self.min_affixes = min_affixes
        self.max_affixes = max_affixes


class AffixType(Enum):
    """Distinguishes between item title prefixes and suffixes."""
    PREFIX = "prefix"
    SUFFIX = "suffix"


@dataclass
class AffixDefinition:
    """A single Diablo-style affix modifying stats and attaching SpEffects."""
    name: str
    affix_type: AffixType
    tier_min: RarityTier
    applies_to_weapon: bool
    applies_to_armor: bool
    field_modifiers: Dict[str, Any] = field(default_factory=dict)
    sp_effect_id: Optional[int] = None
    description: str = ""


# Comprehensive pool of authentic Elden Ring Diablo affixes
AFFIX_POOL: List[AffixDefinition] = [
    # ── PREFIXES: WEAPONS (ELEMENTAL & STATUS BUILDUPS) ──
    AffixDefinition(
        name="Fiery",
        affix_type=AffixType.PREFIX,
        tier_min=RarityTier.MAGIC,
        applies_to_weapon=True,
        applies_to_armor=False,
        field_modifiers={"attackBaseFire": 35},
        description="+35 Fire Damage"
    ),
    AffixDefinition(
        name="Incinerating",
        affix_type=AffixType.PREFIX,
        tier_min=RarityTier.RARE,
        applies_to_weapon=True,
        applies_to_armor=False,
        field_modifiers={"attackBaseFire": 65},
        description="+65 Fire Damage"
    ),
    AffixDefinition(
        name="Shocking",
        affix_type=AffixType.PREFIX,
        tier_min=RarityTier.MAGIC,
        applies_to_weapon=True,
        applies_to_armor=False,
        field_modifiers={"attackBaseThunder": 35},
        description="+35 Lightning Damage"
    ),
    AffixDefinition(
        name="Tempestuous",
        affix_type=AffixType.PREFIX,
        tier_min=RarityTier.RARE,
        applies_to_weapon=True,
        applies_to_armor=False,
        field_modifiers={"attackBaseThunder": 65},
        description="+65 Lightning Damage"
    ),
    AffixDefinition(
        name="Glacial",
        affix_type=AffixType.PREFIX,
        tier_min=RarityTier.MAGIC,
        applies_to_weapon=True,
        applies_to_armor=False,
        field_modifiers={"attackBaseMagic": 40},
        description="+40 Magic & Frostbite Buildup"
    ),
    AffixDefinition(
        name="Hallowed",
        affix_type=AffixType.PREFIX,
        tier_min=RarityTier.MAGIC,
        applies_to_weapon=True,
        applies_to_armor=False,
        field_modifiers={"attackBaseDark": 40},
        description="+40 Holy Damage"
    ),
    AffixDefinition(
        name="Serrated",
        affix_type=AffixType.PREFIX,
        tier_min=RarityTier.RARE,
        applies_to_weapon=True,
        applies_to_armor=False,
        field_modifiers={"attackBasePhysics": 25},
        sp_effect_id=313000,
        description="+25 Physical Attack & Boosts damage on blood loss"
    ),
    AffixDefinition(
        name="Brutal",
        affix_type=AffixType.PREFIX,
        tier_min=RarityTier.MAGIC,
        applies_to_weapon=True,
        applies_to_armor=False,
        field_modifiers={"correctStrength": 25, "attackBasePhysics": 20},
        description="+20 Physical Attack & Enhanced Strength Scaling"
    ),
    AffixDefinition(
        name="Deft",
        affix_type=AffixType.PREFIX,
        tier_min=RarityTier.MAGIC,
        applies_to_weapon=True,
        applies_to_armor=False,
        field_modifiers={"correctAgility": 25, "attackBasePhysics": 20},
        description="+20 Physical Attack & Enhanced Dexterity Scaling"
    ),

    # ── PREFIXES: ARMOR (DEFENSES, POISE, ATTRIBUTES) ──
    AffixDefinition(
        name="Ironclad",
        affix_type=AffixType.PREFIX,
        tier_min=RarityTier.MAGIC,
        applies_to_weapon=False,
        applies_to_armor=True,
        field_modifiers={"defensePhysics": 15, "defenseSlash": 15},
        description="+15 Physical & Slash Damage Negation"
    ),
    AffixDefinition(
        name="Juggernaut's",
        affix_type=AffixType.PREFIX,
        tier_min=RarityTier.RARE,
        applies_to_weapon=False,
        applies_to_armor=True,
        field_modifiers={"defensePhysics": 25, "poise": 10},
        sp_effect_id=311000,
        description="+25 Physical Defense & Bull-Goat Poise (+33%)"
    ),
    AffixDefinition(
        name="Flame-Warded",
        affix_type=AffixType.PREFIX,
        tier_min=RarityTier.MAGIC,
        applies_to_weapon=False,
        applies_to_armor=True,
        field_modifiers={"defenseFire": 20},
        sp_effect_id=314200,
        description="+20 Fire Defense & Flamedrake Ward (+20% Negation)"
    ),
    AffixDefinition(
        name="Spell-Warded",
        affix_type=AffixType.PREFIX,
        tier_min=RarityTier.MAGIC,
        applies_to_weapon=False,
        applies_to_armor=True,
        field_modifiers={"defenseMagic": 20},
        sp_effect_id=314100,
        description="+20 Magic Defense & Spelldrake Ward (+20% Negation)"
    ),
    AffixDefinition(
        name="Titanic",
        affix_type=AffixType.PREFIX,
        tier_min=RarityTier.RARE,
        applies_to_weapon=False,
        applies_to_armor=True,
        field_modifiers={"resistBlood": 40},
        sp_effect_id=310400,
        description="+40 Robustness & Boosts Maximum HP (+6%)"
    ),
    AffixDefinition(
        name="Enlightened",
        affix_type=AffixType.PREFIX,
        tier_min=RarityTier.RARE,
        applies_to_weapon=False,
        applies_to_armor=True,
        field_modifiers={"resistCurse": 40},
        sp_effect_id=310500,
        description="+40 Focus & Boosts Maximum FP (+7%)"
    ),
    AffixDefinition(
        name="Stalwart",
        affix_type=AffixType.PREFIX,
        tier_min=RarityTier.MAGIC,
        applies_to_weapon=False,
        applies_to_armor=True,
        field_modifiers={"resistBlood": 60, "resistFreeze": 60},
        sp_effect_id=315100,
        description="+60 Robustness & Stalwart Charm (Frost/Bleed Resist)"
    ),

    # ── SUFFIXES: WEAPONS & ARMOR (COMBAT PASSIVES & RECOVERY) ──
    AffixDefinition(
        name="of the Leech",
        affix_type=AffixType.SUFFIX,
        tier_min=RarityTier.MAGIC,
        applies_to_weapon=True,
        applies_to_armor=True,
        sp_effect_id=316000,
        description="Taker's Cameo: Restores 3% HP + 30 HP upon slaying foes"
    ),
    AffixDefinition(
        name="of the Phoenix",
        affix_type=AffixType.SUFFIX,
        tier_min=RarityTier.RARE,
        applies_to_weapon=True,
        applies_to_armor=True,
        sp_effect_id=310000,
        description="Blessed Dew: Continuously regenerates HP (+2 HP/sec)"
    ),
    AffixDefinition(
        name="of the Mind",
        affix_type=AffixType.SUFFIX,
        tier_min=RarityTier.MAGIC,
        applies_to_weapon=True,
        applies_to_armor=True,
        sp_effect_id=310100,
        description="Ancestral Spirit: Restores 3 FP upon defeating enemies"
    ),
    AffixDefinition(
        name="of the Wind",
        affix_type=AffixType.SUFFIX,
        tier_min=RarityTier.MAGIC,
        applies_to_weapon=True,
        applies_to_armor=True,
        sp_effect_id=310200,
        description="Green Turtle: Greatly accelerates Stamina recovery speed"
    ),
    AffixDefinition(
        name="of Slaughter",
        affix_type=AffixType.SUFFIX,
        tier_min=RarityTier.RARE,
        applies_to_weapon=True,
        applies_to_armor=False,
        sp_effect_id=316200,
        description="Rotten Winged Insignia: Successive attacks boost power up to 13%"
    ),
    AffixDefinition(
        name="of the Berserker",
        affix_type=AffixType.SUFFIX,
        tier_min=RarityTier.RARE,
        applies_to_weapon=True,
        applies_to_armor=True,
        sp_effect_id=316500,
        description="Branchsword: Grants +20% attack power when HP is critically low"
    ),
    AffixDefinition(
        name="of the Falcon",
        affix_type=AffixType.SUFFIX,
        tier_min=RarityTier.MAGIC,
        applies_to_weapon=True,
        applies_to_armor=True,
        sp_effect_id=311100,
        description="Claw Talisman: Jump attacks deal +15% damage"
    ),
    AffixDefinition(
        name="of the Champion",
        affix_type=AffixType.SUFFIX,
        tier_min=RarityTier.LEGENDARY,
        applies_to_weapon=True,
        applies_to_armor=False,
        sp_effect_id=312500,
        description="Shard of Alexander: Weapon skills deal +15% damage"
    ),
    AffixDefinition(
        name="of Fortune",
        affix_type=AffixType.SUFFIX,
        tier_min=RarityTier.MAGIC,
        applies_to_weapon=True,
        applies_to_armor=True,
        sp_effect_id=317200,
        description="Silver Scarab: Boosts item discovery by +75"
    ),
    AffixDefinition(
        name="of the Hunt",
        affix_type=AffixType.SUFFIX,
        tier_min=RarityTier.MAGIC,
        applies_to_weapon=True,
        applies_to_armor=True,
        sp_effect_id=317100,
        description="Gold Scarab: Increases runes gained from enemies by +20%"
    )
]

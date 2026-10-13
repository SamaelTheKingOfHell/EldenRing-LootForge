"""
Diablo-style affix definitions and pool for LootForge.

Defines rarity tiers, affix types (prefixes and suffixes), elemental damage bonuses,
defense augmentations, and authentic Elden Ring SpEffectParam passive buffs.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
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
    applies_to_accessory: bool = False
    field_modifiers: Dict[str, Any] = field(default_factory=dict)
    sp_effect_id: Optional[int] = None
    sp_effect_msg_id: Optional[int] = None
    is_on_hit_effect: bool = False
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
        sp_effect_id=6702,
        sp_effect_msg_id=6601,
        is_on_hit_effect=True,
        description="+40 Magic Attack & Causes Frostbite Buildup (50)"
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
        sp_effect_id=6400,
        sp_effect_msg_id=6501,
        is_on_hit_effect=True,
        description="+25 Physical Attack & Causes Blood Loss Buildup (45)"
    ),
    AffixDefinition(
        name="Venomous",
        affix_type=AffixType.PREFIX,
        tier_min=RarityTier.MAGIC,
        applies_to_weapon=True,
        applies_to_armor=False,
        field_modifiers={"attackBasePhysics": 15},
        sp_effect_id=6401,
        sp_effect_msg_id=6401,
        is_on_hit_effect=True,
        description="+15 Physical Attack & Causes Poison Buildup (50)"
    ),
    AffixDefinition(
        name="Rot-Infused",
        affix_type=AffixType.PREFIX,
        tier_min=RarityTier.RARE,
        applies_to_weapon=True,
        applies_to_armor=False,
        field_modifiers={"attackBasePhysics": 15},
        sp_effect_id=6451,
        sp_effect_msg_id=6451,
        is_on_hit_effect=True,
        description="+15 Physical Attack & Causes Scarlet Rot Buildup (50)"
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

    # ── PREFIXES: ARMOR & ACCESSORIES (DEFENSES, POISE, ATTRIBUTES, RECOVERY) ──
    AffixDefinition(
        name="Ironclad",
        affix_type=AffixType.PREFIX,
        tier_min=RarityTier.MAGIC,
        applies_to_weapon=False,
        applies_to_armor=True,
        applies_to_accessory=True,
        field_modifiers={"defensePhysics": 15, "defenseSlash": 15},
        description="+15 Physical & Slash Damage Negation"
    ),
    AffixDefinition(
        name="Juggernaut's",
        affix_type=AffixType.PREFIX,
        tier_min=RarityTier.RARE,
        applies_to_weapon=False,
        applies_to_armor=True,
        applies_to_accessory=True,
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
        applies_to_accessory=True,
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
        applies_to_accessory=True,
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
        applies_to_accessory=True,
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
        applies_to_accessory=True,
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
        applies_to_accessory=True,
        field_modifiers={"resistBlood": 60, "resistFreeze": 60},
        sp_effect_id=315100,
        description="+60 Robustness & Stalwart Charm (Frost/Bleed Resist)"
    ),
    AffixDefinition(
        name="Erdtree's",
        affix_type=AffixType.PREFIX,
        tier_min=RarityTier.LEGENDARY,
        applies_to_weapon=False,
        applies_to_armor=True,
        applies_to_accessory=True,
        sp_effect_id=310300,
        description="Erdtree's Favor: Raises maximum HP, Stamina, and Equip Load"
    ),
    AffixDefinition(
        name="Radagon's",
        affix_type=AffixType.PREFIX,
        tier_min=RarityTier.LEGENDARY,
        applies_to_weapon=False,
        applies_to_armor=False,
        applies_to_accessory=True,
        sp_effect_id=313000,
        description="Radagon's Soreseal: Greatly raises physical attributes"
    ),
    AffixDefinition(
        name="Godfrey's",
        affix_type=AffixType.PREFIX,
        tier_min=RarityTier.LEGENDARY,
        applies_to_weapon=True,
        applies_to_armor=False,
        applies_to_accessory=True,
        sp_effect_id=312000,
        description="Godfrey Icon: Enhances charged attack and spell power (+15%)"
    ),

    # ── SUFFIXES: WEAPONS, ARMOR & ACCESSORIES (COMBAT PASSIVES & RECOVERY) ──
    AffixDefinition(
        name="of the Leech",
        affix_type=AffixType.SUFFIX,
        tier_min=RarityTier.MAGIC,
        applies_to_weapon=True,
        applies_to_armor=True,
        applies_to_accessory=True,
        sp_effect_id=316000,
        sp_effect_msg_id=1001,
        description="Taker's Cameo: Restores 3% HP + 30 HP upon slaying foes"
    ),
    AffixDefinition(
        name="of the Phoenix",
        affix_type=AffixType.SUFFIX,
        tier_min=RarityTier.RARE,
        applies_to_weapon=True,
        applies_to_armor=True,
        applies_to_accessory=True,
        sp_effect_id=310000,
        sp_effect_msg_id=1005,
        description="Blessed Dew: Continuously regenerates HP (+2 HP/sec)"
    ),
    AffixDefinition(
        name="of the Mind",
        affix_type=AffixType.SUFFIX,
        tier_min=RarityTier.MAGIC,
        applies_to_weapon=True,
        applies_to_armor=True,
        applies_to_accessory=True,
        sp_effect_id=310100,
        sp_effect_msg_id=1002,
        description="Ancestral Spirit: Restores 3 FP upon defeating enemies"
    ),
    AffixDefinition(
        name="of the Wind",
        affix_type=AffixType.SUFFIX,
        tier_min=RarityTier.MAGIC,
        applies_to_weapon=True,
        applies_to_armor=True,
        applies_to_accessory=True,
        sp_effect_id=310200,
        description="Green Turtle: Greatly accelerates Stamina recovery speed"
    ),
    AffixDefinition(
        name="of Slaughter",
        affix_type=AffixType.SUFFIX,
        tier_min=RarityTier.RARE,
        applies_to_weapon=True,
        applies_to_armor=False,
        applies_to_accessory=True,
        sp_effect_id=316200,
        description="Rotten Winged Insignia: Successive attacks boost power up to 13%"
    ),
    AffixDefinition(
        name="of the Berserker",
        affix_type=AffixType.SUFFIX,
        tier_min=RarityTier.RARE,
        applies_to_weapon=True,
        applies_to_armor=True,
        applies_to_accessory=True,
        sp_effect_id=316500,
        description="Branchsword: Grants +20% attack power when HP is critically low"
    ),
    AffixDefinition(
        name="of the Falcon",
        affix_type=AffixType.SUFFIX,
        tier_min=RarityTier.MAGIC,
        applies_to_weapon=True,
        applies_to_armor=True,
        applies_to_accessory=True,
        sp_effect_id=311100,
        description="Claw Talisman: Jump attacks deal +15% damage"
    ),
    AffixDefinition(
        name="of the Champion",
        affix_type=AffixType.SUFFIX,
        tier_min=RarityTier.LEGENDARY,
        applies_to_weapon=True,
        applies_to_armor=False,
        applies_to_accessory=True,
        sp_effect_id=312500,
        description="Shard of Alexander: Weapon skills deal +15% damage"
    ),
    AffixDefinition(
        name="of Fortune",
        affix_type=AffixType.SUFFIX,
        tier_min=RarityTier.MAGIC,
        applies_to_weapon=True,
        applies_to_armor=True,
        applies_to_accessory=True,
        sp_effect_id=317200,
        description="Silver Scarab: Boosts item discovery by +75"
    ),
    AffixDefinition(
        name="of the Hunt",
        affix_type=AffixType.SUFFIX,
        tier_min=RarityTier.MAGIC,
        applies_to_weapon=True,
        applies_to_armor=True,
        applies_to_accessory=True,
        sp_effect_id=317100,
        description="Gold Scarab: Increases runes gained from enemies by +20%"
    ),
    AffixDefinition(
        name="of the Sorcerer",
        affix_type=AffixType.SUFFIX,
        tier_min=RarityTier.MAGIC,
        applies_to_weapon=False,
        applies_to_armor=False,
        applies_to_accessory=True,
        sp_effect_id=318000,
        description="Graven-School: Raises potency of sorceries (+4%)"
    ),
    AffixDefinition(
        name="of the Faithful",
        affix_type=AffixType.SUFFIX,
        tier_min=RarityTier.MAGIC,
        applies_to_weapon=False,
        applies_to_armor=False,
        applies_to_accessory=True,
        sp_effect_id=318100,
        description="Flock's Canvas: Greatly raises potency of incantations (+8%)"
    ),
    AffixDefinition(
        name="of Swift Casting",
        affix_type=AffixType.SUFFIX,
        tier_min=RarityTier.RARE,
        applies_to_weapon=False,
        applies_to_armor=False,
        applies_to_accessory=True,
        sp_effect_id=318200,
        description="Radagon Icon: Shortens spell casting time"
    )
]


# ── WEAPON SKILLS (ASHES OF WAR / SWORD ARTS) ──

@dataclass
class WeaponSkill:
    """Authentic Elden Ring weapon skill (Ash of War) definition."""
    id: int
    name: str
    description: str = ""


# Comprehensive catalog of iconic and authentic Elden Ring weapon skills
DEFAULT_WEAPON_SKILLS: List[WeaponSkill] = [
    WeaponSkill(100, "Lion's Claw", "Somersault forward, striking foes from above with great force."),
    WeaponSkill(101, "Impaling Thrust", "Lunge forward with a thrusting attack that pierces through shields."),
    WeaponSkill(102, "Piercing Fang", "Step forward and unleash a powerful thrust that completely bypasses shields."),
    WeaponSkill(103, "Spinning Slash", "Spin with great momentum, cleaving surrounding enemies."),
    WeaponSkill(105, "Charge Forth", "Lower weapon and charge forward, impaling any foes in the path."),
    WeaponSkill(106, "Stamp (Upward Cut)", "Brace and stamp down, absorbing incoming attacks before cutting upward."),
    WeaponSkill(107, "Stamp (Sweep)", "Brace and stamp down, absorbing attacks before unleashing a sweeping slash."),
    WeaponSkill(108, "Blood Tax", "Unleash a flurry of thrusts that steal enemy HP with each hit."),
    WeaponSkill(109, "Repeating Thrust", "Twist into a fast succession of sharp thrusts."),
    WeaponSkill(110, "Wild Strikes", "Swing weapon violently and continuously while walking forward."),
    WeaponSkill(111, "Spinning Strikes", "Spin weapon continuously overhead, repelling incoming blows."),
    WeaponSkill(112, "Double Slash", "Perform a swift cross-slash followed by rapid successive strikes."),
    WeaponSkill(113, "Prelate's Charge", "Slam weapon down and charge forward, trailing burning flames."),
    WeaponSkill(114, "Unsheathe", "Sheathe blade and choose between a swift upward slash or heavy overhead strike."),
    WeaponSkill(115, "Square Off", "Adopt a ready stance to break enemy guards with swift strikes."),
    WeaponSkill(116, "Giant Hunt", "Step forward with immense power, launching targets into the air."),
    WeaponSkill(118, "Loretta's Slash", "Leap gracefully into the air, imbuing the blade with magic before descending."),
    WeaponSkill(122, "Storm Assault", "Leap into the air shrouded in stormwinds and crash down upon foes."),
    WeaponSkill(123, "Stormcaller", "Spin weapon to summon a raging tempest that batters nearby foes."),
    WeaponSkill(124, "Sword Dance", "Advance forward in a fluid, rhythmic dance of sweeping blade strikes."),
    WeaponSkill(200, "Glintblade Phalanx", "Form an arch of magical glintblades that automatically fire upon targets."),
    WeaponSkill(201, "Sacred Blade", "Coat blade in holy light and fire a blade-shaped golden projectile."),
    WeaponSkill(202, "Ice Spear", "Channel spinning cold sorcery to launch a piercing spear of ice."),
    WeaponSkill(203, "Glintstone Pebble", "Cast an accelerated glintstone pebble followed by a lunging thrust."),
    WeaponSkill(204, "Bloody Slash", "Coat weapon in blood to loose a wide, devastating crescent wave."),
    WeaponSkill(207, "Eruption", "Slam weapon into the earth, causing molten lava to erupt."),
    WeaponSkill(208, "Prayerful Strike", "Raise weapon to the heavens and slam it down, healing self and allies on hit."),
    WeaponSkill(209, "Gravitas", "Plunge weapon into the ground to create a gravity well that pulls foes inward."),
    WeaponSkill(210, "Storm Blade", "Swing weapon to release a howling projectile blade of stormwinds."),
    WeaponSkill(212, "Earthshaker", "Drive weapon deep into the ground, detonating shockwaves across the earth."),
    WeaponSkill(213, "Golden Land", "Thrust weapon into the ground to erect golden pillars of Erdtree light."),
    WeaponSkill(214, "Flaming Strike", "Sweep weapon forward in a wide arc of fire, coating the blade in flame."),
    WeaponSkill(216, "Thunderbolt", "Call down a bolt of red-gold lightning upon target location."),
    WeaponSkill(217, "Lightning Slash", "Call down lightning into the blade before slamming down a devastating shockwave."),
    WeaponSkill(218, "Carian Grandeur", "Transform blade into a colossal magic greatsword for an earth-shattering strike."),
    WeaponSkill(219, "Carian Greatsword", "Conjure a massive magic blade and sweep it in a wide frontal arc."),
    WeaponSkill(220, "Vacuum Slice", "Swing weapon to release a slicing wave of vacuum blades."),
    WeaponSkill(221, "Black Flame Tornado", "Spin weapon rapidly to create an inferno of God-slaying black flames."),
    WeaponSkill(224, "Blood Blade", "Slash repeatedly to loose projectiles formed of user's own blood."),
    WeaponSkill(225, "Phantom Slash", "Summon a spirit illusion to charge and strike alongside the user."),
    WeaponSkill(226, "Spectral Lance", "Hurl an ethereal lance with superb range and poise-breaking force."),
    WeaponSkill(227, "Chilling Mist", "Coat weapon in frost and exhale a freezing mist that inflicts Frostbite."),
    WeaponSkill(228, "Poisonous Mist", "Coat weapon in venom and expel a poisonous cloud."),
    WeaponSkill(501, "Hoarfrost Stomp", "Stomp the ground to spread a freezing carpet of jagged frost spikes."),
    WeaponSkill(502, "Storm Stomp", "Stomp the earth to unleash a sudden, dizzying tempest."),
    WeaponSkill(504, "Lightning Ram", "Roll forward continuously like a goat shrouded in lightning."),
    WeaponSkill(505, "Flame of the Redmanes", "Breathe a wide carpet of ferocious flame that heavily damages enemy stance."),
    WeaponSkill(508, "Waves of Darkness", "Thrust weapon into the ground to release three waves of dark gravity shockwaves."),
    WeaponSkill(509, "Hoarah Loux's Earthshaker", "Let out a roar and slam the ground twice with ferocious shockwaves."),
    WeaponSkill(600, "Determination", "Focus spirit to dramatically empower the damage of the next attack."),
    WeaponSkill(601, "Royal Knight's Resolve", "Greatly strengthen resolve, multiplying next attack's power by +80%."),
    WeaponSkill(603, "Golden Vow", "Bestow Erdtree blessings, boosting attack power and defense for self and allies."),
    WeaponSkill(606, "Seppuku", "Plunge blade into user's own body to massively boost attack power and Bleed buildup."),
    WeaponSkill(607, "Cragblade", "Encase weapon in shattered stone, boosting physical attack and stance damage."),
    WeaponSkill(800, "Quickstep", "Maneuver swiftly around locked-on enemies to circle behind their guard."),
    WeaponSkill(801, "Bloodhound's Step", "Shadow-step through space with seamless evasive invulnerability."),
    WeaponSkill(802, "Raptor of the Mists", "Duck into shadow upon receiving a hit, instantly jumping high into the air."),
    WeaponSkill(1008, "Moonlight Greatsword", "Infuse blade with dark moonlight, loosing crescent waves with heavy attacks."),
    WeaponSkill(1010, "Rallying Standard", "Wave high the battle standard, inspiring allies with heightened attack and defense."),
    WeaponSkill(1012, "Eochaid's Dancing Blade", "Imbue weapon with telekinetic energy, throwing it forward in a corkscrewing drill."),
    WeaponSkill(1014, "Taker's Flames", "Raise blade aloft and unleash a surging wave of blasphemous fire that absorbs HP."),
    WeaponSkill(1016, "Reduvia Blood Blade", "Slash rapidly to release relentless airborne projectiles of cursed blood."),
    WeaponSkill(1019, "Night-and-Flame Stance", "Adopt stance to unleash either the Night Comet beam or sweeping fire wave."),
    WeaponSkill(1020, "Wave of Gold", "Swing sword to send a towering tidal wave of golden light surging forward."),
    WeaponSkill(1025, "Thundercloud Form", "Transform into a raging red lightning cloud and charge forward, piercing foes."),
    WeaponSkill(1027, "Waterfowl Dance", "Leap into the air and perform a graceful, three-stage flurry of lethal slashes."),
    WeaponSkill(1032, "Starcaller Cry", "Roar to draw foes inward with gravity, followed by a cataclysmic slam."),
    WeaponSkill(1034, "Bloodboon Ritual", "Thrust sacred spear into the sky to commune with the Formless Mother in three bursts."),
    WeaponSkill(1037, "Destined Death", "Unleash a flurry of slashes that erupt in a storm of destined death and HP burn."),
    WeaponSkill(1175, "Bloodhound's Finesse", "Slash upward while backflipping away, followed by an invisible forward dash."),
    WeaponSkill(1177, "Corpse Piler", "Slash across in rapid succession with a cursed blade of solidified blood."),
    WeaponSkill(1178, "Transient Moonlight", "Sheathe blade into dimensional rift before firing horizontal or vertical beam."),
    WeaponSkill(2001, "Aspects of the Crucible: Wings", "Sprout primordial golden wings and fly forward, plunging weapon into targets."),
    WeaponSkill(4000, "Spinning Gravity Thrust", "Soar with corkscrew gravity momentum before driving weapon forward."),
    WeaponSkill(4090, "Blind Spot", "Leap past opponent's side to strike from their undefended flank."),
    WeaponSkill(4100, "Swift Slash", "Dash forward faster than the eye can track, leaving cross-slashes in user's wake.")
]


def load_weapon_skills(paramdex_path: Optional[str] = None) -> List[WeaponSkill]:
    """
    Loads authentic weapon skills from Paramdex SwordArtsParam names table if present,
    falling back cleanly to the built-in curated weapon skills catalog.
    """
    candidate_paths = []
    if paramdex_path:
        candidate_paths.append(Path(paramdex_path))

    # Look up relative to current repository
    base = Path(__file__).resolve().parent.parent
    candidate_paths.extend([
        base / "tools" / "vendor" / "Paramdex" / "ER" / "Names" / "SwordArtsParam.txt",
        Path("tools/vendor/Paramdex/ER/Names/SwordArtsParam.txt")
    ])

    for p in candidate_paths:
        if p.exists() and p.is_file():
            try:
                skills: List[WeaponSkill] = []
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        parts = line.split(" ", 1)
                        if len(parts) != 2:
                            continue
                        try:
                            s_id = int(parts[0])
                        except ValueError:
                            continue
                        name = parts[1].strip()
                        # Filter out "No Skill" (10), developer placeholders, nulls, and dummies
                        if s_id == 10 or name.startswith("%") or "dummy" in name.lower() or not name:
                            continue
                        skills.append(WeaponSkill(id=s_id, name=name))

                if len(skills) >= 10:
                    return skills
            except Exception:
                pass

    return list(DEFAULT_WEAPON_SKILLS)


# Active global pool of weapon skills for procedural randomization
WEAPON_SKILL_POOL: List[WeaponSkill] = load_weapon_skills()

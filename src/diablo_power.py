"""Diablo-only item power, extra passives and rare combat enchantment rolls."""

from dataclasses import replace
from src.diablo_affixes import AffixDefinition, AffixType, RarityTier
from src.models import ProgressionTier


RARITIES = list(RarityTier)
REGION_POWER = (0.18, 0.60, 1.05, 1.55)
RARITY_POWER = (0.50, 0.70, 0.90, 1.15, 1.40)
DROP_WEIGHTS = (
    (40, 43, 15, 1.8, 0.2), (25, 40, 28, 6, 1),
    (15, 35, 35, 12, 3), (10, 30, 40, 16, 4))
BOSS_WEIGHTS = (
    (0, 10, 75, 13, 2), (0, 5, 60, 30, 5),
    (0, 0, 35, 55, 10), (0, 0, 15, 65, 20))
CHEST_WEIGHTS = (
    (15, 43, 35, 6.5, 0.5), (10, 30, 45, 13, 2),
    (5, 20, 45, 25, 5), (0, 10, 40, 40, 10))
# Native SpEffect fields; multiplicative values are relative to neutral 1.0.
PASSIVES = (
    ("Vitality", {"maxHpRate": 0.025}, "+{value}% maximum HP"),
    ("Focus", {"maxMpRate": 0.035}, "+{value}% maximum FP"),
    ("Endurance", {"maxStaminaRate": 0.035}, "+{value}% maximum stamina"),
    ("Recovery", {"staminaRecoverChangeSpeed": 4.0}, "+{value} stamina recovery"),
    ("Renewal", {"changeHpPoint": -1.0}, "Regenerates {value} HP each second"),
    ("Warding", {"physicsDiffenceRate": -0.025}, "{value}% physical damage reduction"),
)


def tier_value(tier):
    """Unknown progression is conservatively early, never an unrestricted roll."""
    value = getattr(tier, "value", tier)
    try:
        return max(1, min(4, int(value)))
    except (TypeError, ValueError):
        return 1


def scale_affixes(rng, affixes, rarity, tier):
    power = REGION_POWER[tier_value(tier) - 1] * RARITY_POWER[RARITIES.index(rarity)]
    power *= rng.uniform(0.90, 1.10)
    result = []
    for aff in affixes:
        fields = {key: (max(1, int(round(value * power))) if isinstance(value, int) and value > 0 else int(round(value * power)) if isinstance(value, int)
                        else round(value * power, 3))
                  for key, value in aff.field_modifiers.items()}
        description = aff.description
        for original, scaled in sorted(zip(aff.field_modifiers.values(), fields.values()),
                                       key=lambda pair: len(str(pair[0])), reverse=True):
            description = description.replace(f"+{original}", f"+{scaled}")
        result.append(replace(aff, field_modifiers=fields, description=description,
                              power_scale=power))
    return result, power


def roll_progression_rarity(rng, tier, is_boss=False, is_chest=False):
    weights = BOSS_WEIGHTS if is_boss else CHEST_WEIGHTS if is_chest else DROP_WEIGHTS
    return rng.choices(RARITIES, weights[tier_value(tier) - 1])[0]


def extra_passives(rng, rarity, power):
    power = max(0.25, round(power * 4) / 4)
    rank = RARITIES.index(rarity)
    if rank < 1:
        return []
    # Magic: occasional one; Rare: one; Legendary/Mythic: two/three.
    count = (0 if rng.random() > 0.25 else 1) if rank == 1 else rank - 1
    result = []
    for name, fields, description in rng.sample(PASSIVES, count):
        key, delta = next(iter(fields.items()))
        delta = round(delta * power, 4)
        rate = key.endswith("Rate")
        if key in ("maxHpRate", "maxMpRate", "maxStaminaRate"):
            delta = max(0.02, delta)
        elif key == "physicsDiffenceRate":
            delta = min(-0.01, delta)
        native = {key: round(1.0 + delta, 4) if rate else delta}
        if key == "changeHpPoint":
            native[key] = -max(1, int(round(abs(delta))))
        value = round(abs(delta) * (100 if rate else 1), 2)
        if key == "changeHpPoint":
            value = abs(native[key])
        result.append(AffixDefinition(
            name=f"of {name}", affix_type=AffixType.SUFFIX,
            tier_min=rarity, applies_to_weapon=True, applies_to_armor=True,
            applies_to_accessory=True, native_fields=native,
            description=description.format(value=f"{value:g}")))
    return result


def roll_enchantment(rng, rarity, tier, power, is_weapon, is_shield=False, is_accessory=False):
    if rarity not in (RarityTier.LEGENDARY, RarityTier.MYTHIC) or is_accessory:
        return []
    if rng.random() >= (0.06 if rarity == RarityTier.LEGENDARY else 0.14):
        return []
    kinds = ["guard_heal", "guard_cast"] if is_shield else (
        ["attack_cast"] if is_weapon else ["thorns", "hurt_heal"])
    kind = rng.choice(kinds)
    descriptions = {
        "attack_cast": "While attacking: casts a glintstone projectile (6s cooldown)",
        "guard_cast": "While guarding: casts a glintstone projectile (10s cooldown)",
        "guard_heal": "While guarding: restores HP (10s cooldown)",
        "thorns": "When struck: retaliates with a magic burst (8s cooldown)",
        "hurt_heal": "When struck: restores HP (12s cooldown)",
    }
    return [AffixDefinition(
        name="of Spellweaving", affix_type=AffixType.SUFFIX, tier_min=RarityTier.LEGENDARY,
        applies_to_weapon=is_weapon, applies_to_armor=not is_weapon,
        proc_kind=kind, power_scale=power, description=descriptions[kind])]

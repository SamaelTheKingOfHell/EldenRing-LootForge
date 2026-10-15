"""Choose one cosmetic theme from real rolled effects without consuming RNG."""

STATUS_THEMES = {6702: "frost", 6400: "blood", 6500: "poison", 6600: "rot"}
FIELD_THEMES = {
    "attackBaseFire": "fire", "attackBaseThunder": "lightning",
    "attackBaseMagic": "glintstone", "attackBaseDark": "holy",
    "defenseFire": "fire", "defenseThunder": "lightning",
    "defenseMagic": "glintstone", "defenseDark": "holy",
}


def aura_theme(affixes):
    """Status, elemental and enchanted-passive themes; mundane items stay plain."""
    for aff in affixes:
        if aff.sp_effect_id in STATUS_THEMES:
            return STATUS_THEMES[aff.sp_effect_id]
    elements = [(abs(value), FIELD_THEMES[key]) for aff in affixes
                for key, value in aff.field_modifiers.items()
                if key in FIELD_THEMES and value]
    if elements:
        return max(elements)[1]
    for aff in affixes:
        if aff.proc_kind in ("guard_heal", "hurt_heal") or "changeHpPoint" in aff.native_fields:
            return "renewal"
        if aff.proc_kind in ("attack_cast", "guard_cast", "thorns"):
            return "glintstone"
        if aff.sp_effect_id in (330000, 340120, 310100, 361100, 330700):
            return "glintstone"
        if aff.sp_effect_id in (330500, 310400, 350200):
            return "holy"
        if aff.sp_effect_id == 340220:
            return "fire"
    return ""

"""Conservative strength-based price previews; the native patcher values final PARAM fields."""
from src.diablo_affixes import RarityTier
from src.models import EquipmentSlot


class PricingEngine:
    """Price combat utility without premiums for tier, rarity labels or boss origin."""
    SLOT_BASE_VALUE = {"weapon": 1500, "body": 1200, "head": 550, "legs": 700,
                       "arms": 400, "accessory": 900}
    DEFAULT_SELL_RATIO = 0.05
    MIN_BUY_PRICE = 300
    MIN_SELL_PRICE = 10

    def __init__(self, price_multiplier=1.0, sell_ratio=DEFAULT_SELL_RATIO, scaling_enabled=True):
        self.price_multiplier = max(0.0, float(price_multiplier))
        self.sell_ratio = max(0.0, min(0.05, float(sell_ratio)))
        self.scaling_enabled = scaling_enabled

    @staticmethod
    def _normalize_slot(slot):
        if isinstance(slot, EquipmentSlot):
            slot = slot.value
        text = str(slot or "weapon").lower()
        for key, value in (("head", "head"), ("helm", "head"), ("body", "body"),
                           ("chest", "body"), ("armor", "body"), ("arm", "arms"),
                           ("gauntlet", "arms"), ("hand", "arms"), ("leg", "legs"),
                           ("boot", "legs"), ("pant", "legs"), ("acc", "accessory"),
                           ("talisman", "accessory")):
            if key in text:
                return value
        return "weapon"

    def calculate_item_power(self, slot=None, tier=None, rarity=None, affixes=None,
                             weapon_skill=None, is_weapon=False, is_accessory=False,
                             is_boss=False, field_updates=None):
        category = "weapon" if is_weapon else "accessory" if is_accessory else self._normalize_slot(slot)
        base = self.SLOT_BASE_VALUE[category]
        extra = 0.0
        for aff in affixes or []:
            for key, value in aff.field_modifiers.items():
                if key.startswith("attackBase"):
                    extra += max(0, value) * 12
                elif key.startswith("defense"):
                    extra += max(0, value) * 4
                elif key.startswith("correct"):
                    extra += max(0, value) * 2
            for key, value in aff.native_fields.items():
                extra += abs(value - 1) * 3000 if key.endswith("Rate") else abs(value) * 40
            if aff.sp_effect_id:
                extra += 250 * max(0, aff.power_scale)
            if aff.proc_kind:
                extra += 400 * max(0, aff.power_scale)
        if field_updates and not affixes:
            for key, value in field_updates.items():
                if not isinstance(value, (int, float)):
                    continue
                if key.startswith("attackBase"):
                    extra += max(0, value) * 12
                elif key.startswith("defense"):
                    extra += max(0, value) * 4
        skill = 200 if is_weapon and weapon_skill else 0
        return {"total_power": base + extra + skill, "base_slot_value": base,
                "tier_multiplier": 1.0, "rarity_multiplier": 1.0, "boss_multiplier": 1.0,
                "affix_count": len(affixes or []), "affix_power": extra, "skill_power": skill}

    def calculate_item_prices(self, slot=None, tier=None, rarity=None, affixes=None,
                              weapon_skill=None, is_weapon=False, is_accessory=False,
                              is_boss=False, field_updates=None):
        info = self.calculate_item_power(slot, tier, rarity, affixes, weapon_skill,
                                         is_weapon, is_accessory, is_boss, field_updates)
        score = info["total_power"] if self.scaling_enabled else info["base_slot_value"]
        buy = min(12000, max(self.MIN_BUY_PRICE, int(round(score * self.price_multiplier / 50) * 50)))
        sell = min(500, max(self.MIN_SELL_PRICE, int(round(buy * self.sell_ratio / 5) * 5)))
        return {"buy_price": buy, "sell_price": sell, "power_score": score, "breakdown": info}

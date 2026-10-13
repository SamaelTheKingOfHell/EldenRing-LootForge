"""
Pricing Engine for LootForge.

Calculates authentic Elden Ring rune buy prices and sell values (EquipParam sellValue,
saleValue, and ShopLineupParam value) based on item power, equipment slot, progression tier,
procedural Diablo rarity tiers, affixes, weapon skills, and boss prestige.

Adheres strictly to [CS-MODULAR], [CS-DECOUPLE], and [CS-GRANULARITY].
"""

from typing import Dict, Any, List, Optional, Union
from src.diablo_affixes import RarityTier, AffixDefinition, WeaponSkill, AffixType
from src.models import EquipmentSlot
from src.logger import system_logger


class PricingEngine:
    """
    Computes dynamic, balanced Rune buy and sell prices based on item power.
    
    Why:
        In Elden Ring, items have intrinsic worth. High-tier procedural relics,
        powerful affixes, boss remembrance armaments, and late-game gear should
        command higher purchase costs at merchants and award greater Runes when sold.
        
    Example:
    ```python
    engine = PricingEngine()
    pricing = engine.calculate_item_prices(
        slot="weapon",
        tier=3,
        rarity=RarityTier.LEGENDARY,
        affixes=rolled_affixes
    )
    print(pricing["buy_price"], pricing["sell_price"])
    ```
    """

    # Base item value by equipment slot / category
    SLOT_BASE_VALUE: Dict[str, int] = {
        "weapon": 3000,        # Primary instruments of combat and scaling
        "body": 2400,          # Chest armor provides ~45% of total protection & poise
        "head": 1600,          # Helm provides ~22% of total protection
        "legs": 1600,          # Leggings provide ~23% of total protection
        "arms": 1200,          # Gauntlets provide ~10% of total protection
        "accessory": 2500,     # Talismans grant permanent passive buffs
    }

    # Progression Tier Multipliers (Lands Between regional scaling)
    PROGRESSION_TIER_MULTIPLIERS: Dict[int, float] = {
        1: 1.0,    # Limgrave / Weeping Peninsula (Early)
        2: 1.75,   # Liurnia / Siofra River / Caelid (Mid)
        3: 2.8,    # Altus Plateau / Leyndell / Mt. Gelmir (Late)
        4: 4.2,    # Mountaintops / Haligtree / Farum Azula / Remembrances (Endgame)
    }

    # Rarity Multipliers for procedural Diablo relics
    RARITY_MULTIPLIERS: Dict[RarityTier, float] = {
        RarityTier.COMMON: 1.0,       # 0 affixes (mundane baseline)
        RarityTier.MAGIC: 1.5,        # 1 affix
        RarityTier.RARE: 2.4,         # 2 affixes
        RarityTier.LEGENDARY: 4.5,    # 3 affixes (often SpEffect passive)
        RarityTier.MYTHIC: 8.0,       # 4 affixes (double passive buffs)
    }

    # Ash of War / Weapon Skill Tier Values
    WEAPON_SKILL_TIER_VALUES: Dict[int, int] = {
        1: 1500,    # Early Ashes of War
        2: 2500,    # Mid Ashes of War
        3: 4500,    # Late Ashes of War
        4: 7500,    # Endgame / Legendary Ashes of War
    }

    DEFAULT_SELL_RATIO = 0.30     # Player receives 30% of buy price when selling
    BOSS_PRESTIGE_MULTIPLIER = 1.8  # Boss Remembrance / Trophy prestige multiplier
    MIN_BUY_PRICE = 500
    MIN_SELL_PRICE = 150

    def __init__(
        self,
        price_multiplier: float = 1.0,
        sell_ratio: float = DEFAULT_SELL_RATIO,
        scaling_enabled: bool = True
    ):
        self.price_multiplier = max(0.05, float(price_multiplier))
        self.sell_ratio = max(0.05, min(0.95, float(sell_ratio)))
        self.scaling_enabled = scaling_enabled

    @staticmethod
    def _normalize_tier(tier: Optional[Union[int, str, Any]]) -> int:
        """Converts diverse tier representations into an integer between 1 and 4."""
        if tier is None:
            return 1
        if isinstance(tier, int):
            return max(1, min(4, tier))
        
        # Check enum value or attribute
        if hasattr(tier, "value"):
            try:
                return max(1, min(4, int(tier.value)))
            except (ValueError, TypeError):
                pass

        s = str(tier).strip().lower()
        if "end" in s or "4" in s:
            return 4
        if "late" in s or "3" in s:
            return 3
        if "mid" in s or "2" in s:
            return 2
        return 1

    @staticmethod
    def _normalize_slot(slot: Optional[Union[str, EquipmentSlot]]) -> str:
        """Normalizes slot representation to lowercase canonical slot string."""
        if slot is None:
            return "weapon"
        if isinstance(slot, EquipmentSlot):
            return slot.value.lower()
        s = str(slot).strip().lower()
        if "head" in s or "helm" in s:
            return "head"
        if "body" in s or "chest" in s or "armor" in s:
            return "body"
        if "arm" in s or "gauntlet" in s or "hand" in s:
            return "arms"
        if "leg" in s or "boot" in s or "pant" in s:
            return "legs"
        if "acc" in s or "talisman" in s:
            return "accessory"
        return "weapon"

    def calculate_item_power(
        self,
        slot: Optional[Union[str, EquipmentSlot]] = None,
        tier: Optional[Union[int, str, Any]] = None,
        rarity: Optional[RarityTier] = None,
        affixes: Optional[List[AffixDefinition]] = None,
        weapon_skill: Optional[Union[WeaponSkill, Dict[str, Any], int]] = None,
        is_weapon: bool = False,
        is_accessory: bool = False,
        is_boss: bool = False,
        field_updates: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calculates an item's raw power score along with an audit breakdown.
        """
        norm_slot = "weapon" if is_weapon else ("accessory" if is_accessory else self._normalize_slot(slot))
        norm_tier = self._normalize_tier(tier)
        norm_rarity = rarity if isinstance(rarity, RarityTier) else RarityTier.COMMON

        # 1. Base slot power
        base_slot_value = self.SLOT_BASE_VALUE.get(norm_slot, 2000)

        # 2. Progression tier multiplier
        tier_mult = self.PROGRESSION_TIER_MULTIPLIERS.get(norm_tier, 1.0)

        # 3. Rarity multiplier
        rarity_mult = self.RARITY_MULTIPLIERS.get(norm_rarity, 1.0)

        # 4. Boss prestige multiplier
        boss_mult = self.BOSS_PRESTIGE_MULTIPLIER if is_boss else 1.0

        # Core scaled power
        scaled_base = base_slot_value * tier_mult * rarity_mult * boss_mult

        # 5. Affix power calculation
        affix_power = 0
        affix_count = 0
        if affixes:
            for aff in affixes:
                affix_count += 1
                # Attack bonuses
                for atk_key in ["attackBasePhysics", "attackBaseMagic", "attackBaseFire", "attackBaseThunder", "attackBaseDark"]:
                    val = aff.field_modifiers.get(atk_key, 0)
                    if val > 0:
                        affix_power += val * 40

                # Defense bonuses
                for def_key in ["defensePhysics", "defenseSlash", "defenseBlow", "defenseThrust", "defenseMagic", "defenseFire", "defenseThunder", "defenseDark"]:
                    val = aff.field_modifiers.get(def_key, 0)
                    if val > 0:
                        affix_power += val * 35

                # Poise bonus
                poise_val = aff.field_modifiers.get("toughnessCorrectRate", 0)
                if poise_val > 0:
                    affix_power += poise_val * 50

                # Stat scaling bonuses
                for stat_key in ["correctStrength", "correctAgility", "correctMagic", "correctFaith"]:
                    stat_val = aff.field_modifiers.get(stat_key, 0)
                    if stat_val > 0:
                        affix_power += stat_val * 30

                # SpEffect passive perks (e.g. Rotten Winged, Alexander Shard, HP regen, Blood loss)
                if getattr(aff, "sp_effect_id", None):
                    affix_power += 2500

                # Status / element UI effect
                if getattr(aff, "sp_effect_msg_id", None):
                    affix_power += 500

        # Also account for raw field_updates if passed directly without affixes
        if field_updates and not affixes:
            for k, v in field_updates.items():
                if isinstance(v, (int, float)):
                    if k.startswith("attackBase") and v > 0:
                        affix_power += int(v * 40)
                    elif k.startswith("defense") and v > 0:
                        affix_power += int(v * 35)
                    elif k.startswith("residentSpEffectId") and v > 0:
                        affix_power += 2500

        # 6. Weapon skill / Ash of War power
        skill_power = 0
        if is_weapon and weapon_skill:
            skill_tier = 2
            if isinstance(weapon_skill, WeaponSkill):
                skill_tier = weapon_skill.tier.value if hasattr(weapon_skill.tier, "value") else int(weapon_skill.tier)
            elif isinstance(weapon_skill, dict):
                skill_tier = int(weapon_skill.get("tier", 2))
            skill_power = self.WEAPON_SKILL_TIER_VALUES.get(skill_tier, 2500)

        total_power = scaled_base + affix_power + skill_power

        return {
            "total_power": total_power,
            "base_slot_value": base_slot_value,
            "tier": norm_tier,
            "tier_multiplier": tier_mult,
            "rarity": norm_rarity.name,
            "rarity_multiplier": rarity_mult,
            "boss_multiplier": boss_mult,
            "affix_count": affix_count,
            "affix_power": affix_power,
            "skill_power": skill_power
        }

    def calculate_item_prices(
        self,
        slot: Optional[Union[str, EquipmentSlot]] = None,
        tier: Optional[Union[int, str, Any]] = None,
        rarity: Optional[RarityTier] = None,
        affixes: Optional[List[AffixDefinition]] = None,
        weapon_skill: Optional[Union[WeaponSkill, Dict[str, Any], int]] = None,
        is_weapon: bool = False,
        is_accessory: bool = False,
        is_boss: bool = False,
        field_updates: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calculates the buy price (ShopLineupParam / saleValue) and sell price (sellValue)
        for an item based on its power.
        
        Returns:
            Dict containing 'buy_price', 'sell_price', 'power_score', and 'breakdown'.
        """
        if not self.scaling_enabled:
            # Flat default baseline when scaling is disabled
            default_buy = 3000 if is_weapon else (2500 if is_accessory else 1500)
            default_sell = int(default_buy * self.sell_ratio)
            return {
                "buy_price": default_buy,
                "sell_price": default_sell,
                "power_score": default_buy,
                "breakdown": {}
            }

        power_info = self.calculate_item_power(
            slot=slot,
            tier=tier,
            rarity=rarity,
            affixes=affixes,
            weapon_skill=weapon_skill,
            is_weapon=is_weapon,
            is_accessory=is_accessory,
            is_boss=is_boss,
            field_updates=field_updates
        )

        raw_buy = power_info["total_power"] * self.price_multiplier

        # Round buy price to authentic Elden Ring amounts
        if raw_buy < 5000:
            buy_price = int(round(raw_buy / 50.0) * 50)
        elif raw_buy < 20000:
            buy_price = int(round(raw_buy / 100.0) * 100)
        elif raw_buy < 100000:
            buy_price = int(round(raw_buy / 500.0) * 500)
        else:
            buy_price = int(round(raw_buy / 1000.0) * 1000)

        buy_price = max(self.MIN_BUY_PRICE, buy_price)

        # Calculate sell price
        raw_sell = buy_price * self.sell_ratio
        if raw_sell < 2000:
            sell_price = int(round(raw_sell / 10.0) * 10)
        elif raw_sell < 10000:
            sell_price = int(round(raw_sell / 50.0) * 50)
        else:
            sell_price = int(round(raw_sell / 100.0) * 100)

        sell_price = max(self.MIN_SELL_PRICE, sell_price)

        return {
            "buy_price": buy_price,
            "sell_price": sell_price,
            "power_score": power_info["total_power"],
            "breakdown": power_info
        }

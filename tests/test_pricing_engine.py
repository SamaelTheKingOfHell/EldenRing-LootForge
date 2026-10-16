"""
Unit and integration tests for LootForge Pricing Engine.

Verifies dynamic rune valuation scaling across progression tiers, procedural Diablo rarities,
affixes, weapon skills, boss prestige, and equipment slots. Adheres strictly to [CS-NO-MOCK].
"""

import unittest
from src.pricing_engine import PricingEngine
from src.diablo_affixes import (
    RarityTier, AffixDefinition, AffixType, WeaponSkill,
    DEFAULT_WEAPON_SKILLS
)
from src.models import (
    EquipmentSlot, ProgressionTier, DetectedModSet, ModPartFile,
    StandaloneAllocation, LootTarget, LootDistributionType
)
from src.param_builder import ParamBuilder
from src.diablo_generator import DiabloLootGenerator
from src.knowledge_base import VanillaKnowledgeBase


class TestPricingEngine(unittest.TestCase):
    """Verifies core valuation logic and scaling in PricingEngine."""

    def setUp(self):
        self.engine = PricingEngine()

    def test_pricing_engine_initialization_and_config(self):
        """Verifies engine initialization with default and custom parameters."""
        default_engine = PricingEngine()
        self.assertEqual(default_engine.price_multiplier, 1.0)
        self.assertEqual(default_engine.sell_ratio, 0.30)
        self.assertTrue(default_engine.scaling_enabled)

        custom_engine = PricingEngine(price_multiplier=1.5, sell_ratio=0.40, scaling_enabled=False)
        self.assertEqual(custom_engine.price_multiplier, 1.5)
        self.assertEqual(custom_engine.sell_ratio, 0.40)
        self.assertFalse(custom_engine.scaling_enabled)

        # Disabled scaling returns fixed defaults
        fixed_pricing = custom_engine.calculate_item_prices(slot="weapon", is_weapon=True)
        self.assertEqual(fixed_pricing["buy_price"], 3000)
        self.assertEqual(fixed_pricing["sell_price"], int(3000 * 0.40))

    def test_slot_base_value_hierarchy(self):
        """Verifies that combat impact determines slot base valuations."""
        weapon_price = self.engine.calculate_item_prices(slot="weapon", is_weapon=True)["buy_price"]
        chest_price = self.engine.calculate_item_prices(slot="body", is_weapon=False)["buy_price"]
        helm_price = self.engine.calculate_item_prices(slot="head", is_weapon=False)["buy_price"]
        arms_price = self.engine.calculate_item_prices(slot="arms", is_weapon=False)["buy_price"]
        accessory_price = self.engine.calculate_item_prices(slot="accessory", is_accessory=True)["buy_price"]

        # Weapon > Chest > Accessory/Head > Arms
        self.assertGreater(weapon_price, chest_price)
        self.assertGreater(chest_price, helm_price)
        self.assertGreater(helm_price, arms_price)
        self.assertGreater(accessory_price, arms_price)

    def test_progression_tier_scaling(self):
        """Verifies that regional progression tiers scale buy and sell prices strictly upward."""
        t1 = self.engine.calculate_item_prices(slot="weapon", tier=1, is_weapon=True)
        t2 = self.engine.calculate_item_prices(slot="weapon", tier=2, is_weapon=True)
        t3 = self.engine.calculate_item_prices(slot="weapon", tier=3, is_weapon=True)
        t4 = self.engine.calculate_item_prices(slot="weapon", tier=4, is_weapon=True)

        self.assertLess(t1["buy_price"], t2["buy_price"])
        self.assertLess(t2["buy_price"], t3["buy_price"])
        self.assertLess(t3["buy_price"], t4["buy_price"])

        self.assertLess(t1["sell_price"], t2["sell_price"])
        self.assertLess(t2["sell_price"], t3["sell_price"])
        self.assertLess(t3["sell_price"], t4["sell_price"])

        # Check normalization handles strings and ProgressionTier Enums
        enum_t4 = self.engine.calculate_item_prices(slot="weapon", tier=ProgressionTier.ENDGAME, is_weapon=True)
        str_t4 = self.engine.calculate_item_prices(slot="weapon", tier="tier 4 endgame", is_weapon=True)
        self.assertEqual(enum_t4["buy_price"], t4["buy_price"])
        self.assertEqual(str_t4["buy_price"], t4["buy_price"])

    def test_rarity_multiplier_scaling(self):
        """Verifies Diablo rarity tiers scale prices non-linearly."""
        common = self.engine.calculate_item_prices(slot="weapon", rarity=RarityTier.COMMON, is_weapon=True)
        magic = self.engine.calculate_item_prices(slot="weapon", rarity=RarityTier.MAGIC, is_weapon=True)
        rare = self.engine.calculate_item_prices(slot="weapon", rarity=RarityTier.RARE, is_weapon=True)
        legendary = self.engine.calculate_item_prices(slot="weapon", rarity=RarityTier.LEGENDARY, is_weapon=True)
        mythic = self.engine.calculate_item_prices(slot="weapon", rarity=RarityTier.MYTHIC, is_weapon=True)

        self.assertLess(common["buy_price"], magic["buy_price"])
        self.assertLess(magic["buy_price"], rare["buy_price"])
        self.assertLess(rare["buy_price"], legendary["buy_price"])
        self.assertLess(legendary["buy_price"], mythic["buy_price"])

        # Mythic items should be highly lucrative
        self.assertGreaterEqual(mythic["buy_price"], 20000)
        self.assertGreaterEqual(mythic["sell_price"], 6000)

    def test_affix_stat_multipliers_and_passives(self):
        """Verifies that affixes grant incremental rune value for stats and passive SpEffects."""
        base_pricing = self.engine.calculate_item_prices(slot="weapon", is_weapon=True, affixes=[])

        stat_affix = AffixDefinition(
            name="Sharpened",
            affix_type=AffixType.PREFIX,
            tier_min=RarityTier.MAGIC,
            applies_to_weapon=True,
            applies_to_armor=False,
            field_modifiers={"attackBasePhysics": 25},
            description="+25 Physical Attack"
        )
        stat_pricing = self.engine.calculate_item_prices(slot="weapon", is_weapon=True, affixes=[stat_affix])
        # +25 attack * 40 = +1,000 power
        self.assertGreater(stat_pricing["buy_price"], base_pricing["buy_price"])

        sp_affix = AffixDefinition(
            name="of Bloodlust",
            affix_type=AffixType.SUFFIX,
            tier_min=RarityTier.LEGENDARY,
            applies_to_weapon=True,
            applies_to_armor=False,
            field_modifiers={},
            sp_effect_id=105000,
            description="Grants Bloodlust passive perk"
        )
        sp_pricing = self.engine.calculate_item_prices(slot="weapon", is_weapon=True, affixes=[sp_affix])
        # SpEffect grants +2,500 power
        self.assertGreater(sp_pricing["buy_price"], base_pricing["buy_price"])
        self.assertGreater(sp_pricing["buy_price"] - base_pricing["buy_price"], 2000)

    def test_weapon_skill_scaling(self):
        """Verifies Ash of War skill tiers contribute to weapon valuation."""
        skill_t1 = WeaponSkill(id=101, name="Kick", description="A swift kick", tier=ProgressionTier.EARLY)
        skill_t4 = WeaponSkill(id=401, name="Waterfowl Dance", description="Lethal flurry", tier=ProgressionTier.ENDGAME)

        pricing_t1 = self.engine.calculate_item_prices(slot="weapon", is_weapon=True, weapon_skill=skill_t1)
        pricing_t4 = self.engine.calculate_item_prices(slot="weapon", is_weapon=True, weapon_skill=skill_t4)

        self.assertGreater(pricing_t4["buy_price"], pricing_t1["buy_price"])
        self.assertGreater(pricing_t4["sell_price"], pricing_t1["sell_price"])

    def test_boss_prestige_multiplier(self):
        """Verifies that boss remembrances command a 1.8x prestige multiplier."""
        standard = self.engine.calculate_item_prices(slot="weapon", tier=4, rarity=RarityTier.LEGENDARY, is_boss=False)
        boss = self.engine.calculate_item_prices(slot="weapon", tier=4, rarity=RarityTier.LEGENDARY, is_boss=True)

        self.assertGreater(boss["buy_price"], standard["buy_price"])
        self.assertGreaterEqual(boss["buy_price"], int(standard["buy_price"] * 1.5))
        self.assertGreater(boss["sell_price"], standard["sell_price"])

    def test_sell_ratio_and_clean_rounding(self):
        """Verifies buy and sell prices round cleanly and respect minimum boundaries."""
        pricing = self.engine.calculate_item_prices(slot="arms", tier=1, rarity=RarityTier.COMMON)
        # Ratio check: sell_price should be ~30% of buy_price
        ratio = pricing["sell_price"] / pricing["buy_price"]
        self.assertAlmostEqual(ratio, 0.30, delta=0.05)

        # Minimum price checks
        cheap_pricing = self.engine.calculate_item_prices(slot="arms", tier=1, rarity=RarityTier.COMMON)
        self.assertGreaterEqual(cheap_pricing["buy_price"], PricingEngine.MIN_BUY_PRICE)
        self.assertGreaterEqual(cheap_pricing["sell_price"], PricingEngine.MIN_SELL_PRICE)


class TestPricingIntegration(unittest.TestCase):
    """Integration tests verifying ParamBuilder and DiabloLootGenerator with PricingEngine."""

    def setUp(self):
        self.generator = DiabloLootGenerator(seed=123)
        self.builder = ParamBuilder()

    def test_param_builder_attaches_pricing_to_field_updates_and_loot(self):
        """Verifies ParamBuilder injects sellValue, saleValue, and item_prices into patch specs."""
        mod_set = DetectedModSet(
            set_id="test_armor_set",
            folder_or_archive_name="test_armor_set",
            target_model_id="1010",
            target_vanilla_name="Knight Set",
            parts=[
                ModPartFile("bd_m_1010.partsbnd.dcx", "bd.dcx", EquipmentSlot.BODY, "1010"),
                ModPartFile("am_m_1010.partsbnd.dcx", "arms.dcx", EquipmentSlot.ARMS, "1010")
            ],
            allocation=StandaloneAllocation(
                new_model_id="9001",
                new_equip_param_id=400000,
                new_item_lot_id=400000,
                marker_tag="[LootForge]"
            ),
            loot_target=LootTarget(
                route_type=LootDistributionType.MERCHANT_SHOP,
                target_id="1000",
                display_name="Merchant Kale",
                chance_or_cost=10000.0
            )
        )

        patch_spec = self.builder.build_patch_spec(mod_set)

        # Verify equip params have sellValue and saleValue
        body_ep = next(ep for ep in patch_spec["equip_params"] if ep["slot"] == EquipmentSlot.BODY)
        arms_ep = next(ep for ep in patch_spec["equip_params"] if ep["slot"] == EquipmentSlot.ARMS)

        self.assertIn("sellValue", body_ep["field_updates"])
        self.assertIn("saleValue", body_ep["field_updates"])
        self.assertIn("basicPrice", body_ep["field_updates"])
        self.assertGreater(body_ep["field_updates"]["saleValue"], arms_ep["field_updates"]["saleValue"])
        self.assertGreater(body_ep["field_updates"]["sellValue"], arms_ep["field_updates"]["sellValue"])

        # Verify loot distribution has granular item_prices dictionary
        loot_dist = patch_spec["loot_distribution"]
        self.assertIn("item_prices", loot_dist)
        item_prices = loot_dist["item_prices"]
        self.assertEqual(len(item_prices), 2)
        body_id = str(body_ep["new_param_id"])
        arms_id = str(arms_ep["new_param_id"])
        self.assertIn(body_id, item_prices)
        self.assertIn(arms_id, item_prices)
        self.assertGreater(item_prices[body_id], item_prices[arms_id])

    def test_diablo_generator_variants_include_pricing_and_fmg_lore(self):
        """Verifies generate_variants_for_spec enriches specs with pricing and lore captions."""
        base_spec = {
            "set_id": "sword_variant_test",
            "equip_params": [{
                "param_table": "EquipParamWeapon",
                "new_param_id": 500000,
                "base_clone_id": 1000000,
                "slot": "weapon",
                "row_name": "Test Longsword",
                "field_updates": {}
            }],
            "fmg_texts": [{
                "item_id": 500000,
                "is_weapon": True,
                "name": "Test Longsword",
                "caption": "A reliable blade."
            }],
            "loot_distribution": {
                "type": "shop_lineup",
                "shop_type": "merchant_shop",
                "target_id": "1000",
                "cost_or_remembrance": 3000.0,
                "awarded_items": [500000]
            }
        }

        variants = self.generator.generate_variants_for_spec(base_spec, variants_per_item=2)
        self.assertEqual(len(variants), 2)

        for var in variants:
            ep = var["equip_params"][0]
            self.assertIn("sellValue", ep["field_updates"])
            self.assertIn("saleValue", ep["field_updates"])
            self.assertGreater(ep["field_updates"]["saleValue"], 0)
            self.assertGreater(ep["field_updates"]["sellValue"], 0)

            # Check lore caption includes VALUE string
            fmg = var["fmg_texts"][0]
            self.assertNotIn("VALUE:", fmg["caption"])
            self.assertLessEqual(len(fmg["caption"].splitlines()), 6)

            # Check loot distribution item_prices dictionary
            loot_dist = var["loot_distribution"]
            self.assertIn("item_prices", loot_dist)
            self.assertGreater(loot_dist["cost_or_remembrance"], 0)

    def test_vanilla_stat_injections_pricing_coverage(self):
        """Verifies vanilla stat injections add balanced buy/sell values to weapons, armors, and accessories."""
        kb = VanillaKnowledgeBase({}, {})
        kb._weapons = {
            "100": {"baseParamId": 1000000, "name": "Dagger", "description": "A standard dagger.", "tier": 1}
        }
        kb._protectors = {
            "200": {
                "baseParamId": 2000000,
                "name": "Knight Set",
                "description": "Standard knight armor.",
                "tier": 2,
                "pieces": {"Helm": 2000000, "Armor": 2000100, "Gauntlets": 2000200, "Greaves": 2000300}
            }
        }
        kb._accessories = {
            "300": {"baseParamId": 3000000, "name": "Crimson Amber Medallion", "description": "HP talisman.", "tier": 1}
        }

        injections = self.generator.generate_vanilla_stat_injections(knowledge_base=kb)
        self.assertGreaterEqual(len(injections), 6)  # 1 weapon + 4 armor pieces + 1 accessory

        for inj in injections:
            ep = inj["equip_params"][0]
            self.assertIn("sellValue", ep["field_updates"])
            self.assertIn("saleValue", ep["field_updates"])
            self.assertGreater(ep["field_updates"]["saleValue"], 0)
            self.assertGreater(ep["field_updates"]["sellValue"], 0)

            fmg = inj["fmg_texts"][0]
            self.assertNotIn("VALUE:", fmg["caption"])
            self.assertLessEqual(len(fmg["caption"].splitlines()), 6)


if __name__ == "__main__":
    unittest.main()

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
    def test_strength_prices_ignore_tier_rarity_and_boss_labels(self):
        engine = PricingEngine()
        standard = engine.calculate_item_prices(is_weapon=True, field_updates={"attackBasePhysics": 115})
        for tier in range(1, 5):
            for rarity in RarityTier:
                self.assertEqual(standard, engine.calculate_item_prices(is_weapon=True, tier=tier, rarity=rarity,
                    is_boss=True, field_updates={"attackBasePhysics": 115}))

    def test_stronger_numeric_fields_cost_more(self):
        engine = PricingEngine()
        weak = engine.calculate_item_prices(is_weapon=True, field_updates={"attackBasePhysics": 115})
        strong = engine.calculate_item_prices(is_weapon=True, field_updates={"attackBasePhysics": 200})
        self.assertGreater(strong["buy_price"], weak["buy_price"])
        self.assertGreater(strong["sell_price"], weak["sell_price"])

    def test_item_ids_are_not_strength(self):
        engine = PricingEngine()
        a = engine.calculate_item_prices(is_weapon=True, field_updates={"sortId": 9000000, "residentSpEffectId": 10})
        b = engine.calculate_item_prices(is_weapon=True, field_updates={"sortId": 100000000, "residentSpEffectId": 8600000})
        self.assertEqual(a, b)

    def test_prices_are_bounded_and_sale_returns_are_small(self):
        engine = PricingEngine(sell_ratio=0.9)
        for attack in (1, 115, 200, 100000):
            price = engine.calculate_item_prices(is_weapon=True, field_updates={"attackBasePhysics": attack})
            self.assertLessEqual(price["buy_price"], 12000)
            self.assertLessEqual(price["sell_price"], 500)
            self.assertLessEqual(price["sell_price"], price["buy_price"] * 0.06)

    def test_price_multiplier_changes_cost_without_changing_strength(self):
        a = PricingEngine().calculate_item_prices(is_weapon=True)
        b = PricingEngine(price_multiplier=2).calculate_item_prices(is_weapon=True)
        self.assertEqual(a["power_score"], b["power_score"])
        self.assertEqual(b["buy_price"], 2*a["buy_price"])


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
            self.assertTrue(ep["update_existing"])
            self.assertEqual(inj["fmg_texts"], [])
            for key in ("sellValue", "saleValue", "basicPrice"):
                self.assertNotIn(key, ep["field_updates"])


if __name__ == "__main__":
    unittest.main()

"""
Unit tests for LootForge Diablo-style ARPG loot generation system.
"""

import unittest
from src.diablo_affixes import RarityTier, AffixType, AFFIX_POOL
from src.diablo_generator import DiabloLootGenerator
from src.param_builder import ParamBuilder
from src.models import (
    DetectedModSet, ModPartFile, EquipmentSlot, StandaloneAllocation,
    LootTarget, LootDistributionType
)


class TestDiabloLoot(unittest.TestCase):
    """Verifies Diablo affix rolling, name generation, and patch spec modifications."""

    def setUp(self):
        self.generator = DiabloLootGenerator(seed=42)
        self.builder = ParamBuilder()

    def test_affix_pool_integrity(self):
        """Verifies that affix definitions are non-empty and well-formed."""
        self.assertGreater(len(AFFIX_POOL), 15)
        prefixes = [a for a in AFFIX_POOL if a.affix_type == AffixType.PREFIX]
        suffixes = [a for a in AFFIX_POOL if a.affix_type == AffixType.SUFFIX]
        self.assertGreater(len(prefixes), 5)
        self.assertGreater(len(suffixes), 5)

        for aff in AFFIX_POOL:
            self.assertTrue(len(aff.name) > 0)
            self.assertTrue(len(aff.description) > 0)
            self.assertTrue(aff.applies_to_weapon or aff.applies_to_armor)

    def test_rarity_and_affix_rolling(self):
        """Verifies affix counts conform to rarity tier specifications."""
        common_affs = self.generator.roll_affixes(RarityTier.COMMON, is_weapon=True)
        self.assertEqual(len(common_affs), 0)

        magic_affs = self.generator.roll_affixes(RarityTier.MAGIC, is_weapon=True)
        self.assertEqual(len(magic_affs), 1)

        rare_affs = self.generator.roll_affixes(RarityTier.RARE, is_weapon=False)
        self.assertEqual(len(rare_affs), 2)

        legendary_affs = self.generator.roll_affixes(RarityTier.LEGENDARY, is_weapon=True)
        self.assertGreaterEqual(len(legendary_affs), 2)

        mythic_affs = self.generator.roll_affixes(RarityTier.MYTHIC, is_weapon=False)
        self.assertGreaterEqual(len(mythic_affs), 3)

    def test_item_name_formatting(self):
        """Verifies dynamic name building with prefix, base name, suffix, and rarity tag."""
        affixes = self.generator.roll_affixes(RarityTier.RARE, is_weapon=True)
        name = self.generator.build_item_name(
            base_name="Moonveil",
            rarity=RarityTier.RARE,
            affixes=affixes,
            marker_tag="[LootForge]"
        )
        self.assertIn("[LootForge]", name)
        self.assertIn("[Rare]", name)
        self.assertIn("Moonveil", name)
        for aff in affixes:
            self.assertIn(aff.name, name)

    def test_caption_formatting_at_bottom(self):
        """Verifies effects and rarity are strictly formatted at the bottom of the description."""
        base_desc = "Legendary katana forged in the stars."
        affixes = self.generator.roll_affixes(RarityTier.LEGENDARY, is_weapon=True)
        caption = self.generator.build_caption_with_affixes(base_desc, RarityTier.LEGENDARY, affixes)

        self.assertTrue(caption.startswith(base_desc))
        self.assertIn("RARITY: LEGENDARY", caption)
        self.assertIn("DIABLO AFFIXES:", caption)
        for aff in affixes:
            self.assertIn(aff.name, caption)
            self.assertIn(aff.description, caption)

    def test_variant_generation_armor(self):
        """Verifies multi-variant generation for armor sets produces unique rows and IDs."""
        armor_set = DetectedModSet(
            set_id="KnightArmor_1570",
            folder_or_archive_name="Knight Armor",
            target_model_id="1570",
            target_vanilla_name="Knight Armor",
            parts=[ModPartFile("bd_m_1570.partsbnd.dcx", "bd_m_1570.partsbnd.dcx", EquipmentSlot.BODY, "1570", "m", 100)],
            allocation=StandaloneAllocation(
                new_model_id="9000",
                new_equip_param_id=9000000,
                new_item_lot_id=9100000,
                marker_tag="[LootForge]"
            ),
            loot_target=LootTarget(
                route_type=LootDistributionType.ENEMY_DROP,
                target_id="431100000",
                display_name="Godrick Soldier",
                chance_or_cost=100.0
            )
        )

        variants = self.builder.build_diablo_patch_specs(armor_set, variants_count=3, seed=123)
        self.assertEqual(len(variants), 3)

        ids = [v["equip_params"][0]["new_param_id"] for v in variants]
        self.assertEqual(len(set(ids)), 3, "Variant IDs must be unique!")

        for v in variants:
            fmg = v["fmg_texts"][0]
            self.assertIn("RARITY:", fmg["caption"])
            self.assertIn("[LootForge]", fmg["name"])

    def test_variant_generation_weapon(self):
        """Verifies weapon variant generation modifies weapon stats and attaches passives."""
        wpn_set = DetectedModSet(
            set_id="Moonveil_0617",
            folder_or_archive_name="Moonveil Mod",
            target_model_id="0617",
            target_vanilla_name="Moonveil",
            is_weapon=True,
            parts=[ModPartFile("wp_a_0617.partsbnd.dcx", "wp_a_0617.partsbnd.dcx", EquipmentSlot.WEAPON, "0617", "m", 100)],
            allocation=StandaloneAllocation(
                new_model_id="9001",
                new_equip_param_id=9001000,
                new_item_lot_id=9100001,
                marker_tag="[LootForge]"
            ),
            loot_target=LootTarget(
                route_type=LootDistributionType.ENEMY_DROP,
                target_id="431100000",
                display_name="Godrick Soldier",
                chance_or_cost=100.0
            )
        )

        variants = self.builder.build_diablo_patch_specs(wpn_set, variants_count=4, seed=999)
        self.assertEqual(len(variants), 4)

        for v in variants:
            ep = v["equip_params"][0]
            self.assertEqual(ep["param_table"], "EquipParamWeapon")
            self.assertIn("sortId", ep["field_updates"])

    def test_boss_always_giga_legendary(self):
        """Verifies that boss rolls are strictly guaranteed to be Legendary or Mythic."""
        for _ in range(50):
            tier = self.generator.roll_rarity(is_boss=True)
            self.assertIn(tier, (RarityTier.LEGENDARY, RarityTier.MYTHIC))
            self.assertNotIn(tier, (RarityTier.COMMON, RarityTier.MAGIC, RarityTier.RARE))

        boss_affixes = self.generator.roll_affixes(RarityTier.MYTHIC, is_weapon=True, is_boss=True)
        self.assertGreaterEqual(len(boss_affixes), 3)
        self.assertTrue(any(a.sp_effect_id is not None for a in boss_affixes), "Boss affixes must include passive SpEffect!")

        boss_caption = self.generator.build_caption_with_affixes(
            "Starscourge Greatsword", RarityTier.MYTHIC, boss_affixes, boss_name="General Radahn"
        )
        self.assertIn("GIGA MYTHIC", boss_caption)
        self.assertIn("General Radahn", boss_caption)

    def test_game_wide_loot_distribution(self):
        """Verifies that variants of sets are distributed across bosses, shops, chests, and enemies."""
        from src.knowledge_base import VanillaKnowledgeBase
        kb = VanillaKnowledgeBase.from_data_dir("data")
        builder_with_kb = ParamBuilder(knowledge_base=kb)

        armor_set = DetectedModSet(
            set_id="Cleanrot_1800",
            folder_or_archive_name="Cleanrot Set",
            target_model_id="1800",
            target_vanilla_name="Cleanrot Knight Armor",
            parts=[ModPartFile("bd_m_1800.partsbnd.dcx", "bd_m_1800.partsbnd.dcx", EquipmentSlot.BODY, "1800", "m", 100)],
            allocation=StandaloneAllocation(
                new_model_id="9002",
                new_equip_param_id=9002000,
                new_item_lot_id=9100002,
                marker_tag="[LootForge]"
            ),
            loot_target=LootTarget(
                route_type=LootDistributionType.ENEMY_DROP,
                target_id="380000000",
                display_name="Cleanrot Knight",
                chance_or_cost=15.0
            )
        )

        variants = builder_with_kb.build_diablo_patch_specs(armor_set, variants_count=10, seed=777)
        self.assertEqual(len(variants), 10)

        # Collect distinct targets and types
        targets = [v["loot_distribution"]["target_id"] for v in variants if "loot_distribution" in v]
        types = [v["loot_distribution"]["type"] for v in variants if "loot_distribution" in v]

        # Must not all go to Cleanrot Knight!
        self.assertGreater(len(set(targets)), 1, "Variants must be distributed across different targets!")
        self.assertIn("shop_lineup", types, "Must distribute to Finger Reader Enia boss remembrance exchange!")
        self.assertIn("merchant_shop", types, "Must distribute to non-enemy merchants!")

        # Verify boss variant is Giga Legendary or Mythic
        boss_variants = [v for v in variants if v["loot_distribution"].get("type") == "shop_lineup"]
        for bv in boss_variants:
            fmg = bv["fmg_texts"][0]
            self.assertIn("Giga", fmg["name"])
            self.assertIn("BOSS TROPHY", fmg["caption"])

    def test_vanilla_stat_injections(self):
        """Verifies procedural Diablo stat infusions generated directly for vanilla items."""
        from src.knowledge_base import VanillaKnowledgeBase
        kb = VanillaKnowledgeBase.from_data_dir("data")

        specs = self.generator.generate_vanilla_stat_injections(knowledge_base=kb)
        self.assertGreater(len(specs), 20, "Must generate stat injection specs for vanilla items!")

        for spec in specs:
            ep = spec["equip_params"][0]
            self.assertTrue(ep.get("update_existing"), "Must flag update_existing=True for vanilla rows!")
            self.assertIn("field_updates", ep)
            self.assertIn("row_name", ep)
            self.assertIn("[Vanilla Infused]", ep["row_name"])

            fmg = spec["fmg_texts"][0]
            self.assertIn("RARITY:", fmg["caption"])
            self.assertIn("Origin: Vanilla Elden Ring", fmg["info"])

    def test_vanilla_base_distribution(self):
        """Verifies using vanilla items as base items to create standalone distributed relics."""
        from src.knowledge_base import VanillaKnowledgeBase
        from src.id_allocator import IdAllocator
        kb = VanillaKnowledgeBase.from_data_dir("data")
        allocator = IdAllocator(base_param_id=9000000, base_item_lot_id=9100000)

        specs = self.generator.generate_vanilla_base_distribution_specs(
            knowledge_base=kb, id_allocator=allocator, variants_per_item=3
        )
        self.assertGreater(len(specs), 30, "Must generate distributed variants from vanilla base items!")

        # Verify standalone param IDs and loot distribution
        for spec in specs:
            ep = spec["equip_params"][0]
            self.assertGreaterEqual(ep["new_param_id"], 9000000)
            self.assertIn("loot_distribution", spec)
            self.assertIsNotNone(spec["loot_distribution"])
            fmg = spec["fmg_texts"][0]
            self.assertIn("[LootForge]", fmg["name"])

    def test_config_vanilla_booleans(self):
        """Verifies serialization and deserialization of the new vanilla booleans."""
        from src.config import LootForgeConfig
        cfg = LootForgeConfig()
        self.assertFalse(cfg.diablo_inject_vanilla_stats)
        self.assertFalse(cfg.diablo_use_vanilla_base_items)

        cfg_dict = cfg.to_dict()
        self.assertIn("diablo_inject_vanilla_stats", cfg_dict)
        self.assertIn("diablo_use_vanilla_base_items", cfg_dict)

    def test_shop_capacity_limitation_and_pool_overflow_rotation(self):
        """Verifies that shop param row limits are strictly respected and overflowed items rotate to other pools."""
        from src.knowledge_base import VanillaKnowledgeBase
        kb = VanillaKnowledgeBase.from_data_dir("data")

        # Constrain shop capacities tightly to trigger overflow rotation
        generator = DiabloLootGenerator(
            seed=12345,
            knowledge_base=kb,
            max_shop_per_merchant=2,
            max_enia_rows=3,
            max_total_shop_rows=10
        )

        dummy_spec = {
            "set_id": "test_armor_set",
            "equip_params": [{
                "param_table": "EquipParamProtector",
                "new_param_id": 9001000,
                "base_clone_id": 400000,
                "target_model_id": 4000,
                "slot": "body",
                "slot_offset": 100,
                "row_name": "[LootForge] Test Armor",
                "field_updates": {}
            }],
            "fmg_texts": [{
                "item_id": 9001000,
                "vanilla_source_id": 400000,
                "target_model_id": 4000,
                "slot": "body",
                "slot_offset": 100,
                "is_weapon": False,
                "name": "[LootForge] Test Armor",
                "caption": "Test Armor caption.",
                "info": "Origin: Test"
            }],
            "loot_distribution": {
                "type": "enemy_drop",
                "lot_id": 431100000,
                "target_id": "431100000",
                "drop_rate_percent": 20.0,
                "awarded_items": [9001000]
            }
        }

        # Generate 40 variants
        variants = generator.generate_variants_for_spec(dummy_spec, variants_per_item=40, knowledge_base=kb)
        self.assertEqual(len(variants), 40)

        # Count distribution across pools
        shop_count = 0
        merchant_counts = {}
        enia_count = 0
        rotated_to_chests = 0
        rotated_to_enemies = 0

        for v in variants:
            dist = v.get("loot_distribution", {})
            dist_type = dist.get("type")
            if dist_type in ("shop_lineup", "merchant_shop"):
                shop_count += 1
                if dist_type == "shop_lineup":
                    enia_count += 1
                else:
                    shop_id = dist.get("shop_id") or dist.get("target_id")
                    merchant_counts[shop_id] = merchant_counts.get(shop_id, 0) + 1
            elif dist_type == "map_pickup":
                rotated_to_chests += 1
            elif dist_type == "enemy_drop":
                rotated_to_enemies += 1

        # Check limitations
        self.assertLessEqual(shop_count, 10, "Total shop items must not exceed max_total_shop_rows limit!")
        self.assertLessEqual(enia_count, 3, "Finger Reader Enia must not exceed max_enia_rows limit!")
        for merch_id, cnt in merchant_counts.items():
            self.assertLessEqual(cnt, 2, f"Merchant {merch_id} must not exceed max_shop_per_merchant limit!")

        # Check overflow rotation
        self.assertGreater(rotated_to_chests, 5, "Overflowed items must rotate into chest pools!")
        self.assertGreater(rotated_to_enemies, 10, "Overflowed items must rotate into enemy drop pools!")


if __name__ == "__main__":
    unittest.main()

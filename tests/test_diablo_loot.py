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


if __name__ == "__main__":
    unittest.main()

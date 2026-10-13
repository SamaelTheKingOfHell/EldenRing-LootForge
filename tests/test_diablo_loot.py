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
            self.assertTrue(aff.applies_to_weapon or aff.applies_to_armor or getattr(aff, "applies_to_accessory", False))

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
        self.assertFalse(cfg.diablo_randomize_weapon_skills)

        cfg_dict = cfg.to_dict()
        self.assertIn("diablo_inject_vanilla_stats", cfg_dict)
        self.assertIn("diablo_use_vanilla_base_items", cfg_dict)
        self.assertIn("diablo_randomize_weapon_skills", cfg_dict)

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

    def test_weapon_skill_pool_integrity(self):
        """Verifies that weapon skill pool is populated with authentic valid skills."""
        from src.diablo_affixes import WEAPON_SKILL_POOL, WeaponSkill
        self.assertGreater(len(WEAPON_SKILL_POOL), 50, "Weapon skill pool must have substantial skills!")
        # Ensure No Skill (10) is excluded from random weapon rolls
        skill_ids = [s.id for s in WEAPON_SKILL_POOL]
        self.assertNotIn(10, skill_ids, "'No Skill' (10) should not be in the active randomization pool!")
        for s in WEAPON_SKILL_POOL:
            self.assertIsInstance(s.id, int)
            self.assertGreater(s.id, 0)
            self.assertTrue(len(s.name) > 0)
            self.assertFalse(s.name.startswith("%"))

    def test_weapon_skill_rolling(self):
        """Verifies roll_weapon_skill produces valid skills."""
        skill = self.generator.roll_weapon_skill()
        self.assertIsNotNone(skill)
        self.assertGreater(skill.id, 0)
        self.assertTrue(len(skill.name) > 0)

    def test_weapon_skill_randomization_enabled(self):
        """Verifies that weapons receive randomized swordArtsParamId when randomize_weapon_skills=True."""
        generator_with_skills = DiabloLootGenerator(seed=101, randomize_weapon_skills=True)

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

        base_spec = self.builder.build_patch_spec(wpn_set)
        variants = generator_with_skills.generate_variants_for_spec(base_spec, variants_per_item=3)
        self.assertEqual(len(variants), 3)

        for v in variants:
            ep = v["equip_params"][0]
            self.assertEqual(ep["param_table"], "EquipParamWeapon")
            self.assertIn("swordArtsParamId", ep["field_updates"], "Weapons must have swordArtsParamId randomized!")
            skill_id = ep["field_updates"]["swordArtsParamId"]
            self.assertGreater(skill_id, 0)
            # Verify caption mentions skill
            fmg = v["fmg_texts"][0]
            self.assertIn("SKILL:", fmg["caption"], "Item description must display randomized skill!")

    def test_weapon_skill_randomization_disabled(self):
        """Verifies that weapons do NOT alter swordArtsParamId when randomize_weapon_skills=False."""
        generator_no_skills = DiabloLootGenerator(seed=101, randomize_weapon_skills=False)

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

        base_spec = self.builder.build_patch_spec(wpn_set)
        variants = generator_no_skills.generate_variants_for_spec(base_spec, variants_per_item=3)
        for v in variants:
            ep = v["equip_params"][0]
            self.assertNotIn("swordArtsParamId", ep["field_updates"], "swordArtsParamId must not be set when disabled!")
            fmg = v["fmg_texts"][0]
            self.assertNotIn("SKILL:", fmg["caption"])

    def test_armor_not_receiving_weapon_skills(self):
        """Verifies that armor pieces never receive swordArtsParamId even when randomize_weapon_skills=True."""
        generator_with_skills = DiabloLootGenerator(seed=101, randomize_weapon_skills=True)

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

        base_spec = self.builder.build_patch_spec(armor_set)
        variants = generator_with_skills.generate_variants_for_spec(base_spec, variants_per_item=3)
        for v in variants:
            ep = v["equip_params"][0]
            self.assertEqual(ep["param_table"], "EquipParamProtector")
            self.assertNotIn("swordArtsParamId", ep["field_updates"])
            fmg = v["fmg_texts"][0]
            self.assertNotIn("SKILL:", fmg["caption"])

    def test_vanilla_stat_injections_weapon_skills(self):
        """Verifies vanilla weapon stat infusions randomize skills when enabled."""
        from src.knowledge_base import VanillaKnowledgeBase
        kb = VanillaKnowledgeBase.from_data_dir("data")

        gen = DiabloLootGenerator(seed=42, randomize_weapon_skills=True)
        specs = gen.generate_vanilla_stat_injections(knowledge_base=kb)

        weapon_specs = [s for s in specs if s["equip_params"][0]["param_table"] == "EquipParamWeapon"]
        protector_specs = [s for s in specs if s["equip_params"][0]["param_table"] == "EquipParamProtector"]

        self.assertGreater(len(weapon_specs), 0)
        for ws in weapon_specs:
            ep = ws["equip_params"][0]
            self.assertIn("swordArtsParamId", ep["field_updates"])
            fmg = ws["fmg_texts"][0]
            self.assertIn("SKILL:", fmg["caption"])

        for ps in protector_specs:
            ep = ps["equip_params"][0]
            self.assertNotIn("swordArtsParamId", ep["field_updates"])
            fmg = ps["fmg_texts"][0]
            self.assertNotIn("SKILL:", fmg["caption"])

    def test_starting_gear_modifications(self):
        """Verifies starting gear for all 10 classes is modified with authentic IDs."""
        from src.knowledge_base import VanillaKnowledgeBase
        kb = VanillaKnowledgeBase.from_data_dir("data")

        gen = DiabloLootGenerator(seed=123)
        specs = gen.generate_vanilla_stat_injections(knowledge_base=kb)

        injected_ids = {s["equip_params"][0]["new_param_id"] for s in specs}

        # Check Starting Class Weapons & Shields
        starting_weapons = [
            2000000,   # Vagabond Longsword
            18000000,  # Vagabond Halberd
            31330000,  # Vagabond Heater Shield
            7140000,   # Warrior Scimitar
            30090000,  # Warrior Riveted Wooden Shield
            14000000,  # Hero Battle Axe
            31230000,  # Hero Large Leather Shield
            1090000,   # Bandit Great Knife
            40000000,  # Bandit Shortbow
            30000000,  # Bandit Buckler
            33130000,  # Astrologer's Staff
            2010000,   # Astrologer Short Sword
            30080000,  # Astrologer Scripture Wooden Shield
            16000000,  # Prophet Short Spear
            34000000,  # Prophet / Confessor Finger Seal
            30030000,  # Prophet Rickety Shield
            9000000,   # Samurai Uchigatana
            41000000,  # Samurai Longbow
            30070000,  # Samurai Red Thorn Roundshield
            5000000,   # Prisoner Estoc
            33000000,  # Prisoner Glintstone Staff
            30110000,  # Prisoner Rift Shield
            2020000,   # Confessor Broadsword
            31100000,  # Confessor Blue-Gold Kite Shield
            11010000,  # Wretch Club
        ]

        for w_id in starting_weapons:
            self.assertIn(w_id, injected_ids, f"Starting weapon/shield {w_id} must be injected!")

        # Check Starting Class Armor Pieces
        starting_armors = [
            660000, 660100, 660200, 660300,  # Vagabond Knight Set
            870000, 870100, 870200, 870300,  # Land of Reeds Set
            630000, 630100, 630200, 630300,  # Astrologer Set
            730000, 730100, 730200, 730300,  # Champion Set
            1401000, 931100, 930200, 930300, # Bandit Set
            670000, 670100, 670200, 670300,  # Blue Cloth Set
            880000, 880100, 880200, 880300,  # Confessor Set
            890000, 890100, 890300,          # Prisoner Set
            620000, 622100, 620300           # Prophet Set
        ]

        for a_id in starting_armors:
            self.assertIn(a_id, injected_ids, f"Starting armor piece {a_id} must be injected!")

    def test_passive_ui_effect_routing(self):
        """Verifies passive effects populate weapon UI slots (spEffectMsgId0..2) and resident/on-hit IDs."""
        from src.diablo_affixes import AFFIX_POOL, AffixDefinition

        # Find status buildup affix (Glacial)
        glacial = next(a for a in AFFIX_POOL if a.name == "Glacial")
        self.assertTrue(glacial.is_on_hit_effect)
        self.assertEqual(glacial.sp_effect_msg_id, 6601)
        self.assertEqual(glacial.sp_effect_id, 6702)

        # Test application to weapon
        updates = {}
        DiabloLootGenerator.apply_affixes_to_equipment(updates, [glacial], is_weapon=True)
        self.assertEqual(updates.get("spEffectBehaviorId0"), 6702)
        self.assertEqual(updates.get("spEffectMsgId0"), 6601)

        # Test resident passive buff (of the Mind)
        mind = next(a for a in AFFIX_POOL if a.name == "of the Mind")
        updates_res = {}
        DiabloLootGenerator.apply_affixes_to_equipment(updates_res, [mind], is_weapon=True)
        self.assertEqual(updates_res.get("residentSpEffectId"), mind.sp_effect_id)
        self.assertEqual(updates_res.get("spEffectMsgId0"), 1002)

    def test_accessory_affixes_and_equipment_updates(self):
        """Verifies accessory affixes roll correctly and map to residentSpEffectId1..4 and refId."""
        accessory_affixes = self.generator.roll_affixes(RarityTier.LEGENDARY, is_weapon=False, is_accessory=True)
        self.assertGreaterEqual(len(accessory_affixes), 2)
        for aff in accessory_affixes:
            self.assertTrue(getattr(aff, "applies_to_accessory", False), f"Affix {aff.name} must be valid for accessories!")

        updates = {}
        DiabloLootGenerator.apply_affixes_to_equipment(updates, accessory_affixes, is_weapon=False, is_accessory=True)
        # Should have residentSpEffectId1..4 or refId populated
        resident_keys = [k for k in updates if k.startswith("residentSpEffectId")]
        self.assertTrue(len(resident_keys) > 0 or "refId" in updates, "Accessory updates must populate residentSpEffects or refId!")

    def test_boss_and_chest_multi_drop_with_accessory(self):
        """Verifies multi-drop bundling for Bosses and Chests with companion accessory relics."""
        from src.knowledge_base import VanillaKnowledgeBase
        kb = VanillaKnowledgeBase.from_data_dir("data")

        armor_set = DetectedModSet(
            set_id="RagingWolf_1500",
            folder_or_archive_name="Raging Wolf Set",
            target_model_id="1500",
            target_vanilla_name="Raging Wolf Helm",
            parts=[ModPartFile("hr_m_1500.partsbnd.dcx", "hr_m_1500.partsbnd.dcx", EquipmentSlot.HEAD, "1500", "m", 100)],
            allocation=StandaloneAllocation(
                new_model_id="9010",
                new_equip_param_id=9010000,
                new_item_lot_id=9100010,
                marker_tag="[LootForge]"
            ),
            loot_target=LootTarget(
                route_type=LootDistributionType.ENEMY_DROP,
                target_id="431100000",
                display_name="Godrick Soldier",
                chance_or_cost=100.0
            )
        )

        base_spec = self.builder.build_patch_spec(armor_set)
        variants = self.generator.generate_variants_for_spec(
            base_spec=base_spec,
            variants_per_item=6,
            knowledge_base=kb
        )
        self.assertEqual(len(variants), 6)

        # Mod buckets: 0=Boss, 1=Chest, 2=Rest, 3=Boss, 4=Chest, 5=Rest
        boss_variants = [v for idx, v in enumerate(variants) if (idx % 3) == 0]
        chest_variants = [v for idx, v in enumerate(variants) if (idx % 3) == 1]
        rest_variants = [v for idx, v in enumerate(variants) if (idx % 3) == 2]

        self.assertEqual(len(boss_variants), 2)
        self.assertEqual(len(chest_variants), 2)
        self.assertEqual(len(rest_variants), 2)

        # Boss variants must have multiple drops (companion accessory)
        for bv in boss_variants:
            awarded = bv["loot_distribution"]["awarded_items"]
            self.assertEqual(len(awarded), 2, "Boss variants must have multiple drops (relic + companion accessory)!")
            tables = [ep["param_table"] for ep in bv["equip_params"]]
            self.assertIn("EquipParamAccessory", tables, "Boss variant must bundle an EquipParamAccessory companion relic!")
            fmg_acc = [ft for ft in bv["fmg_texts"] if ft.get("is_accessory")]
            self.assertGreaterEqual(len(fmg_acc), 1, "Must have an FMG entry marked as accessory!")

        # Chest variants must have multiple extra injections (at least 2 companion accessories)
        for cv in chest_variants:
            awarded = cv["loot_distribution"]["awarded_items"]
            self.assertGreaterEqual(len(awarded), 3, "Chest variants must have multiple extra injections (relic + multiple companion accessories)!")
            tables = [ep["param_table"] for ep in cv["equip_params"]]
            self.assertIn("EquipParamAccessory", tables, "Chest variant must bundle EquipParamAccessory companion relics!")
            fmg_acc = [ft for ft in cv["fmg_texts"] if ft.get("is_accessory")]
            self.assertGreaterEqual(len(fmg_acc), 2, "Must have multiple FMG entries marked as accessory for chest extra injections!")


        # Rest variants must only have single primary item
        for rv in rest_variants:
            awarded = rv["loot_distribution"]["awarded_items"]
            self.assertEqual(len(awarded), 1, "Rest variants (mobs/merchants) must have single item drop!")

    def test_vanilla_accessory_stat_injections(self):
        """Verifies Diablo stat infusion specs for vanilla accessories/talismans."""
        from src.knowledge_base import VanillaKnowledgeBase
        kb = VanillaKnowledgeBase.from_data_dir("data")

        specs = self.generator.generate_vanilla_stat_injections(knowledge_base=kb)
        acc_specs = [s for s in specs if s["equip_params"][0].get("param_table") == "EquipParamAccessory"]
        self.assertGreaterEqual(len(acc_specs), 20, "Must inject stats into vanilla accessories/talismans!")

        for spec in acc_specs:
            ep = spec["equip_params"][0]
            self.assertTrue(ep["update_existing"])
            self.assertEqual(ep["param_table"], "EquipParamAccessory")
            fmg = spec["fmg_texts"][0]
            self.assertTrue(fmg.get("is_accessory"))
            self.assertIn("RARITY:", fmg["caption"])

    def test_standalone_accessory_generation(self):
        """Verifies standalone accessory relics generated from vanilla base models."""
        from src.knowledge_base import VanillaKnowledgeBase
        from src.id_allocator import IdAllocator
        kb = VanillaKnowledgeBase.from_data_dir("data")
        allocator = IdAllocator(base_param_id=9000000, base_item_lot_id=9100000)

        specs = self.generator.generate_vanilla_base_distribution_specs(
            knowledge_base=kb, id_allocator=allocator, variants_per_item=2
        )
        acc_specs = [s for s in specs if s["equip_params"][0].get("param_table") == "EquipParamAccessory"]
        self.assertGreaterEqual(len(acc_specs), 20, "Must generate standalone accessory relics from vanilla base models!")

        for spec in acc_specs:
            ep = spec["equip_params"][0]
            self.assertEqual(ep["param_table"], "EquipParamAccessory")
            self.assertGreaterEqual(ep["new_param_id"], 9000000)
            self.assertIn("loot_distribution", spec)
            fmg = spec["fmg_texts"][0]
            self.assertTrue(fmg.get("is_accessory"))
            self.assertIn("[LootForge]", fmg["name"])


if __name__ == "__main__":
    unittest.main()

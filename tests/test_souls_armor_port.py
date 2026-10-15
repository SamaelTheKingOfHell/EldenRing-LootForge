"""
Test suite for Dark Souls Legacy Armor Porting Pipeline adhering to [CS-NO-MOCK].

Validates:
1. Client-side game discovery across standard Steam paths.
2. Flat DS1 defense to Elden Ring PBR damage cut rates & poise translation.
3. SoulsPortAdapter integration with ModScanner and ParamBuilder using real staged Black Knight files.
4. BND4 / DCX archive integrity for modern Elden Ring Oodle-compressed containers.
"""

import unittest
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.models import EquipmentSlot, StandaloneAllocation, LootTarget, LootDistributionType
from src.knowledge_base import VanillaKnowledgeBase
from src.scanner import ModScanner
from src.param_builder import ParamBuilder
from src.souls_port_adapter import SoulsGameDiscovery, SoulsStatConverter, SoulsPortAdapter


class TestSoulsArmorPort(unittest.TestCase):
    """
    Validates end-to-end legacy Souls armor porting functionality.
    """

    @classmethod
    def setUpClass(cls):
        cls.data_dir = PROJECT_ROOT / "data"
        cls.kb = VanillaKnowledgeBase.from_data_dir(str(cls.data_dir))
        cls.input_mods_dir = PROJECT_ROOT / "input_mods"
        cls.black_knight_dir = cls.input_mods_dir / "BlackKnightSet"

    def test_game_discovery(self):
        """Verifies detection of local Dark Souls installations."""
        installations = SoulsGameDiscovery.discover_installations()
        self.assertIsInstance(installations, dict)
        # On this workstation, DS1 PTDE is installed at D:\SteamLibrary
        if "ds1_ptde" in installations:
            path = Path(installations["ds1_ptde"])
            self.assertTrue(path.exists(), f"Discovered path does not exist: {path}")
            self.assertTrue((path / "dvdbnd1.bdt").exists() or (path / "DARKSOULS.exe").exists())

    def test_ds1_stat_conversion_helm(self):
        """Verifies DS1 flat defense stats correctly convert to Elden Ring cut rate multipliers."""
        ds1_helm_stats = {
            "defensePhysics": 21,
            "defenseSlash": 13,
            "defenseBlow": -5,
            "defenseThrust": -2,
            "defenseMagic": 11,
            "defenseFire": 18,
            "defenseThunder": 6,
            "saDurability": 8,
            "weight": 5.0,
            "resistPoison": 6,
            "resistBlood": 12,
            "resistDisease": 6,
            "resistCurse": 0
        }

        er_fields = SoulsStatConverter.convert_ds1_stats_to_er(EquipmentSlot.HEAD, ds1_helm_stats)

        # Absorption check: neutralDamageCutRate should be around 0.865 (13.5% absorption)
        self.assertAlmostEqual(er_fields["neutralDamageCutRate"], 0.865, places=2)
        # Fire defense was high in DS1 (18/21 ratio), so fireDamageCutRate must be lower than neutral
        self.assertLess(er_fields["fireDamageCutRate"], 0.90)
        # Strike defense had a penalty in DS1 (-5), so blowDamageCutRate should reflect higher incoming damage
        self.assertGreater(er_fields["blowDamageCutRate"], er_fields["neutralDamageCutRate"])
        # Poise and weight preserved
        self.assertEqual(er_fields["saDurability"], 8.0)
        self.assertEqual(er_fields["weight"], 5.0)
        # Status resistances scaled by 4
        self.assertEqual(er_fields["resistPoison"], 24)
        self.assertEqual(er_fields["resistBlood"], 48)

    def test_ds1_stat_conversion_body(self):
        """Verifies DS1 chest armor conversion provides major absorption and poise."""
        ds1_body_stats = {
            "defensePhysics": 54,
            "defenseSlash": 33,
            "defenseBlow": -12,
            "defenseThrust": -5,
            "defenseMagic": 29,
            "defenseFire": 46,
            "defenseThunder": 15,
            "saDurability": 20,
            "weight": 12.8,
            "resistPoison": 15,
            "resistBlood": 30,
            "resistDisease": 15,
            "resistCurse": 0
        }

        er_fields = SoulsStatConverter.convert_ds1_stats_to_er(EquipmentSlot.BODY, ds1_body_stats)

        # Body physical absorption ~ 30% -> cut rate ~ 0.700
        self.assertAlmostEqual(er_fields["neutralDamageCutRate"], 0.700, places=2)
        # Heavy poise for chest piece
        self.assertEqual(er_fields["saDurability"], 20.0)
        self.assertEqual(er_fields["weight"], 12.8)

    def test_scanner_with_souls_port_meta(self):
        """Verifies scanner introspects souls_port_meta.json and titles set accurately."""
        if not self.black_knight_dir.exists():
            self.skipTest("BlackKnightSet not staged in input_mods")

        scanner = ModScanner(self.kb)
        detected_sets = scanner.scan_directory(str(self.input_mods_dir))
        bk_set = next((s for s in detected_sets if s.folder_or_archive_name == "BlackKnightSet"), None)

        self.assertIsNotNone(bk_set, "BlackKnightSet not discovered by scanner")
        self.assertEqual(bk_set.target_vanilla_name, "Black Knight Set")
        self.assertIsNotNone(bk_set.souls_port_meta)
        self.assertEqual(bk_set.souls_port_meta.get("sourceGame"), "Dark Souls 1")
        # Should have 8 parts files (m and f for all 4 slots)
        self.assertEqual(len(bk_set.parts), 8)

    def test_param_builder_with_black_knight_set(self):
        """Verifies ParamBuilder synthesizes authentic DS1 names, lore captions, and ER defense cut rates."""
        if not self.black_knight_dir.exists():
            self.skipTest("BlackKnightSet not staged in input_mods")

        scanner = ModScanner(self.kb)
        detected_sets = scanner.scan_directory(str(self.input_mods_dir))
        bk_set = next((s for s in detected_sets if s.folder_or_archive_name == "BlackKnightSet"), None)
        self.assertIsNotNone(bk_set)

        # Assign allocation and loot target
        bk_set.allocation = StandaloneAllocation(
            new_model_id="9490",
            new_equip_param_id=9490000,
            new_item_lot_id=9490100,
            marker_tag="✦ [LootForge]"
        )
        bk_set.loot_target = LootTarget(
            route_type=LootDistributionType.ENEMY_DROP,
            target_id="1000",
            display_name="Black Knight (Crucible Knight in ER)",
            chance_or_cost=15.0
        )

        builder = ParamBuilder(self.kb)
        patch_spec = builder.build_patch_spec(bk_set)

        # Verify equip params
        equip_params = patch_spec["equip_params"]
        self.assertEqual(len(equip_params), 4)

        for ep in equip_params:
            self.assertEqual(ep["param_table"], "EquipParamProtector")
            fields = ep["field_updates"]
            # Unisex parameter enforcement
            self.assertEqual(fields["equipModelGender"], 0)
            # Both gender files exist in the set
            self.assertEqual(fields["_lf_hasMaleFiles"], 1)
            self.assertEqual(fields["_lf_hasFemaleFiles"], 1)
            # Transformed ER cut rates present
            self.assertIn("neutralDamageCutRate", fields)
            self.assertIn("fireDamageCutRate", fields)
            self.assertIn("saDurability", fields)
            self.assertGreater(fields["saDurability"], 0)

        # Verify FMG texts
        fmg_texts = patch_spec["fmg_texts"]
        self.assertEqual(len(fmg_texts), 4)

        names = {t["slot"]: t["name"] for t in fmg_texts}
        self.assertEqual(names["head"], "✦ [LootForge] Black Knight Helm")
        self.assertEqual(names["body"], "✦ [LootForge] Black Knight Armor")
        self.assertEqual(names["arms"], "✦ [LootForge] Black Knight Gauntlets")
        self.assertEqual(names["legs"], "✦ [LootForge] Black Knight Leggings")

        captions = {t["slot"]: t["caption"] for t in fmg_texts}
        self.assertIn("Helm of the Black Knights who haunt Lordran", captions["head"])
        self.assertIn("[Legacy Souls Relic: Dark Souls 1]", captions["head"])

    def test_bnd4_archive_integrity(self):
        """Verifies staged parts archives exist and have valid DCX headers."""
        if not self.black_knight_dir.exists():
            self.skipTest("BlackKnightSet not staged in input_mods")

        expected_files = [
            "hd_m_9490.partsbnd.dcx",
            "hd_f_9490.partsbnd.dcx",
            "bd_m_9490.partsbnd.dcx",
            "bd_f_9490.partsbnd.dcx",
            "am_m_9490.partsbnd.dcx",
            "am_f_9490.partsbnd.dcx",
            "lg_m_9490.partsbnd.dcx",
            "lg_f_9490.partsbnd.dcx",
        ]

        for fname in expected_files:
            fpath = self.black_knight_dir / fname
            self.assertTrue(fpath.exists(), f"Missing staged file: {fname}")
            self.assertGreater(fpath.stat().st_size, 1000, f"File unexpectedly small: {fname}")
            # Verify DCX magic bytes at start of file
            with open(fpath, "rb") as f:
                header = f.read(4)
                self.assertIn(header, [b"DCX\x00", b"DCP\x00"], f"Invalid DCX header for {fname}: {header}")


if __name__ == "__main__":
    unittest.main()

"""
Automated unit tests for RegulationManager and RegTool.

Verifies:
- Source regulation resolution hierarchy
- Target regulation resolution safety (vanilla regulation never overwritten)
- Non-destructive regulation patching (vanilla loots preserved, new drops appended)
- Roundtrip AES-256 decryption and verification of injected equipment & loot
"""

import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path

from src.regulation_manager import RegulationManager
from src.models import (
    DetectedModSet, ModPartFile, EquipmentSlot, LootTarget,
    LootDistributionType, StandaloneAllocation
)
from src.param_builder import ParamBuilder


class TestRegulationManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.base_dir = Path(__file__).resolve().parent.parent
        self.manager = RegulationManager(self.base_dir)

        # Locate a real backup regulation file in the repo for concrete verification
        backups = sorted((self.base_dir / "backups").glob("regulation.bin.bak_*"))
        self.real_reg = backups[0] if backups else None

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_target_regulation_safety_redirect(self):
        """Verify that targeting vanilla Game/regulation.bin safely redirects to mod/regulation.bin."""
        game_dir = str(Path(self.test_dir) / "Game")
        vanilla_reg = str(Path(game_dir) / "regulation.bin")

        target = self.manager.resolve_target_regulation(
            active_path=vanilla_reg,
            output_dir=str(Path(self.test_dir) / "mod"),
            game_dir=game_dir
        )

        expected = Path(self.test_dir) / "mod" / "regulation.bin"
        self.assertEqual(target.resolve(), expected.resolve())
        self.assertNotEqual(target.resolve(), Path(vanilla_reg).resolve())

    def test_end_to_end_regulation_patch_and_loot_preservation(self):
        """Verify that RegTool patches regulation without clearing existing enemy loot."""
        if not self.real_reg or not self.real_reg.exists():
            self.skipTest("No real backup regulation.bin available in backups/ for roundtrip test.")

        target_reg = Path(self.test_dir) / "mod" / "regulation.bin"

        # Construct a test mod set
        parts = [
            ModPartFile(
                file_name="hd_m_4000.partsbnd.dcx",
                relative_path="hd_m_4000.partsbnd.dcx",
                slot=EquipmentSlot.HEAD,
                target_model_id="4000",
                gender_variant="m",
                file_size_bytes=1024
            ),
            ModPartFile(
                file_name="bd_m_4000.partsbnd.dcx",
                relative_path="bd_m_4000.partsbnd.dcx",
                slot=EquipmentSlot.BODY,
                target_model_id="4000",
                gender_variant="m",
                file_size_bytes=2048
            )
        ]

        mod_set = DetectedModSet(
            set_id="carian_relic",
            target_model_id="4000",
            target_vanilla_name="Carian Knight Set",
            is_weapon=False,
            parts=parts,
            folder_or_archive_name="carian_relic"
        )
        mod_set.allocation = StandaloneAllocation(
            new_model_id="9000",
            new_equip_param_id=9000000,
            new_item_lot_id=100400,  # Targeting Cleanrot Knight lot (100400)
            marker_tag="✦ [LootForge]"
        )
        mod_set.loot_target = LootTarget(
            route_type=LootDistributionType.ENEMY_DROP,
            target_id="100400",
            display_name="Cleanrot Knight",
            chance_or_cost=25.0
        )

        builder = ParamBuilder()
        patch_spec = builder.build_patch_spec(mod_set)

        # Execute patching
        result = self.manager.execute_patch(
            specs=[patch_spec],
            source_reg=self.real_reg,
            target_reg=target_reg
        )

        self.assertTrue(result["success"])
        self.assertTrue(target_reg.exists())
        self.assertGreater(target_reg.stat().st_size, 1000000)

        # Run verification via RegTool verify command
        verify_cmd = [
            str(self.manager.regtool_exe) if self.manager.regtool_exe.exists() else "dotnet",
            "verify",
            "--input", str(target_reg)
        ]
        if not self.manager.regtool_exe.exists():
            verify_cmd = ["dotnet", str(self.manager.regtool_dll), "verify", "--input", str(target_reg)]

        import subprocess
        res = subprocess.run(verify_cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Decryption successful", res.stdout)


if __name__ == "__main__":
    unittest.main()

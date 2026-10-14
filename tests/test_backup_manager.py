"""
Backup manager test suite adhering to [CS-NO-MOCK].

Creates real binary files, generates timestamped backups, validates SHA-256 checksums,
and verifies byte-for-byte restoration.
"""

import unittest
import sys
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backup_manager import BackupManager


class TestBackupManager(unittest.TestCase):
    """
    Tests real file backup, hashing, and rollback mechanisms.
    """

    def setUp(self):
        self.test_dir = Path(__file__).resolve().parent / "tmp_backup_test"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir = self.test_dir / "backups"

        # Create authentic dummy regulation.bin
        self.regulation_file = self.test_dir / "regulation.bin"
        self.original_payload = b"BND4_ELDEN_RING_REGULATION_HEADER_PAYLOAD_12345"
        with open(self.regulation_file, "wb") as f:
            f.write(self.original_payload)

        self.mgr = BackupManager(backup_dir=str(self.backup_dir))

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_backup_and_checksum(self):
        """Verifies backup creation and accurate SHA-256 calculation."""
        record = self.mgr.create_backup(str(self.regulation_file))
        self.assertTrue((self.backup_dir / record.backup_file_name).exists())
        self.assertEqual(record.file_size_bytes, len(self.original_payload))
        self.assertTrue(len(record.sha256_checksum) == 64)

    def test_restore_backup(self):
        """Verifies restoring pristine state overwriting modified file."""
        self.mgr.create_backup(str(self.regulation_file))

        # Mutate regulation.bin
        with open(self.regulation_file, "wb") as f:
            f.write(b"CORRUPTED_OR_MUTATED_PAYLOAD")

        # Restore
        self.mgr.restore_latest_backup(str(self.regulation_file))

        with open(self.regulation_file, "rb") as f:
            restored_data = f.read()

        self.assertEqual(restored_data, self.original_payload)

    def test_msg_file_backup_and_restore(self):
        """Verifies backing up and restoring non-regulation files such as item.msgbnd.dcx."""
        msg_file = self.test_dir / "item.msgbnd.dcx"
        original_msg = b"MSGBND_ORIGINAL_TEXT_DATA_12345"
        with open(msg_file, "wb") as f:
            f.write(original_msg)

        rec = self.mgr.create_file_backup(str(msg_file), category="msg")
        self.assertTrue((self.backup_dir / rec.backup_file_name).exists())

        # Mutate
        with open(msg_file, "wb") as f:
            f.write(b"MSGBND_MUTATED_DATA")

        # Restore
        self.mgr.restore_latest_backup_for_file(str(msg_file))
        with open(msg_file, "rb") as f:
            self.assertEqual(f.read(), original_msg)

    def test_comprehensive_rollback_all(self):
        """Verifies rollback_all restores regulation.bin, restores msg files, and cleans parts across target and mod dirs."""
        from src.regulation_manager import RegulationManager
        from src.manifest_store import ManifestStore
        from src.models import ManifestRecord

        target_dir = self.test_dir / "target_profile"
        target_dir.mkdir(parents=True, exist_ok=True)
        local_mod_dir = self.test_dir / "mod"
        local_mod_dir.mkdir(parents=True, exist_ok=True)

        # 1. Setup target regulation and backup
        target_reg = target_dir / "regulation.bin"
        pristine_reg = b"PRISTINE_REGULATION_BYTES"
        with open(target_reg, "wb") as f:
            f.write(pristine_reg)
        self.mgr.create_backup(str(target_reg))

        # Mutate target_reg as if forge occurred
        with open(target_reg, "wb") as f:
            f.write(b"FORGED_MODIFIED_REGULATION_BYTES")

        # 2. Setup existing item.msgbnd.dcx and backup
        target_msg = target_dir / "msg" / "engUS" / "item.msgbnd.dcx"
        target_msg.parent.mkdir(parents=True, exist_ok=True)
        pristine_msg = b"PRISTINE_MSG_BYTES"
        with open(target_msg, "wb") as f:
            f.write(pristine_msg)
        msg_bak = self.mgr.create_file_backup(str(target_msg), category="msg")

        # Mutate target_msg
        with open(target_msg, "wb") as f:
            f.write(b"FORGED_MODIFIED_MSG_BYTES")

        # Setup newly created DLC msg file that did NOT exist before forge
        created_dlc_msg = target_dir / "msg" / "engUS" / "item_dlc02.msgbnd.dcx"
        with open(created_dlc_msg, "wb") as f:
            f.write(b"CREATED_DLC_MSG_BYTES")

        # 3. Setup deployed parts files
        deployed_part1 = target_dir / "parts" / "bd_m_9000.partsbnd.dcx"
        deployed_part1.parent.mkdir(parents=True, exist_ok=True)
        with open(deployed_part1, "wb") as f:
            f.write(b"PART_1_BYTES")

        staged_part2 = local_mod_dir / "parts" / "hd_m_9000.partsbnd.dcx"
        staged_part2.parent.mkdir(parents=True, exist_ok=True)
        with open(staged_part2, "wb") as f:
            f.write(b"PART_2_BYTES")

        # 4. Setup manifest
        manifest_file = self.test_dir / "manifest.json"
        store = ManifestStore(manifest_path=str(manifest_file))
        store._records["set_1"] = ManifestRecord(
            set_id="set_1",
            created_timestamp="2026-10-12 12:00:00",
            allocated_model_id="9000",
            allocated_param_id=9000000,
            source_mod_name="TestSet",
            target_vanilla_name="Knight Set",
            loot_route="enemy_drop",
            loot_target_name="Cleanrot Knight",
            staged_files=["parts/hd_m_9000.partsbnd.dcx"]
        )
        store.record_deployment(
            target_regulation_path=str(target_reg),
            deployed_files=[str(deployed_part1)],
            created_msg_files=[str(created_dlc_msg)],
            backed_up_files={str(target_msg): msg_bak.backup_file_name}
        )

        reg_mgr = RegulationManager(base_dir=self.test_dir)
        res = reg_mgr.rollback_all(
            backup_manager=self.mgr,
            manifest_store=store,
            target_reg_path=str(target_reg),
            output_dir=str(local_mod_dir)
        )

        self.assertTrue(res["success"])
        # Regulation restored
        with open(target_reg, "rb") as f:
            self.assertEqual(f.read(), pristine_reg)
        # Msg restored
        with open(target_msg, "rb") as f:
            self.assertEqual(f.read(), pristine_msg)
        # Created DLC msg deleted
        self.assertFalse(created_dlc_msg.exists())
        # Deployed parts deleted
        self.assertFalse(deployed_part1.exists())
        self.assertFalse(staged_part2.exists())
        # Manifest cleared
        self.assertEqual(len(store.get_all_records()), 0)

    def test_chr_moveset_asset_backup_and_rollback_preservation(self):
        """
        Validates that pre-existing chr/ assets carrying double jump or core features
        are backed up when overwritten and restored on rollback WITHOUT deleting chr/.
        """
        from src.regulation_manager import RegulationManager
        from src.manifest_store import ManifestStore

        target_dir = self.test_dir / "ordo_profile"
        target_dir.mkdir(parents=True, exist_ok=True)
        chr_dir = target_dir / "chr"
        chr_dir.mkdir(parents=True, exist_ok=True)

        # Pre-existing file carrying double jump
        double_jump_file = chr_dir / "c0000_a00_hi.anibnd.dcx"
        original_dj_content = b"DOUBLE_JUMP_PLAYER_ANIMATION_TAE_BYTES"
        with open(double_jump_file, "wb") as f:
            f.write(original_dj_content)

        bak_rec = self.mgr.create_file_backup(str(double_jump_file), category="chr")

        # Simulate overwriting it with a foreign mod file
        with open(double_jump_file, "wb") as f:
            f.write(b"OVERWRITTEN_WEAPON_MOD_BYTES")

        # Newly deployed file from LootForge
        new_anim_file = chr_dir / "c0000_a1x.anibnd.dcx"
        with open(new_anim_file, "wb") as f:
            f.write(b"NEW_WEAPON_ANIM_BYTES")

        manifest_file = self.test_dir / "manifest_chr.json"
        store = ManifestStore(manifest_path=str(manifest_file))
        store.record_deployment(
            target_regulation_path=str(target_dir / "regulation.bin"),
            deployed_files=[str(double_jump_file), str(new_anim_file)],
            backed_up_files={str(double_jump_file): bak_rec.backup_file_name}
        )

        reg_mgr = RegulationManager(base_dir=self.test_dir)
        res = reg_mgr.rollback_all(
            backup_manager=self.mgr,
            manifest_store=store,
            target_reg_path=str(target_dir / "regulation.bin")
        )

        self.assertTrue(res["success"])
        # Original double jump file MUST be restored byte-for-byte
        self.assertTrue(double_jump_file.exists())
        with open(double_jump_file, "rb") as f:
            self.assertEqual(f.read(), original_dj_content)

        # Newly created file MUST be deleted
        self.assertFalse(new_anim_file.exists())

        # chr/ directory MUST NOT be deleted because it still contains restored double jump file
        self.assertTrue(chr_dir.exists())

    def test_host_core_player_assets_preservation(self):
        """
        Validates that SkillMovesetDeployer does NOT clobber pre-existing host player assets
        (c0000_a00_hi.anibnd.dcx, c0000.hks, c0000.behbnd.dcx) when import_custom_skills_movesets is active.
        """
        from src.skill_moveset_deployer import SkillMovesetDeployer
        from src.models import DetectedModSet, SkillMovesetMetadata

        input_base = self.test_dir / "input_mods"
        mod_source = input_base / "ForeignWeaponMod"
        src_chr = mod_source / "chr"
        src_chr.mkdir(parents=True, exist_ok=True)
        src_action = mod_source / "action" / "script"
        src_action.mkdir(parents=True, exist_ok=True)

        # Foreign mod ships these files
        (src_chr / "c0000_a00_hi.anibnd.dcx").write_bytes(b"FOREIGN_BASE_ANIM")
        (src_chr / "c0000_a2x.anibnd.dcx").write_bytes(b"FOREIGN_WEAPON_ANIM")
        (src_action / "c0000.hks").write_bytes(b"FOREIGN_HKS_NO_DOUBLE_JUMP")

        output_dir = self.test_dir / "target_mod"
        out_chr = output_dir / "chr"
        out_chr.mkdir(parents=True, exist_ok=True)
        out_action = output_dir / "action" / "script"
        out_action.mkdir(parents=True, exist_ok=True)

        # Target mod already has double jump in these files
        target_dj_anim = out_chr / "c0000_a00_hi.anibnd.dcx"
        target_dj_anim.write_bytes(b"HOST_ORDO_DOUBLE_JUMP_ANIM")
        target_hks = out_action / "c0000.hks"
        target_hks.write_bytes(b"HOST_ORDO_HKS_AIRMOVE_LUA")

        mod_set = DetectedModSet(
            set_id="mod_foreign",
            folder_or_archive_name="ForeignWeaponMod",
            target_model_id="999",
            target_vanilla_name="Sword",
            parts=[],
            is_weapon=True,
            skill_moveset=SkillMovesetMetadata(has_custom_moveset=True)
        )

        deployer = SkillMovesetDeployer()
        deployed = deployer.deploy_moveset_assets(
            mod_set=mod_set,
            input_base_dir=input_base,
            output_dir=output_dir,
            backup_manager=self.mgr
        )

        # Host mod's double jump files MUST be untouched!
        self.assertEqual(target_dj_anim.read_bytes(), b"HOST_ORDO_DOUBLE_JUMP_ANIM")
        self.assertEqual(target_hks.read_bytes(), b"HOST_ORDO_HKS_AIRMOVE_LUA")

        # Foreign mod's weapon-specific anim bank MUST be deployed
        target_weapon_anim = out_chr / "c0000_a2x.anibnd.dcx"
        self.assertTrue(target_weapon_anim.exists())
        self.assertEqual(target_weapon_anim.read_bytes(), b"FOREIGN_WEAPON_ANIM")
        self.assertIn(str(target_weapon_anim), deployed)
        # Host files must NOT be in deployed_files
        self.assertNotIn(str(target_dj_anim), deployed)
        self.assertNotIn(str(target_hks), deployed)


if __name__ == "__main__":
    unittest.main()


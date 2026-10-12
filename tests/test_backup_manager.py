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


if __name__ == "__main__":
    unittest.main()

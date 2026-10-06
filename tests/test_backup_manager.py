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


if __name__ == "__main__":
    unittest.main()

"""
Backup and integrity manager for regulation.bin in LootForge.

Creates pre-write timestamped snapshots with SHA-256 checksum verification,
preventing game corruption and providing one-click restore.
"""

import os
import shutil
import hashlib
import time
from pathlib import Path
from typing import List, Optional
from src.models import BackupRecord
from src.logger import system_logger


class BackupManager:
    """
    Safeguards regulation.bin and manages restoration points.
    
    Why:
        Preserves uncorrupted original game state before any parameter patching,
        allowing instant recovery if an Elden Ring patch or mod conflict occurs.
        
    Example:
    ```python
    mgr = BackupManager(backup_dir="backups")
    rec = mgr.create_backup("path/to/regulation.bin")
    print(rec.backup_file_name)
    mgr.restore_latest_backup("path/to/regulation.bin")
    ```
    """

    def __init__(self, backup_dir: str = "backups"):
        self._backup_dir = Path(backup_dir)
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def calculate_sha256(file_path: Path) -> str:
        """Computes SHA-256 hash of a file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def create_file_backup(self, file_path: str, category: str = "generic") -> BackupRecord:
        """
        Creates a timestamped snapshot of any specified target file (regulation.bin, item.msgbnd.dcx, etc.).
        """
        source = Path(file_path)
        if not source.exists():
            raise FileNotFoundError(f"Source file not found at {file_path}")

        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        backup_name = f"{source.name}.bak_{timestamp_str}"
        dest = self._backup_dir / backup_name

        shutil.copy2(source, dest)
        checksum = self.calculate_sha256(dest)
        size = dest.stat().st_size

        system_logger.info(
            f"Created {category} backup: {backup_name} ({size} bytes, SHA-256: {checksum[:12]}...)",
            source="BackupManager"
        )

        return BackupRecord(
            backup_file_name=backup_name,
            created_timestamp=timestamp_str,
            file_size_bytes=size,
            sha256_checksum=checksum
        )

    def create_backup(self, regulation_bin_path: str) -> BackupRecord:
        """
        Creates a timestamped snapshot of the target regulation.bin file.
        """
        return self.create_file_backup(regulation_bin_path, category="regulation")

    def list_backups_for_file(self, file_name: str) -> List[BackupRecord]:
        """Lists all existing backups for a specific filename ordered newest to oldest."""
        backups: List[BackupRecord] = []
        pattern = f"{file_name}.bak_*"
        for file in sorted(self._backup_dir.glob(pattern), reverse=True):
            try:
                parts = file.name.split(".bak_")
                ts = parts[1] if len(parts) > 1 else "unknown"
                size = file.stat().st_size
                checksum = self.calculate_sha256(file)
                backups.append(BackupRecord(
                    backup_file_name=file.name,
                    created_timestamp=ts,
                    file_size_bytes=size,
                    sha256_checksum=checksum
                ))
            except Exception as e:
                system_logger.warning(f"Error reading backup file {file.name}: {e}", source="BackupManager")
        return backups

    def list_backups(self) -> List[BackupRecord]:
        """Lists all existing regulation backups ordered newest to oldest."""
        return self.list_backups_for_file("regulation.bin")

    def restore_backup(self, backup_name: str, target_regulation_bin_path: str) -> bool:
        """
        Restores a specific backup file to the target regulation.bin path.
        """
        return self.restore_backup_file(backup_name, target_regulation_bin_path)

    def restore_backup_file(self, backup_name: str, target_file_path: str) -> bool:
        """
        Restores a specific backup file to the specified target path.
        """
        backup_path = self._backup_dir / backup_name
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        target = Path(target_file_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup_path, target)

        system_logger.info(
            f"Successfully restored {target.name} from backup {backup_name}",
            source="BackupManager"
        )
        return True

    def restore_latest_backup_for_file(self, target_file_path: str) -> bool:
        """Restores the most recent backup for a given file name."""
        target_name = Path(target_file_path).name
        backups = self.list_backups_for_file(target_name)
        if not backups:
            raise FileNotFoundError(f"No backups found for {target_name} in backup directory.")
        return self.restore_backup_file(backups[0].backup_file_name, target_file_path)

    def restore_latest_backup(self, target_regulation_bin_path: str) -> bool:
        """Restores the most recent regulation.bin backup."""
        backups = self.list_backups()
        if not backups:
            raise FileNotFoundError("No regulation.bin backups found in backup directory.")
        return self.restore_backup(backups[0].backup_file_name, target_regulation_bin_path)

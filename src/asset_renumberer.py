"""
Asset renumberer and isolation engine for LootForge.

Stages replacement 3D model files into the output mod directory using newly allocated
standalone IDs, ensuring original vanilla game assets remain untouched.
"""

import os
import shutil
import re
from pathlib import Path
from typing import List, Tuple, Dict
from src.models import DetectedModSet
from src.logger import system_logger


class AssetRenumberer:
    """
    Safely re-indexes .partsbnd.dcx assets to standalone IDs.
    
    Why:
        By copying and re-indexing the files with a safe model ID (e.g., 9001),
        the mod assets coexist with vanilla assets rather than replacing them.
        
    Example:
    ```python
    renumberer = AssetRenumberer(output_dir="mod")
    staged = renumberer.stage_mod_set(input_base="input_mods", mod_set=my_set)
    print(f"Staged {len(staged)} files.")
    ```
    """

    def __init__(self, output_dir: str = "mod"):
        self._output_dir = Path(output_dir)
        self._parts_dir = self._output_dir / "parts"
        self._parts_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _sync_part_file(src: Path, dst: Path) -> None:
        """
        Fast incremental file deployment:
        - If destination already exists with identical file size and destination mtime >= source mtime,
          skip the operation entirely (zero disk I/O).
        - Otherwise, attempt hardlink (os.link) for instant 0-second deployment on NTFS/same-volume.
        - Fallback safely to shutil.copy2 if cross-volume or permission restricted.
        """
        if dst.exists():
            try:
                src_stat = src.stat()
                dst_stat = dst.stat()
                if src_stat.st_size == dst_stat.st_size and dst_stat.st_mtime >= src_stat.st_mtime:
                    return
            except OSError:
                pass

        try:
            if dst.exists():
                dst.unlink()
            os.link(src, dst)
        except (OSError, AttributeError):
            shutil.copy2(src, dst)

    def stage_mod_set(self, input_base: str, mod_set: DetectedModSet) -> List[str]:
        """
        Copies each part file of the mod set to the output parts directory,
        renaming the model ID token to the allocated standalone ID.
        Ensures cross-gender compatibility by mirroring single-gender meshes.
        """
        if not mod_set.allocation:
            raise ValueError(f"ModSet '{mod_set.set_id}' has no allocated standalone IDs.")

        new_model_id = mod_set.allocation.new_model_id
        input_root = Path(input_base)
        staged_files: List[str] = []
        staged_by_name: Dict[str, Path] = {}

        for part in mod_set.parts:
            source_file = input_root / part.relative_path
            if not source_file.exists():
                system_logger.warning(f"Source asset not found: {source_file}", source="AssetRenumberer")
                continue

            # Compute new filename by substituting target_model_id with new_model_id.
            # Normalize to lowercase: Elden Ring expects conventional lowercase part names
            # (e.g. bd_m_9001.partsbnd.dcx); mixed-case inputs like BD_M_4000.partsbnd.dcx
            # would be invisible to the game on case-sensitive filesystems.
            old_name = part.file_name
            new_name = old_name.replace(part.target_model_id, new_model_id).lower()
            dest_file = self._parts_dir / new_name

            self._sync_part_file(source_file, dest_file)
            staged_files.append(str(dest_file.relative_to(self._output_dir)))
            staged_by_name[new_name] = dest_file

            system_logger.debug(
                f"Renumbered and staged: {old_name} -> {new_name}",
                source="AssetRenumberer"
            )

        # Cross-mirror armor parts to ensure unisex body type compatibility (both Type A and Type B).
        # All filenames are already lowercase at this point.
        ARMOR_FILE_RE = re.compile(r"^(am|bd|hd|lg)_([mf])_(.+)$", re.IGNORECASE)
        for staged_name, staged_path in list(staged_by_name.items()):
            match = ARMOR_FILE_RE.match(staged_path.name)
            if not match:
                continue
            prefix, gender, rest = match.groups()
            opposing_gender = "f" if gender.lower() == "m" else "m"
            opposing_name = f"{prefix.lower()}_{opposing_gender}_{rest.lower()}"
            if opposing_name not in staged_by_name:
                opposing_dest = self._parts_dir / opposing_name
                try:
                    self._sync_part_file(staged_path, opposing_dest)
                    staged_files.append(str(opposing_dest.relative_to(self._output_dir)))
                    staged_by_name[opposing_name] = opposing_dest
                    system_logger.info(
                        f"Cross-mirrored staged armor asset for unisex body compatibility: {staged_path.name} -> {opposing_name}",
                        source="AssetRenumberer"
                    )
                except Exception as ex:
                    system_logger.error(
                        f"Failed to cross-mirror staged asset {opposing_name}: {ex}",
                        source="AssetRenumberer"
                    )

        system_logger.info(
            f"Staged {len(staged_files)} part file(s) for '{mod_set.set_id}' as Model ID {new_model_id}",
            source="AssetRenumberer"
        )
        return staged_files

    def stage_all_mod_sets(self, input_base: str, mod_sets: List[DetectedModSet]) -> Dict[str, List[str]]:
        """
        Batch renumber and stage all mod sets in a single unified pass before patching.
        Returns mapping of set_id -> list of staged file paths relative to output_dir.
        """
        staged_map: Dict[str, List[str]] = {}
        total_files = 0
        for s in mod_sets:
            if not getattr(s, "allocation", None) or not getattr(s, "is_enabled", True):
                continue
            staged = self.stage_mod_set(input_base, s)
            staged_map[s.set_id] = staged
            total_files += len(staged)

        system_logger.info(
            f"Batch renumbered and staged {total_files} file(s) across {len(staged_map)} mod set(s) in a single pass.",
            source="AssetRenumberer"
        )
        return staged_map

    def cleanup_files(self, relative_file_paths: List[str]) -> None:
        """
        Removes staged files during uninstallation.
        """
        for rel_path in relative_file_paths:
            target = self._output_dir / rel_path
            if target.exists():
                try:
                    target.unlink()
                    system_logger.debug(f"Removed staged asset: {target}", source="AssetRenumberer")
                except Exception as e:
                    system_logger.warning(f"Could not remove {target}: {e}", source="AssetRenumberer")

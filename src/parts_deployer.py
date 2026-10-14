"""
Parts deployer service for LootForge.

Copies and renames standalone model .partsbnd.dcx files from mod inputs
to the target mod directory, mapping vanilla model IDs to allocated standalone model IDs.
Adheres to [CS-MODULAR] and [CS-GRANULARITY].
"""

import os
import shutil
import re
from pathlib import Path
from typing import List, Dict, Optional, Any
from src.models import DetectedModSet
from src.logger import system_logger


class PartsDeployer:
    """
    Deploys custom model parts (.partsbnd.dcx) alongside regulation.bin.
    
    Why:
        Standalone Elden Ring armor and weapons require both parameter records
        and renumbered asset files matching the allocated model IDs.
    """

    def __init__(self):
        self.last_deployed_files: List[str] = []
        self.last_backed_up_files: Dict[str, str] = {}

    @staticmethod
    def _sync_file(src: Path, dst: Path) -> None:
        """
        Transfers src to dst quickly:
        - If dst exists with identical size and equal/newer mtime, skip copy.
        - Attempts hardlink (os.link) first for instant staging on same drive.
        - Falls back safely to shutil.copy2.
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

    def deploy_parts(
        self,
        mod_sets: List[DetectedModSet],
        input_base_dir: Path,
        output_dir: Path,
        backup_manager: Optional[Any] = None
    ) -> int:
        """
        Copies and renames standalone model parts files to the output directory.

        For each mod set, copies the mod's .partsbnd.dcx files from the input directory
        to output/parts/, renaming them from the vanilla model ID to the standalone
        allocated model ID so the game loads the correct custom visuals.

        Example:
            input:  input_mods/BerserkArmor/parts/bd_m_4200.partsbnd.dcx
            output: mod/parts/bd_m_9001.partsbnd.dcx
        """
        parts_output = Path(output_dir) / "parts"
        parts_output.mkdir(parents=True, exist_ok=True)

        self.last_deployed_files = []
        self.last_backed_up_files = {}
        deployed = 0
        ARMOR_FILE_RE = re.compile(r"^(am|bd|hd|lg)_([mf])_(.+)$", re.IGNORECASE)

        for ms in mod_sets:
            if not getattr(ms, "allocation", None) or not getattr(ms, "is_enabled", True):
                continue

            set_deployed_files: Dict[str, Path] = {}
            for part in ms.parts:
                source = input_base_dir / ms.folder_or_archive_name / part.relative_path
                if not source.exists():
                    # Also try without the folder name (flat input layout)
                    source = input_base_dir / part.relative_path

                if not source.exists():
                    system_logger.warning(
                        f"Parts file not found: {source} (set: {ms.set_id})",
                        source="PartsDeployer"
                    )
                    continue

                # Rename with standalone model ID and normalize to lowercase.
                # Elden Ring resolves part files case-sensitively on Linux/Proton and
                # expects the conventional all-lowercase filenames (e.g. bd_m_9001.partsbnd.dcx).
                # Mixed-case input filenames (e.g. BD_M_4200.partsbnd.dcx) must be
                # lowercased on output to prevent the game from failing to find the file.
                target_name = part.file_name.replace(
                    part.target_model_id, ms.allocation.new_model_id, 1
                ).lower()
                target = parts_output / target_name
                try:
                    if target.exists() and backup_manager:
                        try:
                            bak = backup_manager.create_file_backup(str(target), category="parts")
                            self.last_backed_up_files[str(target)] = bak.backup_file_name
                        except Exception as be:
                            system_logger.warning(f"Could not backup {target}: {be}", source="PartsDeployer")

                    self._sync_file(source, target)
                    deployed += 1
                    self.last_deployed_files.append(str(target))
                    set_deployed_files[target_name] = target
                    system_logger.debug(
                        f"Deployed: {part.file_name} -> {target_name}",
                        source="PartsDeployer"
                    )
                except Exception as ex:
                    system_logger.error(
                        f"Failed to deploy part {part.file_name}: {ex}",
                        source="PartsDeployer"
                    )

            # Cross-mirror armor parts to ensure unisex body type compatibility (both Type A and Type B).
            # If a mod only ships one gender variant, copy it to the opposing gender slot so
            # the game finds both bd_m_{id} and bd_f_{id} (or hd/am/lg equivalents).
            # This is the primary defence against invisible body parts on cross-gender wear.
            # All filenames are already lowercase at this point (normalized on deploy above).
            for target_name, target_path in list(set_deployed_files.items()):
                m = ARMOR_FILE_RE.match(target_path.name)
                if not m:
                    continue
                prefix, gender, rest = m.groups()
                opposing_gender = "f" if gender.lower() == "m" else "m"
                # All components are already lowercase; build opposing name directly
                opposing_target_name = f"{prefix.lower()}_{opposing_gender}_{rest.lower()}"
                if opposing_target_name not in set_deployed_files:
                    opposing_target = parts_output / opposing_target_name
                    try:
                        if opposing_target.exists() and backup_manager:
                            try:
                                bak = backup_manager.create_file_backup(str(opposing_target), category="parts")
                                self.last_backed_up_files[str(opposing_target)] = bak.backup_file_name
                            except Exception as be:
                                system_logger.warning(f"Could not backup {opposing_target}: {be}", source="PartsDeployer")

                        self._sync_file(target_path, opposing_target)
                        deployed += 1
                        self.last_deployed_files.append(str(opposing_target))
                        set_deployed_files[opposing_target_name] = opposing_target
                        system_logger.info(
                            f"Cross-mirrored armor part for body type compatibility: {target_path.name} -> {opposing_target_name}",
                            source="PartsDeployer"
                        )
                    except Exception as ex:
                        system_logger.error(
                            f"Failed to cross-mirror part {opposing_target_name}: {ex}",
                            source="PartsDeployer"
                        )

            # If weapon has custom moveset assets (chr/, sfx/, action/), deploy them alongside parts
            if ms.is_weapon and getattr(ms, "import_custom_moveset", True) and ms.skill_moveset:
                try:
                    from src.skill_moveset_importer import SkillMovesetImporter
                    importer = SkillMovesetImporter(output_dir.parent if output_dir.name == "mod" else output_dir)
                    moveset_files = importer.deploy_moveset_assets(
                        mod_set=ms,
                        input_base_dir=input_base_dir,
                        output_dir=output_dir,
                        backup_manager=backup_manager
                    )
                    deployed += len(moveset_files)
                    self.last_deployed_files.extend(moveset_files)
                    if hasattr(importer, "last_backed_up_files") and importer.last_backed_up_files:
                        self.last_backed_up_files.update(importer.last_backed_up_files)
                except Exception as ex:
                    system_logger.error(
                        f"Failed to deploy custom moveset assets for {ms.set_id}: {ex}",
                        source="PartsDeployer"
                    )

        system_logger.info(
            f"Deployed {deployed} parts file(s) to {parts_output}",
            source="PartsDeployer"
        )
        return deployed

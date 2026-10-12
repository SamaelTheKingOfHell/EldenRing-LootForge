"""
Parts deployer service for LootForge.

Copies and renames standalone model .partsbnd.dcx files from mod inputs
to the target mod directory, mapping vanilla model IDs to allocated standalone model IDs.
Adheres to [CS-MODULAR] and [CS-GRANULARITY].
"""

import shutil
from pathlib import Path
from typing import List
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

    def deploy_parts(
        self,
        mod_sets: List[DetectedModSet],
        input_base_dir: Path,
        output_dir: Path
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
        deployed = 0
        for ms in mod_sets:
            if not getattr(ms, "allocation", None) or not getattr(ms, "is_enabled", True):
                continue

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

                # Rename with standalone model ID
                target_name = part.file_name.replace(
                    part.target_model_id, ms.allocation.new_model_id, 1
                )
                target = parts_output / target_name
                try:
                    shutil.copy2(str(source), str(target))
                    deployed += 1
                    self.last_deployed_files.append(str(target))
                    system_logger.debug(
                        f"Deployed: {part.file_name} -> {target_name}",
                        source="PartsDeployer"
                    )
                except Exception as ex:
                    system_logger.error(
                        f"Failed to deploy part {part.file_name}: {ex}",
                        source="PartsDeployer"
                    )

        system_logger.info(
            f"Deployed {deployed} parts file(s) to {parts_output}",
            source="PartsDeployer"
        )
        return deployed

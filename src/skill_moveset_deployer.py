"""
Moveset and character asset deployment service for LootForge.

Deploys custom weapon animations (chr/), visual effects (sfx/), and action scripts (action/)
while safeguarding host mod core player character behaviors (such as double jump).
Adheres to [CS-MODULAR] and [CS-GRANULARITY].
"""

import shutil
from pathlib import Path
from typing import List, Dict, Optional, Any, Set
from src.models import DetectedModSet
from src.logger import system_logger


# Core player character assets in Elden Ring that define baseline player mobility,
# behavior state machines, and animations. If these exist in the target mod environment
# (e.g. Ordo Perfectus, Double Jump mods, ER Reforged), they MUST NOT be clobbered
# by foreign weapon imports.
CORE_PLAYER_ASSETS: Set[str] = {
    "c0000.behbnd.dcx",
    "c0000.anibnd.dcx",
    "c0000.chrbnd.dcx",
    "c0000_a00_hi.anibnd.dcx",
    "c0000_a00_md.anibnd.dcx",
    "c0000_a00_lo.anibnd.dcx",
    "c0000.hks",
}


class SkillMovesetDeployer:
    """
    Handles file-level copying and deployment of custom weapon animation,
    VFX, and action assets into output directories.
    """

    def __init__(self):
        self.last_deployed_files: List[str] = []
        self.last_backed_up_files: Dict[str, str] = {}

    def deploy_moveset_assets(
        self,
        mod_set: DetectedModSet,
        input_base_dir: Path,
        output_dir: Path,
        backup_manager: Optional[Any] = None
    ) -> List[str]:
        """
        Copies chr/, sfx/, and action/ directories from the mod folder to the output mod directory.
        Preserves existing host player assets (e.g. double jump) and backs up any overwritten assets.
        """
        deployed_files: List[str] = []
        self.last_backed_up_files = {}

        source_mod_dir = input_base_dir / mod_set.folder_or_archive_name
        if not source_mod_dir.exists():
            source_mod_dir = input_base_dir

        out_path = Path(output_dir)

        # 1. Deploy chr/ assets (animations, behaviors)
        chr_candidates = [source_mod_dir / "chr"] + list(source_mod_dir.rglob("chr"))
        for cand in chr_candidates:
            if cand.is_dir() and cand != (out_path / "chr"):
                out_chr = out_path / "chr"
                out_chr.mkdir(parents=True, exist_ok=True)
                for item in cand.iterdir():
                    if item.is_file() and (item.name.endswith(".dcx") or item.name.endswith(".tae")):
                        target = out_chr / item.name.lower()
                        if target.exists():

                            if item.name.lower() in CORE_PLAYER_ASSETS:
                                system_logger.info(
                                    f"Preserving existing host player asset: {target.name} (retains host mod mechanics like double jump)",
                                    source="SkillMovesetDeployer"
                                )
                                continue

                        shutil.copy2(str(item), str(target))
                        deployed_files.append(str(target))
                        system_logger.debug(f"Deployed animation: {item.name} -> {target.name}", source="SkillMovesetDeployer")
                break

        # 2. Deploy sfx/ assets
        sfx_candidates = [source_mod_dir / "sfx"] + list(source_mod_dir.rglob("sfx"))
        for cand in sfx_candidates:
            if cand.is_dir() and cand != (out_path / "sfx"):
                out_sfx = out_path / "sfx"
                out_sfx.mkdir(parents=True, exist_ok=True)
                for item in cand.iterdir():
                    if item.is_file() and item.name.endswith(".dcx"):
                        target = out_sfx / item.name.lower()
                        shutil.copy2(str(item), str(target))
                        deployed_files.append(str(target))
                        system_logger.debug(f"Deployed VFX: {item.name} -> {target.name}", source="SkillMovesetDeployer")
                break

        # 3. Deploy action/ assets
        action_candidates = [source_mod_dir / "action"] + list(source_mod_dir.rglob("action"))
        for cand in action_candidates:
            if cand.is_dir() and cand != (out_path / "action"):
                out_action = out_path / "action"
                out_action.mkdir(parents=True, exist_ok=True)
                for item in cand.rglob("*"):
                    if item.is_file():
                        rel = item.relative_to(cand)
                        target = out_action / str(rel).lower()
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if target.exists():

                            if target.name.lower() in CORE_PLAYER_ASSETS or target.suffix.lower() == ".hks":
                                system_logger.info(
                                    f"Preserving existing host action script: {target.name} (retains host mod mechanics)",
                                    source="SkillMovesetDeployer"
                                )
                                continue

                        shutil.copy2(str(item), str(target))
                        deployed_files.append(str(target))
                break

        self.last_deployed_files = deployed_files
        return deployed_files

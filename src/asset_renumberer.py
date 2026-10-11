"""
Asset renumberer and isolation engine for LootForge.

Stages replacement 3D model files into the output mod directory using newly allocated
standalone IDs, ensuring original vanilla game assets remain untouched.
"""

import shutil
from pathlib import Path
from typing import List, Tuple
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

    def stage_mod_set(self, input_base: str, mod_set: DetectedModSet) -> List[str]:
        """
        Copies each part file of the mod set to the output parts directory,
        renaming the model ID token to the allocated standalone ID.
        """
        if not mod_set.allocation:
            raise ValueError(f"ModSet '{mod_set.set_id}' has no allocated standalone IDs.")

        new_model_id = mod_set.allocation.new_model_id
        input_root = Path(input_base)
        staged_files: List[str] = []

        for part in mod_set.parts:
            source_file = input_root / part.relative_path
            if not source_file.exists():
                system_logger.warning(f"Source asset not found: {source_file}", source="AssetRenumberer")
                continue

            # Compute new filename by substituting target_model_id with new_model_id
            old_name = part.file_name
            # Replace target_model_id suffix before .partsbnd.dcx
            new_name = old_name.replace(part.target_model_id, new_model_id)
            dest_file = self._parts_dir / new_name

            shutil.copy2(source_file, dest_file)
            staged_files.append(str(dest_file.relative_to(self._output_dir)))

            system_logger.debug(
                f"Renumbered and staged: {old_name} -> {new_name}",
                source="AssetRenumberer"
            )

        system_logger.info(
            f"Staged {len(staged_files)} part file(s) for '{mod_set.set_id}' as Model ID {new_model_id}",
            source="AssetRenumberer"
        )
        return staged_files

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

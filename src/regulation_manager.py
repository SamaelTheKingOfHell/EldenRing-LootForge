"""
Regulation Manager for LootForge.

Orchestrates Elden Ring regulation.bin decryption, param patching, and AES-256 re-encryption
via RegTool (built on SoulsFormats and Paramdex).
"""

import os
import sys
import json
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from src.logger import system_logger


class RegulationManager:
    """
    Manages the lifecycle of Elden Ring regulation.bin files:
    discovering source regulations, resolving staging targets, and executing
    non-destructive param injections.
    """

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir).resolve()
        self.defs_dir = self.base_dir / "tools" / "vendor" / "Paramdex" / "ER" / "Defs"
        self.regtool_exe = self.base_dir / "tools" / "RegTool" / "bin" / "Release" / "net9.0" / "RegTool.exe"
        self.regtool_dll = self.base_dir / "tools" / "RegTool" / "bin" / "Release" / "net9.0" / "RegTool.dll"
        self.regtool_proj = self.base_dir / "tools" / "RegTool" / "RegTool.csproj"

    def backup_game_assets(self, game_dir: str) -> None:
        """
        Backs up vanilla regulation.bin and extracts msg folder from Data0.bdt
        to the backups/ folder, allowing LootForge to work without needing
        the game installation path in the future.
        """
        if not game_dir:
            return

        game_path = Path(game_dir)
        backups_dir = self.base_dir / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)

        # Copy Oodle compression DLL if needed by RegTool
        # Try version 9, 8, or 6
        for oodle_version in ["oo2core_9_win64.dll", "oo2core_8_win64.dll", "oo2core_6_win64.dll"]:
            oodle_dll = game_path / oodle_version
            if oodle_dll.exists():
                # Copy to RegTool directory
                regtool_dir = self.regtool_exe.parent if self.regtool_exe.exists() else self.regtool_dll.parent
                target_oodle = regtool_dir / oodle_version
                if not target_oodle.exists():
                    shutil.copy2(oodle_dll, target_oodle)
                    system_logger.info(f"Copied {oodle_version} to RegTool directory", source="RegulationManager")
                break

        # Backup regulation.bin if not already backed up
        game_reg = game_path / "regulation.bin"
        if game_reg.exists():
            existing_backups = list(backups_dir.glob("regulation.bin.bak_*"))
            if not existing_backups:
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = backups_dir / f"regulation.bin.bak_{timestamp}"
                shutil.copy2(game_reg, backup_path)
                system_logger.info(f"Backed up regulation.bin to: {backup_path}", source="RegulationManager")

        # Extract or copy msg folder
        backup_msg = backups_dir / "msg" / "engUS"
        if not (backup_msg / "item.msgbnd.dcx").exists():
            # First, check if we have a bundled copy in data/
            bundled_msg = self.base_dir / "data" / "item.msgbnd.dcx"
            if bundled_msg.exists():
                system_logger.info("Copying bundled item.msgbnd.dcx from data/ folder...", source="RegulationManager")
                backup_msg.mkdir(parents=True, exist_ok=True)
                shutil.copy2(bundled_msg, backup_msg / "item.msgbnd.dcx")
                system_logger.info(f"Copied item.msgbnd.dcx to: {backup_msg}", source="RegulationManager")
                return

            # If no bundled copy, try extracting from game files
            system_logger.info("Extracting item.msgbnd.dcx from Data0.bdt...", source="RegulationManager")
            
            msg_output = backups_dir / "msg"
            
            if sys.platform.startswith("win") and self.regtool_exe.exists():
                cmd = [str(self.regtool_exe), "extract-msg", "--game-dir", str(game_path), "--output", str(msg_output)]
            elif self.regtool_dll.exists():
                cmd = ["dotnet", str(self.regtool_dll), "extract-msg", "--game-dir", str(game_path), "--output", str(msg_output)]
            else:
                cmd = ["dotnet", "run", "--project", str(self.regtool_proj), "--", "extract-msg", "--game-dir", str(game_path), "--output", str(msg_output)]
            
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(self.base_dir), check=False)
                
                if res.returncode == 0:
                    system_logger.info(f"Successfully extracted item.msgbnd.dcx to: {backup_msg}", source="RegulationManager")
                else:
                    system_logger.warning(
                        f"Failed to extract item.msgbnd.dcx: {res.stderr or res.stdout}\n"
                        "FMG text injection will be skipped. Items will show as ?ProtectorName? in-game.",
                        source="RegulationManager"
                    )
            except Exception as e:
                system_logger.warning(f"Could not extract msg files: {e}", source="RegulationManager")

    def resolve_source_regulation(
        self,
        active_path: str = "",
        game_dir: str = "",
        output_dir: str = ""
    ) -> Optional[Path]:
        """
        Locates the best source regulation.bin to read from.
        Priority:
        1. Explicitly configured and existing active_path
        2. Existing regulation.bin in output_dir (e.g. mod/regulation.bin)
        3. Vanilla regulation.bin in game_dir (e.g. Game/regulation.bin)
        4. Any regulation backup in backups/
        """
        candidates = []

        if active_path:
            p = Path(active_path)
            if not p.is_absolute():
                p = self.base_dir / p
            candidates.append(p)

        if output_dir:
            p = Path(output_dir) / "regulation.bin"
            if not p.is_absolute():
                p = self.base_dir / p
            candidates.append(p)

        if game_dir:
            candidates.append(Path(game_dir) / "regulation.bin")

        # Fallback to backups if available
        backups_dir = self.base_dir / "backups"
        if backups_dir.exists():
            baks = sorted(backups_dir.glob("regulation.bin.bak_*"), key=lambda f: f.stat().st_mtime, reverse=True)
            candidates.extend(baks)

        for cand in candidates:
            if cand.exists() and cand.stat().st_size > 100000:
                system_logger.info(f"Resolved source regulation.bin at: {cand}", source="RegulationManager")
                return cand

        return None

    def resolve_target_regulation(
        self,
        active_path: str = "",
        output_dir: str = "mod",
        game_dir: str = ""
    ) -> Path:
        """
        Resolves the target path where the patched regulation.bin should be created.
        
        If the user has an active regulation.bin that is NOT the vanilla game copy,
        output is placed in the same folder automatically.
        Safety Rule: If the user selected the vanilla Game/regulation.bin, we redirect
        to the mod/ folder so the vanilla game is never ruined.
        """
        out_folder = Path(output_dir)
        if not out_folder.is_absolute():
            out_folder = self.base_dir / out_folder

        if active_path:
            p = Path(active_path)
            if not p.is_absolute():
                p = self.base_dir / p

            # Safety: if user targeted vanilla game folder directly, redirect
            if game_dir and p.resolve() == (Path(game_dir) / "regulation.bin").resolve():
                target = out_folder / "regulation.bin"
                system_logger.info(
                    f"Redirecting output from vanilla game folder to mod staging folder: {target}",
                    source="RegulationManager"
                )
                return target

            # Auto-place in the same folder as the active regulation.bin
            target = p.parent / "regulation.bin"
            system_logger.info(
                f"Auto-placing output in active regulation folder: {target}",
                source="RegulationManager"
            )
            return target

        # Default: mod/regulation.bin
        return out_folder / "regulation.bin"

    def execute_patch(
        self,
        specs: List[Dict[str, Any]],
        source_reg: Path,
        target_reg: Path,
        game_dir: str = ""
    ) -> Dict[str, Any]:
        """
        Executes RegTool to inject patch specifications into target regulation.bin.
        Non-destructive: never clears existing vanilla drops or parameters.

        If game_dir is provided, also injects FMG text entries (item names,
        descriptions, icons) into the game's item.msgbnd.dcx.
        """
        if not source_reg.exists():
            raise FileNotFoundError(f"Source regulation not found: {source_reg}")

        if not self.defs_dir.exists():
            raise FileNotFoundError(f"Paramdex definitions directory not found: {self.defs_dir}")

        target_reg.parent.mkdir(parents=True, exist_ok=True)

        # Ensure Oodle DLL is available for RegTool
        if game_dir:
            game_path = Path(game_dir)
            # Try version 9, 8, or 6
            for oodle_version in ["oo2core_9_win64.dll", "oo2core_8_win64.dll", "oo2core_6_win64.dll"]:
                oodle_dll = game_path / oodle_version
                if oodle_dll.exists():
                    # Copy to RegTool directory
                    regtool_dir = self.regtool_exe.parent if self.regtool_exe.exists() else self.regtool_dll.parent
                    target_oodle = regtool_dir / oodle_version
                    if not target_oodle.exists():
                        shutil.copy2(oodle_dll, target_oodle)
                        system_logger.info(f"Copied {oodle_version} to RegTool directory", source="RegulationManager")
                    break

        # Resolve msg directory for FMG text injection
        msg_dir = self._resolve_msg_dir(game_dir, target_reg)

        # Write specs to temporary JSON file
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf:
            json.dump(specs, tf, indent=2)
            temp_spec_path = tf.name

        try:
            # Build command line for RegTool
            base_args = [
                "patch",
                "--input", str(source_reg),
                "--output", str(target_reg),
                "--defs", str(self.defs_dir),
                "--spec", temp_spec_path
            ]

            # Add --msg for FMG text injection if msg directory exists
            if msg_dir:
                base_args.extend(["--msg", str(msg_dir)])
                system_logger.info(f"FMG source directory: {msg_dir}", source="RegulationManager")

            if sys.platform.startswith("win") and self.regtool_exe.exists():
                cmd = [str(self.regtool_exe)] + base_args
            elif self.regtool_dll.exists():
                cmd = ["dotnet", str(self.regtool_dll)] + base_args
            else:
                cmd = ["dotnet", "run", "--project", str(self.regtool_proj), "--"] + base_args

            system_logger.info(f"Running RegTool command: {' '.join(cmd)}", source="RegulationManager")

            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(self.base_dir),
                check=False
            )

            if res.returncode != 0:
                err_msg = res.stderr or res.stdout
                system_logger.error(f"RegTool execution failed (code {res.returncode}): {err_msg}", source="RegulationManager")
                raise RuntimeError(f"RegTool failed: {err_msg}")

            system_logger.info(f"RegTool stdout: {res.stdout.strip()}", source="RegulationManager")

            if not target_reg.exists() or target_reg.stat().st_size < 100000:
                raise RuntimeError(f"RegTool completed but target regulation was not created or is invalid: {target_reg}")

            return {
                "success": True,
                "source_path": str(source_reg),
                "target_path": str(target_reg),
                "target_size_bytes": target_reg.stat().st_size,
                "log": res.stdout.strip()
            }
        finally:
            if os.path.exists(temp_spec_path):
                try:
                    os.remove(temp_spec_path)
                except Exception:
                    pass

    def _resolve_msg_dir(self, game_dir: str, target_reg: Path) -> Optional[Path]:
        """
        Ensures the mod output directory has a vanilla item.msgbnd.dcx to modify.
        Copies from backups or game directory if needed, then returns the mod msg path.

        This makes the mod self-contained and portable.
        """
        mod_msg = target_reg.parent / "msg" / "engUS"
        mod_item_msgbnd = mod_msg / "item.msgbnd.dcx"

        # If mod already has item.msgbnd.dcx, use it (preserves existing modifications)
        if mod_item_msgbnd.exists():
            system_logger.info(f"Using existing item.msgbnd.dcx at: {mod_msg}", source="RegulationManager")
            return mod_msg

        # Otherwise, copy vanilla item.msgbnd.dcx to mod directory
        vanilla_source = None

        # Try backups first (allows working without game installation)
        backup_msg = self.base_dir / "backups" / "msg" / "engUS" / "item.msgbnd.dcx"
        if backup_msg.exists():
            vanilla_source = backup_msg
            system_logger.info(f"Copying vanilla item.msgbnd.dcx from backups to mod directory...", source="RegulationManager")

        # Fall back to game directory
        elif game_dir:
            game_msg = Path(game_dir) / "msg" / "engUS" / "item.msgbnd.dcx"
            if game_msg.exists():
                vanilla_source = game_msg
                system_logger.info(f"Copying vanilla item.msgbnd.dcx from game directory to mod...", source="RegulationManager")

        if vanilla_source:
            mod_msg.mkdir(parents=True, exist_ok=True)
            shutil.copy2(vanilla_source, mod_item_msgbnd)
            system_logger.info(f"Vanilla item.msgbnd.dcx copied to: {mod_item_msgbnd}", source="RegulationManager")
            return mod_msg

        system_logger.warning("No vanilla item.msgbnd.dcx found to copy. FMG text injection will be skipped.", source="RegulationManager")
        return None

    def deploy_parts(
        self,
        mod_sets: list,
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

        deployed = 0
        for ms in mod_sets:
            if not ms.allocation or not ms.is_enabled:
                continue
            for part in ms.parts:
                source = input_base_dir / ms.folder_or_archive_name / part.relative_path
                if not source.exists():
                    # Also try without the folder name (flat input layout)
                    source = input_base_dir / part.relative_path
                if not source.exists():
                    system_logger.warning(
                        f"Parts file not found: {source} (set: {ms.set_id})",
                        source="RegulationManager"
                    )
                    continue

                # Rename with standalone model ID
                target_name = part.file_name.replace(
                    part.target_model_id, ms.allocation.new_model_id, 1
                )
                target = parts_output / target_name
                shutil.copy2(str(source), str(target))
                deployed += 1
                system_logger.debug(
                    f"Deployed: {part.file_name} -> {target_name}",
                    source="RegulationManager"
                )

        system_logger.info(
            f"Deployed {deployed} parts file(s) to {parts_output}",
            source="RegulationManager"
        )
        return deployed


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
        game_dir: str = "",
        boss_loot_pools_enabled: bool = True,
        boss_weapons_per_pool: int = 3,
        sweep_vanilla_items: bool = False
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
            json.dump(specs, tf, separators=(',', ':'))
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

            # Automatically inject progression-tier weapon loot pools for all bosses if enabled
            if boss_loot_pools_enabled:
                try:
                    boss_cmd = [str(self.regtool_exe)] if (sys.platform.startswith("win") and self.regtool_exe.exists()) else (
                        ["dotnet", str(self.regtool_dll)] if self.regtool_dll.exists() else
                        ["dotnet", "run", "--project", str(self.regtool_proj), "--"]
                    )
                    boss_cmd.extend([
                        "inject-boss-loot-pools",
                        "--input", str(target_reg),
                        "--output", str(target_reg),
                        "--defs", str(self.defs_dir),
                        "--count", str(max(1, min(5, boss_weapons_per_pool)))
                    ])
                    b_res = subprocess.run(boss_cmd, capture_output=True, text=True, cwd=str(self.base_dir), check=False)
                    if b_res.returncode == 0:
                        system_logger.info("Enriched all bosses with progression-tier weapon loot pools.", source="RegulationManager")
                    else:
                        system_logger.warning(f"Boss loot pool injection returned code {b_res.returncode}: {b_res.stderr or b_res.stdout}", source="RegulationManager")
                except Exception as be:
                    system_logger.warning(f"Boss loot pool notice: {be}", source="RegulationManager")

            # Automatically sweep and infuse all vanilla items across EquipParamWeapon, EquipParamProtector, and FMGs
            if sweep_vanilla_items:
                try:
                    sweep_cmd = [str(self.regtool_exe)] if (sys.platform.startswith("win") and self.regtool_exe.exists()) else (
                        ["dotnet", str(self.regtool_dll)] if self.regtool_dll.exists() else
                        ["dotnet", "run", "--project", str(self.regtool_proj), "--"]
                    )
                    sweep_cmd.extend([
                        "sweep-vanilla",
                        "--input", str(target_reg),
                        "--output", str(target_reg),
                        "--defs", str(self.defs_dir),
                    ])
                    if msg_dir:
                        sweep_cmd.extend(["--msg", str(msg_dir)])
                    s_res = subprocess.run(sweep_cmd, capture_output=True, text=True, cwd=str(self.base_dir), check=False)
                    if s_res.returncode == 0:
                        system_logger.info("Successfully swept and infused all vanilla items across the regulation file.", source="RegulationManager")
                    else:
                        system_logger.warning(f"Vanilla sweeper returned code {s_res.returncode}: {s_res.stderr or s_res.stdout}", source="RegulationManager")
                except Exception as se:
                    system_logger.warning(f"Vanilla sweeper notice: {se}", source="RegulationManager")

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
        if not (mod_msg / "item.msgbnd.dcx").exists():
            mod_msg_lower = target_reg.parent / "msg" / "engus"
            if (mod_msg_lower / "item.msgbnd.dcx").exists():
                mod_msg = mod_msg_lower

        mod_item_msgbnd = mod_msg / "item.msgbnd.dcx"

        # If mod already has item.msgbnd.dcx, use it (preserves existing modifications)
        if mod_item_msgbnd.exists():
            system_logger.info(f"Using existing item.msgbnd.dcx at: {mod_msg}", source="RegulationManager")
            return mod_msg

        # Otherwise, copy vanilla item.msgbnd.dcx to mod directory
        vanilla_source = None
        dlc_source = None

        # Try backups first (allows working without game installation)
        backup_msg = self.base_dir / "backups" / "msg" / "engUS" / "item.msgbnd.dcx"
        if backup_msg.exists():
            vanilla_source = backup_msg
            system_logger.info("Copying vanilla item.msgbnd.dcx from backups to mod directory...", source="RegulationManager")

        # Fall back to game directory
        elif game_dir:
            for lang in ["engUS", "engus"]:
                candidate = Path(game_dir) / "msg" / lang / "item.msgbnd.dcx"
                if candidate.exists():
                    vanilla_source = candidate
                    system_logger.info(f"Copying vanilla item.msgbnd.dcx from game directory ({lang}) to mod...", source="RegulationManager")
                    dlc_cand = Path(game_dir) / "msg" / lang / "item_dlc02.msgbnd.dcx"
                    if dlc_cand.exists():
                        dlc_source = dlc_cand
                    break

        if vanilla_source:
            mod_msg.mkdir(parents=True, exist_ok=True)
            shutil.copy2(vanilla_source, mod_item_msgbnd)
            system_logger.info(f"Vanilla item.msgbnd.dcx copied to: {mod_item_msgbnd}", source="RegulationManager")

            # Also copy DLC msgbnd if present
            if dlc_source and not (mod_msg / "item_dlc02.msgbnd.dcx").exists():
                shutil.copy2(dlc_source, mod_msg / "item_dlc02.msgbnd.dcx")
                system_logger.info(f"DLC item_dlc02.msgbnd.dcx copied to: {mod_msg / 'item_dlc02.msgbnd.dcx'}", source="RegulationManager")

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
        Delegates parts deployment and renaming to PartsDeployer service.
        Preserves backwards compatibility for existing callers.
        """
        from src.parts_deployer import PartsDeployer
        deployer = PartsDeployer()
        count = deployer.deploy_parts(mod_sets, input_base_dir, output_dir)
        self.last_deployed_files = getattr(deployer, "last_deployed_files", [])
        return count

    def rollback_all(
        self,
        backup_manager: Any,
        manifest_store: Any,
        target_reg_path: Optional[str] = None,
        output_dir: Optional[str] = None,
        asset_renumberer: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Comprehensively reverts all injected mod assets, parameters, and message files
        across both the active profile directory and the local staging directory.
        """
        restored_files: List[str] = []
        removed_files: List[str] = []
        errors: List[str] = []

        # 1. Resolve target regulation path
        target_path_str = target_reg_path or getattr(manifest_store, "target_regulation_path", None)
        target_reg = Path(target_path_str) if target_path_str else None
        target_dir = target_reg.parent if target_reg else None

        local_out_dir = Path(output_dir) if output_dir else self.base_dir / "mod"
        if not local_out_dir.is_absolute():
            local_out_dir = self.base_dir / local_out_dir

        # 2. Restore or clean regulation.bin
        if target_reg:
            try:
                backups = backup_manager.list_backups_for_file("regulation.bin")
                if backups:
                    backup_manager.restore_latest_backup(str(target_reg))
                    restored_files.append(str(target_reg))
                    system_logger.info(f"Restored regulation.bin at {target_reg}", source="Rollback")
                elif target_reg.exists():
                    try:
                        if target_reg.resolve().is_relative_to(local_out_dir.resolve()):
                            target_reg.unlink()
                            removed_files.append(str(target_reg))
                            system_logger.info(f"Removed forged regulation.bin at {target_reg}", source="Rollback")
                    except Exception:
                        pass
            except Exception as e:
                errors.append(f"Regulation restore failed ({target_reg}): {e}")

        # Local output regulation if different from target_reg
        local_reg = local_out_dir / "regulation.bin"
        if local_reg.exists():
            try:
                if not target_reg or local_reg.resolve() != target_reg.resolve():
                    local_reg.unlink()
                    removed_files.append(str(local_reg))
            except Exception as e:
                errors.append(f"Failed to remove local staged regulation ({local_reg}): {e}")

        # 3. Clean and restore message files (.msgbnd.dcx)
        created_msg_files = getattr(manifest_store, "created_msg_files", [])
        for cmf in created_msg_files:
            p = Path(cmf)
            if p.exists():
                try:
                    p.unlink()
                    removed_files.append(str(p))
                    system_logger.info(f"Removed created msg file: {p}", source="Rollback")
                except Exception as e:
                    errors.append(f"Failed to remove created msg file ({p}): {e}")

        backed_up_files = getattr(manifest_store, "backed_up_files", {})
        for orig_path_str, bak_name in backed_up_files.items():
            orig_p = Path(orig_path_str)
            try:
                backup_manager.restore_backup_file(bak_name, str(orig_p))
                restored_files.append(str(orig_p))
                system_logger.info(f"Restored msg file from {bak_name} to {orig_p}", source="Rollback")
            except Exception as e:
                errors.append(f"Failed to restore {orig_p} from {bak_name}: {e}")

        msg_dirs_to_check = set()
        if target_dir:
            msg_dirs_to_check.add(target_dir / "msg")
        msg_dirs_to_check.add(local_out_dir / "msg")

        for md in msg_dirs_to_check:
            if not md.exists():
                continue
            for lang in ["engUS", "engus"]:
                lang_dir = md / lang
                if not lang_dir.exists():
                    continue
                for fname in ["item.msgbnd.dcx", "item_dlc02.msgbnd.dcx", "item_dlc01.msgbnd.dcx"]:
                    msg_file = lang_dir / fname
                    if msg_file.exists() and str(msg_file) not in restored_files and str(msg_file) not in removed_files:
                        baks = backup_manager.list_backups_for_file(fname)
                        if baks:
                            try:
                                backup_manager.restore_latest_backup_for_file(str(msg_file))
                                restored_files.append(str(msg_file))
                            except Exception as e:
                                errors.append(f"Failed to restore {msg_file}: {e}")
                        else:
                            try:
                                if md.resolve().is_relative_to(local_out_dir.resolve()):
                                    msg_file.unlink()
                                    removed_files.append(str(msg_file))
                            except Exception as e:
                                errors.append(f"Failed to remove {msg_file}: {e}")

                try:
                    if lang_dir.exists() and not any(lang_dir.iterdir()):
                        lang_dir.rmdir()
                except Exception:
                    pass

            try:
                if md.exists() and not any(md.iterdir()):
                    md.rmdir()
            except Exception:
                pass

        # 4. Clean deployed & staged 3D parts (.partsbnd.dcx)
        deployed_files = getattr(manifest_store, "deployed_files", [])
        for df in deployed_files:
            p = Path(df)
            if p.exists() and str(p) not in removed_files:
                try:
                    p.unlink()
                    removed_files.append(str(p))
                    system_logger.info(f"Removed deployed part: {p}", source="Rollback")
                except Exception as e:
                    errors.append(f"Failed to remove deployed part ({p}): {e}")

        records = manifest_store.get_all_records() if hasattr(manifest_store, "get_all_records") else []
        allocated_model_ids = {r.allocated_model_id for r in records if getattr(r, "allocated_model_id", None)}

        if asset_renumberer:
            for rec in records:
                try:
                    asset_renumberer.cleanup_files(rec.staged_files)
                except Exception as e:
                    errors.append(f"Failed to cleanup staged files for {rec.set_id}: {e}")

        for rec in records:
            for staged in rec.staged_files:
                for base in [target_dir, local_out_dir]:
                    if base:
                        sp = base / staged
                        if sp.exists() and str(sp) not in removed_files:
                            try:
                                sp.unlink()
                                removed_files.append(str(sp))
                            except Exception as e:
                                errors.append(f"Failed to remove {sp}: {e}")

        parts_dirs_to_clean = set()
        if target_dir:
            parts_dirs_to_clean.add(target_dir / "parts")
        parts_dirs_to_clean.add(local_out_dir / "parts")

        for pd in parts_dirs_to_clean:
            if not pd.exists():
                continue
            for f in list(pd.glob("*.partsbnd.dcx")):
                if any(mid in f.name for mid in allocated_model_ids):
                    if str(f) not in removed_files:
                        try:
                            f.unlink()
                            removed_files.append(str(f))
                            system_logger.info(f"Removed allocated part matching model ID: {f}", source="Rollback")
                        except Exception as e:
                            errors.append(f"Failed to remove {f}: {e}")

            try:
                if pd.exists() and not any(pd.iterdir()):
                    pd.rmdir()
            except Exception:
                pass

        # 5. Clear manifest
        if hasattr(manifest_store, "clear"):
            manifest_store.clear()

        return {
            "success": len(errors) == 0,
            "restored_files": list(set(restored_files)),
            "removed_files": list(set(removed_files)),
            "errors": errors
        }

    def introspect_world(
        self,
        reg_path: Path,
        msg_dir: Optional[Path] = None,
        output_json: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Executes RegTool's smart introspection service on regulation.bin,
        extracting all valid weapons, armor, accessories, and boss encounter lots.
        """
        if not reg_path.exists():
            raise FileNotFoundError(f"Regulation file not found: {reg_path}")

        out_path = output_json or (self.base_dir / "data" / "world_snapshot.json")
        cmd = [str(self.regtool_exe)] if (sys.platform.startswith("win") and self.regtool_exe.exists()) else (
            ["dotnet", str(self.regtool_dll)] if self.regtool_dll.exists() else
            ["dotnet", "run", "--project", str(self.regtool_proj), "--"]
        )
        cmd.extend([
            "introspect-world",
            "--input", str(reg_path),
            "--defs", str(self.defs_dir),
            "--output", str(out_path)
        ])
        if msg_dir and Path(msg_dir).exists():
            cmd.extend(["--msg", str(msg_dir)])

        res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(self.base_dir), check=False)
        if res.returncode != 0:
            system_logger.warning(f"Introspect world returned non-zero code {res.returncode}: {res.stderr or res.stdout}", source="RegulationManager")

        if out_path.exists():
            try:
                with open(out_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                system_logger.warning(f"Failed to load world snapshot JSON: {e}", source="RegulationManager")

        return {}

    def sweep_vanilla_items(
        self,
        reg_path: Path,
        msg_dir: Optional[Path] = None
    ) -> bool:
        """
        Executes universal sweeper on target regulation.bin, infusing all
        vanilla weapons, armor, and accessories with Diablo stats and FMG text.
        """
        if not reg_path.exists():
            raise FileNotFoundError(f"Regulation file not found: {reg_path}")

        cmd = [str(self.regtool_exe)] if (sys.platform.startswith("win") and self.regtool_exe.exists()) else (
            ["dotnet", str(self.regtool_dll)] if self.regtool_dll.exists() else
            ["dotnet", "run", "--project", str(self.regtool_proj), "--"]
        )
        cmd.extend([
            "sweep-vanilla",
            "--input", str(reg_path),
            "--output", str(reg_path),
            "--defs", str(self.defs_dir)
        ])
        if msg_dir and Path(msg_dir).exists():
            cmd.extend(["--msg", str(msg_dir)])

        res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(self.base_dir), check=False)
        return res.returncode == 0


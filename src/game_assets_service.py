"""
Game assets service for LootForge.
Handles regulation discovery, backup management, msg extraction, and Oodle DLL setup.
Complies with [CS-MODULAR] and [CS-GRANULARITY] (<= 300 lines).
"""

import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional
from src.logger import system_logger


class GameAssetsService:
    """
    Manages game assets, regulation resolution, backup extraction, and compression libraries.
    """

    OODLE_DLL_CANDIDATES = ["oo2core_9_win64.dll", "oo2core_8_win64.dll", "oo2core_6_win64.dll"]

    @classmethod
    def ensure_oodle_copied(cls, game_dir: str, regtool_dir: Path) -> None:
        """Copies Oodle compression DLL from game directory to RegTool directory if missing."""
        if not game_dir:
            return
        game_path = Path(game_dir)
        for oodle_version in cls.OODLE_DLL_CANDIDATES:
            oodle_dll = game_path / oodle_version
            if oodle_dll.exists():
                target_oodle = regtool_dir / oodle_version
                if not target_oodle.exists():
                    shutil.copy2(oodle_dll, target_oodle)
                    system_logger.info(f"Copied {oodle_version} to RegTool directory", source="GameAssetsService")
                break

    @classmethod
    def backup_game_assets(
        cls,
        base_dir: Path,
        game_dir: str,
        regtool_exe: Path,
        regtool_dll: Path,
        regtool_proj: Path
    ) -> None:
        """
        Backs up vanilla regulation.bin and extracts msg folder from Data0.bdt.
        """
        if not game_dir:
            return

        game_path = Path(game_dir)
        backups_dir = base_dir / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)

        regtool_dir = regtool_exe.parent if regtool_exe.exists() else regtool_dll.parent
        cls.ensure_oodle_copied(game_dir, regtool_dir)

        # Backup regulation.bin if not already backed up
        game_reg = game_path / "regulation.bin"
        if game_reg.exists():
            existing_backups = list(backups_dir.glob("regulation.bin.bak_*"))
            if not existing_backups:
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = backups_dir / f"regulation.bin.bak_{timestamp}"
                shutil.copy2(game_reg, backup_path)
                system_logger.info(f"Backed up regulation.bin to: {backup_path}", source="GameAssetsService")

        # Extract or copy msg folder
        backup_msg = backups_dir / "msg" / "engUS"
        if not (backup_msg / "item.msgbnd.dcx").exists():
            bundled_msg = base_dir / "data" / "item.msgbnd.dcx"
            if bundled_msg.exists():
                system_logger.info("Copying bundled item.msgbnd.dcx from data/ folder...", source="GameAssetsService")
                backup_msg.mkdir(parents=True, exist_ok=True)
                shutil.copy2(bundled_msg, backup_msg / "item.msgbnd.dcx")
                system_logger.info(f"Copied item.msgbnd.dcx to: {backup_msg}", source="GameAssetsService")
                return

            system_logger.info("Extracting item.msgbnd.dcx from Data0.bdt...", source="GameAssetsService")
            msg_output = backups_dir / "msg"

            if sys.platform.startswith("win") and regtool_exe.exists():
                cmd = [str(regtool_exe), "extract-msg", "--game-dir", str(game_path), "--output", str(msg_output)]
            elif regtool_dll.exists():
                cmd = ["dotnet", str(regtool_dll), "extract-msg", "--game-dir", str(game_path), "--output", str(msg_output)]
            else:
                cmd = ["dotnet", "run", "--project", str(regtool_proj), "--", "extract-msg", "--game-dir", str(game_path), "--output", str(msg_output)]

            try:
                res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(base_dir), check=False)
                if res.returncode == 0:
                    system_logger.info(f"Successfully extracted item.msgbnd.dcx to: {backup_msg}", source="GameAssetsService")
                else:
                    system_logger.warning(
                        f"Failed to extract item.msgbnd.dcx: {res.stderr or res.stdout}\n"
                        "FMG text injection will be skipped. Items will show as ?ProtectorName? in-game.",
                        source="GameAssetsService"
                    )
            except Exception as e:
                system_logger.warning(f"Could not extract msg files: {e}", source="GameAssetsService")

    @classmethod
    def resolve_source_regulation(
        cls,
        base_dir: Path,
        active_path: str = "",
        game_dir: str = "",
        output_dir: str = ""
    ) -> Optional[Path]:
        """Locates the best source regulation.bin to read from."""
        candidates = []

        if active_path:
            p = Path(active_path)
            if not p.is_absolute():
                p = base_dir / p
            candidates.append(p)

        if output_dir:
            p = Path(output_dir) / "regulation.bin"
            if not p.is_absolute():
                p = base_dir / p
            candidates.append(p)

        if game_dir:
            candidates.append(Path(game_dir) / "regulation.bin")

        backups_dir = base_dir / "backups"
        if backups_dir.exists():
            baks = sorted(backups_dir.glob("regulation.bin.bak_*"), key=lambda f: f.stat().st_mtime, reverse=True)
            candidates.extend(baks)

        for cand in candidates:
            if cand.exists() and cand.stat().st_size > 100000:
                system_logger.info(f"Resolved source regulation.bin at: {cand}", source="GameAssetsService")
                return cand

        return None

    @classmethod
    def resolve_target_regulation(
        cls,
        base_dir: Path,
        active_path: str = "",
        output_dir: str = "mod",
        game_dir: str = ""
    ) -> Path:
        """Resolves target regulation path, preventing accidental overwrite of retail game folder."""
        out_folder = Path(output_dir)
        if not out_folder.is_absolute():
            out_folder = base_dir / out_folder

        if active_path:
            p = Path(active_path)
            if not p.is_absolute():
                p = base_dir / p

            if game_dir and p.resolve() == (Path(game_dir) / "regulation.bin").resolve():
                target = out_folder / "regulation.bin"
                system_logger.info(
                    f"Redirecting output from vanilla game folder to mod staging folder: {target}",
                    source="GameAssetsService"
                )
                return target

            target = p.parent / "regulation.bin"
            system_logger.info(
                f"Auto-placing output in active regulation folder: {target}",
                source="GameAssetsService"
            )
            return target

        return out_folder / "regulation.bin"

    @classmethod
    def resolve_msg_dir(cls, base_dir: Path, game_dir: str, target_reg: Path) -> Optional[Path]:
        """Ensures the mod output directory has a vanilla item.msgbnd.dcx to modify."""
        mod_msg = target_reg.parent / "msg" / "engUS"
        if not (mod_msg / "item.msgbnd.dcx").exists():
            mod_msg_lower = target_reg.parent / "msg" / "engus"
            if (mod_msg_lower / "item.msgbnd.dcx").exists():
                mod_msg = mod_msg_lower

        mod_item_msgbnd = mod_msg / "item.msgbnd.dcx"

        if mod_item_msgbnd.exists():
            system_logger.info(f"Using existing item.msgbnd.dcx at: {mod_msg}", source="GameAssetsService")
            return mod_msg

        vanilla_source = None
        dlc_source = None

        backup_msg = base_dir / "backups" / "msg" / "engUS" / "item.msgbnd.dcx"
        if backup_msg.exists():
            vanilla_source = backup_msg
            system_logger.info("Copying vanilla item.msgbnd.dcx from backups to mod directory...", source="GameAssetsService")

        elif game_dir:
            for lang in ["engUS", "engus"]:
                candidate = Path(game_dir) / "msg" / lang / "item.msgbnd.dcx"
                if candidate.exists():
                    vanilla_source = candidate
                    system_logger.info(f"Copying vanilla item.msgbnd.dcx from game directory ({lang}) to mod...", source="GameAssetsService")
                    dlc_cand = Path(game_dir) / "msg" / lang / "item_dlc02.msgbnd.dcx"
                    if dlc_cand.exists():
                        dlc_source = dlc_cand
                    break

        if vanilla_source:
            mod_msg.mkdir(parents=True, exist_ok=True)
            shutil.copy2(vanilla_source, mod_item_msgbnd)
            system_logger.info(f"Vanilla item.msgbnd.dcx copied to: {mod_item_msgbnd}", source="GameAssetsService")

            if dlc_source and not (mod_msg / "item_dlc02.msgbnd.dcx").exists():
                shutil.copy2(dlc_source, mod_msg / "item_dlc02.msgbnd.dcx")
                system_logger.info(f"DLC item_dlc02.msgbnd.dcx copied to: {mod_msg / 'item_dlc02.msgbnd.dcx'}", source="GameAssetsService")

            return mod_msg

        system_logger.warning("No vanilla item.msgbnd.dcx found to copy. FMG text injection will be skipped.", source="GameAssetsService")
        return None

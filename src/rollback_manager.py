"""
Rollback Manager for LootForge.
Reverts injected mod assets, parameters, message files, and moveset files.
Complies with [CS-MODULAR] and [CS-GRANULARITY] (<= 300 lines).
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
from src.logger import system_logger


class RollbackManager:
    """
    Comprehensively reverts all injected mod assets, parameters, and message files
    across both the active profile directory and the local staging directory.
    """

    @classmethod
    def rollback_all(
        cls,
        base_dir: Path,
        backup_manager: Any,
        manifest_store: Any,
        target_reg_path: Optional[str] = None,
        output_dir: Optional[str] = None,
        asset_renumberer: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Reverts all injected mod assets, parameters, and message files.
        """
        restored_files: List[str] = []
        removed_files: List[str] = []
        errors: List[str] = []

        # 1. Resolve target regulation path
        target_path_str = target_reg_path or getattr(manifest_store, "target_regulation_path", None)
        target_reg = Path(target_path_str) if target_path_str else None
        target_dir = target_reg.parent if target_reg else None

        local_out_dir = Path(output_dir) if output_dir else base_dir / "mod"
        if not local_out_dir.is_absolute():
            local_out_dir = base_dir / local_out_dir

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
        for folder_name in ["parts", "chr", "sfx", "action"]:
            if target_dir:
                parts_dirs_to_clean.add(target_dir / folder_name)
            parts_dirs_to_clean.add(local_out_dir / folder_name)

        for pd in parts_dirs_to_clean:
            if not pd.exists():
                continue
            if pd.name == "parts":
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

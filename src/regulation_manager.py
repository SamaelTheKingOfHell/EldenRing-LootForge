"""
Regulation Manager for LootForge.

Orchestrates Elden Ring regulation.bin decryption, param patching, and AES-256 re-encryption
via RegTool (built on SoulsFormats and Paramdex).
Complies with [CS-MODULAR] and [CS-GRANULARITY] (<= 300 lines).
"""

import os
import sys
import json
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from src.logger import system_logger
from src.game_assets_service import GameAssetsService
from src.rollback_manager import RollbackManager


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
        """Backs up vanilla regulation.bin and extracts msg folder from Data0.bdt."""
        GameAssetsService.backup_game_assets(
            base_dir=self.base_dir,
            game_dir=game_dir,
            regtool_exe=self.regtool_exe,
            regtool_dll=self.regtool_dll,
            regtool_proj=self.regtool_proj
        )

    def resolve_source_regulation(
        self,
        active_path: str = "",
        game_dir: str = "",
        output_dir: str = ""
    ) -> Optional[Path]:
        """Locates the best source regulation.bin to read from."""
        return GameAssetsService.resolve_source_regulation(
            base_dir=self.base_dir,
            active_path=active_path,
            game_dir=game_dir,
            output_dir=output_dir
        )

    def resolve_target_regulation(
        self,
        active_path: str = "",
        output_dir: str = "mod",
        game_dir: str = ""
    ) -> Path:
        """Resolves target regulation path, preventing accidental overwrite of retail game folder."""
        return GameAssetsService.resolve_target_regulation(
            base_dir=self.base_dir,
            active_path=active_path,
            output_dir=output_dir,
            game_dir=game_dir
        )

    def _resolve_msg_dir(self, game_dir: str, target_reg: Path) -> Optional[Path]:
        """Ensures the mod output directory has a vanilla item.msgbnd.dcx to modify."""
        return GameAssetsService.resolve_msg_dir(
            base_dir=self.base_dir,
            game_dir=game_dir,
            target_reg=target_reg
        )

    def _get_regtool_cmd(self, subcmd: str) -> List[str]:
        """Builds executable command prefix for RegTool."""
        if sys.platform.startswith("win") and self.regtool_exe.exists():
            return [str(self.regtool_exe), subcmd]
        if self.regtool_dll.exists():
            return ["dotnet", str(self.regtool_dll), subcmd]
        return ["dotnet", "run", "--project", str(self.regtool_proj), "--", subcmd]

    def equipment_row_counts(self, source_reg: Path) -> Dict[str, int]:
        """Read exact surviving row counts, cached only while source and native tool identities match."""
        stat = source_reg.stat()
        tool = self.regtool_dll if self.regtool_dll.exists() else self.regtool_proj
        identity = (str(source_reg.resolve()), stat.st_size, stat.st_mtime_ns, tool.stat().st_mtime_ns)
        if getattr(self, "_capacity_identity", None) == identity:
            return dict(self._capacity_counts)
        response = subprocess.run(self._get_regtool_cmd("capacity") + ["--input", str(source_reg), "--defs", str(self.defs_dir)],
                                  capture_output=True, text=True, cwd=self.base_dir, check=False)
        if response.returncode:
            raise RuntimeError(f"Could not calculate regulation capacity: {response.stderr or response.stdout}")
        counts = json.loads(response.stdout[response.stdout.index("{"):])
        self._capacity_identity, self._capacity_counts = identity, counts
        return dict(counts)

    def execute_patch(
        self,
        specs: List[Dict[str, Any]],
        source_reg: Path,
        target_reg: Path,
        game_dir: str = "",
        boss_loot_pools_enabled: bool = True,
        boss_weapons_per_pool: int = 3,
        chest_loot_pools_enabled: bool = True,
        chest_min_items: int = 1,
        chest_max_items: int = 4,
        sweep_vanilla_items: bool = False,
        randomize_skills: bool = True,
        seed: Optional[int] = None
    ) -> Dict[str, Any]:
        """Executes RegTool to inject patch specifications into target regulation.bin."""
        if not source_reg.exists():
            raise FileNotFoundError(f"Source regulation not found: {source_reg}")
        if not self.defs_dir.exists():
            raise FileNotFoundError(f"Paramdex definitions directory not found: {self.defs_dir}")

        specs = self.prepare_patch_specs(specs, source_reg)

        target_reg.parent.mkdir(parents=True, exist_ok=True)
        if game_dir:
            regtool_dir = self.regtool_exe.parent if self.regtool_exe.exists() else self.regtool_dll.parent
            GameAssetsService.ensure_oodle_copied(game_dir, regtool_dir)

        temp_spec_path = None
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf:
                temp_spec_path = tf.name
                tf.write("[")
                for index, spec in enumerate(specs):
                    if index:
                        tf.write(",")
                    json.dump(spec, tf, separators=(',', ':'))
                tf.write("]")
            msg_dir = self._resolve_msg_dir(game_dir, target_reg)
            base_args = ["--input", str(source_reg), "--output", str(target_reg), "--defs", str(self.defs_dir), "--spec", temp_spec_path]
            if game_dir:
                base_args.extend(["--game-dir", game_dir])
            base_args.extend(["--loot-backups", str(self.base_dir / "backups")])
            if msg_dir:
                base_args.extend(["--msg", str(msg_dir)])
                system_logger.info(f"FMG source directory: {msg_dir}", source="RegulationManager")

            if boss_loot_pools_enabled:
                base_args.extend(["--enrich-bosses", "true", "--boss-count", str(max(1, min(5, boss_weapons_per_pool)))])

            if chest_loot_pools_enabled:
                base_args.extend(["--enrich-chests", "true", "--chest-min-items", str(chest_min_items), "--chest-max-items", str(chest_max_items)])

            if sweep_vanilla_items:
                base_args.extend(["--sweep-vanilla", "true", "--randomize-skills", str(randomize_skills).lower()])
                if seed is not None:
                    base_args.extend(["--seed", str(seed)])

            cmd = self._get_regtool_cmd("patch") + base_args
            system_logger.info(f"Running RegTool command: {' '.join(cmd)}", source="RegulationManager")

            res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(self.base_dir), check=False)
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
            if temp_spec_path and os.path.exists(temp_spec_path):
                try:
                    os.remove(temp_spec_path)
                except Exception:
                    pass

    def prepare_patch_specs(self, specs: List[Dict[str, Any]], source_reg: Path) -> List[Dict[str, Any]]:
        """Validate imports against the host before staging assets or writing patch output."""
        from src.patch_validation import iter_compact_specs, validate_patch_specs
        validate_patch_specs(specs)
        existing = {}
        if any(spec.get(key) for spec in specs for key in ("custom_skills", "custom_behaviors", "custom_attacks")):
            stat = source_reg.stat()
            tool = self.regtool_dll if self.regtool_dll.exists() else self.regtool_proj
            identity = (str(source_reg.resolve()), stat.st_size, stat.st_mtime_ns, tool.stat().st_mtime_ns)
            if getattr(self, "_import_identity", None) != identity:
                response = subprocess.run(self._get_regtool_cmd("imported-row-ids") + ["--input", str(source_reg)],
                                          capture_output=True, text=True, cwd=self.base_dir, check=False)
                if response.returncode:
                    raise RuntimeError(f"Could not validate imported rows: {response.stderr or response.stdout}")
                payload = json.loads(response.stdout[response.stdout.index("{"):])
                self._host_import_ids = {key: frozenset(ids) for key, ids in payload.items()}
                self._import_identity = identity
            existing = self._host_import_ids
        return list(iter_compact_specs(specs, existing))

    def deploy_parts(
        self,
        mod_sets: list,
        input_base_dir: Path,
        output_dir: Path,
        backup_manager: Optional[Any] = None
    ) -> int:
        """Delegates parts deployment and renaming to PartsDeployer service."""
        from src.parts_deployer import PartsDeployer
        deployer = PartsDeployer()
        count = deployer.deploy_parts(mod_sets, input_base_dir, output_dir, backup_manager=backup_manager)
        self.last_deployed_files = getattr(deployer, "last_deployed_files", [])
        self.last_backed_up_files = getattr(deployer, "last_backed_up_files", {})
        return count

    def rollback_all(
        self,
        backup_manager: Any,
        manifest_store: Any,
        target_reg_path: Optional[str] = None,
        output_dir: Optional[str] = None,
        asset_renumberer: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Comprehensively reverts all injected mod assets, parameters, and message files."""
        return RollbackManager.rollback_all(
            base_dir=self.base_dir,
            backup_manager=backup_manager,
            manifest_store=manifest_store,
            target_reg_path=target_reg_path,
            output_dir=output_dir,
            asset_renumberer=asset_renumberer
        )

    def introspect_world(
        self,
        reg_path: Path,
        msg_dir: Optional[Path] = None,
        output_json: Optional[Path] = None
    ) -> Dict[str, Any]:
        """Executes RegTool's smart introspection service on regulation.bin."""
        if not reg_path.exists():
            raise FileNotFoundError(f"Regulation file not found: {reg_path}")

        out_path = output_json
        cmd = self._get_regtool_cmd("introspect-world") + [
            "--input", str(reg_path),
            "--defs", str(self.defs_dir)
        ]
        if out_path:
            cmd.extend(["--output", str(out_path)])
        else:
            cmd.append("--stdout")

        if msg_dir and Path(msg_dir).exists():
            cmd.extend(["--msg", str(msg_dir)])

        res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(self.base_dir), check=False)
        if res.returncode != 0:
            system_logger.warning(f"Introspect world returned non-zero code {res.returncode}: {res.stderr or res.stdout}", source="RegulationManager")

        if out_path and Path(out_path).exists():
            try:
                with open(out_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                system_logger.warning(f"Failed to load snapshot JSON: {e}", source="RegulationManager")
        else:
            try:
                out_text = res.stdout.strip()
                start = out_text.find("{")
                end = out_text.rfind("}")
                if start != -1 and end != -1 and end > start:
                    return json.loads(out_text[start:end+1])
            except Exception as e:
                system_logger.warning(f"Failed to parse live table snapshot from memory: {e}", source="RegulationManager")

        return {}

    def sweep_vanilla_items(self, reg_path: Path, msg_dir: Optional[Path] = None) -> bool:
        """Executes universal sweeper on target regulation.bin."""
        if not reg_path.exists():
            raise FileNotFoundError(f"Regulation file not found: {reg_path}")

        cmd = self._get_regtool_cmd("sweep-vanilla") + [
            "--input", str(reg_path),
            "--output", str(reg_path),
            "--defs", str(self.defs_dir)
        ]
        if msg_dir and Path(msg_dir).exists():
            cmd.extend(["--msg", str(msg_dir)])

        res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(self.base_dir), check=False)
        return res.returncode == 0

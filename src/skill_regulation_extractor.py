"""
Regulation data extractor for custom weapon skills and movesets in LootForge.

Executes RegTool extract-skills-movesets on a mod's regulation.bin, caching
the result in-memory and on-disk for fast introspection.
Adheres to [CS-MODULAR] and [CS-GRANULARITY].
"""

import sys
import json
import hashlib
import os
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from src.logger import system_logger


class SkillRegulationExtractor:
    """Extracts and caches custom weapon skills/movesets parameters from mod regulations."""

    _regulation_cache: Dict[str, Dict[str, Any]] = {}
    CACHE_VERSION = 2

    @classmethod
    def clear_cache(cls):
        """Clears the in-memory regulation extraction cache."""
        cls._regulation_cache.clear()

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir).resolve()
        self.defs_dir = self.base_dir / "tools" / "vendor" / "Paramdex" / "ER" / "Defs"
        self.regtool_exe = self.base_dir / "tools" / "RegTool" / "bin" / "Release" / "net9.0" / "RegTool.exe"
        self.regtool_dll = self.base_dir / "tools" / "RegTool" / "bin" / "Release" / "net9.0" / "RegTool.dll"
        self.regtool_debug_dll = self.base_dir / "tools" / "RegTool" / "bin" / "Debug" / "net9.0" / "RegTool.dll"
        self.regtool_proj = self.base_dir / "tools" / "RegTool" / "RegTool.csproj"

    def cache_key(self, reg_file: Path, msg_candidate: Optional[Path] = None) -> str:
        """Bind cached extraction to source identity, message archives, schemas and native tool revision."""
        def identity(path):
            path = Path(path).resolve()
            try:
                stat = path.stat()
                return (os.path.normcase(str(path)), stat.st_size, stat.st_mtime_ns)
            except FileNotFoundError:
                return (os.path.normcase(str(path)), None, None)

        messages = []
        if msg_candidate and Path(msg_candidate).exists():
            messages = [identity(path) for path in sorted(Path(msg_candidate).rglob("*.msgbnd.dcx"))]
        tool = next((path for path in (self.regtool_dll, self.regtool_debug_dll, self.regtool_proj) if path.exists()), self.regtool_proj)
        schemas = [identity(self.defs_dir / (name + ".xml")) for name in
                   ("EquipParamWeapon", "SwordArtsParam", "BehaviorParam", "AtkParam")]
        signature = (self.CACHE_VERSION, identity(reg_file), identity(tool),
                     str(Path(msg_candidate).resolve()) if msg_candidate else None, messages, schemas)
        return hashlib.sha256(json.dumps(signature, separators=(",", ":")).encode("utf-8")).hexdigest()

    def cache_path(self, reg_file: Path, msg_candidate: Optional[Path] = None) -> Path:
        """Locate a versioned extraction without reusing legacy stem/size cache files."""
        return self.base_dir / "scratch" / f"extracted_v{self.CACHE_VERSION}_{self.cache_key(reg_file, msg_candidate)}.json"

    def extract_regulation_data(
        self,
        reg_file: Path,
        msg_candidate: Optional[Path] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Executes RegTool extract-skills-movesets on a mod's regulation.bin, caching
        the result in-memory so subsequent weapon lookups from the same mod regulation
        are instantaneous.
        """
        reg_path = Path(reg_file).resolve()
        cache_key = self.cache_key(reg_path, msg_candidate)
        if cache_key in self._regulation_cache:
            return self._regulation_cache[cache_key]

        scratch_dir = self.base_dir / "scratch"
        scratch_dir.mkdir(parents=True, exist_ok=True)
        out_json = self.cache_path(reg_path, msg_candidate)

        # The versioned key already captures source, schemas, tool and message identities.
        if out_json.exists():
            try:
                with open(out_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._regulation_cache[cache_key] = data
                    return data
            except Exception:
                pass

        msg_dir_arg = []
        if msg_candidate and Path(msg_candidate).exists():
            msg_dir_arg = ["--msg", str(msg_candidate)]

        if sys.platform.startswith("win") and self.regtool_exe.exists():
            cmd = [str(self.regtool_exe), "extract-skills-movesets", "--input", str(reg_path), "--defs", str(self.defs_dir), "--output", str(out_json)] + msg_dir_arg
        elif self.regtool_dll.exists():
            cmd = ["dotnet", str(self.regtool_dll), "extract-skills-movesets", "--input", str(reg_path), "--defs", str(self.defs_dir), "--output", str(out_json)] + msg_dir_arg
        elif self.regtool_debug_dll.exists():
            cmd = ["dotnet", str(self.regtool_debug_dll), "extract-skills-movesets", "--input", str(reg_path), "--defs", str(self.defs_dir), "--output", str(out_json)] + msg_dir_arg
        else:
            cmd = ["dotnet", "run", "--project", str(self.regtool_proj), "--", "extract-skills-movesets", "--input", str(reg_path), "--defs", str(self.defs_dir), "--output", str(out_json)] + msg_dir_arg

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(self.base_dir), check=False)
            if res.returncode != 0:
                system_logger.warning(f"RegTool extract-skills-movesets failed: {res.stderr or res.stdout}", source="SkillRegulationExtractor")
                return None

            if not out_json.exists():
                return None

            with open(out_json, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._regulation_cache[cache_key] = data
            return data
        except Exception as ex:
            system_logger.error(f"Failed to extract mod regulation data: {ex}", source="SkillRegulationExtractor")
            return None

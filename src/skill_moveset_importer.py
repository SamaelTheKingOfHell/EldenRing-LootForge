"""
Skill and Moveset Importer Service for LootForge.

Discovers, extracts, and ports custom weapon skills (SwordArtsParam, EquipParamGem),
movesets (BehaviorParam_PC, AtkParam_Pc, wepmotionCategory, behaviorVariationId),
animation archives (chr/c0000_*.anibnd.dcx, chr/c0000.behbnd.dcx), and visual effects (sfx/).
Adheres to [CS-MODULAR] and [CS-GRANULARITY].
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any
from src.models import DetectedModSet, SkillMovesetMetadata
from src.logger import system_logger


class SkillMovesetImporter:
    """
    Introspects mod directories for custom weapon skills, animations, and movesets,
    and deploys them into Mod Engine 2 staging directories alongside standalone parameter specs.
    """

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir).resolve()
        self.defs_dir = self.base_dir / "tools" / "vendor" / "Paramdex" / "ER" / "Defs"
        self.regtool_exe = self.base_dir / "tools" / "RegTool" / "bin" / "Release" / "net9.0" / "RegTool.exe"
        self.regtool_dll = self.base_dir / "tools" / "RegTool" / "bin" / "Release" / "net9.0" / "RegTool.dll"
        self.regtool_debug_dll = self.base_dir / "tools" / "RegTool" / "bin" / "Debug" / "net9.0" / "RegTool.dll"
        self.regtool_proj = self.base_dir / "tools" / "RegTool" / "RegTool.csproj"

    def introspect_mod_folder(
        self,
        mod_folder: Path,
        target_model_id: Optional[str] = None
    ) -> Optional[SkillMovesetMetadata]:
        """
        Scans a mod directory for custom animations, moveset parameters, and skills.
        If a mod regulation.bin is present, executes RegTool extract-skills-movesets
        to retrieve authentic weapon and skill metadata.
        """
        mod_path = Path(mod_folder).resolve()
        if not mod_path.exists():
            return None

        # Check for moveset animation and visual assets
        animation_banks: List[str] = []
        has_behavior_graph = False
        has_sfx = False
        has_action_scripts = False

        chr_dir = mod_path / "chr"
        if not chr_dir.exists():
            # Check recursive chr folder
            for sub in mod_path.rglob("chr"):
                if sub.is_dir():
                    chr_dir = sub
                    break

        if chr_dir.exists():
            for f in chr_dir.glob("c0000*.anibnd.dcx"):
                animation_banks.append(f.name)
            if (chr_dir / "c0000.behbnd.dcx").exists():
                has_behavior_graph = True

        sfx_dir = mod_path / "sfx"
        if not sfx_dir.exists():
            for sub in mod_path.rglob("sfx"):
                if sub.is_dir():
                    sfx_dir = sub
                    break
        if sfx_dir.exists() and any(sfx_dir.glob("*.ffxbnd.dcx")):
            has_sfx = True

        action_dir = mod_path / "action"
        if not action_dir.exists():
            for sub in mod_path.rglob("action"):
                if sub.is_dir():
                    action_dir = sub
                    break
        if action_dir.exists() and any(action_dir.iterdir()):
            has_action_scripts = True

        has_custom_moveset_assets = bool(animation_banks or has_behavior_graph or has_sfx)

        # Check for mod regulation.bin
        reg_file = mod_path / "regulation.bin"
        if not reg_file.exists():
            for sub in mod_path.rglob("regulation.bin"):
                if sub.is_file() and sub.stat().st_size > 100000:
                    reg_file = sub
                    break

        if not reg_file.exists():
            if has_custom_moveset_assets:
                return SkillMovesetMetadata(
                    has_custom_moveset=True,
                    animation_banks=animation_banks,
                    has_behavior_graph=has_behavior_graph,
                    has_sfx=has_sfx,
                    has_action_scripts=has_action_scripts
                )
            return None

        # Execute RegTool extract-skills-movesets
        scratch_dir = self.base_dir / "scratch"
        scratch_dir.mkdir(parents=True, exist_ok=True)
        out_json = scratch_dir / f"extracted_{mod_path.name}_{target_model_id or 'all'}.json"

        # Check for optional mod msg directory
        msg_dir_arg = []
        msg_candidate = mod_path / "msg"
        if not msg_candidate.exists():
            for sub in mod_path.rglob("msg"):
                if sub.is_dir():
                    msg_candidate = sub
                    break
        if msg_candidate.exists():
            msg_dir_arg = ["--msg", str(msg_candidate)]

        if sys.platform.startswith("win") and self.regtool_exe.exists():
            cmd = [str(self.regtool_exe), "extract-skills-movesets", "--input", str(reg_file), "--defs", str(self.defs_dir), "--output", str(out_json)] + msg_dir_arg
        elif self.regtool_dll.exists():
            cmd = ["dotnet", str(self.regtool_dll), "extract-skills-movesets", "--input", str(reg_file), "--defs", str(self.defs_dir), "--output", str(out_json)] + msg_dir_arg
        elif self.regtool_debug_dll.exists():
            cmd = ["dotnet", str(self.regtool_debug_dll), "extract-skills-movesets", "--input", str(reg_file), "--defs", str(self.defs_dir), "--output", str(out_json)] + msg_dir_arg
        else:
            cmd = ["dotnet", "run", "--project", str(self.regtool_proj), "--", "extract-skills-movesets", "--input", str(reg_file), "--defs", str(self.defs_dir), "--output", str(out_json)] + msg_dir_arg

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(self.base_dir), check=False)
            if res.returncode != 0:
                system_logger.warning(f"RegTool extract-skills-movesets failed: {res.stderr or res.stdout}", source="SkillMovesetImporter")
                return None

            if not out_json.exists():
                return None

            with open(out_json, "r", encoding="utf-8") as f:
                data = json.load(f)

            weapons = data.get("Weapons", [])
            custom_skills = data.get("CustomSkills", {})
            custom_behaviors = data.get("CustomBehaviors", {})
            custom_attacks = data.get("CustomAttacks", {})

            # Filter for weapon matching target_model_id if specified
            matched_weapon = None
            if target_model_id:
                try:
                    m_int = int(target_model_id.lstrip("0") or "0")
                    for w in weapons:
                        if w.get("ModelId") == m_int:
                            matched_weapon = w
                            break
                except ValueError:
                    pass

            if not matched_weapon and weapons:
                matched_weapon = weapons[0]

            if not matched_weapon:
                return None

            skill_id = matched_weapon.get("SwordArtsParamId", 0)
            skill_name = matched_weapon.get("SkillName") or ""
            skill_caption = matched_weapon.get("SkillCaption") or ""
            beh_var = matched_weapon.get("BehaviorVariationId", 0)
            mot_cat = matched_weapon.get("WepmotionCategory", 0)
            mot_1h = matched_weapon.get("WepmotionOneHandId", 0)
            mot_2h = matched_weapon.get("WepmotionBothHandId", 0)
            sp_atk = matched_weapon.get("SpAtkCategory", 0)

            has_custom_skill = skill_id > 0 and (skill_id >= 1000 or str(skill_id) in custom_skills)
            has_custom_moveset = has_custom_moveset_assets or beh_var >= 800 or mot_cat == 60 or sp_atk > 100

            skills_spec = []
            if str(skill_id) in custom_skills:
                skills_spec.append({
                    "skill_id": skill_id,
                    "name": skill_name,
                    "fields": custom_skills[str(skill_id)]
                })

            behaviors_spec = []
            if str(beh_var) in custom_behaviors:
                for b_row in custom_behaviors[str(beh_var)]:
                    behaviors_spec.append({
                        "id": b_row.get("_row_id", 0),
                        "fields": b_row
                    })

            attacks_spec = []
            for atk_id, a_row in custom_attacks.items():
                attacks_spec.append({
                    "id": int(atk_id),
                    "fields": a_row
                })

            metadata = SkillMovesetMetadata(
                has_custom_skill=has_custom_skill,
                skill_id=skill_id,
                skill_name=skill_name,
                skill_caption=skill_caption,
                has_custom_moveset=has_custom_moveset,
                behavior_variation_id=beh_var,
                wepmotion_category=mot_cat,
                wepmotion_one_hand_id=mot_1h,
                wepmotion_both_hand_id=mot_2h,
                sp_atk_category=sp_atk,
                animation_banks=animation_banks,
                has_behavior_graph=has_behavior_graph,
                has_sfx=has_sfx,
                has_action_scripts=has_action_scripts,
                custom_skills_spec=skills_spec,
                custom_behaviors_spec=behaviors_spec,
                custom_attacks_spec=attacks_spec
            )

            system_logger.info(
                f"Introspected mod: skill={skill_name} (ID {skill_id}), behVar={beh_var}, motCat={mot_cat}",
                source="SkillMovesetImporter"
            )
            return metadata

        except Exception as ex:
            system_logger.error(f"Failed to introspect mod skills and movesets: {ex}", source="SkillMovesetImporter")
            return None

    def deploy_moveset_assets(
        self,
        mod_set: DetectedModSet,
        input_base_dir: Path,
        output_dir: Path
    ) -> List[str]:
        """
        Copies chr/, sfx/, and action/ directories from the mod folder to the output mod directory.
        Normalizes filenames to lowercase for Proton/Linux compatibility.
        """
        deployed_files: List[str] = []
        source_mod_dir = input_base_dir / mod_set.folder_or_archive_name
        if not source_mod_dir.exists():
            source_mod_dir = input_base_dir

        out_path = Path(output_dir)

        # Deploy chr/ assets (animations, behaviors)
        chr_candidates = [source_mod_dir / "chr"] + list(source_mod_dir.rglob("chr"))
        for cand in chr_candidates:
            if cand.is_dir() and cand != (out_path / "chr"):
                out_chr = out_path / "chr"
                out_chr.mkdir(parents=True, exist_ok=True)
                for item in cand.iterdir():
                    if item.is_file() and (item.name.endswith(".dcx") or item.name.endswith(".tae")):
                        target = out_chr / item.name.lower()
                        shutil.copy2(str(item), str(target))
                        deployed_files.append(str(target))
                        system_logger.debug(f"Deployed animation: {item.name} -> {target.name}", source="SkillMovesetImporter")
                break

        # Deploy sfx/ assets
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
                        system_logger.debug(f"Deployed VFX: {item.name} -> {target.name}", source="SkillMovesetImporter")
                break

        # Deploy action/ assets
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
                        shutil.copy2(str(item), str(target))
                        deployed_files.append(str(target))
                break

        return deployed_files

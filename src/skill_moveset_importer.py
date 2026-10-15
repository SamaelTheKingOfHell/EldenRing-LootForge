"""
Skill and Moveset Importer Service for LootForge.

Discovers, extracts, and ports custom weapon skills (SwordArtsParam, EquipParamGem),
movesets (BehaviorParam_PC, AtkParam_Pc, wepmotionCategory, behaviorVariationId),
animation archives (chr/c0000_*.anibnd.dcx, chr/c0000.behbnd.dcx), and visual effects (sfx/).
Adheres to [CS-MODULAR] and [CS-GRANULARITY].
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
from src.models import DetectedModSet, SkillMovesetMetadata
from src.logger import system_logger
from src.skill_regulation_extractor import SkillRegulationExtractor
from src.skill_moveset_deployer import SkillMovesetDeployer


class SkillMovesetImporter:
    """
    Introspects mod directories for custom weapon skills, animations, and movesets,
    and deploys them into Mod Engine 2 staging directories alongside standalone parameter specs.
    Adheres to [CS-MODULAR] and [CS-GRANULARITY].
    """

    _regulation_cache = SkillRegulationExtractor._regulation_cache

    @classmethod
    def clear_cache(cls):
        """Clears the in-memory regulation extraction cache."""
        SkillRegulationExtractor.clear_cache()

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir).resolve()
        self.extractor = SkillRegulationExtractor(self.base_dir)
        self.deployer = SkillMovesetDeployer()

    @property
    def last_deployed_files(self) -> List[str]:
        return self.deployer.last_deployed_files

    @property
    def last_backed_up_files(self) -> Dict[str, str]:
        return self.deployer.last_backed_up_files

    def extract_regulation_data(
        self,
        reg_file: Path,
        msg_candidate: Optional[Path] = None
    ) -> Optional[Dict[str, Any]]:
        """Delegates regulation data extraction to SkillRegulationExtractor."""
        return self.extractor.extract_regulation_data(reg_file, msg_candidate)

    def introspect_mod_folder(
        self,
        mod_folder: Path,
        target_model_id: Optional[str] = None,
        deep: bool = True
    ) -> Optional[SkillMovesetMetadata]:
        """
        Scans a mod directory for custom animations, moveset parameters, and skills.
        If deep=False, executes purely in-memory/filesystem checks (<1ms).
        If deep=True, extracts authentic weapon and skill metadata from regulation.bin.
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
                    has_action_scripts=has_action_scripts,
                    is_deep_introspected=True
                )
            return None

        if not deep:
            return SkillMovesetMetadata(
                has_custom_skill=True,
                has_custom_moveset=has_custom_moveset_assets,
                animation_banks=animation_banks,
                has_behavior_graph=has_behavior_graph,
                has_sfx=has_sfx,
                has_action_scripts=has_action_scripts,
                is_deep_introspected=False,
                regulation_path=str(reg_file.resolve())
            )

        msg_candidate = mod_path / "msg"
        if not msg_candidate.exists():
            for sub in mod_path.rglob("msg"):
                if sub.is_dir():
                    msg_candidate = sub
                    break

        data = self.extract_regulation_data(
            reg_file,
            msg_candidate if msg_candidate and msg_candidate.exists() else None
        )
        if not data:
            if has_custom_moveset_assets:
                return SkillMovesetMetadata(
                    has_custom_moveset=True,
                    animation_banks=animation_banks,
                    has_behavior_graph=has_behavior_graph,
                    has_sfx=has_sfx,
                    has_action_scripts=has_action_scripts,
                    is_deep_introspected=True,
                    regulation_path=str(reg_file.resolve())
                )
            return None

        try:
            weapons = data.get("Weapons", [])
            custom_skills = data.get("CustomSkills", {})
            custom_behaviors = data.get("CustomBehaviors", {})
            custom_attacks = data.get("CustomAttacks", {})

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

            if not matched_weapon and weapons and target_model_id is None:
                matched_weapon = weapons[0]

            if not matched_weapon:
                if has_custom_moveset_assets:
                    return SkillMovesetMetadata(
                        has_custom_moveset=True,
                        animation_banks=animation_banks,
                        has_behavior_graph=has_behavior_graph,
                        has_sfx=has_sfx,
                        has_action_scripts=has_action_scripts,
                        is_deep_introspected=True,
                        regulation_path=str(reg_file.resolve())
                    )
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
            # refType 0 addresses AtkParam_Pc; refType 1 addresses Bullet.
            # A regulation-wide catalogue includes unrelated weapons and must
            # never be attached wholesale to each selected model.
            attack_ids = {int(b["fields"]["refId"]) for b in behaviors_spec
                          if b["fields"].get("refType") == 0 and b["fields"].get("refId", -1) >= 0}
            for atk_id in sorted(attack_ids):
                a_row = custom_attacks.get(str(atk_id))
                if a_row is None:
                    continue
                attacks_spec.append({
                    "id": atk_id,
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
                custom_attacks_spec=attacks_spec,
                is_deep_introspected=True,
                regulation_path=str(reg_file.resolve())
            )

            system_logger.info(
                f"Introspected mod: skill={skill_name} (ID {skill_id}), behVar={beh_var}, motCat={mot_cat}",
                source="SkillMovesetImporter"
            )
            return metadata

        except Exception as ex:
            system_logger.error(f"Failed to introspect mod skills and movesets: {ex}", source="SkillMovesetImporter")
            return None

    def ensure_deep_introspected(
        self,
        mod_set: DetectedModSet,
        input_base_dir: Optional[Path] = None
    ) -> bool:
        """
        Lazily ensures that a mod set's skill_moveset metadata has been fully introspected
        from regulation.bin if it hasn't been already.
        """
        if not mod_set.is_weapon or not mod_set.skill_moveset:
            return False

        if mod_set.skill_moveset.is_deep_introspected:
            return True

        mod_dir = None
        if mod_set.skill_moveset.regulation_path:
            reg_p = Path(mod_set.skill_moveset.regulation_path)
            if reg_p.exists():
                mod_dir = reg_p.parent

        if not mod_dir or not mod_dir.exists():
            if input_base_dir:
                candidate = Path(input_base_dir) / mod_set.folder_or_archive_name
                if candidate.exists():
                    mod_dir = candidate
            if not mod_dir:
                candidate = self.base_dir / "input_mods" / mod_set.folder_or_archive_name
                if candidate.exists():
                    mod_dir = candidate
                else:
                    candidate = self.base_dir / mod_set.folder_or_archive_name
                    if candidate.exists():
                        mod_dir = candidate

        if not mod_dir or not mod_dir.exists():
            mod_set.skill_moveset.is_deep_introspected = True
            return False

        deep_meta = self.introspect_mod_folder(mod_dir, mod_set.target_model_id, deep=True)
        if deep_meta:
            mod_set.skill_moveset.has_custom_skill = deep_meta.has_custom_skill
            mod_set.skill_moveset.skill_id = deep_meta.skill_id
            mod_set.skill_moveset.skill_name = deep_meta.skill_name
            mod_set.skill_moveset.skill_caption = deep_meta.skill_caption
            mod_set.skill_moveset.has_custom_moveset = deep_meta.has_custom_moveset
            mod_set.skill_moveset.behavior_variation_id = deep_meta.behavior_variation_id
            mod_set.skill_moveset.wepmotion_category = deep_meta.wepmotion_category
            mod_set.skill_moveset.wepmotion_one_hand_id = deep_meta.wepmotion_one_hand_id
            mod_set.skill_moveset.wepmotion_both_hand_id = deep_meta.wepmotion_both_hand_id
            mod_set.skill_moveset.sp_atk_category = deep_meta.sp_atk_category
            mod_set.skill_moveset.animation_banks = deep_meta.animation_banks
            mod_set.skill_moveset.has_behavior_graph = deep_meta.has_behavior_graph
            mod_set.skill_moveset.has_sfx = deep_meta.has_sfx
            mod_set.skill_moveset.has_action_scripts = deep_meta.has_action_scripts
            mod_set.skill_moveset.custom_skills_spec = deep_meta.custom_skills_spec
            mod_set.skill_moveset.custom_behaviors_spec = deep_meta.custom_behaviors_spec
            mod_set.skill_moveset.custom_attacks_spec = deep_meta.custom_attacks_spec
            mod_set.skill_moveset.is_deep_introspected = True
            mod_set.skill_moveset.regulation_path = deep_meta.regulation_path
            return True

        mod_set.skill_moveset.is_deep_introspected = True
        return False

    def deploy_moveset_assets(
        self,
        mod_set: DetectedModSet,
        input_base_dir: Path,
        output_dir: Path,
        backup_manager: Optional[Any] = None
    ) -> List[str]:
        """Delegates moveset asset deployment to SkillMovesetDeployer."""
        return self.deployer.deploy_moveset_assets(
            mod_set=mod_set,
            input_base_dir=input_base_dir,
            output_dir=output_dir,
            backup_manager=backup_manager
        )

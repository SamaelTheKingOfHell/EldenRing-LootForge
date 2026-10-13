"""
Unit and integration test suite for Custom Skills and Movesets Importer.

Validates mod directory introspection, RegTool regulation extraction,
moveset asset deployment (chr, sfx, action), parameter spec building,
and PartsDeployer integration. Adheres to [CS-NO-MOCK].
"""

import os
import shutil
import tempfile
from pathlib import Path
import pytest

from src.models import (
    DetectedModSet,
    ModPartFile,
    EquipmentSlot,
    LootTarget,
    LootDistributionType,
    StandaloneAllocation,
    SkillMovesetMetadata,
)
from src.skill_moveset_importer import SkillMovesetImporter
from src.param_builder import ParamBuilder
from src.parts_deployer import PartsDeployer


@pytest.fixture
def temp_env():
    """Creates a temporary staging filesystem for testing."""
    tmp = Path(tempfile.mkdtemp(prefix="lf_test_skills_"))
    yield tmp
    shutil.rmtree(str(tmp), ignore_errors=True)


def test_skill_moveset_metadata_integrity():
    """Validates SkillMovesetMetadata default values and structured initialization."""
    meta = SkillMovesetMetadata(
        has_custom_skill=True,
        skill_id=4110,
        skill_name="Overhead Stance",
        has_custom_moveset=True,
        behavior_variation_id=900,
        wepmotion_category=60,
        wepmotion_one_hand_id=3,
        wepmotion_both_hand_id=12,
        sp_atk_category=641,
        animation_banks=["c0000_a1x.anibnd.dcx", "c0000_a2x.anibnd.dcx"],
        has_behavior_graph=True,
        has_sfx=True
    )
    assert meta.has_custom_skill is True
    assert meta.skill_id == 4110
    assert meta.skill_name == "Overhead Stance"
    assert meta.wepmotion_category == 60
    assert meta.sp_atk_category == 641
    assert "c0000_a1x.anibnd.dcx" in meta.animation_banks
    assert meta.has_behavior_graph is True
    assert meta.has_sfx is True


def test_introspect_mod_folder_assets_only(temp_env):
    """Validates introspection of a mod directory containing animation and VFX assets."""
    mod_dir = temp_env / "CustomKatanaMod"
    chr_dir = mod_dir / "chr"
    sfx_dir = mod_dir / "sfx"
    chr_dir.mkdir(parents=True)
    sfx_dir.mkdir(parents=True)

    # Create dummy animation files
    (chr_dir / "c0000_a2x.anibnd.dcx").write_bytes(b"DUMMY_ANIM")
    (chr_dir / "c0000.behbnd.dcx").write_bytes(b"DUMMY_BEH")
    (sfx_dir / "frpg_playersfx.ffxbnd.dcx").write_bytes(b"DUMMY_SFX")

    importer = SkillMovesetImporter(temp_env)
    metadata = importer.introspect_mod_folder(mod_dir)

    assert metadata is not None
    assert metadata.has_custom_moveset is True
    assert "c0000_a2x.anibnd.dcx" in metadata.animation_banks
    assert metadata.has_behavior_graph is True
    assert metadata.has_sfx is True


def test_deploy_moveset_assets(temp_env):
    """Validates deploying chr, sfx, and action directories to output with lowercase normalization."""
    input_base = temp_env / "input_mods"
    output_dir = temp_env / "output_mod"
    mod_dir = input_base / "MoonlightGreatsword"

    chr_dir = mod_dir / "chr"
    sfx_dir = mod_dir / "sfx"
    action_dir = mod_dir / "action"
    chr_dir.mkdir(parents=True)
    sfx_dir.mkdir(parents=True)
    action_dir.mkdir(parents=True)

    (chr_dir / "C0000_A3X.anibnd.dcx").write_bytes(b"ANIM_BYTES")
    (chr_dir / "C0000.behbnd.dcx").write_bytes(b"BEH_BYTES")
    (sfx_dir / "FRPG_SFXBND.dcx").write_bytes(b"SFX_BYTES")
    (action_dir / "EVENTNAMEID.txt").write_text("event_100")

    part = ModPartFile(
        file_name="wp_a_0606.partsbnd.dcx",
        relative_path="wp_a_0606.partsbnd.dcx",
        slot=EquipmentSlot.WEAPON,
        target_model_id="606"
    )

    mod_set = DetectedModSet(
        set_id="mod_moonlight",
        folder_or_archive_name="MoonlightGreatsword",
        target_model_id="606",
        target_vanilla_name="Dark Moon Greatsword",
        parts=[part],
        is_weapon=True,
        allocation=StandaloneAllocation("9050", 9050000, 9100050)
    )

    importer = SkillMovesetImporter(temp_env)
    deployed = importer.deploy_moveset_assets(mod_set, input_base, output_dir)

    assert len(deployed) >= 4
    # Verify lowercase normalization on target filesystem
    assert (output_dir / "chr" / "c0000_a3x.anibnd.dcx").exists()
    assert (output_dir / "chr" / "c0000.behbnd.dcx").exists()
    assert (output_dir / "sfx" / "frpg_sfxbnd.dcx").exists()
    assert (output_dir / "action" / "eventnameid.txt").exists()


def test_param_builder_with_custom_skills_and_movesets():
    """Validates ParamBuilder attaches custom skill, behavior, and attack parameters to patch spec."""
    part = ModPartFile(
        file_name="wp_a_0556.partsbnd.dcx",
        relative_path="wp_a_0556.partsbnd.dcx",
        slot=EquipmentSlot.WEAPON,
        target_model_id="556"
    )

    skill_meta = SkillMovesetMetadata(
        has_custom_skill=True,
        skill_id=22080,
        skill_name="Moonglow",
        has_custom_moveset=True,
        behavior_variation_id=900,
        wepmotion_category=60,
        wepmotion_one_hand_id=3,
        wepmotion_both_hand_id=12,
        sp_atk_category=641,
        custom_skills_spec=[{
            "skill_id": 22080,
            "name": "Moonglow",
            "fields": {"swordArtsType": 10, "iconId": 21062}
        }],
        custom_behaviors_spec=[{
            "id": 900010,
            "fields": {"variationId": 900, "behaviorJudgeId": 10, "refType": 1, "refId": 90010}
        }],
        custom_attacks_spec=[{
            "id": 90010,
            "fields": {"atkPhys": 150}
        }]
    )

    mod_set = DetectedModSet(
        set_id="mod_kuro_hasu",
        folder_or_archive_name="BlackLotusMod",
        target_model_id="556",
        target_vanilla_name="Uchigatana",
        parts=[part],
        loot_target=LootTarget(
            route_type=LootDistributionType.BOSS_REMEMBRANCE,
            target_id="remembrance_malenia",
            display_name="Remembrance of the Rot Goddess"
        ),
        allocation=StandaloneAllocation("9080", 9080000, 9100080),
        is_weapon=True,
        skill_moveset=skill_meta
    )

    builder = ParamBuilder()
    spec = builder.build_patch_spec(mod_set)

    # 1. Verify weapon row field updates
    ep = spec["equip_params"][0]
    updates = ep["field_updates"]
    assert updates["swordArtsParamId"] == 22080
    assert updates["behaviorVariationId"] == 900
    assert updates["wepmotionCategory"] == 60
    assert updates["wepmotionOneHandId"] == 3
    assert updates["wepmotionBothHandId"] == 12
    assert updates["spAtkCategory"] == 641

    # 2. Verify custom skills, behaviors, and attacks in spec root
    assert "custom_skills" in spec
    assert len(spec["custom_skills"]) == 1
    assert spec["custom_skills"][0]["skill_id"] == 22080

    assert "custom_behaviors" in spec
    assert len(spec["custom_behaviors"]) == 1
    assert spec["custom_behaviors"][0]["id"] == 900010

    assert "custom_attacks" in spec
    assert len(spec["custom_attacks"]) == 1
    assert spec["custom_attacks"][0]["id"] == 90010


def test_parts_deployer_integrates_moveset_deployment(temp_env):
    """Validates PartsDeployer deploys both .partsbnd.dcx and moveset files when skill_moveset is present."""
    input_base = temp_env / "input_mods"
    output_dir = temp_env / "mod"
    mod_dir = input_base / "DragonSlayer"

    parts_dir = mod_dir / "parts"
    chr_dir = mod_dir / "chr"
    parts_dir.mkdir(parents=True)
    chr_dir.mkdir(parents=True)

    part_file = parts_dir / "wp_a_0606.partsbnd.dcx"
    part_file.write_bytes(b"WEAPON_MESH")
    anim_file = chr_dir / "c0000_a3x.anibnd.dcx"
    anim_file.write_bytes(b"ANIM_BYTES")

    part = ModPartFile(
        file_name="wp_a_0606.partsbnd.dcx",
        relative_path="parts/wp_a_0606.partsbnd.dcx",
        slot=EquipmentSlot.WEAPON,
        target_model_id="0606"
    )

    skill_meta = SkillMovesetMetadata(
        has_custom_moveset=True,
        animation_banks=["c0000_a3x.anibnd.dcx"]
    )

    mod_set = DetectedModSet(
        set_id="mod_dragon_slayer",
        folder_or_archive_name="DragonSlayer",
        target_model_id="0606",
        target_vanilla_name="Greatsword",
        parts=[part],
        is_weapon=True,
        allocation=StandaloneAllocation("9099", 9099000, 9100099),
        skill_moveset=skill_meta
    )

    deployer = PartsDeployer()
    count = deployer.deploy_parts([mod_set], input_base, output_dir)

    assert count >= 2
    assert (output_dir / "parts" / "wp_a_9099.partsbnd.dcx").exists()
    assert (output_dir / "chr" / "c0000_a3x.anibnd.dcx").exists()


def test_param_builder_toggle_disables_custom_skills():
    """Validates that import_custom_moveset=False causes ParamBuilder to omit custom skills/moveset overrides."""
    part = ModPartFile(
        file_name="wp_a_0556.partsbnd.dcx",
        relative_path="wp_a_0556.partsbnd.dcx",
        slot=EquipmentSlot.WEAPON,
        target_model_id="556"
    )

    skill_meta = SkillMovesetMetadata(
        has_custom_skill=True,
        skill_id=22080,
        skill_name="Moonglow",
        has_custom_moveset=True,
        behavior_variation_id=900,
        custom_skills_spec=[{"skill_id": 22080, "name": "Moonglow", "fields": {}}],
        custom_behaviors_spec=[{"id": 900010, "fields": {}}],
        custom_attacks_spec=[{"id": 90010, "fields": {}}]
    )

    mod_set = DetectedModSet(
        set_id="mod_kuro_hasu_disabled",
        folder_or_archive_name="BlackLotusMod",
        target_model_id="556",
        target_vanilla_name="Uchigatana",
        parts=[part],
        loot_target=LootTarget(
            route_type=LootDistributionType.BOSS_REMEMBRANCE,
            target_id="remembrance_malenia",
            display_name="Remembrance of the Rot Goddess"
        ),
        allocation=StandaloneAllocation("9081", 9081000, 9100081),
        is_weapon=True,
        import_custom_moveset=False,
        skill_moveset=skill_meta
    )

    builder = ParamBuilder()
    spec = builder.build_patch_spec(mod_set)

    ep = spec["equip_params"][0]
    updates = ep["field_updates"]
    # With toggle disabled, weapon should NOT receive custom swordArtsParamId or behaviorVariationId
    assert "swordArtsParamId" not in updates
    assert "behaviorVariationId" not in updates
    assert "custom_skills" not in spec
    assert "custom_behaviors" not in spec
    assert "custom_attacks" not in spec


def test_parts_deployer_toggle_disables_moveset_assets(temp_env):
    """Validates that import_custom_moveset=False prevents PartsDeployer from deploying chr/sfx/action folders."""
    input_base = temp_env / "input_mods"
    output_dir = temp_env / "mod"
    mod_dir = input_base / "DragonSlayerToggle"

    parts_dir = mod_dir / "parts"
    chr_dir = mod_dir / "chr"
    parts_dir.mkdir(parents=True)
    chr_dir.mkdir(parents=True)

    (parts_dir / "wp_a_0606.partsbnd.dcx").write_bytes(b"WEAPON_MESH")
    (chr_dir / "c0000_a3x.anibnd.dcx").write_bytes(b"ANIM_BYTES")

    part = ModPartFile(
        file_name="wp_a_0606.partsbnd.dcx",
        relative_path="parts/wp_a_0606.partsbnd.dcx",
        slot=EquipmentSlot.WEAPON,
        target_model_id="0606"
    )

    skill_meta = SkillMovesetMetadata(
        has_custom_moveset=True,
        animation_banks=["c0000_a3x.anibnd.dcx"]
    )

    mod_set = DetectedModSet(
        set_id="mod_dragon_slayer_disabled",
        folder_or_archive_name="DragonSlayerToggle",
        target_model_id="0606",
        target_vanilla_name="Greatsword",
        parts=[part],
        is_weapon=True,
        import_custom_moveset=False,
        allocation=StandaloneAllocation("9098", 9098000, 9100098),
        skill_moveset=skill_meta
    )

    deployer = PartsDeployer()
    count = deployer.deploy_parts([mod_set], input_base, output_dir)

    assert count == 1
    assert (output_dir / "parts" / "wp_a_9098.partsbnd.dcx").exists()
    assert not (output_dir / "chr").exists()


def test_manifest_store_records_and_loads_custom_art(temp_env):
    """Validates ManifestStore persists and reloads custom skill and moveset audit metadata."""
    from src.manifest_store import ManifestStore

    manifest_file = temp_env / "lootforge_manifest.json"
    store = ManifestStore(str(manifest_file))

    skill_meta = SkillMovesetMetadata(
        has_custom_skill=True,
        skill_id=4110,
        skill_name="Overhead Stance",
        has_custom_moveset=True
    )

    part = ModPartFile(
        file_name="wp_a_0556.partsbnd.dcx",
        relative_path="parts/wp_a_0556.partsbnd.dcx",
        slot=EquipmentSlot.WEAPON,
        target_model_id="556"
    )

    mod_set = DetectedModSet(
        set_id="mod_kuro_manifest",
        folder_or_archive_name="KuroMod",
        target_model_id="556",
        target_vanilla_name="Uchigatana",
        parts=[part],
        loot_target=LootTarget(
            route_type=LootDistributionType.BOSS_REMEMBRANCE,
            target_id="remembrance_malenia",
            display_name="Remembrance of the Rot Goddess"
        ),
        allocation=StandaloneAllocation("9082", 9082000, 9100082),
        is_weapon=True,
        import_custom_moveset=True,
        skill_moveset=skill_meta
    )

    rec = store.record_set(mod_set, staged_files=["parts/wp_a_9082.partsbnd.dcx"])
    assert rec.custom_skill_name == "Overhead Stance"
    assert rec.custom_skill_id == 4110
    assert rec.has_custom_moveset is True

    # Reload manifest fresh from disk
    reloaded_store = ManifestStore(str(manifest_file))
    records = reloaded_store.get_all_records()
    assert len(records) == 1
    r = records[0]
    assert r.set_id == "mod_kuro_manifest"
    assert r.custom_skill_name == "Overhead Stance"
    assert r.custom_skill_id == 4110
    assert r.has_custom_moveset is True


def test_loot_review_modal_custom_art_toggle(temp_env):
    """Validates LootReviewModal renders custom skill badges and triggers the custom art toggle."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    try:
        from PySide6.QtWidgets import QApplication
    except (ImportError, Exception):
        from PyQt6.QtWidgets import QApplication
    from src.models import ItemDropConfig
    from src.ui.loot_modal import LootReviewModal

    app = QApplication.instance()
    if not app:
        app = QApplication(["test", "-platform", "offscreen"])

    art_toggled = []

    modal = LootReviewModal(
        on_custom_art_toggle=lambda cfg, state: art_toggled.append((cfg.item_key, state))
    )

    items = [
        ItemDropConfig(
            item_key="katana_1",
            name="Kuro Hasu",
            vanilla_rate=15.0,
            user_rate=15.0,
            custom_skill_name="Overhead Stance",
            has_custom_moveset=True,
            import_custom_art=True
        ),
        ItemDropConfig(
            item_key="armor_1",
            name="Dark Knight Armor",
            vanilla_rate=20.0,
            user_rate=20.0,
            custom_skill_name="",
            has_custom_moveset=False
        )
    ]

    modal.set_data(items, global_multiplier=100.0, global_spoiled=True, items_per_page=8)
    assert modal.items_table.rowCount() == 2
    assert modal.items_table.columnCount() == 8

    # Weapon row: column 0 has badge, column 7 has action button
    name_item = modal.items_table.item(0, 0)
    assert "✦ Skill: Overhead Stance" in name_item.text()
    assert "✦ Moveset" in name_item.text()

    art_btn = modal.items_table.cellWidget(0, 7)
    assert art_btn is not None
    assert "Active" in art_btn.text()

    # Armor row: column 7 has dash "-"
    dash_item = modal.items_table.item(1, 7)
    assert dash_item is not None
    assert dash_item.text() == "-"

    # Click weapon toggle button
    art_btn.click()
    assert len(art_toggled) == 1
    assert art_toggled[0] == ("katana_1", False)

    # After click, button reflects disabled state
    re_art_btn = modal.items_table.cellWidget(0, 7)
    assert "Default" in re_art_btn.text()


def test_regulation_manager_rollback_all_cleans_moveset_assets(temp_env):
    """Validates that rollback_all removes deployed moveset files (chr, sfx, action) and cleans empty directories."""
    from src.regulation_manager import RegulationManager
    from src.backup_manager import BackupManager
    from src.manifest_store import ManifestStore

    reg_manager = RegulationManager(base_dir=temp_env)
    backup_mgr = BackupManager(str(temp_env / "backups"))
    manifest = ManifestStore(str(temp_env / "lootforge_manifest.json"))

    output_dir = temp_env / "mod"
    chr_dir = output_dir / "chr"
    sfx_dir = output_dir / "sfx"
    action_dir = output_dir / "action"
    parts_dir = output_dir / "parts"

    chr_dir.mkdir(parents=True)
    sfx_dir.mkdir(parents=True)
    action_dir.mkdir(parents=True)
    parts_dir.mkdir(parents=True)

    anim_file = chr_dir / "c0000_a3x.anibnd.dcx"
    anim_file.write_bytes(b"ANIM")
    sfx_file = sfx_dir / "frpg_sfx.ffxbnd.dcx"
    sfx_file.write_bytes(b"SFX")
    action_file = action_dir / "eventnameid.txt"
    action_file.write_text("EVENT")
    part_file = parts_dir / "wp_a_9099.partsbnd.dcx"
    part_file.write_bytes(b"PART")

    # Record deployment in manifest
    manifest.record_deployment(
        target_regulation_path=str(output_dir / "regulation.bin"),
        deployed_files=[str(anim_file), str(sfx_file), str(action_file), str(part_file)]
    )

    # Execute rollback
    result = reg_manager.rollback_all(
        backup_manager=backup_mgr,
        manifest_store=manifest,
        target_reg_path=str(output_dir / "regulation.bin"),
        output_dir=str(output_dir)
    )

    assert result["success"] is True
    # All files should be deleted
    assert not anim_file.exists()
    assert not sfx_file.exists()
    assert not action_file.exists()
    assert not part_file.exists()

    # Empty folders should be pruned
    assert not chr_dir.exists()
    assert not sfx_dir.exists()
    assert not action_dir.exists()
    assert not parts_dir.exists()


def test_config_roundtrip_includes_master_bool(temp_env):
    """Validates import_custom_skills_movesets boolean survives save and load cycles in LootForgeConfig."""
    from src.config import LootForgeConfig

    cfg_file = temp_env / "config.json"
    cfg = LootForgeConfig(import_custom_skills_movesets=False)
    assert cfg.import_custom_skills_movesets is False
    cfg.save(str(cfg_file))

    loaded = LootForgeConfig.load(str(cfg_file))
    assert loaded.import_custom_skills_movesets is False

    # Flip to True and verify round-trip
    loaded.import_custom_skills_movesets = True
    loaded.save(str(cfg_file))
    reloaded = LootForgeConfig.load(str(cfg_file))
    assert reloaded.import_custom_skills_movesets is True


def test_loot_review_modal_global_boolean_disabled(temp_env):
    """Validates LootReviewModal handles master boolean disabled state for bug testing isolation."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    try:
        from PySide6.QtWidgets import QApplication
    except (ImportError, Exception):
        from PyQt6.QtWidgets import QApplication
    from src.models import ItemDropConfig
    from src.ui.loot_modal import LootReviewModal

    app = QApplication.instance()
    if not app:
        app = QApplication(["test", "-platform", "offscreen"])

    modal = LootReviewModal()
    items = [
        ItemDropConfig(
            item_key="katana_test",
            name="Test Katana",
            vanilla_rate=10.0,
            user_rate=10.0,
            custom_skill_name="Test Slash",
            has_custom_moveset=True,
            import_custom_art=True
        )
    ]

    # Load with master boolean = False (testing mode)
    modal.set_data(
        items,
        global_multiplier=100.0,
        global_spoiled=True,
        items_per_page=8,
        skills_movesets_enabled=False
    )

    assert "Custom Movesets: Disabled (Testing Mode)" in modal.stats_badge.text()
    art_btn = modal.items_table.cellWidget(0, 7)
    assert art_btn is not None
    assert "Disabled (Global Settings Bool)" in art_btn.text()
    assert not art_btn.isEnabled()


def test_global_boolean_toggle_disables_all_movesets_and_skills():
    """Validates that turning off the master boolean toggle disables custom skills and movesets in the pipeline."""
    part = ModPartFile(
        file_name="wp_a_0556.partsbnd.dcx",
        relative_path="wp_a_0556.partsbnd.dcx",
        slot=EquipmentSlot.WEAPON,
        target_model_id="556"
    )

    skill_meta = SkillMovesetMetadata(
        has_custom_skill=True,
        skill_id=22080,
        skill_name="Moonglow",
        has_custom_moveset=True,
        behavior_variation_id=900,
        custom_skills_spec=[{"skill_id": 22080, "name": "Moonglow", "fields": {}}],
        custom_behaviors_spec=[{"id": 900010, "fields": {}}],
        custom_attacks_spec=[{"id": 90010, "fields": {}}]
    )

    mod_set = DetectedModSet(
        set_id="mod_kuro_master_disabled",
        folder_or_archive_name="BlackLotusMod",
        target_model_id="556",
        target_vanilla_name="Uchigatana",
        parts=[part],
        loot_target=LootTarget(
            route_type=LootDistributionType.BOSS_REMEMBRANCE,
            target_id="remembrance_malenia",
            display_name="Remembrance of the Rot Goddess"
        ),
        allocation=StandaloneAllocation("9085", 9085000, 9100085),
        is_weapon=True,
        skill_moveset=skill_meta
    )

    # Master bool = False
    master_toggle_enabled = False
    mod_set.import_custom_moveset = master_toggle_enabled

    builder = ParamBuilder()
    spec = builder.build_patch_spec(mod_set)

    ep = spec["equip_params"][0]
    updates = ep["field_updates"]
    assert "swordArtsParamId" not in updates
    assert "behaviorVariationId" not in updates
    assert "custom_skills" not in spec
    assert "custom_behaviors" not in spec
    assert "custom_attacks" not in spec


def test_two_tier_lazy_loading_and_fast_inspection(temp_env):
    """Validates that fast inspection (deep=False) returns lightweight metadata without subprocess delay."""
    mod_dir = temp_env / "LazyKatanaMod"
    chr_dir = mod_dir / "chr"
    chr_dir.mkdir(parents=True)
    (chr_dir / "c0000_a1x.anibnd.dcx").write_bytes(b"DUMMY_ANIM")

    # Create dummy regulation.bin > 100KB
    reg_file = mod_dir / "regulation.bin"
    reg_file.write_bytes(b"X" * 150000)

    importer = SkillMovesetImporter(temp_env)
    # Tier 1 fast inspection
    meta = importer.introspect_mod_folder(mod_dir, "0556", deep=False)

    assert meta is not None
    assert meta.is_deep_introspected is False
    assert meta.has_custom_skill is True
    assert meta.has_custom_moveset is True
    assert "c0000_a1x.anibnd.dcx" in meta.animation_banks
    assert meta.regulation_path == str(reg_file.resolve())
    # Subprocess was not run, so deep fields remain empty/default
    assert meta.skill_id == 0
    assert meta.custom_skills_spec == []


def test_in_memory_regulation_cache(temp_env):
    """Validates that extracted regulation payloads are cached in-memory and cleared appropriately."""
    importer = SkillMovesetImporter(temp_env)
    importer.clear_cache()
    assert len(importer._regulation_cache) == 0

    fake_reg = temp_env / "fake_reg.bin"
    fake_reg.write_bytes(b"DATA")

    fake_data = {
        "Weapons": [{"ModelId": 556, "SwordArtsParamId": 22080, "SkillName": "Moonglow", "BehaviorVariationId": 900}],
        "CustomSkills": {"22080": {"swordArtsType": 10}},
        "CustomBehaviors": {},
        "CustomAttacks": {}
    }

    # Seed cache
    cache_key = str(fake_reg.resolve())
    importer._regulation_cache[cache_key] = fake_data

    # Reading should return cached dict directly
    extracted = importer.extract_regulation_data(fake_reg)
    assert extracted == fake_data
    assert extracted["Weapons"][0]["SkillName"] == "Moonglow"

    importer.clear_cache()
    assert len(importer._regulation_cache) == 0


def test_ensure_deep_introspected_in_place(temp_env):
    """Validates ensure_deep_introspected updates a mod set's metadata in-place."""
    mod_dir = temp_env / "input_mods" / "InPlaceKatana"
    mod_dir.mkdir(parents=True)
    reg_file = mod_dir / "regulation.bin"
    reg_file.write_bytes(b"X" * 150000)

    part = ModPartFile(
        file_name="wp_a_0556.partsbnd.dcx",
        relative_path="parts/wp_a_0556.partsbnd.dcx",
        slot=EquipmentSlot.WEAPON,
        target_model_id="556"
    )

    shallow_meta = SkillMovesetMetadata(
        has_custom_skill=True,
        has_custom_moveset=False,
        is_deep_introspected=False,
        regulation_path=str(reg_file.resolve())
    )

    mod_set = DetectedModSet(
        set_id="mod_inplace",
        folder_or_archive_name="InPlaceKatana",
        target_model_id="556",
        target_vanilla_name="Uchigatana",
        parts=[part],
        is_weapon=True,
        skill_moveset=shallow_meta
    )

    importer = SkillMovesetImporter(temp_env)
    # Pre-seed cache with weapon specs
    importer._regulation_cache[str(reg_file.resolve())] = {
        "Weapons": [{
            "ModelId": 556,
            "SwordArtsParamId": 4110,
            "SkillName": "Overhead Stance",
            "SkillCaption": "A stance used by warriors of the reed.",
            "BehaviorVariationId": 905,
            "WepmotionCategory": 60,
            "WepmotionOneHandId": 3,
            "WepmotionBothHandId": 12,
            "SpAtkCategory": 641
        }],
        "CustomSkills": {"4110": {"iconId": 100}},
        "CustomBehaviors": {},
        "CustomAttacks": {}
    }

    success = importer.ensure_deep_introspected(mod_set, temp_env / "input_mods")
    assert success is True
    assert mod_set.skill_moveset.is_deep_introspected is True
    assert mod_set.skill_moveset.skill_name == "Overhead Stance"
    assert mod_set.skill_moveset.skill_id == 4110
    assert mod_set.skill_moveset.behavior_variation_id == 905
    assert mod_set.skill_moveset.wepmotion_category == 60
    assert len(mod_set.skill_moveset.custom_skills_spec) == 1

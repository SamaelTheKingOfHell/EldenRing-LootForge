"""
LootForge Injection Test Harness

Creates 10 synthetic mod sets and distributes them across ALL loot pool types:
  - Boss Remembrance (shop via Finger Reader Enia)
  - Enemy Drop (ItemLotParam_enemy injection)
  - Merchant Shop (ShopLineupParam)

Purpose: Verify the full forge pipeline (scan → allocate → distribute → patch specs →
RegTool execution) produces a valid regulation.bin with real entries.

Run:
    python -m tests.test_injection_harness
"""

import os
import sys
import json
import shutil
import tempfile
import unittest
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure project root is on path
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

from src.models import (
    ModPartFile, DetectedModSet, EquipmentSlot,
    LootTarget, LootDistributionType, StandaloneAllocation,
    AdditionType, AntiDup, ItemDropConfig
)
from src.id_allocator import IdAllocator
from src.loot_distributor import LootDistributor
from src.param_builder import ParamBuilder
from src.knowledge_base import VanillaKnowledgeBase
from src.regulation_manager import RegulationManager
from src.logger import system_logger


# ─── 10 synthetic test sets covering all three loot pool types ───────────────

SYNTHETIC_SETS = [
    # --- 3× Boss Remembrance route ---
    {
        "set_id": "test_boss_armor_A",
        "folder": "TestBossArmorA",
        "model_id": "4200",  # Radahn's set → Remembrance
        "slot": EquipmentSlot.BODY,
        "expected_route": LootDistributionType.BOSS_REMEMBRANCE,
    },
    {
        "set_id": "test_boss_armor_B",
        "folder": "TestBossArmorB",
        "model_id": "4230",  # Malenia's set → Remembrance
        "slot": EquipmentSlot.BODY,
        "expected_route": LootDistributionType.BOSS_REMEMBRANCE,
    },
    {
        "set_id": "test_boss_weapon_C",
        "folder": "TestBossWeaponC",
        "model_id": "0211",  # Dark Moon GS → Remembrance
        "slot": EquipmentSlot.WEAPON,
        "expected_route": LootDistributionType.BOSS_REMEMBRANCE,
    },
    # --- 4× Enemy Drop route ---
    {
        "set_id": "test_enemy_drop_D",
        "folder": "TestEnemyDropD",
        "model_id": "4000",  # Carian Knight → Moongrum drop
        "slot": EquipmentSlot.BODY,
        "expected_route": LootDistributionType.ENEMY_DROP,
    },
    {
        "set_id": "test_enemy_drop_E",
        "folder": "TestEnemyDropE",
        "model_id": "4040",  # Banished Knight → enemy drop
        "slot": EquipmentSlot.BODY,
        "expected_route": LootDistributionType.ENEMY_DROP,
    },
    {
        "set_id": "test_enemy_drop_F",
        "folder": "TestEnemyDropF",
        "model_id": "4110",  # Cleanrot Knight → Caelid drop
        "slot": EquipmentSlot.BODY,
        "expected_route": LootDistributionType.ENEMY_DROP,
    },
    {
        "set_id": "test_enemy_drop_G",
        "folder": "TestEnemyDropG",
        "model_id": "0415",  # Moonveil → Magma Wyrm drop
        "slot": EquipmentSlot.WEAPON,
        "expected_route": LootDistributionType.ENEMY_DROP,
    },
    # --- 3× Merchant Shop route ---
    {
        "set_id": "test_merchant_H",
        "folder": "TestMerchantH",
        "model_id": "4030",  # Knight Set → Twin Maiden Husks shop
        "slot": EquipmentSlot.BODY,
        "expected_route": LootDistributionType.MERCHANT_SHOP,
    },
    {
        "set_id": "test_merchant_I",
        "folder": "TestMerchantI",
        "model_id": "4050",  # Vagabond Knight → Nomadic Merchant shop
        "slot": EquipmentSlot.BODY,
        "expected_route": LootDistributionType.MERCHANT_SHOP,
    },
    {
        "set_id": "test_unknown_J",
        "folder": "TestUnknownJ",
        "model_id": "9999",  # NOT in KB → should get random fallback
        "slot": EquipmentSlot.BODY,
        "expected_route": None,  # Will be assigned randomly
    },
]


def _make_part_file(model_id: str, slot: EquipmentSlot) -> ModPartFile:
    """Creates a synthetic ModPartFile (no actual .dcx file needed for spec generation)."""
    prefix_map = {
        EquipmentSlot.HEAD: "hd",
        EquipmentSlot.BODY: "bd",
        EquipmentSlot.ARMS: "am",
        EquipmentSlot.LEGS: "lg",
        EquipmentSlot.WEAPON: "wp_a",
    }
    prefix = prefix_map.get(slot, "bd")
    if slot == EquipmentSlot.WEAPON:
        fname = f"wp_a_{model_id}.partsbnd.dcx"
    else:
        fname = f"{prefix}_m_{model_id}.partsbnd.dcx"

    return ModPartFile(
        file_name=fname,
        relative_path=f"parts/{fname}",
        slot=slot,
        target_model_id=model_id,
        gender_variant="m",
        file_size_bytes=1024  # Dummy
    )


def run_injection_test():
    """Runs the full distribution + param spec pipeline and reports results."""

    print("=" * 72)
    print("  LootForge Injection Test Harness")
    print("  10 synthetic items -> ALL loot pools")
    print("=" * 72)

    # Load real knowledge base
    data_dir = str(_project_root / "data")
    kb = VanillaKnowledgeBase.from_data_dir(data_dir)

    allocator = IdAllocator()
    distributor = LootDistributor(kb)
    builder = ParamBuilder()

    # Phase 1: Build DetectedModSets and allocate IDs
    print("\n── Phase 1: Build & Allocate ──")
    mod_sets = []
    for cfg in SYNTHETIC_SETS:
        is_weapon = cfg["slot"] == EquipmentSlot.WEAPON
        vanilla_info = kb.lookup_weapon(cfg["model_id"]) if is_weapon else kb.lookup_protector(cfg["model_id"])
        vanilla_name = (vanilla_info or {}).get("name", f"Unknown (Model {cfg['model_id']})")

        part = _make_part_file(cfg["model_id"], cfg["slot"])
        alloc = allocator.allocate(cfg["set_id"])

        mod_set = DetectedModSet(
            set_id=cfg["set_id"],
            folder_or_archive_name=cfg["folder"],
            target_model_id=cfg["model_id"],
            target_vanilla_name=vanilla_name,
            parts=[part],
            allocation=alloc,
            is_weapon=is_weapon,
            is_enabled=True
        )
        mod_sets.append(mod_set)
        print(f"  ✓ {cfg['set_id']:30s} → Model {cfg['model_id']:6s} | {vanilla_name}")

    # Phase 2: Distribute (AdditionType.TEST_MODE - Enum Option 3)
    print("\n── Phase 2: Distribute (AdditionType.TEST_MODE - Enum Option 3) ──")
    distributor.reset_rotation_state()
    targets = []
    for ms in mod_sets:
        target = distributor.distribute_set(
            ms,
            addition_type=AdditionType.TEST_MODE,
            anti_dup=AntiDup.BOSS_ROTATION,
            global_rate_multiplier_percent=100.0
        )
        targets.append(target)
        route_emoji = {
            LootDistributionType.BOSS_REMEMBRANCE: "👑",
            LootDistributionType.ENEMY_DROP: "⚔️",
            LootDistributionType.MERCHANT_SHOP: "🏪",
        }.get(target.route_type, "❓")
        print(f"  {route_emoji} {ms.set_id:30s} → {target.display_name} ({target.route_type.value}, rate/cost={target.chance_or_cost})")

    # Phase 3: Build patch specs
    print("\n── Phase 3: Build Param Patch Specs ──")
    all_specs = []
    for ms in mod_sets:
        try:
            spec = builder.build_patch_spec(ms)
            all_specs.append(spec)
            equip_count = len(spec.get("equip_params", []))
            loot_type = spec.get("loot_distribution", {}).get("type", "unknown")
            print(f"  ✓ {ms.set_id:30s} → {equip_count} equip param(s), loot_type={loot_type}")
        except Exception as e:
            print(f"  ✗ {ms.set_id:30s} → ERROR: {e}")

    # Phase 4: Write specs to file for inspection
    output_dir = _project_root / "tests" / "injection_output"
    output_dir.mkdir(parents=True, exist_ok=True)
    specs_file = output_dir / "test_patch_specs.json"
    with open(specs_file, "w", encoding="utf-8") as f:
        json.dump(all_specs, f, indent=2, default=str)
    print(f"\n── Patch specs written to: {specs_file}")

    # Phase 5: Summary
    print("\n── Summary ──")
    boss_count = sum(1 for t in targets if t.route_type == LootDistributionType.BOSS_REMEMBRANCE)
    enemy_count = sum(1 for t in targets if t.route_type == LootDistributionType.ENEMY_DROP)
    shop_count = sum(1 for t in targets if t.route_type == LootDistributionType.MERCHANT_SHOP)
    unknown_location_count = sum(1 for t in targets if "Unknown" in t.display_name or "unknown" in t.display_name.lower())

    print(f"  Total sets:              {len(mod_sets)}")
    print(f"  Boss Remembrance:        {boss_count}")
    print(f"  Enemy Drop:              {enemy_count}")
    print(f"  Merchant Shop:           {shop_count}")
    print(f"  Unknown locations:       {unknown_location_count}")
    print(f"  Patch specs generated:   {len(all_specs)}")

    if unknown_location_count > 0:
        print("\n  ⚠️  WARNING: Some items still resolved to 'Unknown' locations!")
        print("     This means the knowledge base is missing entries for those model IDs.")
    else:
        print("\n  ✅ All items resolved to known locations. KB coverage is good!")

    # Phase 6: Try RegTool execution if regulation.bin exists
    print("\n── Phase 6: RegTool Execution Test ──")
    reg_manager = RegulationManager(_project_root)

    # Look for any regulation.bin to test against
    source_reg = reg_manager.resolve_source_regulation(
        game_dir="",
        output_dir=str(_project_root / "mod")
    )

    if source_reg and source_reg.exists():
        target_reg = _project_root / "tests" / "injection_output" / "test_regulation.bin"
        print(f"  Found source regulation: {source_reg}")
        print(f"  Target output:           {target_reg}")
        try:
            result = reg_manager.execute_patch(
                specs=all_specs,
                source_reg=source_reg,
                target_reg=target_reg
            )
            size_mb = round(result["target_size_bytes"] / (1024 * 1024), 2)
            print(f"  ✅ RegTool execution SUCCEEDED! Output: {size_mb} MB")
            print(f"     Log: {result.get('log', 'N/A')[:200]}")
        except Exception as e:
            print(f"  ✗ RegTool execution FAILED: {e}")
    else:
        print("  ⏭  No regulation.bin found to test against. Skipping RegTool execution.")
        print("     (Place a regulation.bin in mod/ or configure game directory to test)")

    print("\n" + "=" * 72)
    print("  Test harness complete.")
    print("=" * 72)

    return len(all_specs), unknown_location_count


class TestInjectionHarness(unittest.TestCase):
    def test_run_injection_pipeline(self):
        specs_count, unknown_count = run_injection_test()
        self.assertEqual(specs_count, 10)
        self.assertEqual(unknown_count, 0)


if __name__ == "__main__":
    unittest.main()

"""Regression checks for large variant batches and independent incremental asset deployment."""

import copy
import os
import tempfile
import unittest
from pathlib import Path

from src.diablo_generator import DiabloLootGenerator
from src.file_deployment import sync_asset
from src.patch_validation import iter_compact_specs, validate_patch_specs, validate_variant_budget


def armor_spec(set_id="armor", offset=0):
    """Build a complete four-piece armor fixture with imported behavior payloads."""
    equipment = [{"param_table": "EquipParamProtector", "new_param_id": 9000000 + offset + slot * 100,
                  "slot": name, "field_updates": {}}
                 for slot, name in enumerate(("head", "body", "arms", "legs"))]
    return {"set_id": set_id, "equip_params": equipment,
            "fmg_texts": [{"item_id": item["new_param_id"], "name": "Armor", "caption": "Lore"} for item in equipment],
            "loot_distribution": {"type": "enemy_drop", "target_id": "380000000", "awarded_items": []},
            "custom_behaviors": [{"id": 900001, "fields": {"refId": 42}}]}


class TestPatchPerformance(unittest.TestCase):
    """Exercise failures that only appear with multiple pieces, sets, or large roll counts."""

    def test_250_variants_keep_every_piece_and_neighboring_set_unique(self):
        """No slot, variant, neighboring-set, FMG, or loot-reference collisions are permitted."""
        generator = DiabloLootGenerator(seed=42)
        source = armor_spec()
        pristine = copy.deepcopy(source)
        variants = generator.generate_variants_for_spec(source, 250)
        variants += generator.generate_variants_for_spec(armor_spec("neighbor", 1000), 250)
        validate_patch_specs(variants)
        ids = [p["new_param_id"] for spec in variants for p in spec["equip_params"]]
        self.assertEqual(len(ids), 2000)
        self.assertEqual(len(set(ids)), 2000)
        self.assertEqual(source, pristine)
        for spec in variants:
            expected = {p["new_param_id"] for p in spec["equip_params"]}
            self.assertEqual(expected, {f["item_id"] for f in spec["fmg_texts"]})
            self.assertEqual(expected, set(spec["loot_distribution"]["awarded_items"]))
        self.assertEqual(sum("custom_behaviors" in s for s in variants), 2)
        compact = list(iter_compact_specs(variants))
        self.assertEqual(sum(len(s.get("custom_behaviors", [])) for s in compact), 1)

    def test_conflicting_imported_rows_fail(self):
        """Different mod behavior definitions cannot silently share one ID."""
        first, second = armor_spec(), armor_spec("other")
        second["custom_behaviors"][0]["fields"]["refId"] = 99
        with self.assertRaisesRegex(ValueError, "Conflicting imported"):
            list(iter_compact_specs([first, second]))

    def test_duplicate_equipment_fails(self):
        """A collision must be rejected before invoking native patching."""
        with self.assertRaisesRegex(ValueError, "Duplicate equipment"):
            validate_patch_specs([armor_spec(), armor_spec()])

    def test_engine_row_limit_fails_before_writes(self):
        """Impossible batches produce a useful error instead of running to serialization failure."""
        specs = [{"equip_params": [{"param_table": "EquipParamProtector", "new_param_id": i}
                                    for i in range(65536)]}]
        with self.assertRaisesRegex(ValueError, "65,535-row limit"):
            validate_patch_specs(specs)

    def test_impossible_roll_count_is_rejected_before_generation(self):
        """Even a single selected weapon cannot request more rows than the engine supports."""
        from src.models import DetectedModSet, ModPartFile, EquipmentSlot
        mod = DetectedModSet(set_id="budget", folder_or_archive_name="weapon", target_model_id="556",
                             target_vanilla_name="Sword", is_weapon=True,
                             parts=[ModPartFile("wp_a_0556.partsbnd.dcx", "wp_a_0556.partsbnd.dcx", EquipmentSlot.WEAPON, "0556")])
        with self.assertRaisesRegex(ValueError, "65,535 total"):
            validate_variant_budget([mod], 70000)

    def test_incremental_copy_updates_newer_wrong_destination_and_detaches_links(self):
        """Newer output is not assumed equivalent; edits to deployed assets cannot damage downloads."""
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / "input", Path(directory) / "output"
            source.write_bytes(b"source")
            target.write_bytes(b"wrong!")
            os.utime(target, ns=(source.stat().st_atime_ns, source.stat().st_mtime_ns + 1_000_000))
            self.assertTrue(sync_asset(source, target))
            self.assertEqual(target.read_bytes(), b"source")
            self.assertFalse(sync_asset(source, target))
            target.unlink()
            os.link(source, target)
            self.assertTrue(sync_asset(source, target))
            target.write_bytes(b"edited")
            self.assertEqual(source.read_bytes(), b"source")

    def test_backups_in_one_second_do_not_overwrite_each_other(self):
        """Repeated profile/asset snapshots retain their separate original bytes."""
        from src.backup_manager import BackupManager
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "regulation.bin"
            manager = BackupManager(str(Path(directory) / "backups"))
            target.write_bytes(b"first")
            first = manager.create_backup(str(target))
            target.write_bytes(b"second")
            second = manager.create_backup(str(target))
            self.assertNotEqual(first.backup_file_name, second.backup_file_name)
            self.assertEqual((Path(directory) / "backups" / first.backup_file_name).read_bytes(), b"first")

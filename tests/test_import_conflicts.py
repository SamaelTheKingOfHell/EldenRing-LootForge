"""Regression tests for the reported attack 11 conflict and scoped, fresh import extraction."""

import json
import os
from pathlib import Path
import tempfile
import unittest

from src.patch_validation import iter_compact_specs
from src.skill_moveset_importer import SkillMovesetImporter
from src.skill_regulation_extractor import SkillRegulationExtractor


class TestImportConflicts(unittest.TestCase):
    """Use real schema definitions and filesystem caches instead of mocked extraction calls."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.importer = SkillMovesetImporter(self.root)
        SkillRegulationExtractor.clear_cache()

    def tearDown(self):
        SkillRegulationExtractor.clear_cache()
        self.temporary.cleanup()

    def cached_mod(self, name="weapon", model=556):
        """Stage a bounded extraction fixture with selected, unrelated and non-attack references."""
        directory = self.root / name
        directory.mkdir()
        regulation = directory / "regulation.bin"
        regulation.write_bytes(b"fixture-regulation")
        data = {"SchemaVersion": 2,
                "Weapons": [{"ModelId": model, "SwordArtsParamId": 4110, "BehaviorVariationId": 900}],
                "CustomSkills": {"4110": {"swordArtsType": 1}},
                "CustomBehaviors": {"900": [
                    {"_row_id": 100900001, "refType": 0, "refId": 123},
                    {"_row_id": 100900002, "refType": 1, "refId": 11},
                    {"_row_id": 100900003, "refType": 2, "refId": 456}],
                    "1699": [{"_row_id": 101699001, "refType": 0, "refId": 999}]},
                "CustomAttacks": {"123": {"atkPhys": 150}, "11": {"atkPhys": 0}, "999": {"atkPhys": 999}}}
        cache = self.importer.extractor.cache_path(regulation)
        cache.parent.mkdir(exist_ok=True)
        cache.write_text(json.dumps(data), encoding="utf-8")
        return directory, regulation, data

    def test_attack_11_padding_and_extraction_names_do_not_conflict(self):
        """The reported raw pad4 difference is irrelevant to the native writer."""
        first = {"set_id": "first mod", "custom_attacks": [{"id": 11, "fields": {
            "atkPhys": 120, "pad4": "AAAA/////wAAAAAAAAAAAAAAAA==", "_row_name": "first"}}]}
        second = {"set_id": "second mod", "custom_attacks": [{"id": 11, "fields": {
            "atkPhys": 120, "pad4": "AAAAAAAAAAAAAAAAAAAAAAAAAA==", "_row_name": "second"}}]}
        result = list(iter_compact_specs([first, second]))
        self.assertEqual(sum(len(s.get("custom_attacks", [])) for s in result), 1)

    def test_actual_attack_difference_still_names_both_mods(self):
        """Real new-row conflicts cannot become a silent first-wins overwrite."""
        specs = [{"set_id": name, "custom_attacks": [{"id": 90010, "fields": {"atkPhys": attack}}]}
                 for name, attack in (("first mod", 100), ("second mod", 200))]
        with self.assertRaisesRegex(ValueError, "first mod versus second mod.*atkphys"):
            list(iter_compact_specs(specs))

    def test_host_row_preservation_matches_native_injection(self):
        """Imports that native injection would skip cannot produce a preflight conflict."""
        specs = [{"custom_skills": [{"skill_id": 112, "fields": {"swordArtsType": value}}]}
                 for value in (1, 2)]
        result = list(iter_compact_specs(specs, {"custom_skills": {112}}))
        self.assertTrue(all("custom_skills" not in spec for spec in result))

    def test_only_selected_weapon_attack_dependencies_are_imported(self):
        """Bullet 11 and other weapon attack 999 never become this weapon's custom attacks."""
        directory, _, _ = self.cached_mod()
        metadata = self.importer.introspect_mod_folder(directory, "0556", deep=True)
        self.assertIsNotNone(metadata)
        self.assertEqual([attack["id"] for attack in metadata.custom_attacks_spec], [123])
        self.assertEqual(len(metadata.custom_behaviors_spec), 3)

    def test_unmatched_model_does_not_borrow_first_weapons_moveset(self):
        directory, _, _ = self.cached_mod()
        self.assertIsNone(self.importer.introspect_mod_folder(directory, "9999", deep=True))

    def test_same_size_same_filename_sources_have_distinct_caches(self):
        _, first, first_data = self.cached_mod("first", 556)
        _, second, second_data = self.cached_mod("second", 580)
        stamp = first.stat().st_mtime_ns
        os.utime(second, ns=(stamp, stamp))
        cache = self.importer.extractor.cache_path(second)
        cache.write_text(json.dumps(second_data), encoding="utf-8")
        self.assertNotEqual(self.importer.extractor.cache_key(first), self.importer.extractor.cache_key(second))
        self.assertEqual(self.importer.extract_regulation_data(first), first_data)
        self.assertEqual(self.importer.extract_regulation_data(second), second_data)

    def test_in_memory_cache_invalidates_on_source_change(self):
        _, regulation, data = self.cached_mod()
        self.assertEqual(self.importer.extract_regulation_data(regulation), data)
        old_key = self.importer.extractor.cache_key(regulation)
        stamp = regulation.stat().st_mtime_ns + 1_000_000
        regulation.write_bytes(b"changed-regulation")
        os.utime(regulation, ns=(stamp, stamp))
        changed = dict(data, Weapons=[{"ModelId": 999}])
        self.importer.extractor.cache_path(regulation).write_text(json.dumps(changed), encoding="utf-8")
        self.assertNotEqual(self.importer.extractor.cache_key(regulation), old_key)
        self.assertEqual(self.importer.extract_regulation_data(regulation), changed)

    def test_tool_and_message_changes_invalidate_cache(self):
        _, regulation, _ = self.cached_mod()
        first = self.importer.extractor.cache_key(regulation)
        tool = self.importer.extractor.regtool_dll
        tool.parent.mkdir(parents=True)
        tool.write_bytes(b"new native extractor")
        self.assertNotEqual(first, self.importer.extractor.cache_key(regulation))
        messages = self.root / "msg"
        messages.mkdir()
        archive = messages / "item.msgbnd.dcx"
        archive.write_bytes(b"message")
        before = self.importer.extractor.cache_key(regulation, messages)
        archive.write_bytes(b"new message")
        self.assertNotEqual(before, self.importer.extractor.cache_key(regulation, messages))

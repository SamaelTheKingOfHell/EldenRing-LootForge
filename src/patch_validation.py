"""Validate patch batches before assets or game output are written."""

from collections import Counter


def validate_variant_budget(mod_sets, variants_per_item):
    """Reject impossible selections before generating hundreds of thousands of relics."""
    counts = Counter()
    for mod_set in mod_sets:
        if not getattr(mod_set, "is_enabled", True):
            continue
        table = "EquipParamWeapon" if mod_set.is_weapon else "EquipParamProtector"
        counts[table] += len({part.slot for part in mod_set.parts}) * max(1, variants_per_item)
    for table, count in counts.items():
        if count > 65535:
            raise ValueError(f"{table} would need at least {count:,} new rows; Elden Ring permits 65,535 total. "
                             "Reduce variants per item or select fewer sets.")


def iter_compact_specs(specs, existing_imported_ids=None):
    """Emit imported skill/behavior/attack rows once across all sets, rejecting conflicting IDs."""
    known = {"custom_skills": {}, "custom_behaviors": {}, "custom_attacks": {}}
    from src.imported_param_fields import applied_fields, writable_import_fields
    schemas = {key: writable_import_fields(key) for key in known}
    existing = existing_imported_ids or {}
    for spec in specs:
        compact = spec.copy()
        for key, rows_by_id in known.items():
            if key not in spec:
                continue
            unique = []
            for row in spec[key]:
                row_id = row["skill_id" if key == "custom_skills" else "id"]
                # Native injection deliberately preserves host/overhaul rows.
                # Rows tagged as prior LootForge imports are purged and are not
                # included in this set, so a reforge still reinstalls them.
                if row_id in existing.get(key, ()):
                    continue
                previous = rows_by_id.get(row_id)
                if previous is not None:
                    prior_row, prior_fields, owner = previous
                    if prior_row is not row:
                        current_fields = applied_fields(row, schemas[key])
                        if prior_fields != current_fields:
                            changed = sorted(name for name in prior_fields.keys() | current_fields.keys()
                                             if prior_fields.get(name) != current_fields.get(name))
                            raise ValueError(f"Conflicting imported {key} ID {row_id}: {owner} versus "
                                             f"{spec.get('set_id', 'unnamed set')} (fields: {', '.join(changed[:5])}).")
                    continue
                rows_by_id[row_id] = (row, applied_fields(row, schemas[key]), spec.get("set_id", "unnamed set"))
                unique.append(row)
            if unique:
                compact[key] = unique
            else:
                compact.pop(key)
        yield compact


def validate_patch_specs(specs):
    """Reject duplicate item IDs and impossible table sizes instead of silently losing items."""
    counts = Counter()
    seen = set()
    for spec in specs:
        for item in spec.get("equip_params", []):
            key = (item["param_table"], item["new_param_id"])
            if key in seen:
                raise ValueError(f"Duplicate equipment ID {key[1]} in {key[0]}.")
            seen.add(key)
            if not item.get("update_existing"):
                counts[key[0]] += 1
                if counts[key[0]] > 65535:
                    raise ValueError(
                        f"{key[0]} exceeds Elden Ring's 65,535-row limit even before existing items. "
                        "Reduce variants per item or select fewer sets."
                    )

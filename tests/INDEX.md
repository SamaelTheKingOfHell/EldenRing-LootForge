# LootForge: Test Suites

Automated verification suites adhering to `[CS-NO-MOCK]`. Tests exercise concrete filesystem staging, ID range collision checks, SHA-256 backup verification, and parameter generation.

## Test Files

| File | Purpose |
| :--- | :--- |
| `INDEX.md` | Test suites directory reference. |
| `test_scanner.py` | Validates mod file pattern extraction and grouping into armor sets. |
| `test_id_allocator.py` | Validates standalone ID allocation without collisions. |
| `test_backup_manager.py` | Validates regulation.bin snapshotting, hashing, and rollback. |
| `test_param_builder.py` | Validates parameter spec construction for Boss Remembrances and enemy drops. |
| `test_loot_distributor.py` | Validates AdditionType & AntiDup Enums, set invariance, and rate color coding. |
| `test_qt_app.py` | Validates Qt GUI headless launch, manual folder pickers, path bindings, and presets. |
| `test_diablo_loot.py` | Validates Diablo-style ARPG affix rolling, weapon skills randomization, rarity tiers, and distribution pools. |
| `test_diablo_power.py` | Region/rarity potency, rarity floors, rare proc frequency and equipment categories, settings persistence, zero multipliers and strict region fallback. |
| `DiabloChecks/` | Installed PARAM template and common event serialization checks, field restoration, external-edit preservation and controlled family scaling. |
| `test_ui_modular_schema.py` | Validates modular parameter descriptors, widget factory generation, and interactive Loot Review Modal dialog. |
| `test_injection_harness.py` | Synthetic injection harness testing all loot pools and distribution modes. |
| `test_regulation_manager.py` | Validates non-destructive regulation decryption, parameter injection, and encryption. |
| `test_localization_parity.py` | Verifies 100% string key parity across all localization dictionaries (`[CS-LOCALIZATION]`). |
| `test_pricing_engine.py` | Validates power-scaled rune pricing, regional progression tiers, rarity multipliers, affixes, boss prestige, and sell ratios (`[CS-NO-MOCK]`). |
| `test_skill_moveset_importer.py` | Validates custom weapon skills extraction, moveset asset deployment (chr, sfx, action), parameter spec generation, and PartsDeployer integration. |
| `test_accessory_modular_injection.py` | Validates authentic talisman iconId extraction (>= 18000), absence of transparent/placeholder icons, and accessory FMG text specs. |
| `test_souls_armor_port.py` | Validates DS1 game discovery, flat-to-curve defense translation, FMG lore generation, and ParamBuilder integration (`[CS-NO-MOCK]`). |
| `verify_server.py` | End-to-end integration test validating HTTP API endpoints and UI asset serving (`[CS-NO-MOCK]`). |




## Patcher performance and capacity

- `test_refinement.py`: Real Qt aura toggles, legacy settings migration, positive affix/resource bonuses and preservation of vanilla text/economy specs.

- `test_loot_runtime_routes.py`: Weapon identity blocks, complete armor reservation, finite vendor stock and source-route immutability.
- `LootRuntimeChecks/`: Read-only exact encrypted-profile acceptance for original lotteries, complete generated rewards, armor assets, vendor stock and all installed FMG tables.

- `test_patch_performance.py`: Large multi-set variant, batch validation and incremental file safety regressions.
- `test_import_conflicts.py`: Attack ID 11 padding regression, selected-weapon dependencies, host-row preservation and extraction cache invalidation.
- `test_variant_capacity.py`: Exact maximum, source occupancy, vanilla inclusion and real companion-count parity.
- `test_qt_app.py`: Real Qt setting signals, immediate vanilla-toggle clamp/persistence, paired-limit invalidation and stale-worker protection (controlled capacity fixtures).
- `RegToolChecks/`: Dependency-free native PARAM/FMG, additive lottery preservation, backup recovery, accessory text, enrichment, infusion and transaction checks.
- `benchmark_patcher.py`: Reproducible pre-change versus current patch/generation benchmark.

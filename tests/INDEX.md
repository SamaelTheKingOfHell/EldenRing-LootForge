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
| `test_ui_modular_schema.py` | Validates modular parameter descriptors, widget factory generation, and interactive Loot Review Modal dialog. |
| `test_injection_harness.py` | Synthetic injection harness testing all loot pools and distribution modes. |
| `test_regulation_manager.py` | Validates non-destructive regulation decryption, parameter injection, and encryption. |
| `test_localization_parity.py` | Verifies 100% string key parity across all localization dictionaries (`[CS-LOCALIZATION]`). |
| `test_pricing_engine.py` | Validates power-scaled rune pricing, regional progression tiers, rarity multipliers, affixes, boss prestige, and sell ratios (`[CS-NO-MOCK]`). |
| `test_skill_moveset_importer.py` | Validates custom weapon skills extraction, moveset asset deployment (chr, sfx, action), parameter spec generation, and PartsDeployer integration. |
| `test_accessory_modular_injection.py` | Validates authentic talisman iconId extraction (>= 18000), absence of transparent/placeholder icons, and accessory FMG text specs. |
| `verify_server.py` | End-to-end integration test validating HTTP API endpoints and UI asset serving (`[CS-NO-MOCK]`). |



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
| `test_regulation_manager.py` | Validates non-destructive regulation decryption, parameter injection, and encryption. |
| `test_localization_parity.py` | Verifies 100% string key parity across all localization dictionaries (`[CS-LOCALIZATION]`). |
| `verify_server.py` | End-to-end integration test validating HTTP API endpoints and UI asset serving (`[CS-NO-MOCK]`). |

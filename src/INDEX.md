# LootForge: Source Modules Index

This directory contains the core Python engine implementation for LootForge, organized into decoupled single-responsibility classes adhering to `[CS-MODULAR]` and `[CS-DECOUPLE]`.

## Source Modules

| File | Class / Component | Purpose |
| :--- | :--- | :--- |
| `INDEX.md` | - | Index and reference for all source modules. |
| `config.py` | `LootForgeConfig` | Global configuration and auto-detection of Windows / Steam Deck game paths. |
| `models.py` | Data Models | Strongly typed dataclasses for mod items, ID allocations, and manifests. |
| `logger.py` | `EventLogger` | Real-time in-memory event logger supporting the developer console (`[CS-DEBUG]`). |
| `knowledge_base.py` | `VanillaKnowledgeBase` | Loads model catalog and resolves targeted vanilla gear and boss remembrances. |
| `id_allocator.py` | `IdAllocator` | Safe namespace allocation for standalone model IDs and param IDs. |
| `backup_manager.py` | `BackupManager` | Pre-write timestamped snapshots of `regulation.bin` and 1-click restore. |
| `scanner.py` | `ModScanner` | Discovers replacement partsbnd files, parses IDs, and groups sets. |
| `asset_renumberer.py` | `AssetRenumberer` | Stages and renumbers `.partsbnd.dcx` files to standalone IDs without overwriting originals. |
| `param_builder.py` | `ParamBuilder` | Builds patch records for `EquipParam`, `ItemLotParam`, `ShopLineupParam`, and FMG text. |
| `manifest_store.py` | `ManifestStore` | Ledger tracking injected items for auditability and clean 1-click rollbacks. |
| `loot_distributor.py` | `LootDistributor` | Calculates drop rates, set invariance, boss rotation, and color statuses. |
| `regulation_manager.py` | `RegulationManager` | Non-destructive regulation.bin decryptor, param patcher, and AES-256 encryptor. |
| `qt_app.py` | `LootForgeMainWindow` | Full Qt desktop GUI with folder pickers, Dark Souls theme, and developer drawer. |
| `server.py` | `LootForgeServer` | Lightweight cross-platform local HTTP server serving UI and REST APIs. |

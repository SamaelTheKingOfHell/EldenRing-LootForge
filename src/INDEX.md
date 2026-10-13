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
| `asset_renumberer.py` | `AssetRenumberer` | Stages and renumbers `.partsbnd.dcx` files to standalone IDs with cross-gender mesh mirroring. |
| `param_builder.py` | `ParamBuilder` | Builds patch records for `EquipParam`, `ItemLotParam`, `ShopLineupParam`, and FMG text with unisex protector support. |
| `manifest_store.py` | `ManifestStore` | Ledger tracking injected items for auditability and clean 1-click rollbacks. |
| `loot_distributor.py` | `LootDistributor` | Calculates drop rates, set invariance, boss rotation, and color statuses. |
| `diablo_affixes.py` | Diablo Affix Engine | Rarity tiers, affix definitions, stat deltas, Elden Ring SpEffect passives, and authentic WeaponSkill (Ash of War) pool. |
| `diablo_generator.py` | `DiabloLootGenerator` | Procedural multi-tier variant generator, affix roll engine, weapon skills randomization, and dynamic lore injector. |
| `pricing_engine.py` | `PricingEngine` | Dynamic power-based buy and sell price valuation engine for runes, equipment params, and shop lineups. |
| `regulation_manager.py` | `RegulationManager` | Non-destructive regulation.bin decryptor, param patcher, and AES-256 encryptor. |
| `parts_deployer.py` | `PartsDeployer` | Standalone .partsbnd.dcx model deployment and cross-gender mesh mirroring service. |
| `skill_moveset_importer.py` | `SkillMovesetImporter` | Mod regulation introspection, custom weapon skill & moveset extraction, and chr/sfx/action asset deployment. |
| `ui/` | UI Components | Themed styles (`theme.py`), modular parameter schema, widget factory, and modals. |
| `qt_app.py` | `LootForgeMainWindow` | Full Qt desktop GUI with schema-driven settings, Diablo ARPG card, and loot modal launcher. |
| `server.py` | `LootForgeServer` | Lightweight cross-platform local HTTP server serving UI and REST APIs. |

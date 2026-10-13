# LootForge: Source Modules Index

This directory contains the core Python engine implementation for LootForge, organized into decoupled single-responsibility classes adhering to `[CS-MODULAR]`, `[CS-DECOUPLE]`, and `[CS-GRANULARITY]`.

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
| `diablo_affix_roller.py` | `DiabloAffixRoller` | Rolls rarity tiers, prefixes/suffixes, and progression-balanced weapon skills. |
| `diablo_equipment_modifier.py` | `DiabloEquipmentModifier` | Routes affix stat deltas and SpEffect passives to equipment param dictionaries. |
| `diablo_text_formatter.py` | `DiabloTextFormatter` | Diablo-style item name formatting and rich lore caption assembly. |
| `diablo_vanilla_base_distributor.py` | `VanillaBaseDistributor` | Procedural standalone relic creation from curated vanilla base items. |
| `diablo_vanilla_stat_injector.py` | `VanillaStatInjector` | In-place procedural stat and affix infusion for vanilla items. |
| `diablo_variant_builder.py` | `DiabloVariantBuilder` | Multi-tier variant generation, rotation, and companion accessory distribution. |
| `diablo_generator.py` | `DiabloLootGenerator` | Unified coordinator for procedural Diablo-style ARPG variants and item infusion. |
| `pricing_engine.py` | `PricingEngine` | Dynamic power-based buy and sell price valuation engine for runes, equipment params, and shop lineups. |
| `regulation_manager.py` | `RegulationManager` | Non-destructive regulation.bin decryptor, param patcher, and AES-256 encryptor. |
| `rollback_manager.py` | `RollbackManager` | Comprehensively reverts all injected mod assets, parameters, and message files. |
| `game_assets_service.py` | `GameAssetsService` | Manages regulation resolution, backups, and message file extraction. |
| `parts_deployer.py` | `PartsDeployer` | Standalone .partsbnd.dcx model deployment and cross-gender mesh mirroring service. |
| `skill_moveset_importer.py` | `SkillMovesetImporter` | Mod regulation introspection, custom weapon skill & moveset extraction, and chr/sfx/action asset deployment. |
| `ui/` | UI Components | Themed styles (`theme.py`), modular parameter schema, widget factory, builder, orchestrator, and modals. |
| `qt_app.py` | `LootForgeMainWindow` | Full Qt desktop GUI coordinating layout, settings, and modal inspection. |
| `server.py` | `LootForgeServer` | Lightweight cross-platform local HTTP server serving UI and REST APIs. |

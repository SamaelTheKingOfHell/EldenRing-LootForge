# Elden Ring: LootForge — Roadmap

This roadmap defines the implementation phases for the cross-platform Standalone Mod and Loot Injector tool.

## Phase 1: Core Engine & Data Architecture
- [ ] Build the **Vanilla Model & Loot Knowledgebase** (`data/vanilla_mapping.json`):
  - Catalog vanilla model IDs (`XXXX`), associated armor/weapon names, base param IDs, and thematic acquisition types (Remembrance boss soul, enemy drop, or merchant).
- [ ] Implement the **ID Allocator & Collision Guard**:
  - Safe range definitions: Model IDs `9000-9999`, EquipParam IDs `9000000+`, ItemLot IDs `9100000+`.
  - Manifest validation to prevent collision across multiple user runs.
- [ ] Implement the **Safety & Backup Manager**:
  - Pre-write timestamped snapshots of `regulation.bin`.
  - Checksum validation (SHA-256) and one-click rollback engine.

## Phase 2: Param, FMG & Asset Processing Pipeline
- [ ] Implement **Mod Asset Scanner & Renumberer**:
  - Scan input folder/archives for `.partsbnd.dcx` files (`am_m_`, `bd_m_`, `hd_m_`, `lg_m_`, `wp_a_`).
  - Extract target vanilla model IDs and copy/renumber assets to newly allocated standalone IDs in the target mod directory.
- [ ] Implement **Param Patcher**:
  - Read and clone rows in `EquipParamProtector` and `EquipParamWeapon`.
  - Bind rows to the new model IDs, preserve defense/weight scaling, and set distinct sort values.
  - Patch `ItemLotParam_enemy` for enemy mob drops with configurable drop rates.
  - Patch `ShopLineupParam` for Remembrance / Finger Reader Enia boss exchanges.
- [ ] Implement **FMG Text & Lore Ingestion**:
  - Inject custom names and lore descriptions into `item.msgbnd.dcx` (`ProtectorName`, `WeaponName`, `ProtectorCaption`).
  - Apply custom markers (e.g. `✦ [Relic]`) to in-game item titles.

## Phase 3: Manifest & Reversible Tagging Engine
- [ ] Implement `lootforge_manifest.json` tracker:
  - Record generated IDs, original mod file paths, injection targets, and timestamps.
- [ ] Implement 1-click **Uninstall / Clean Re-roll**:
  - Prunes generated rows and removes staged mod assets without affecting vanilla files or unrelated mods.

## Phase 4: Cross-Platform Modern GUI
- [ ] Develop the user interface:
  - Dark fantasy Souls aesthetic (obsidian slate background, antique gold `#c5a059` highlights, glowing runes).
  - Drag-and-drop mod importer zone.
  - Interactive Mod Review Table: Displays detected vanilla set, assigned standalone IDs, and selectable loot target (Boss Soul vs. Enemy drop).
  - 1-click "Forge & Inject" pipeline execution with real-time progress steps.
- [ ] Implement **Developer Console & Debug Floating Button** (`[CS-DEBUG]`):
  - Glowing circular floating button intercepting and rendering logs in real-time.
  - Global `debug` mode toggle.
- [ ] Implement **Universal Localization** (`[CS-LOCALIZATION]`):
  - Structured string catalogs for `en` and `pt-br` with 100% key parity.

## Phase 5: Cross-Platform Packaging & Verification
- [ ] Validate on Windows 10/11 and Linux (Steam Deck Proton / SteamOS paths).
- [ ] End-to-end automated tests with sample replacer assets.

# Elden Ring: LootForge — Roadmap

This roadmap defines the implementation phases for the cross-platform Standalone Mod and Loot Injector tool.

## Phase 1: Core Engine & Data Architecture
- [x] Build the **Vanilla Model & Loot Knowledgebase** (`data/vanilla_mapping.json`):
  - Catalog vanilla model IDs (`XXXX`), associated armor/weapon names, base param IDs, and thematic acquisition types (Remembrance boss soul, enemy drop, or merchant).
- [x] Implement the **ID Allocator & Collision Guard**:
  - Safe range definitions: Model IDs `9000-9999`, EquipParam IDs `9000000+`, ItemLot IDs `9100000+`.
  - Manifest validation to prevent collision across multiple user runs.
- [x] Implement the **Safety & Backup Manager**:
  - Pre-write timestamped snapshots of `regulation.bin`.
  - Checksum validation (SHA-256) and one-click rollback engine.

## Phase 2: Param, FMG & Asset Processing Pipeline
- [x] Implement **Mod Asset Scanner & Renumberer**:
  - Scan input folder/archives for `.partsbnd.dcx` files (`am_m_`, `bd_m_`, `hd_m_`, `lg_m_`, `wp_a_`).
  - Extract target vanilla model IDs and copy/renumber assets to newly allocated standalone IDs in the target mod directory.
- [x] Implement **Param Patcher**:
  - Read and clone rows in `EquipParamProtector` and `EquipParamWeapon`.
  - Bind rows to the new model IDs, preserve defense/weight scaling, and set distinct sort values.
  - Patch `ItemLotParam_enemy` for enemy mob drops with configurable drop rates.
  - Patch `ShopLineupParam` for Remembrance / Finger Reader Enia boss exchanges and merchants.
- [x] Implement **FMG Text & Lore Ingestion**:
  - Inject custom names and lore descriptions into `item.msgbnd.dcx` (`ProtectorName`, `WeaponName`, `ProtectorCaption`).
  - Mirror custom entries into DLC message packages (`item_dlc02.msgbnd.dcx`).
  - Apply custom markers (e.g. `✦ [LootForge]`) to in-game item titles.

## Phase 3: Manifest & Reversible Tagging Engine
- [x] Implement `lootforge_manifest.json` tracker:
  - Record generated IDs, original mod file paths, injection targets, and timestamps.
- [x] Implement 1-click **Uninstall / Clean Re-roll**:
  - Prunes generated rows and removes staged mod assets without affecting vanilla files or unrelated mods.

## Phase 4: Cross-Platform Modern GUI & Modular Architecture
- [x] Develop the user interface:
  - Dark fantasy Souls aesthetic (obsidian slate background, antique gold `#c5a059` highlights, glowing runes).
  - Drag-and-drop mod importer zone.
  - Interactive Mod Review Table: Displays detected vanilla set, assigned standalone IDs, and selectable loot target (Boss Soul vs. Enemy drop).
  - 1-click "Forge & Inject" pipeline execution with real-time progress steps.
- [x] Implement **Developer Console & Debug Floating Button** (`[CS-DEBUG]`):
  - Glowing circular floating button intercepting and rendering logs in real-time.
  - Global `debug` mode toggle.
- [x] Implement **Universal Localization** (`[CS-LOCALIZATION]`):
  - Structured string catalogs for `en` and `pt-br` with 100% key parity.
- [x] Decompose monoliths into single-responsibility modules adhering to `[CS-MODULAR]` & `[CS-GRANULARITY]`:
  - `tools/RegTool`: Decomposed into `Program.cs`, `PatchService.cs`, `ParamInjector.cs`, `FmgInjector.cs`, and `ParamHelper.cs`.
  - `src/`: Decomposed `PartsDeployer` and `src/ui/theme.py`.

## Phase 5: Cross-Platform Packaging & Verification
- [x] Validate on Windows 10/11 and Linux (Steam Deck Proton / SteamOS paths).
- [x] End-to-end automated tests with synthetic replacer assets and verification test harness.

## Phase 6: Diablo-Style Procedural ARPG Loot System
- [x] **Rarity Tiers & Weight Engine** (`src/diablo_affixes.py`):
  - Common, Magic, Rare, Legendary, and Mythic tiers with star ratings and authentic ARPG roll distributions.
- [x] **Extensive Elden Ring Affix Library** (`src/diablo_affixes.py`):
  - Elemental attack infusions (Fire, Lightning, Magic/Frost, Holy), physical scalings (Str, Dex), and defenses (Physical, Poise, Elemental Wards).
  - Authentic `SpEffectParam` passives: HP regeneration (Blessed Dew), FP on kill (Ancestral Horn), Stamina recovery (Green Turtle), successive hit attack ramps (Rotten Winged Insignia), critical strike recovery, and low-HP buffs.
- [x] **Procedural Variant Generator** (`src/diablo_generator.py`):
  - Generates multiple uniquely-rolled instances per base item/set (scalable up to 1,000+ variants per item) with non-colliding ID offsets.
- [x] **Dynamic Diablo Naming Convention**:
  - Dynamically synthesizes item titles: `✦ [LootForge] [{Rarity}] {Prefix} {BaseName} {Suffix} ({Slot})`.
- [x] **In-Game Lore & Affix Breakdowns**:
  - Injects rarity tier, star ratings, and detailed affix descriptions formatted strictly at the bottom of item descriptions in `item.msgbnd.dcx` and `item_dlc02.msgbnd.dcx`.
- [x] **Modular Integration & User Configuration** (`src/config.py`):
  - Optional toggle via `diablo_loot_enabled`, configurable instance counts (`diablo_variants_per_item`), and reproducible RNG seeding (`diablo_seed`).

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

## Phase 7: Robust Loot Routing & Regulation Clean-Up Pipeline
- [x] **Pre-Patch Regulation Purge**:
  - Automatically wipes previous LootForge item injections in `ItemLotParam_enemy` (clearing slots 1-8 of vanilla mobs), `ShopLineupParam`, `EquipParamWeapon`, `EquipParamProtector`, and `SpEffectParam` before applying new patch specs, preventing stale test mode drops from accumulating across forge runs.
- [x] **Authentic Regional Enemy Lot Mapping**:
  - Elite enemies mapped to their authentic regional `lotParamId`s across the Lands Between (Raya Lucaria Academy, Auriza Hero's Grave, Deeproot Depths, Caelid, Altus Plateau, Consecrated Snowfield, etc.) rather than defaulting to early-game Gatefront mobs.
- [x] **Boss Weapon Retention in Standard Addition**:
  - Boss weapons preserve their authentic Finger Reader Enia Remembrance exchanges without cascading into wild starting mobs.
- [x] **UI Forge Synchronization**:
  - `_forge_mods` immediately re-synchronizes active dropdowns, drop rate spinboxes, and multipliers right before executing the patch.

## Phase 8: Modular Schema-Driven UI & Dedicated Loot Modal
- [x] **Data-Driven Parameter Schema (`src/ui/param_schema.py`)**:
  - Strongly-typed parameter descriptors (`ParamDescriptor`, `ParamType`, `ParamPurpose`) decoupling engine parameter definitions from visual rendering per `[CS-DECOUPLE]`.
  - Automatic organization into purposeful cards: Loot & Drop Rules (Enums, Multipliers), Diablo ARPG Generator (Bools, Variant Counts, Seeds), and Staging Paths.
- [x] **ParamWidgetFactory (`src/ui/param_widget_factory.py`)**:
  - Automatically constructs Dark Souls styled controls (QComboBox, QSpinBox, QSlider, QCheckBox, Path LineEdit + Browse) and groups them by purpose.
- [x] **Interactive Loot Review Modal (`src/ui/loot_modal.py`)**:
  - Extracted giant static table into a spacious, dedicated modal dialog (`QDialog`).
  - Features real-time search filtering across item names and drop locations, page size selector, global mystery mode toggle, editable drop rate spinboxes with color status, and pagination.
- [x] **Full Diablo UI Integration & Pipeline Execution**:
  - Exposed Diablo procedural loot toggle, scalable variants count (1 to 1,000 instances), and optional seed controls directly in UI.
  - Automatically invokes procedural variant generation during `_forge_mods()` with synchronized `awarded_items` for authentic in-game discovery.

## Phase 9: Vanilla Item Infusion & Base Item Distribution
- [x] **Vanilla Item Stat Infusions (`diablo_inject_vanilla_stats`)**:
  - Direct procedural Diablo stat/affix injection into base vanilla `EquipParamWeapon` and `EquipParamProtector` rows with `update_existing` support in RegTool.
  - Dynamically titles and appends Diablo rarity and affix breakdowns to vanilla item lore descriptions in FMGs.
- [x] **Vanilla Items as Base Distribution Items (`diablo_use_vanilla_base_items`)**:
  - Uses cataloged vanilla weapons and armor sets as base items to create standalone procedural relics without requiring replacement mods.
  - Distributes variants organically across bosses, merchants, chests, and enemies.

## Phase 10: Cross-Gender Mesh Mirroring & Unisex Armor Support
- [x] **Automatic Cross-Gender Armor Mirroring (`src/parts_deployer.py` & `src/asset_renumberer.py`)**:
  - Mirrors single-gender model files (`_m_` <-> `_f_`) across all armor slots (`am_`, `bd_`, `hd_`, `lg_`), ensuring both Type A (Male) and Type B (Female) body types render custom armor without invisible limbs or floating heads.
  - Preserves authentic meshes when mod author supplies both variants without overwriting.
  - Seamlessly tracks mirrored files in manifest and deployment ledgers for clean 1-click rollback.
- [x] **Universal Unisex Parameter Enforcement (`src/param_builder.py` & `tools/RegTool/EquipInjector.cs`)**:
  - Explicitly sets `equipModelGender = 0` on all forged and cloned `EquipParamProtector` rows, eliminating equip lockouts.
  - Cleansed title and lore descriptions of gender-restriction tags.

## Phase 11: High-Value Post-Boss Chests & Progression-Locked Anti-Duplication
- [x] **Post-Boss Chest Routing (`AntiDup.CHEST_AFTER_BOSS`)**:
  - Direct routing of custom items into canonical treasure chests located in or after major boss chambers.
  - Automatic boss rotation cascade directly to post-boss chests when tier boss capacity (1 set per boss) is exhausted.
- [x] **High-Value Multi-Injection Chests**:
  - Guaranteed Legendary / Mythic tier rolls in Diablo procedural mode (`roll_rarity(..., is_chest=True)`).
  - Bundled multi-companion accessory injections (`num_extra = 2`, delivering $\ge 3$ awarded items total) via non-destructive sequential lot chaining in `ItemLotParam_map` (`targetLotId + 1..9`).
- [x] **Strict 4-Tier World Progression Gating (`ProgressionTier`)**:
  - Partitioned items and encounter destinations into Early, Mid, Late, and Endgame tiers.
  - Strict progression locking preventing late-game items from appearing in early regions.



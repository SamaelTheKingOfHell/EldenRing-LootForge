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
### Progression power, optional combat enchantments and auras (2026-10-15)
- [x] Separate persisted Diablo settings for regional power, additional passives, rare Legendary/Mythic combat magic and cosmetic auras.
- [x] Nine deterministic visual themes using neutral effect attachments and low-priority VFX; preserve buff eligibility.
- [x] Enforce affix rarity floors, preserve early rare Legendary rolls, scale stats and passive chains by regional tier, and prevent empty regional pools from falling back across progression.
- [x] Additional native HP/FP/stamina/recovery/ward passives, including weapon rolls; bounded script triggers for attacking, guarding and armor retaliation/healing.
- [x] Reversible in-place infusion, external-edit preservation, family-consistent weapon bonuses and existing common-script merging.
- [x] Build and deploy the local Release patcher; exercise the full copied-profile forge pipeline, binary round-trips and Qt controls.
- [ ] In-game acceptance of casts, healing, retaliation, cooldowns, aura/buff overlap and unequip/disable behavior on freshly forged gear. Armor retaliation is a magic burst, not a percentage reflection of incoming damage.

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
  - Preserves vanilla names, descriptions and info; restores earlier generated text from per-language history (refinement correction).
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
  - Progression-weighted chest rarities with rare early Legendary/Mythic discoveries.
  - A 7% chance of one regional bonus accessory; no unconditional companion bundles. Only attached, one-time chest records qualify (2026-10-16 correction).
- [x] **Strict 4-Tier World Progression Gating (`ProgressionTier`)**:
  - Partitioned items and encounter destinations into Early, Mid, Late, and Endgame tiers.
  - Strict progression locking preventing late-game items from appearing in early regions.

## Phase 12: Progression-Balanced Ashes of War (Weapon Skills)
- [x] **Progression-Tiered Weapon Skill Categorization (`src/diablo_affixes.py`)**:
  - Categorized all authentic Ashes of War (`DEFAULT_WEAPON_SKILLS` and Paramdex definitions) across `ProgressionTier` (Early, Mid, Late, Endgame).
  - Early: Starter/early ashes (Impaling Thrust, Unsheathe, Bloody Slash, Sacred Blade, Gravitas, Quickstep, Reduvia Blood Blade, etc.).
  - Mid: Mid-game ashes (Lion's Claw, Blood Tax, Double Slash, Giant Hunt, Glintblade Phalanx, Ice Spear, Hoarfrost Stomp, Transient Moonlight, etc.).
  - Late: Late-game ashes (Prelate's Charge, Prayerful Strike, Waves of Darkness, Royal Knight's Resolve, Bloodhound's Step, Moonlight Greatsword, Taker's Flames, etc.).
  - Endgame: Top boss/endgame ashes (Waterfowl Dance, Destined Death, Corpse Piler, Bloodboon Ritual, Wave of Gold, Swift Slash, etc.).
- [x] **Tier-Weighted Weapon Skill Rolling Engine (`src/diablo_generator.py`)**:
  - `roll_weapon_skill(tier=...)` partitions the weapon skill pool and bounds roll possibilities strictly by the encounter/item progression tier (Early tier has 0% chance of Mid/Late/Endgame; Mid tier has 0% chance of Late/Endgame, etc.).
- [x] **Configurable Toggle & UI Integration (`diablo_balance_weapon_skills_by_progression`)**:
  - Added boolean toggle (defaults to `True`) enabling players to preserve progression balance or opt into unbound chaotic rolls across all tiers.
  - Fully integrated across `LootForgeConfig`, UI schema (`ParamDescriptor`), and Qt app.

## Phase 14: Dynamic Power-Scaled Economy & Pricing Engine
- [x] **Modular Pricing Engine (`src/pricing_engine.py`)**:
  - Calculates dynamic, authentic Rune valuations for buying (`ShopLineupParam.value`, `saleValue`, `basicPrice`) and selling (`EquipParamWeapon.sellValue`, `EquipParamProtector.sellValue`, `EquipParamAccessory.sellValue`).
  - Finalized native damage, scaling, negation, poise, buildup and passive strength determine prices; no tier/rarity/prestige premium. Sale returns are small and bounded (refinement correction).
- [x] **Granular Multi-Piece Set Valuation (`tools/RegTool/LootInjector.cs`)**:
  - Implemented per-item pricing support via `item_prices` dictionary in `loot_distribution`. Chest armor commands higher value than gauntlets within the same set, with seamless fallback for standard standalone sets.
- [x] **In-Game Economy Integration & FMG Lore Presentation**:
  - Native final valuation updates generated equipment/vendor prices; vanilla infusion preserves original prices.
  - Original vanilla lore is preserved. Generated captions omit the redundant economy panel to fit the game layout.
- [x] **Full Config & Regression Suite**:
  - Configurable scaling parameters (`price_power_scaling_enabled`, `price_multiplier`, `sell_price_ratio`) in `src/config.py`.
  - Comprehensive unit and integration test suite in `tests/test_pricing_engine.py` verifying mathematical bounds, rounding, and patch spec integrations (`[CS-NO-MOCK]`).

## Phase 15: Custom Skills & Movesets Porting Engine
- [x] **Mod Regulation Introspection (`tools/RegTool/SkillMovesetService.cs`)**:
  - Discovers and decrypts mod `regulation.bin` in intake directories.
  - Extracts custom weapon definitions, `swordArtsParamId`, `behaviorVariationId`, and animation category mappings (`wepmotionCategory`, `wepmotionOneHandId`, `wepmotionBothHandId`, `spAtkCategory`).
  - Traces and extracts custom `SwordArtsParam`, `EquipParamGem`, `BehaviorParam_PC`, `AtkParam_Pc`, `SpEffectParam`, and `Bullet` records.
  - Ingests custom skill titles and descriptions from mod FMGs (`item.msgbnd.dcx`).
- [x] **Moveset & Animation Asset Deployment (`src/skill_moveset_importer.py` & `src/parts_deployer.py`)**:
  - Discovers player character animation containers (`chr/c0000_a*.anibnd.dcx`, `chr/c0000.behbnd.dcx`), visual effects (`sfx/`), and action dictionaries (`action/`).
  - Safely deploys them into Mod Engine 2 staging directories with case normalization.
- [x] **Parameter Injection & Standalone Binding (`tools/RegTool/PatchService.cs` & `src/param_builder.py`)**:
  - Binds standalone forged weapons to custom skill IDs and behavior variations.
  - Injects extracted skill and moveset parameter rows into the target `regulation.bin`.
  - Injects skill name and caption texts into `item.msgbnd.dcx`.
  - Supports clean purge and uninstallation tracking via `lootforge_manifest.json`.
- [x] **UI & Review Table Custom Art Controls (`src/ui/loot_modal.py` & `src/qt_app.py`)**:
  - Real-time badges for custom skills (`✦ Skill: <Name>`) and movesets (`✦ Moveset`) in the review table.
  - Per-item action toggle allowing players to choose between custom mod art vs default vanilla/Diablo roll.
- [x] **Audit Logging & Clean Rollback (`src/manifest_store.py` & `src/regulation_manager.py`)**:
  - Full audit logging of custom skill names, IDs, and moveset flags in `lootforge_manifest.json`.
  - 1-click comprehensive rollback unlinks deployed moveset files across `chr/`, `sfx/`, and `action/`, and prunes empty folders.

## Phase 13: Dark Souls 1/2/3 Legacy Armor Porting Subsystem
- [x] **Client-Side Game Installation Discovery**:
  - Automated detection of Steam/local installations of DS1 (PTDE/DSR), DS2 (SOTFS), and DS3 via registry and `libraryfolders.vdf` (`src/souls_port_adapter.py` & `SoulsGameDiscovery`).
- [x] **Selective In-Memory Archive Extraction**:
  - High-performance random-access BHD5/BDT extraction of armor `parts/` archives, FMG lore texts, and `EquipParamProtector` stats without requiring 50 GB full game unpacking (`tools/RegTool/SoulsPort/Ds1ArchiveReader.cs`).
- [x] **FLVER2 & MATBIN Conversion Engine**:
  - Upgrading legacy FLVER headers (0x2000C -> 0x20014), re-packing vertex buffer layouts to Elden Ring 40-byte rigged armor layout, re-targeting `.mtd` shaders to `.matbin` PBR shaders, and compressing with Oodle (`DCX_KRAK`) (`tools/RegTool/SoulsPort/FlverModernizer.cs`).
- [x] **Skeletal Bone Remapping & Unisex Mirroring**:
  - Translating legacy Havok skeleton nodes to Elden Ring's `c0000` player skeleton, with automated cross-gender mesh mirroring (`_m_` and `_f_`) and unisex parameter enforcement (`equipModelGender = 0`).
- [x] **Pre-Diablo Integration & Drop Distribution**:
  - Ingesting ported sets as authentic `DetectedModSet` objects into LootForge's standalone ID allocator, boss remembrance exchanges, post-boss chests, and optional Diablo procedural ARPG stat infusion with authentic DS1 lore descriptions and converted absorption curves.

## Phase 14: Equipment Category Decoupling & Talisman System Parity
- [x] **Modular Equipment Injector Decomposition (`[CS-MODULAR]`, `[CS-DECOUPLE]`, `[CS-GRANULARITY]`)**:
  - Decomposed monolithic equipment injection into single-responsibility modules: `ProtectorInjector.cs`, `WeaponInjector.cs`, and `AccessoryInjector.cs` (<= 240 lines each).
  - Isolated accessory mutations so that armor and weapon modifications can never regress accessory injection and vice-versa.
- [x] **Accessory Regulation Name-Stripping Resilience & Authentic Icons**:
  - Updated `AccessoryInjector.cs` to prevent valid talismans from being rejected when regulation binary files strip row names.
  - Eliminated transparent placeholder icon bug (row ID 1000) by strictly resolving and validating authentic talisman icon IDs (>= 18000, Crimson Amber Medallion fallback 18000).
  - Captured `IconId` in `SmartDiscoveryModels.cs`, `SmartDiscoveryService.cs`, `KnowledgeLoader`, and variant generation pipelines.
- [x] **DLC Message Archive Parity & Elimination of `?AccessoryName?`**:
  - Implemented `FmgArchiveService.cs` matching all category variants (`_dlc01`, `_dlc02`, base) across `item.msgbnd.dcx`, `item_dlc01.msgbnd.dcx`, and `item_dlc02.msgbnd.dcx`.
  - Guaranteed custom accessory, weapon, and armor text entries are written to all active DLC FMG containers.




## Patcher Performance & Capacity (2026-10-14)
- [x] Share imported payloads and cache schema, world/tier and free-slot lookups.
- [x] Combine patching and vanilla infusion into one regulation/archive pass.
- [x] Allocate unique procedural IDs and reject row collisions/engine overflow.
- [x] Calculate and enforce selection/source-aware variant maximums, including vanilla bases and companion talismans, in the Qt UI and forge pipeline.
- [x] Preserve existing loot chain/tutorial rewards and make repeated infusion stable.
- [x] Stage native output transactionally and deploy independent assets beside the selected regulation.
- [x] Retain real-regulation benchmark, Python/native tests and actual Qt capacity transitions. See `docs/PATCHER_PERFORMANCE.md`.
- [ ] Independent copied-profile/gameplay acceptance of acquisition, save/reload, visuals and new item IDs.
- [x] Correct reported attack ID 11 false conflicts: compare writable fields, select only the weapon's actual attack dependencies, preserve host-owned rows and invalidate aliased/stale extraction caches (2026-10-15).
- [x] Finite, provenance-backed destination capacity and strict progression fallbacks (2026-10-16).
- [ ] Follow-up audits: asynchronous forging and full asset/manifest transactionality.

## Additive loot and accessory inventory follow-up (2026-10-15)
- [x] Replace mixed original/custom lotteries with independent chained rolls across direct drops, shops, boss and chest enrichment.
- [x] Recover legacy mixed slots only from a clean backup whose unrelated data matches; preserve item categories during cleanup.
- [x] Include independent loot-row space in variant capacity and serialize explicit PARAM IDs in sorted order.
- [x] Precompute both vanilla modes so toggling immediately clamps and saves the selected variants; reject stale worker results and invalidate changed source/tool limits.
- [x] Patch installed message languages/DLC archives, fail on missing name tables and prune only obsolete generated text IDs.
- [ ] Confirm the reported English inventory accessory name/icon failure in Elden Ring. Current selected-profile rows have valid English name entries and nonzero icons; source-file validation does not establish runtime acceptance.

## Runtime inventory and loot repair (2026-10-16)
- [x] Correct weapon reinforcement/name blocks and canonical clone discovery; bound captions to six lines.
- [x] Replace guessed loot targets with MSB chest/NPC references, boss award events and ESD-opened shop intervals.
- [x] Preserve one-time map flags, finite vendor stock and original loot; reject unrelated table overflow.
- [x] Remove guaranteed medallion bundles; reserve complete armor groups and scale inherited starter passives.
- [x] Reforge and deploy all 469 selected input groups into Ordo Perfectus: 1,203 weapons, 324 armor pieces and 32 bonus talismans; three variants per input group.
- [x] Pass 148 Python tests, 53 native regressions, 11,078 magic checks and 64,730 exact deployed-file checks. Retain identities and coverage in `docs/LOOT_RUNTIME_VALIDATION.json`.
- [ ] Actual game retest of descriptions, pickups, boss awards, ordinary rest/reload, vendor stock, armor visuals and combat effects. No save identities were migrated.

## Equipment refinement (2026-10-16)
- [x] Normalize generated armor to native negation with zero obsolete flat defense, slot/region caps and bounded poise.
- [x] Preserve native weapon damage channels and buildup; bound only added bonuses and keep positive effects useful.
- [x] Restore vanilla names/info/descriptions and prices, prevent future replacements and preserve passive UI slot originals across rerolls.
- [x] Price finalized combat strength without region, rarity or boss premiums; bound rune sell returns.
- [x] Split armor and weapon auras into independently persisted booleans with legacy migration and actual Qt checks.
- [x] Reforge the active profile through the normal backup/manifest pipeline and retain exact output/source verification in `docs/REFINEMENT_VALIDATION.json`.
- [ ] In-game retest of reported balance, descriptions, actual buildup/damage, economy and both aura controls. See `docs/REFINEMENT_CHECKLIST.md`.

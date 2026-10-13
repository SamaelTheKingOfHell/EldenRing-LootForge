# Elden Ring: LootForge — Objective

## Mission Statement

Develop a cross-platform desktop application and mod engine for *Elden Ring* that eliminates the replacer dilemma in the modding community. Users drop replacer armor and weapon mods into an input folder; the tool automatically detects target assets, converts them into standalone items with unique IDs, and organically distributes them into the game as loot dropped by appropriate enemies or sold via Boss Soul Remembrance exchanges, without altering or removing the original vanilla sets.

## Key Objectives

1. **Vanilla Gear Preservation**:
   - Original armor and weapons remain fully intact and unaltered in appearance, stats, and loot locations.
   - NPCs wearing vanilla sets retain their authentic appearance.

2. **Automated Standalone Conversion**:
   - Detects FromSoftware model IDs from filename patterns (e.g., `am_m_XXXX.partsbnd.dcx`, `bd_m_XXXX.partsbnd.dcx`, `hd_m_XXXX...`, `lg_m_XXXX...`, `wp_a_XXXX...`).
   - Allocates unused high-range model IDs and parameter IDs (e.g., `9000+` / `9000000+`) to prevent collision with vanilla data and official DLCs.
   - Automatically duplicates the base item's `EquipParamProtector` or `EquipParamWeapon` parameter row, binding it to the new model IDs.

3. **Contextual & Thematic Loot Distribution**:
   - **Boss Soul / Remembrance**: Boss-themed sets (e.g., Radahn, Malenia, Mohg, Maliketh, Godfrey) are added to Finger Reader Enia's trade menu (`ShopLineupParam`) tied to the corresponding Remembrance or Rune cost.
   - **Enemy Drop Tables**: Enemy-specific sets (e.g., Cleanrot Knight, Crucible Knight, Banished Knight, Tree Sentinel, Black Knife Assassin) are injected into `ItemLotParam_enemy`.
   - **Thematic Fallback**: World/chest gear maps to thematic regional merchants or mini-bosses.
   - **User Customization**: Users can inspect and override loot targets in the GUI prior to building.

4. **Safety & Integrity**:
   - Automatic timestamped backup (`regulation.bin.bak_YYYYMMDD_HHMMSS`) before any file write.
   - 1-click restore functionality to revert the game state cleanly.
   - Internal manifest (`lootforge_manifest.json`) tracking every injected row, ID, and asset for clean uninstallation.

5. **Cross-Platform Compatibility**:
   - Windows and Linux / Steam Deck support (handles native Steam Deck proton paths and POSIX path separators).
   - Zero Windows-exclusive native registry hooks or locked dependencies.

6. **Aesthetic & User Experience**:
   - Modern, sleek desktop interface inspired by the dark Souls aesthetic (obsidian surfaces, antique gold accents, responsive animations).
   - Real-time floating developer console button (`[CS-DEBUG]`).
   - Centralized multi-language localization catalog (`[CS-LOCALIZATION]`).

7. **Diablo-Style Procedural ARPG Loot & Affixes**:
   - Optional procedural ARPG loot generator that transforms standalone mod items into multi-tier relics.
   - Generates multiple distinct instances per item with randomized rarity tiers (Common to Mythic), prefix/suffix stat infusions, and authentic FromSoftware `SpEffectParam` passives (HP regen, FP on kill, successive attack multipliers, resistance charms).
   - Dynamically titles items based on rolled affixes and formats rarity and combat perks at the bottom of in-game lore descriptions.

8. **Dynamic Power-Scaled Economy & Valuation**:
   - Items scale rune purchase costs in shops (`ShopLineupParam.value`, `saleValue`) and resale returns (`sellValue`) dynamically based on their combat potency.
   - Valuation engine integrates slot impact (weapon > body > head/legs > arms), regional progression tier (Early to Endgame), Diablo rarity tier (Common to Mythic), rolled affix stat points and passive buffs, weapon skill tiers, and boss remembrance prestige.
   - Granular piece pricing ensures multi-piece sets price high-stat armor appropriately relative to minor accessories or gauntlets.


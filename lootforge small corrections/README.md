# LootForge: Small Corrections Reference & Architecture

This directory documents three critical corrections implemented in LootForge on the `small-corrections` branch.

---

## 1. Non-Destructive Chest Loot Injection via Sequential Lot Chaining

### The Problem
Previously, when injecting mod items into treasure chests or fixed world pickups (`ItemLotParam_map`), mod items were placed into secondary empty slots (e.g. slots 2 through 8) of an existing row with `basePoint = 1000`.
In FromSoftware's Souls engine, `ItemLotParam` functions as a single-roll weighted lottery among non-zero slots. Placing a mod item with 1000 points into an existing chest row turned a guaranteed 100% vanilla drop (e.g., Gatefront Ruins Whetstone Knife) into a 50/50 roll, causing the vanilla chest item to be replaced or lost 50% of the time.

### The Correction
- **Dedicated Sequential Chaining**: In `tools/RegTool/LootInjector.cs`, chests and fixed pickups (`ItemLotParam_map`) as well as 100% enemy drops (`basePoint >= 1000`) now utilize sequential chained IDs: `targetLotId + 1`, `targetLotId + 2`, up to `targetLotId + 9`.
- **Concurrent Engine Evaluation**: FromSoftware's game engine evaluates contiguous sequential lot IDs concurrently upon triggering chest opens or corpse pickups.
- **Result**: The vanilla chest item row is left 100% untouched. The chained companion row fires simultaneously, guaranteeing both the vanilla item AND the injected Diablo relic drop side-by-side without replacing or cannibalizing vanilla loot!

---

## 2. Vanilla Gear & Starting Equipment Stat Infusion

### The Problem
When the Diablo ARPG setting "Inject Stats into Vanilla Item Loots" was enabled, no vanilla items were modified in-game, and starting equipment was untouched.
Investigation revealed two causes:
1. `data/vanilla_models.json` contained manufactured placeholder IDs (e.g., Greatsword `2060000` instead of `4000000`, Moonveil `4150000` instead of `9060000`, Vagabond Knight Set `405000` instead of `660000`). Because these IDs did not exist in Elden Ring's `EquipParamWeapon` or `EquipParamProtector`, the param injector could never locate or modify the vanilla rows.
2. None of the 10 starting classes' equipment (weapons, shields, and armor sets) were cataloged in `vanilla_models.json`.

### The Correction
- **100% Authentic ID Catalog**: Every item in `data/vanilla_models.json` was cross-referenced directly with retail Elden Ring FMG archives and `regulation.bin` tables.
- **Full Starting Gear Infusion**: All 10 starting classes and their weapons, shields, and armors were added:
  - **Vagabond**: Longsword (`2000000`), Halberd (`18000000`), Heater Shield (`31330000`), Vagabond Knight Set (`660000`).
  - **Samurai**: Uchigatana (`9000000`), Longbow (`41000000`), Red Thorn Roundshield (`30070000`), Land of Reeds Set (`870000`).
  - **Astrologer**: Astrologer's Staff (`33130000`), Short Sword (`2010000`), Scripture Wooden Shield (`30080000`), Astrologer Set (`630000`).
  - **Hero**: Battle Axe (`14000000`), Large Leather Shield (`31230000`), Champion Set (`730000`).
  - **Bandit**: Great Knife (`1090000`), Shortbow (`40000000`), Buckler (`30000000`), Bandit Set (`1401000`, `931100`, `930200`, `930300`).
  - **Warrior**: Scimitar (`7140000`), Riveted Wooden Shield (`30090000`), Blue Cloth Set (`670000`).
  - **Confessor**: Broadsword (`2020000`), Finger Seal (`34000000`), Blue-Gold Kite Shield (`31100000`), Confessor Set (`880000`).
  - **Prisoner**: Estoc (`5000000`), Glintstone Staff (`33000000`), Rift Shield (`30110000`), Prisoner Set (`890000`, `890100`, `890300`).
  - **Prophet**: Short Spear (`16000000`), Finger Seal (`34000000`), Rickety Shield (`30030000`), Prophet Set (`620000`, `622100`, `620300`).
  - **Wretch**: Club (`11010000`).
- **Explicit Piece Mapping**: `src/diablo_generator.py` now supports both standard 4-piece sets and non-standard armor configurations (such as Bandit Garb and Prisoner Mask) via explicit `pieces` mappings.

---

## 3. Weapon Passive UI Slots & In-Game Status Effects

### The Problem
Previously, passive affixes (like Frostbite, Bleed, Poison, FP on Kill) were appended only to lore text descriptions (`WeaponCaption.fmg`). The weapon inspection screen in Elden Ring has a dedicated section accepting up to 3 passive effects which remained completely empty, and the actual game logic did not apply on-hit status buildups.

### The Correction
- **FMG WeaponEffect Message Routing**:
  Elden Ring's weapon inspection UI displays up to 3 passive effects using `spEffectMsgId0`, `spEffectMsgId1`, and `spEffectMsgId2` (referencing `WeaponEffect.fmg`):
  - Frostbite Buildup: `sp_effect_msg_id = 6601` ("Causes frost buildup (<?freezeATKpwr?>)")
  - Blood Loss Buildup: `sp_effect_msg_id = 6501` ("Causes blood loss buildup (<?bleedATKpwr?>)")
  - Poison Buildup: `sp_effect_msg_id = 6401` ("Causes poison buildup (<?poisonATKpwr?>)")
  - Scarlet Rot Buildup: `sp_effect_msg_id = 6451` ("Causes scarlet rot buildup (<?diseaseATKpwr?>)")
  - HP Restore on Kill: `sp_effect_msg_id = 1001`
  - FP Restore on Kill: `sp_effect_msg_id = 1002`
  - Life Steal on Hit: `sp_effect_msg_id = 1005`
- **Behavior & Resident Effect Routing**:
  - On-hit status buildups are assigned to `spEffectBehaviorId0..2` with retail SpEffects (`6702` Frostbite, `6400` Bleed, `6401` Poison, `6451` Scarlet Rot).
  - Resident passive buffs are assigned to `residentSpEffectId`, `residentSpEffectId1`, `residentSpEffectId2`.
  - Up to 3 effects cleanly populate `spEffectMsgId0`, `spEffectMsgId1`, `spEffectMsgId2`, displaying authentic yellow-glow passive badges in the Elden Ring weapon inspection UI.

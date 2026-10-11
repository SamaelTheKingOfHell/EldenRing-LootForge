# Diablo-Style Procedural ARPG Loot System

## Overview

The Diablo Loot System is an optional, procedural item generation engine in **LootForge** that enhances standalone mod assets into multi-tier, randomized ARPG relics. Instead of importing only a single static replacement item, the engine can procedurally generate multiple unique variants per item (configurable from 1 up to 1,000+ variants), each with randomized rarity tiers, prefixes, suffixes, stat scalings, and authentic FromSoftware `SpEffectParam` passives.

---

## 1. Rarity Tiers & Drop Weights

| Tier | Stars | Affix Count | Drop Weight | Name Marker |
| :--- | :--- | :--- | :--- | :--- |
| **Common** | ★☆☆☆☆ | 0 affixes | 25% | `✦ [LootForge] BaseName` |
| **Magic** | ★★☆☆☆ | 1 affix (prefix or suffix) | 40% | `✦ [LootForge] [Magic] Prefix BaseName` |
| **Rare** | ★★★☆☆ | 2 affixes (1 prefix + 1 suffix) | 25% | `✦ [LootForge] [Rare] Prefix BaseName of Suffix` |
| **Legendary** | ★★★★☆ | 3 affixes (2 pref + 1 suff, or 1 pref + 2 suff) | 8% | `✦ [LootForge] [Legendary] Prefix1 Prefix2 BaseName of Suffix` |
| **Mythic** | ★★★★★ | 4 affixes (2 pref + 2 suff) | 2% | `✦ [LootForge] [Mythic] Prefix1 Prefix2 BaseName of Suffix1 of Suffix2` |

---

## 2. Affix Library & Engine Mappings

The affix system is implemented in [`src/diablo_affixes.py`](file:///d:/The%20Order's%20Operations/Projects/modding/FromSoftware/Elden%20Ring/LootForge/src/diablo_affixes.py) and maps directly to Elden Ring parameter tables:

### A. Prefixes (Weapon Attacks & Scaling)
* **Fiery / Incinerating**: Adds +35 to +65 Fire Damage (`attackBaseFire`).
* **Shocking / Tempestuous**: Adds +35 to +65 Lightning Damage (`attackBaseThunder`).
* **Glacial**: Adds +40 Magic & Frost Damage (`attackBaseMagic`).
* **Hallowed**: Adds +40 Holy Damage (`attackBaseDark`).
* **Serrated**: Adds +25 Physical Damage (`attackBasePhysics`) and Lord of Blood passive (`spEffectId = 313000`).
* **Brutal**: Enhances Strength scaling (`correctStrength = 25`) and physical attack.
* **Deft**: Enhances Dexterity scaling (`correctAgility = 25`) and physical attack.

### B. Prefixes (Armor Defenses & Resistances)
* **Ironclad**: Adds +15 Physical & Slash Damage Negation (`defensePhysics`, `defenseSlash`).
* **Juggernaut's**: Adds +25 Physical Defense, +10 Poise, and Bull-Goat Poise passive (`spEffectId = 311000`).
* **Flame-Warded**: Adds +20 Fire Defense and Flamedrake Charm passive (`spEffectId = 314200`).
* **Spell-Warded**: Adds +20 Magic Defense and Spelldrake Charm passive (`spEffectId = 314100`).
* **Titanic**: Adds +40 Robustness and Crimson Amber passive (+6% Max HP, `spEffectId = 310400`).
* **Enlightened**: Adds +40 Focus and Cerulean Amber passive (+7% Max FP, `spEffectId = 310500`).
* **Stalwart**: Adds +60 Robustness and Stalwart Charm passive (`spEffectId = 315100`).

### C. Suffixes (Combat Passives via SpEffectParam)
* **of the Leech** (`SpEffect 316000`): Restores 3% HP + 30 HP on enemy defeat (Taker's Cameo).
* **of the Phoenix** (`SpEffect 310000`): Continuously regenerates HP at +2 HP/sec (Blessed Dew Talisman).
* **of the Mind** (`SpEffect 310100`): Restores 3 FP on enemy defeat (Ancestral Spirit's Horn).
* **of the Wind** (`SpEffect 310200`): Greatly accelerates Stamina recovery (Green Turtle Talisman).
* **of Slaughter** (`SpEffect 316200`): Successive attacks boost attack power up to 13% (Rotten Winged Sword Insignia).
* **of the Berserker** (`SpEffect 316500`): Grants +20% attack power at low HP (Red-Feathered Branchsword).
* **of the Falcon** (`SpEffect 311100`): Jump attacks deal +15% damage (Claw Talisman).
* **of the Champion** (`SpEffect 312500`): Weapon skill attacks deal +15% damage (Shard of Alexander).
* **of Fortune** (`SpEffect 317200`): Boosts item discovery by +75 (Silver Scarab).
* **of the Hunt** (`SpEffect 317100`): Increases runes gained from enemies by +20% (Gold Scarab).

---

## 3. Dynamic In-Game Presentation

### Dynamic Titles
Generated names follow the Diablo convention:
`✦ [LootForge] [{Rarity}] {Prefix} {BaseName} {Suffix} ({Slot})`
Example:
* `✦ [LootForge] [Legendary] Fiery Serrated Moonveil of Slaughter (Weapon)`
* `✦ [LootForge] [Rare] Titanic Knight Armor of the Phoenix (Body)`

### Description / Caption Formatting
Per design specifications, affix breakdowns and rarity are formatted strictly at the **bottom** of the in-game description:

```text
A finely balanced katana of foreign origin.
Known for its iridescent blade that channels the moonlight.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
◆ RARITY: LEGENDARY ★★★★☆
----------------------------------------
✦ DIABLO AFFIXES:
• [Prefix] Fiery: +35 Fire Damage
• [Prefix] Serrated: +25 Physical Attack & Boosts damage on blood loss
• [Suffix] of Slaughter: Rotten Winged Insignia: Successive attacks boost power up to 13%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 4. Multi-Variant Procedural Scaling

The procedural variant generator is implemented in [`src/diablo_generator.py`](file:///d:/The%20Order's%20Operations/Projects/modding/FromSoftware/Elden%20Ring/LootForge/src/diablo_generator.py):
* Given any base patch spec, `generate_variants_for_spec(base_spec, variants_per_item)` generates $N$ variant specs.
* **ID Isolation**: Each variant calculates `new_param_id = old_id + ((v_idx + 1) * 100)`, preventing collision with other base sets.
* **Seeding**: Supports deterministic generation with `seed` for reproducible game saves or pure stochastic rolls.

---

## 5. Configuration & Activation

Add the following keys to `config.json` to enable or tune the system:

```json
{
  "diablo_loot_enabled": true,
  "diablo_variants_per_item": 5,
  "diablo_seed": 42
}
```

* `diablo_loot_enabled`: `true` enables procedural variant generation during the Forge pipeline; `false` keeps standard 1:1 standalone items.
* `diablo_variants_per_item`: Number of randomized rolls generated per standalone mod item (e.g. 5, 10, or up to 1,000).
* `diablo_seed`: Optional integer seed for deterministic rolls across builds.

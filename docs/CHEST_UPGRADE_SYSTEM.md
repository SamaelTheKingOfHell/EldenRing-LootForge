# LootForge: High-Value Post-Boss Chest Upgrade System

## Executive Summary

The **Chest Upgrade System** transforms treasure discovery across the Lands Between into high-value, progression-locked encounters. By extending the anti-duplication architecture (`AntiDup.CHEST_AFTER_BOSS`), custom armor sets, weapons, and standalone relics are routed directly into canonical treasure chests located in or immediately after major boss chambers. 

Current implementation: only attached one-time MSB chest records qualify. Diablo chest rarity follows regional weights, and each boss/chest group has a 7% chance of one bonus talisman. Complete armor groups reserve their rows together. The earlier guaranteed rarity and two-companion design caused flooding and was removed. See [runtime repair and evidence](LOOT_RUNTIME_REPAIR.md).

---

## 1. Distribution Logic & Anti-Duplication Routing

The system integrates directly with the `AntiDup` enum (`src/models.py`) to govern how 100% drop items are placed:

### 1.1. `AntiDup.CHEST_AFTER_BOSS` (Value: 3)
- **Direct Post-Boss Routing**: Directly routes custom sets to the high-value chest situated immediately after a defeated boss (or within that boss's regional sanctum).
- **Progression Match**: Selects chests strictly matching the item's progression tier (e.g. Margit/Godrick $\rightarrow$ Stormveil Throne Room Chest; Rennala $\rightarrow$ Raya Lucaria Library Chest; Radahn $\rightarrow$ Redmane Armory Chest).
- **Thematic Association**: Ties powerful equipment to the triumph of clearing significant dungeon chambers.

### 1.2. `AntiDup.BOSS_ROTATION` (Value: 1) Cascade Rule
- **1 Custom Set per Boss Quota**: Enforces a strict maximum of one custom set per major boss.
- **Hierarchical Cascade**:
  1. Major bosses in the matching progression tier.
  2. **Chest After Boss**: When all eligible bosses in that progression tier are filled, the rotation cascades immediately into high-value post-boss chests in that tier.
  3. Elite enemies and mini-bosses in that tier.
  4. Strong wild mobs within the same tier.

---

## 2. High-Value Chest Mechanics & Multi-Injections

### 2.1. Progression-weighted rarity
With progression enabled, chest rarity uses regional weights. Early Legendary/Mythic items remain possible with weaker bonuses. Disabling progression retains the legacy high-rarity behavior.

### 2.2. Bounded equipment groups
Vanilla chests in *Elden Ring* typically reward a single item. LootForge upgrades chests to function like ARPG treasure troves:
- **Primary Reward**: The forged standalone weapon or armor set.
- **Companion Injections**: A 7% chance of one extra regional talisman; ordinary enemy and merchant placements do not receive bonus talismans.
- **Total Yield**: Original reward plus the selected complete equipment group and its rare optional companion, limited by actual contiguous row space.

### 2.3. Non-Destructive Sequential Lot Chaining
To prevent overwriting vanilla rewards (such as key items, somber smithing stones, or spells):
- LootForge injects extra drops into sequential chained rows: `targetLotId + 1`, `targetLotId + 2`, etc., in `ItemLotParam_map`.
- Added chest rows share the original acquisition flag and never spill into another map pickup or enemy table.
- The retail *Elden Ring* engine triggers all contiguous lot rows within the container event script simultaneously upon chest interaction.
- Vanilla loot remains 100% intact while the modded rewards appear concurrently in the player's acquisition banner.

---

## 3. Strict 4-Tier World Progression Gating

LootForge enforces strict progression locking (`ProgressionTier`) across all item placements:

| Tier | Enum Value | Region Coverage | Canonical Post-Boss Chests |
| :--- | :---: | :--- | :--- |
| **EARLY** | `1` | Limgrave, Stormveil Castle, Weeping Peninsula | Stormveil Throne Room Chest, Limgrave Tower Bridge Sanctum |
| **MID** | `2` | Liurnia of the Lakes, Raya Lucaria, Caelid, Altus Plateau | Raya Lucaria Library Chamber, Redmane Armory, Altus Grotto Chest |
| **LATE** | `3` | Leyndell Royal Capital, Mt. Gelmir, Mountaintops | Leyndell Treasury Chest, Volcano Manor Throne Room, Mountaintops Vault |
| **ENDGAME** | `4` | Crumbling Farum Azula, Miquella's Haligtree, Mohgwyn Palace | Dragon Temple Sanctum Chest, Haligtree Roots Vault, Ashen Capital Sanctum |

### Progression Invariants
- **No Early-Game Spoilers**: Late-game and endgame gear (e.g. Malenia, Maliketh, Radagon/Elden Beast) can **never** drop in Early or Mid-game chests or bosses (e.g. Margit, Godrick, Gatefront).
- **No Endgame Degradation**: Early-game items do not dilute endgame treasure vaults.
- **Consistent Set Preservation**: All pieces of a 4-piece armor set remain unified in the exact same chest.

---

## 4. Architecture & Key Files

| Module / File | Responsibility |
| :--- | :--- |
| [`src/models.py`](../src/models.py) | Defines `ProgressionTier` (`EARLY=1`, `MID=2`, `LATE=3`, `ENDGAME=4`) and `AntiDup.CHEST_AFTER_BOSS=3`. |
| [`data/loot_routes.json`](../data/loot_routes.json) | Catalogs post-boss chests with authentic `chestLotId`, associated bosses, and `progressionTier`. |
| [`data/vanilla_models.json`](../data/vanilla_models.json) | Tags all protectors, weapons, and vanilla accessories with canonical progression tiers. |
| [`src/knowledge_base.py`](../src/knowledge_base.py) | Provides `get_chest_after_boss()`, `list_chests(tier=...)`, and tier-filtered accessory lookups. |
| [`src/loot_distributor.py`](../src/loot_distributor.py) | Implements `_route_chest_after_boss()` and tier-constrained `_rotate_boss_drop()` cascade. |
| [`src/diablo_generator.py`](../src/diablo_generator.py) | Enforces `is_chest=True` rarity elevation and injects multiple companion accessories. |
| [`src/param_builder.py`](../src/param_builder.py) | Constructs non-destructive chained rows in `ItemLotParam_map` for chest drops. |
| [`src/ui/param_schema.py`](../src/ui/param_schema.py) | Exposes `[3] Chest After Boss` in the UI drop rule selector. |

---

## 5. Verification & Testing

The system is validated by automated test suites in `tests/`:
- `tests/test_loot_distributor.py`:
  - `test_anti_dup_chest_after_boss_direct_routing`: Verifies direct placement into tier-appropriate post-boss chests.
  - `test_anti_dup_boss_rotation_cascades_to_chest_after_boss_when_tier_bosses_full`: Verifies cascade to chests when boss slots are occupied.
  - `test_progression_locking_no_late_game_on_beginning`: Confirms late-game gear cannot appear in early regions.
  - `test_chest_always_contains_multiple_extra_injections`: Confirms multi-accessory bundling ($\ge 3$ awarded items).
- `tests/test_diablo_loot.py`: Verifies high-rarity rolling and multi-injection chaining in procedural mode.

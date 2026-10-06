# LootForge: Technical Design Document (Qt & Python Architecture)

## 1. Executive Summary

LootForge is an open-source, cross-platform desktop application built with Python 3 and Qt (PyQt6/PySide6) for *Elden Ring*. It solves the replacer mod conflict by converting replacement armor and weapon mods into standalone items without replacing vanilla gear, organically injecting them into boss soul transfusions, shops, and enemy drop tables while preserving existing mod loadouts.

---

## 2. Core Enums and Distribution Logic

### 2.1. `AdditionType` Enum
Defines the macro placement strategy:
1. `RANDOM_ADDITION (1)`:
   - Places modded items on mobs randomly across the Lands Between.
   - **Exception Rule**: Items whose vanilla counterparts are *not* standard mob drops (e.g. Remembrance boss soul transfusions, Remembrance gear, shop inventory, quest rewards) are **never** dumped onto random trash mobs; instead, they are randomized across Bosses, Finger Reader Enia transfusions, and regional Merchant shops.
2. `STANDARD_ADDITION (2)`:
   - Places modded items on the thematic vanilla-expected drop list, shop, or boss weapon transfusion (e.g. Radahn set goes to Radahn Remembrance/Enia, Cleanrot set goes to Cleanrot Knights).

### 2.2. `AntiDup` Enum (for 100% Drop Items)
Governs how items with guaranteed (100%) boss drops are handled:
1. `BOSS_ROTATION (1)`:
   - If the original item is a 100% drop from a boss, LootForge rotates the custom item to a **different boss**.
   - **Limit Rule**: Maximum of **1 custom set per boss**.
   - **Cascading Fallback**:
     1. Available major bosses (Remembrances & Great Runes).
     2. If major bosses are exhausted, distribute to **mini-bosses** (Tree Sentinels, Night's Cavalry, Bell Bearing Hunters, Deathbirds).
     3. If mini-bosses are exhausted, distribute to **stronger wild enemies** at normal vanilla drop rates.
2. `EVERYTHING_IN_THE_WILD (2)`:
   - Bypasses boss rotation completely; all items are placed onto wild monsters at normal drop rates.

### 2.3. Set Invariance Mandate
- **Rule**: In all distribution modes, all pieces of a set from the same mod **always drop from the exact same mob, boss, or shop**.
- Helm, chest, gauntlets, and greaves remain unified so the player earns complete, cohesive gear.

### 2.4. Custom Weapons Fallback
- Custom weapons ignore complex `regulation.bin` weapon parameter injection and fall back to their original standalone asset definitions.

---

## 3. Drop Rate Engine & Color-Coding Mechanics

### 3.1. Global Multiplier
- A prominent global rate factor governed by `100%` (`1.0x` / `1*` baseline) makes scaling intuitive for users.
- `Final Drop Rate = Configured Base Rate × (Global Multiplier / 100)`.

### 3.2. Paginated Tuning Table
- Divided into pages (e.g. 10 items per page) with search and filtering.
- Displays:
  - **Item Name & Set**: Item and piece identifier.
  - **Vanilla Default Rate**: Benchmark drop percentage.
  - **User-Configured Rate**: Editable spinbox/input.
  - **Final Rate**: Computed percentage.
  - **Visual Indicator**:
    - 🔴 **Red**: Final rate is **lower** than default.
    - ⚪ **Grey / Neutral**: Final rate is **equal** to default.
    - 🟢 **Green**: Final rate is **higher** than default.
  - **Reset Button**: 1-click restore to vanilla benchmark.

---

## 4. Mystery & Spoiler Protection System

- By default, enemy and boss placement locations are obscured in the interface (`??? Hidden Location`).
- **Global Toggle**: "Reveal All Placements" / "Hide All (Mystery Mode)".
- **Individual Eye Toggle**: Users can reveal or obscure specific items one by one.

---

## 5. Qt UI Architecture (`src/qt_ui/`)

- Built with **PyQt6** for native cross-platform performance (Windows and Steam Deck / Linux).
- Dark Souls QSS styling: deep obsidian slate (`#0c0d12`), antique gold accents (`#c5a059`, `#ffd475`), custom tables, and status badges.
- Prominent Mod Manager Banner instructing users to target their current active `regulation.bin`.
- Floating developer console drawer (`[CS-DEBUG]`).

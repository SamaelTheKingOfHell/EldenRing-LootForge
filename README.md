# LootForge: Standalone Relic & Loot Injector

**LootForge** is a cross-platform desktop application and mod engine for *Elden Ring* (Windows & Linux / Steam Deck). It automatically converts replacement armor and weapon mods into standalone items, preserves original vanilla equipment, and organically injects the custom gear as in-game loot into Boss Soul Remembrance exchanges or enemy drop tables.

---

## Key Features

1. **Vanilla Preservation**:
   - Never overwrites authentic armor sets or weapons.
   - NPCs wearing vanilla sets retain their intended appearance.
2. **Automated Standalone Conversion**:
   - Detects model ID patterns in `.partsbnd.dcx` files (`am_`, `bd_`, `hd_`, `lg_`, `wp_`).
   - Allocates collision-free IDs (`9000+` models, `9000000+` params).
   - Stages and renumbers files into `mod/parts/` for ModEngine 2 without modifying original mod downloads or game files.
3. **Organic In-Game Loot Placement**:
   - **Boss Soul Remembrances**: Boss-themed sets (Radahn, Malenia, Mohg, Maliketh, etc.) are routed to Finger Reader Enia's trade menu (`ShopLineupParam`).
   - **Enemy Drop Tables**: Knight/mob sets (Cleanrot, Crucible, Banished, Tree Sentinel, etc.) are injected into enemy drop tables (`ItemLotParam_enemy`).
   - **Full UI Customization**: Easily change any mod's target boss or drop chance in the interactive table.
4. **Safety & 1-Click Rollback**:
   - Timestamped pre-write snapshots of `regulation.bin` with SHA-256 verification.
   - Reversible manifest (`lootforge_manifest.json`) enabling clean 1-click uninstallation.
5. **Cross-Platform & Modern Souls-Themed GUI**:
   - Deep obsidian slate surfaces, antique gold accents, and glowing rune status indicators.
   - Glowing circular floating developer console button (`[CS-DEBUG]`) with real-time log streaming.
   - Full universal localization (`[CS-LOCALIZATION]`) supporting English and Portuguese (BR).

---

## Quick Start

### 1. Place Replacement Mods
Drop any downloaded armor or weapon mod folder or `.partsbnd.dcx` files into the `input_mods/` folder:

```text
LootForge/
  └── input_mods/
      └── DarkKnightBerserk/
          ├── am_m_4000.partsbnd.dcx
          ├── bd_m_4000.partsbnd.dcx
          ├── hd_m_4000.partsbnd.dcx
          └── lg_m_4000.partsbnd.dcx
```

### 2. Launch LootForge
Run the launcher:

```bash
python run_lootforge.py
```

The application will start the local engine and open your default browser to `http://127.0.0.1:8383`.

### 3. Review & Inject
1. In the interface, click **Scan & Analyze Mods** (or drag files onto the dropzone).
2. Review the detected vanilla sets, allocated standalone IDs, and loot targets.
3. Adjust the target Boss Remembrance or Enemy drop rate if desired.
4. Click **Forge Standalone Gear & Inject Loot**.
5. Launch Elden Ring via ModEngine 2 (`launchmod_eldenring.bat`).

---

## 💡 Using with Mod Managers (Mod Engine 2, Metis, MO2)

If you already have active gameplay mods installed (movesets, balance overhauls, Seamless Co-op, etc.):

1. **Use Your Current `regulation.bin`**: In the **Target Configuration & Game Paths** section in the LootForge UI, select your **Active `regulation.bin`** (e.g., `mod\regulation.bin` inside your ModEngine 2 folder or your Mod Manager's active profile).
2. **Click "Use Mod Engine Regulation"**: LootForge provides a 1-click button to automatically target your modded `mod/regulation.bin`.
3. **Preserve Your Mod Loadout**: LootForge merges the new standalone equipment rows, enemy loot tables, and Boss Remembrance trades directly into your existing modded regulation file, rather than resetting to vanilla.
4. **Automatic Safety Snapshot**: LootForge creates a pre-write backup (`regulation.bin.bak_YYYYMMDD_HHMMSS`) of your modded regulation file before making any changes, so your custom loadout is always protected.

---

## Project Structure

```text
LootForge/
  ├── INDEX.md               # Folder index
  ├── OBJECTIVE.md           # Mission and design invariants
  ├── ROADMAP.md             # Development roadmap
  ├── README.md              # Project documentation
  ├── run_lootforge.py       # Application launcher
  ├── data/                  # Knowledge base (models, loot tables, i18n)
  ├── src/                   # Core Python engine
  ├── ui/                    # Modern Souls-themed interface
  ├── input_mods/            # Mod ingestion dropzone
  └── tests/                 # Automated test suite
```

---

## Testing

Run the automated test suite:

```bash
python -m unittest discover tests
```

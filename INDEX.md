# LootForge: Standalone Relic & Loot Injector

Cross-platform desktop application and mod engine for *Elden Ring*. Converts replacement armor and weapon mods into standalone items, preserves original vanilla gear, organically injects items into Boss Soul (Remembrance) exchanges and enemy drop tables, manages safe `regulation.bin` backups, and tracks modifications with a reversible manifest.

## Directory Layout

| Path | Purpose |
| :--- | :--- |
| `INDEX.md` | Index of LootForge components and documentation. |
| `DESIGN.md` | Detailed architectural design document for Qt UI, Enums, and distribution algorithms. |
| `OBJECTIVE.md` | Mission statement, technical boundaries, and system goals. |
| `ROADMAP.md` | Development phases, milestones, and deliverables. |
| `src/` | Core Python engine (scanner, ID allocator, backup manager, param patcher, manifest). |
| `data/` | Knowledge database (vanilla model-to-item mapping, loot routing tables). |
| `ui/` | Modern Souls-themed Web/Desktop graphical user interface. |
| `tests/` | Automated test suite verifying detection, ID allocation, and param generation. |
| `input_mods/` | Default staging folder where users place replacement mod files. |

# LootForge Documentation Directory

## Overview
This folder contains system specifications, guides, and architectural design references for the LootForge engine.

## Documents
* [`LOOT_RUNTIME_REPAIR.md`](LOOT_RUNTIME_REPAIR.md): Screenshot-driven repair of inventory identity, one-time chests, event-proven bosses, vendor stock, armor completeness and starter balance.
* `LOOT_RUNTIME_VALIDATION.json`: Exact-profile acceptance counts, deployed identities and outstanding game QA.
* [`DIABLO_POWER_AND_MAGIC.md`](DIABLO_POWER_AND_MAGIC.md): Progression scaling, optional passives, combat magic toggles, reversible infusion and local validation boundaries.
* [`DIABLO_LOOT_SYSTEM.md`](DIABLO_LOOT_SYSTEM.md): Architectural design, rarity tiers, affix pools, FromSoftware engine mappings, and configuration for the Diablo-style procedural ARPG loot engine.
* [`ITEM_DISTRIBUTION_PLAN.md`](ITEM_DISTRIBUTION_PLAN.md): Architectural plan for eliminating shop monoculture, expanding merchant roster from 3 to 22+, regional progression tiering, and item category balance.
* [`CHEST_UPGRADE_SYSTEM.md`](CHEST_UPGRADE_SYSTEM.md): Architectural specification for post-boss high-value treasure chests, AntiDup.CHEST_AFTER_BOSS routing, non-destructive multi-lot injection chaining, and progression tier gating.
* [**`CRITICAL_BOSS_DROP_SYSTEM_RESEARCH.md`**](CRITICAL_BOSS_DROP_SYSTEM_RESEARCH.md): **CRITICAL**: Reverse-engineering of Souls engine drop mechanics. Analysis of `ItemLotParam_map` vs `ItemLotParam_enemy`, the single-roll multi-slot lottery trap, contiguous chained lot row mechanics (`baseLotId + 1..N`), EMEVD `AwardItemLot` event decompilation, and progression-tier boss loot injection architecture.
* [`research/`](../research/INDEX.md): Local link to canonical research repository (`knowledge/research/elden-ring-loot-forge`).


## Patcher performance and capacity

- `PATCHER_PERFORMANCE.md`: Measured performance, dynamic caps, imported attack and additive-loot corrections, accessory inventory investigation, local release evidence and unresolved audit findings.

- `DIABLO_POWER_VALIDATION.json`: Retained local build, Python/native, reroll, disable and Qt evidence; separates game acceptance.
- `DIABLO_MAGIC_QA.json`: Portable, unexecuted in-game acceptance assignment.

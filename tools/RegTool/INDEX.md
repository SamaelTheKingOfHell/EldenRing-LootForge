# RegTool: Regulation & Binary Patching CLI

CLI utility written in C# (.NET 9.0) for decrypting Elden Ring `regulation.bin`, non-destructively injecting standalone parameters (`EquipParamProtector`, `EquipParamWeapon`, `EquipParamAccessory`, `ItemLotParam_enemy`, `ShopLineupParam`), injecting and mirroring FMG item text across base and DLC archives, and re-encrypting with AES-256.

Adheres to `[CS-MODULAR]`, `[CS-GRANULARITY]`, and `[CS-DECOUPLE]` by decomposing into single-responsibility classes under 300 lines so that changes to one equipment category cannot regress another.

## Architecture & Source Modules

| File | Class / Responsibility | Purpose |
| :--- | :--- | :--- |
| `INDEX.md` | - | Index and architectural documentation for RegTool. |
| `Program.cs` | `Program` | Entry point, CLI argument parsing, and command routing. |
| `PatchService.cs` | `PatchService` | Regulation decryption, loading paramdefs, orchestrating patch pipeline, and re-encryption. |
| `EquipInjector.cs` | `EquipInjector` | High-level equipment dispatcher routing to specialized category injectors. |
| `ProtectorInjector.cs` | `ProtectorInjector` | Dedicated armor row cloning (`EquipParamProtector`), gender coverage, unisex flags, and authentic icon inheritance. |
| `WeaponInjector.cs` | `WeaponInjector` | Dedicated weapon row cloning (`EquipParamWeapon`), model matching, and valid icon inheritance. |
| `AccessoryInjector.cs` | `AccessoryInjector` | Dedicated talisman row cloning (`EquipParamAccessory`), name-stripping resilience, and authentic icon resolution. |
| `LootInjector.cs` | `LootInjector` | Safe distribution injection (`ItemLotParam_enemy`, `ShopLineupParam`) with merchant capacity spillover. |
| `ParamInjector.cs` | `ParamInjector` | Backward-compatible facade delegating to EquipInjector and LootInjector. |
| `FmgInjector.cs` | `FmgInjector` | FMG orchestration, backup management, output paths, and DLC package mirroring. |
| `FmgArchiveService.cs` | `FmgArchiveService` | In-memory BND4 FMG loading, base and DLC variant matching (`_dlc01`, `_dlc02`), and parallel serialization. |
| `DiagnosticService.cs` | `DiagnosticService` | Regulation verification, FMG text searching, regulation dumping, and Data0 archive extraction. |
| `BossLootPoolService.cs` | `BossLootPoolService` | Boss encounter progression-tier loot pool generation and contiguous chained row injection (`ItemLotParam_map`). |
| `SmartDiscoveryService.cs` | `SmartDiscoveryService` | Schema-driven dynamic world introspection for weapons, armor, accessories, and boss lots. |
| `SmartDiscoveryModels.cs` | `DiscoveredWorldSnapshot` | Data contracts for world introspection records including `DiscoveredAccessory` with `IconId`. |
| `UniversalSweeperService.cs` | `UniversalSweeperService` | 100% full-regulation vanilla item infusion across EquipParamWeapon, EquipParamProtector, and FMGs. |
| `SkillMovesetService.cs` | `SkillMovesetService` | Mod regulation introspection, extracting custom weapon skills (`SwordArtsParam`), moveset behaviors (`BehaviorParam_PC`, `AtkParam_Pc`), and injection. |
| `ParamHelper.cs` | `ParamHelper` | Utility methods for safely reading, writing, and type-converting PARAM cell values. |
| `RegTool.csproj` | - | .NET 9.0 project definition linking `SoulsFormatsNEXT`. |


## Patcher performance and capacity

- `CapacityService.cs`: Fast surviving equipment row counts from source metadata.
- `SkillExtractionIndex.cs`: Single-pass skill, behavior variation and attack lookup indices for dependency extraction.
- `PatchPreflight.cs`: Native collision and row-limit validation before large batch cloning.
- `PatchOutputTransaction.cs`: Staged regulation/FMG publication with rollback on commit failure.
- `LootSlotAllocator.cs`: Amortized-linear free overflow slot allocation.
- `SweepFmgService.cs`: Indexed infusion text updates preserving base and DLC-exclusive entries.

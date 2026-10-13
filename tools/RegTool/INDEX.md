# RegTool: Regulation & Binary Patching CLI

CLI utility written in C# (.NET 9.0) for decrypting Elden Ring `regulation.bin`, non-destructively injecting standalone parameters (`EquipParamProtector`, `EquipParamWeapon`, `ItemLotParam_enemy`, `ShopLineupParam`), injecting and mirroring FMG item text, and re-encrypting with AES-256.

Adheres to `[CS-MODULAR]`, `[CS-GRANULARITY]`, and `[CS-DECOUPLE]` by decomposing into single-responsibility classes under 300 lines.

## Architecture & Source Modules

| File | Class / Responsibility | Purpose |
| :--- | :--- | :--- |
| `INDEX.md` | - | Index and architectural documentation for RegTool. |
| `Program.cs` | `Program` | Entry point, CLI argument parsing, and command routing. |
| `PatchService.cs` | `PatchService` | Regulation decryption, loading paramdefs, orchestrating patch pipeline, and re-encryption. |
| `EquipInjector.cs` | `EquipInjector` | Equipment row cloning (`EquipParamProtector`, `EquipParamWeapon`), icon inheritance, and validity checks. |
| `LootInjector.cs` | `LootInjector` | Safe distribution injection (`ItemLotParam_enemy`, `ShopLineupParam`) with merchant capacity spillover. |
| `ParamInjector.cs` | `ParamInjector` | Backward-compatible facade delegating to EquipInjector and LootInjector. |
| `FmgInjector.cs` | `FmgInjector` | FMG loading, vanilla name/description lookup, item text injection, and DLC archive mirroring. |
| `DiagnosticService.cs` | `DiagnosticService` | Regulation verification, FMG text searching, regulation dumping, and Data0 archive extraction. |
| `BossLootPoolService.cs` | `BossLootPoolService` | Boss encounter progression-tier loot pool generation and contiguous chained row injection (`ItemLotParam_map`). |
| `SmartDiscoveryService.cs` | `SmartDiscoveryService` | Schema-driven dynamic world introspection for weapons, armor, accessories, and boss lots. |
| `UniversalSweeperService.cs` | `UniversalSweeperService` | 100% full-regulation vanilla item infusion across EquipParamWeapon, EquipParamProtector, and FMGs. |
| `SkillMovesetService.cs` | `SkillMovesetService` | Mod regulation introspection, extracting custom weapon skills (`SwordArtsParam`), moveset behaviors (`BehaviorParam_PC`, `AtkParam_Pc`), and injection. |
| `ParamHelper.cs` | `ParamHelper` | Utility methods for safely reading, writing, and type-converting PARAM cell values. |
| `RegTool.csproj` | - | .NET 9.0 project definition linking `SoulsFormatsNEXT`. |

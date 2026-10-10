# RegTool: Regulation & Binary Patching CLI

CLI utility written in C# (.NET 9.0) for decrypting Elden Ring `regulation.bin`, non-destructively injecting standalone parameters (`EquipParamProtector`, `EquipParamWeapon`, `ItemLotParam_enemy`, `ShopLineupParam`), injecting and mirroring FMG item text, and re-encrypting with AES-256.

Adheres to `[CS-MODULAR]`, `[CS-GRANULARITY]`, and `[CS-DECOUPLE]` by decomposing into single-responsibility classes under 300 lines.

## Architecture & Source Modules

| File | Class / Responsibility | Purpose |
| :--- | :--- | :--- |
| `INDEX.md` | - | Index and architectural documentation for RegTool. |
| `Program.cs` | `Program` | Entry point, CLI argument parsing, and command routing. |
| `PatchService.cs` | `PatchService` | Regulation decryption, loading paramdefs, orchestrating patch pipeline, and re-encryption. |
| `ParamInjector.cs` | `ParamInjector` | Safe injection into `EquipParamProtector`, `EquipParamWeapon`, `ItemLotParam_enemy`, and `ShopLineupParam`. |
| `FmgInjector.cs` | `FmgInjector` | FMG loading, vanilla name/description lookup, item text injection, and DLC archive mirroring. |
| `ParamHelper.cs` | `ParamHelper` | Utility methods for safely reading, writing, and type-converting PARAM cell values. |
| `RegTool.csproj` | - | .NET 9.0 project definition linking `SoulsFormatsNEXT`. |

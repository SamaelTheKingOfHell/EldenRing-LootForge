# LootForge: Tools Directory

This directory contains standalone native tooling used by LootForge for FromSoftware binary manipulation and regulation patching.

## Components

| Directory / File | Technology | Purpose |
| :--- | :--- | :--- |
| `INDEX.md` | Markdown | Directory documentation and index. |
| `RegTool/` | C# / .NET 9.0 (`net9.0`) | CLI utility for decrypting Elden Ring `regulation.bin`, non-destructively patching parameters (`EquipParamProtector`, `EquipParamWeapon`, `ItemLotParam_enemy`, `ShopLineupParam`), and re-encrypting with AES-256. |
| `vendor/SoulsFormatsNEXT/` | C# Library | .NET library by Joseph Anderson / Souls community for reading and writing FromSoftware file formats (BND4, PARAM, AES cryptography). |
| `vendor/Paramdex/` | XML Definitions | Complete schema and paramdefs for Elden Ring game parameters (`Paramdex/ER/Defs`). |

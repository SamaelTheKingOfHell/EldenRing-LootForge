# RegTool: SoulsPort Subsystem

Modular service for selective in-memory extraction, FLVER2 modernization, and BND4 packaging of legacy Souls game armors into Elden Ring formats.

## Components
- `INDEX.md`: Directory documentation and index.
- `Ds1ArchiveReader.cs`: Random-access BHD5/BDT reader for Dark Souls 1 (PTDE) archives.
- `FlverModernizer.cs`: Upgrades legacy FLVERs (0x2000C) to Elden Ring FLVER2 (0x20014) with DX12 PBR layout and Oodle Kraken packaging.
- `SoulsPortService.cs`: Service entry point, catalog lookup, parameter/lore extraction, and asset generation.

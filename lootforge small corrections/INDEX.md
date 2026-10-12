# LootForge Small Corrections

## Purpose
This directory encapsulates the architectural and parametric corrections implemented on the `small-corrections` branch to address loot preservation, vanilla gear infusion, and weapon passive effect UI display in Elden Ring.

## Directory Contents
- `INDEX.md`: Routing and directory overview (this file).
- `README.md`: In-depth breakdown of the three core corrections and technical mechanics.
- `verify_corrections.py`: Standalone verification test script verifying loot chaining, starting gear cataloging, and passive UI slot routing.

## Related Files
- `src/diablo_affixes.py`: Affix definitions with passive UI message IDs and on-hit behavior flags.
- `src/diablo_generator.py`: Passive effect routing (`spEffectMsgId0..2`, `spEffectBehaviorId0..2`, `residentSpEffectId..2`) and vanilla starting gear generator.
- `data/vanilla_models.json`: Authenticated Elden Ring IDs and starting class catalogs.
- `tools/RegTool/LootInjector.cs`: Sequential ID chaining for non-destructive chest loot injection.

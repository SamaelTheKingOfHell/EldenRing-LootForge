# Diablo native checks

`Program.cs` checks generated Diablo rolls against real installed PARAM rows and
round-trips the generated common event script in an isolated output directory.
It checks all aura templates, argument byte layouts, initializer counts and disabled-output restoration.
Existing profile infusion fields are restored in memory before cloning fixtures,
so previous generated passives do not consume the fixture's native resident slots.
It does not launch the game or prove combat/aura behavior.

Optional modes after the five positional arguments: `inspect-auras`,
`compare-events <first common> <second common>`, and `verify-disabled`.

Run `dotnet run --project tests/DiabloChecks -- <repo> <source regulation> <spec JSON> <game directory> <output directory>`.

`build_specs.py` generates real-template plus controlled high-rarity inputs from
the current local discovery snapshot (seed 94715). Run it from the repository:

```powershell
python tests/DiabloChecks/build_specs.py scratch/diablo-power/native-specs.json
```

The builder forces aura coverage on those fixtures; it does not represent drop odds.

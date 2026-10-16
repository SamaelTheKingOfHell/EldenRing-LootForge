# Loot runtime regression checks

- `LootRuntimeChecks.csproj`: native checks against installed game/profile files.
- `Program.cs`: exact-profile source lottery preservation, sorted equipment lookup, weapon reinforcement/name blocks, complete armor awards/assets, native item categories, one-time map flags, finite vendor stock, installed base/DLC FMGs and preservation of host common-event instructions.

Run `dotnet run --project tests/LootRuntimeChecks -c Release -- <repo> <source-reg> <target-reg> <game> <specs.json> <report.json> [profile-reg-for-assets-and-map-overrides]`.
The final argument supports a retained source backup outside the deployed profile.
This checks files; it does not execute the game.

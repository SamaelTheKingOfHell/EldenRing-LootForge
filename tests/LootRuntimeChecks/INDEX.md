# Loot runtime regression checks

- `LootRuntimeChecks.csproj`: native checks against installed game/profile files.
- `Program.cs`: exact-profile source lottery preservation, sorted equipment lookup, weapon reinforcement/name blocks, complete armor awards/assets, native item categories, one-time map flags, finite vendor stock, installed base/DLC FMGs and preservation of host common-event instructions.
- `RefinementAudit.cs`: Read-only actual PARAM values for baseline/retail comparison. Run `inspect <repo> <source-reg> <game> <report.json>`.
- `RefinementVerification.cs`: Check every generated armor piece and price plus all tracked vanilla text and original price fields. Run `refine <repo> <baseline-folder> <target-reg> <game> <report.json>`.
  Its explicit `migrate-messages` command repairs missing passive-UI history from a retained pre-refinement PARAM/state baseline; back up the target state first. This is the only write mode in these profile checks.

Run `dotnet run --project tests/LootRuntimeChecks -c Release -- <repo> <source-reg> <target-reg> <game> <specs.json> <report.json> [profile-reg-for-assets-and-map-overrides]`.
The final argument supports a retained source backup outside the deployed profile.
This checks files; it does not execute the game.

- `DropBudgetAudit.cs`: Count all original and generated reward rows in each proven boss/chest chain. Run `drop-budget <repo> <profile-reg> <game> <report.json> [enforce]`; native bundles already exceeding four remain intact and receive no additions.

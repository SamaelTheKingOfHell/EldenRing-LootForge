# Native patch regression checks

- `RegToolChecks.csproj`: dependency-free console checks against the production RegTool assembly.
- `Program.cs`: real PARAM/FMG and encrypted moveset extraction roundtrips, attack/bullet dependency separation, overflow allocation, dynamic common.emevd flag-to-lot discovery, Option B opcode injection for zero-loot bosses, enrichment preservation, infusion repeatability, and output transaction failure checks.
- `ProfileAudit.cs`: Read-only real-profile comparison of every original loot field and generated accessory names in each base/DLC language archive. Run with `<root> audit <source> <target> <report.json>`.
- `AdditiveLootChecks.cs`: Concrete additive lottery, separation-gap, legacy backup recovery, category-safe purge, sorted PARAM and multilingual FMG regressions.
- `BalanceChecks.cs`: Weapon-relative bounds, preserved Uchigatana damage/bleed and passive UI, meaningful added buildup, native armor negation, positive discovery/attribute scaling and final strength-based economy.
- `DropBudgetChecks.cs`: Aggregate direct/boss/chest injection limits, shared chain aliases, rejection before partial insertion, original stack/lottery preservation and separation gaps.

Run `dotnet run --project tests/RegToolChecks -c Release -- <repository-root>`.

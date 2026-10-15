# Native patch regression checks

- `RegToolChecks.csproj`: dependency-free console checks against the production RegTool assembly.
- `Program.cs`: real PARAM/FMG and encrypted moveset extraction roundtrips, attack/bullet dependency separation, overflow allocation, enrichment preservation, infusion repeatability, and output transaction failure checks.
- `ProfileAudit.cs`: Read-only real-profile comparison of every original loot field and generated accessory names in each base/DLC language archive. Run with `<root> audit <source> <target> <report.json>`.
- `AdditiveLootChecks.cs`: Concrete additive lottery, separation-gap, legacy backup recovery, category-safe purge, sorted PARAM and multilingual FMG regressions.

Run `dotnet run --project tests/RegToolChecks -c Release -- <repository-root>`.

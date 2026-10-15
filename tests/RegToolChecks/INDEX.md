# Native patch regression checks

- `RegToolChecks.csproj`: dependency-free console checks against the production RegTool assembly.
- `Program.cs`: real PARAM/FMG roundtrips, overflow allocation, enrichment preservation, infusion repeatability, and output transaction failure checks.

Run `dotnet run --project tests/RegToolChecks -c Release -- <repository-root>`.

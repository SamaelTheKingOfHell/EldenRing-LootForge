using System.Text.Json;
using SoulsFormats;

namespace LootForge.RegTool;

/// <summary>Reversible vanilla infusion fields, preserving intervening changes from other mods.</summary>
public sealed class DiabloInfusionState
{
    public const string Filename = "lootforge_diablo_fields.json";
    public sealed class FieldState
    {
        public JsonElement Original { get; set; }
        public JsonElement Applied { get; set; }
    }
    readonly Dictionary<string, Dictionary<int, Dictionary<string, FieldState>>> saved;
    readonly Dictionary<(string, int), PARAM.Row> touched = new();

    public DiabloInfusionState(string targetRegulation, Func<string, string, (PARAM Param, BinderFile File)> load)
    {
        string path = Path.Combine(Path.GetDirectoryName(Path.GetFullPath(targetRegulation))!, Filename);
        saved = File.Exists(path) ? JsonSerializer.Deserialize<Dictionary<string, Dictionary<int, Dictionary<string, FieldState>>>>(File.ReadAllText(path))!
            : new();
        foreach (var (table, rows) in saved)
        {
            if (table is not ("EquipParamWeapon" or "EquipParamProtector" or "EquipParamAccessory"))
                throw new InvalidDataException("Unexpected table in Diablo infusion state.");
            var index = load(table, table).Param.Rows.ToDictionary(row => row.ID);
            foreach (var (id, fields) in rows)
            {
                if (!index.TryGetValue(id, out var row)) continue;
                foreach (var (name, state) in fields)
                {
                    var cell = ParamHelper.FindCell(row, name);
                    if (cell == null) continue;
                    var current = JsonSerializer.SerializeToElement(cell.Value);
                    // Never revert an intervening external edit. It becomes the
                    // new base for subsequent rolls of this particular field.
                    if (current.ToString() == state.Applied.ToString())
                        ParamHelper.SetCellValue(cell, state.Original);
                    else state.Original = current;
                    state.Applied = JsonSerializer.SerializeToElement(cell.Value);
                }
            }
        }
    }

    public void Capture(PARAM.Row row, string table, JsonElement updates)
    {
        if (!saved.TryGetValue(table, out var rows)) saved[table] = rows = new();
        if (!rows.TryGetValue(row.ID, out var fields)) rows[row.ID] = fields = new();
        var names = updates.EnumerateObject().Select(field => field.Name).Where(name => !name.StartsWith("_lf_"))
            .Concat(new[] { "attackBasePhysics", "attackBaseMagic", "attackBaseFire", "attackBaseThunder", "attackBaseDark",
                "defensePhysics", "defenseMagic", "defenseFire", "defenseThunder", "defenseDark", "refId",
                "residentSpEffectId", "residentSpEffectId1", "residentSpEffectId2", "residentSpEffectId3", "residentSpEffectId4",
                "spEffectBehaviorId0", "spEffectBehaviorId1", "spEffectBehaviorId2" });
        foreach (string name in names.Distinct())
        {
            var cell = ParamHelper.FindCell(row, name);
            if (cell != null && !fields.ContainsKey(name))
            {
                var value = JsonSerializer.SerializeToElement(cell.Value);
                fields[name] = new() { Original = value, Applied = value };
            }
        }
        touched[(table, row.ID)] = row;
    }

    public void Stage(string stagedRegulation)
    {
        if (saved.Count == 0) return;
        foreach (var ((table, id), row) in touched)
            foreach (var (name, state) in saved[table][id])
                state.Applied = JsonSerializer.SerializeToElement(ParamHelper.FindCell(row, name)!.Value);
        File.WriteAllText(Path.Combine(Path.GetDirectoryName(stagedRegulation)!, Filename), JsonSerializer.Serialize(saved));
    }
}

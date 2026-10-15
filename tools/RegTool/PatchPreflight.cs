using System.Text.Json;
using SoulsFormats;

namespace LootForge.RegTool;

/// <summary>Reject item collisions and engine row-limit violations before cloning a large batch.</summary>
public static class PatchPreflight
{
    /// <summary>Validate the exact surviving source tables after previous injections have been purged.</summary>
    public static void Validate(IEnumerable<JsonElement> specs,
        Func<string, string, (PARAM Param, BinderFile File)> load)
    {
        var ids = new Dictionary<string, HashSet<int>>();
        var requested = new Dictionary<string, HashSet<int>>();
        foreach (var spec in specs)
        {
            if (!spec.TryGetProperty("equip_params", out var equipment)) continue;
            foreach (var item in equipment.EnumerateArray())
            {
                string table = item.GetProperty("param_table").GetString()!;
                int id = item.GetProperty("new_param_id").GetInt32();
                if (!ids.TryGetValue(table, out var tableIds))
                {
                    tableIds = load(table, table).Param.Rows.Select(r => r.ID).ToHashSet();
                    ids[table] = tableIds;
                    requested[table] = new();
                }
                if (!requested[table].Add(id))
                    throw new InvalidDataException($"Duplicate equipment ID {id} in {table}.");
                bool update = item.TryGetProperty("update_existing", out var flag) && flag.GetBoolean();
                if (!tableIds.Add(id) && !update)
                    throw new InvalidDataException($"Equipment ID {id} already exists in {table}. Refusing to discard or overwrite an item.");
                if (tableIds.Count > ushort.MaxValue)
                    throw new InvalidDataException($"{table} exceeds the {ushort.MaxValue}-row engine limit. Reduce variants per item or select fewer sets.");
            }
        }
    }
}

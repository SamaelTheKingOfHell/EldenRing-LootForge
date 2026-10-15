using System.Text.Json;
using SoulsFormats;
using SoulsFormats.Cryptography;

namespace LootForge.RegTool;

/// <summary>Read surviving equipment row counts without materializing parameter cells.</summary>
public static class CapacityService
{
    /// <summary>List host-owned import rows that the native injector preserves rather than replacing.</summary>
    public static int ImportedRowIds(Dictionary<string, string> options)
    {
        var binder = RegulationDecryptor.DecryptERRegulation(options["input"]);
        var rows = new Dictionary<string, int[]>();
        foreach (var (category, table) in new[] { ("custom_skills", "SwordArtsParam"),
                     ("custom_behaviors", "BehaviorParam_PC"), ("custom_attacks", "AtkParam_Pc") })
        {
            var file = binder.Files.FirstOrDefault(f => f.Name.EndsWith(table + ".param", StringComparison.OrdinalIgnoreCase));
            rows[category] = file == null ? Array.Empty<int>() : PARAM.Read(file.Bytes).Rows
                .Where(r => r.Name?.Contains("[LootForge]") != true).Select(r => r.ID).ToArray();
        }
        Console.WriteLine(JsonSerializer.Serialize(rows));
        return 0;
    }

    /// <summary>Emit exact source capacities after excluding rows purged during a forge.</summary>
    public static int Execute(Dictionary<string, string> options)
    {
        var binder = RegulationDecryptor.DecryptERRegulation(options["input"]);
        var counts = new Dictionary<string, int>();
        foreach (string table in new[] { "EquipParamWeapon", "EquipParamProtector", "EquipParamAccessory" })
        {
            var file = binder.Files.First(f => f.Name.EndsWith(table + ".param", StringComparison.OrdinalIgnoreCase));
            var param = PARAM.Read(file.Bytes);
            counts[table] = param.Rows.Count(r => r.Name?.Contains("[LootForge]") != true);
        }
        Console.WriteLine(JsonSerializer.Serialize(counts));
        return 0;
    }
}

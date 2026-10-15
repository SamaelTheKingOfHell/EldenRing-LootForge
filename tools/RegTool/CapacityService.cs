using System.Text.Json;
using SoulsFormats;
using SoulsFormats.Cryptography;

namespace LootForge.RegTool;

/// <summary>Read surviving equipment row counts without materializing parameter cells.</summary>
public static class CapacityService
{
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

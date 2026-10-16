using System.Text.Json;
using SoulsFormats;
using SoulsFormats.Cryptography;
using LootForge.RegTool;

/// <summary>Read-only aggregate reward counts for every proven boss and chest in a deployed profile.</summary>
public static class DropBudgetAudit
{
    /// <summary>Record every proven reward chain and optionally reject generated overflow.</summary>
    public static void Run(string root, string source, string game, string report, bool enforce)
    {
        Oodle.Oodle6Ptr = System.Runtime.InteropServices.NativeLibrary.Load(Path.Combine(game, "oo2core_6_win64.dll"));
        string defs = Path.Combine(root, "tools/vendor/Paramdex/ER/Defs");
        var binder = RegulationDecryptor.DecryptERRegulation(source);
        PARAM Load(string name)
        {
            var param = PARAM.Read(binder.Files.Single(f => f.Name.EndsWith(name + ".param", StringComparison.OrdinalIgnoreCase)).Bytes);
            param.ApplyParamdefSomewhatCarefully(PARAMDEF.XmlDeserialize(Path.Combine(defs, (name.StartsWith("ItemLot") ? "ItemLotParam" : name) + ".xml"), false, false));
            return param;
        }
        var map = Load("ItemLotParam_map");
        var world = WorldLootCatalog.Load(source, game, defs, map, Load("ItemLotParam_enemy"), Load("NpcParam"), Load("ShopLineupParam"));
        var rewards = world.Bosses.Select(d => (kind: "boss", d)).Concat(world.Chests.Select(d => (kind: "chest", d)))
            .Select(pair => new { pair.kind, pair.d.LotId, pair.d.Name, original = pair.d.OriginalRewards,
                total = AdditiveLootService.RewardCount(map, pair.d.LotId) }).ToArray();
        var violations = rewards.Where(r => r.total > Math.Max(4, r.original)).ToArray();
        File.WriteAllText(report, JsonSerializer.Serialize(new { source, destinations = rewards.Length,
            maximum = rewards.Max(r => r.total), distribution = rewards.GroupBy(r => r.total).ToDictionary(g => g.Key, g => g.Count()),
            violations, rewards }, new JsonSerializerOptions { WriteIndented = true }));
        Console.WriteLine($"Boss/chest reward audit: {rewards.Length} destinations, maximum {rewards.Max(r => r.total)}, {violations.Length} over budget.");
        if (enforce && violations.Length > 0) throw new InvalidDataException("Deployed boss/chest rewards exceed four items.");
    }
}

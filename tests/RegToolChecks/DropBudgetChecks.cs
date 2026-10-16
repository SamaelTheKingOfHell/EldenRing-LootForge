using System.Text.Json;
using LootForge.RegTool;
using SoulsFormats;

/// <summary>Concrete reward-chain regressions for aggregate boss/chest limits.</summary>
public static class DropBudgetChecks
{
    /// <summary>Exercise shared budgets with real PARAM definitions and production injection paths.</summary>
    public static void Run(string defs, Action<bool, string> check)
    {
        PARAM Table(string name)
        {
            var definition = PARAMDEF.XmlDeserialize(Path.Combine(defs, name + ".xml"), false, false);
            var param = new PARAM { ParamType = definition.ParamType, Rows = new() };
            param.ApplyParamdef(definition);
            return param;
        }
        var map = Table("ItemLotParam");
        foreach (int id in new[] { 10000, 10001, 10008 })
        {
            var row = new PARAM.Row(id, "Host reward", map.AppliedParamdef);
            ParamHelper.SetCellIfExists(row, "lotItemId01", 100);
            ParamHelper.SetCellIfExists(row, "lotItemBasePoint01", (ushort)1000);
            ParamHelper.SetCellIfExists(row, "lotItemNum01", (byte)99);
            ParamHelper.SetCellIfExists(row, "getItemFlagId", 123u);
            map.Rows.Add(row);
        }
        ParamHelper.SetCellIfExists(map.Rows[0], "lotItemId02", 200);
        ParamHelper.SetCellIfExists(map.Rows[0], "lotItemBasePoint02", (ushort)1000);
        ParamHelper.SetCellIfExists(map.Rows[0], "lotItemNum02", (byte)1);
        string before = JsonSerializer.Serialize(map.Rows.Select(row => row.Cells.Select(c => c.Value)));
        check(AdditiveLootService.RewardCount(map, 10000) == 2 && AdditiveLootService.RewardCount(map, 10001) == 2,
            "lottery alternatives and native stacks count once; chain aliases share the reward count");
        var weapons = Table("EquipParamWeapon");
        for (int id = 100000000; id < 100000010; id++) weapons.Rows.Add(new(id, "[LootForge] Early sword", weapons.AppliedParamdef));
        var armor = Table("EquipParamProtector");
        (PARAM, BinderFile) Load(string name, string _) => (map, new());
        using var tooMany = JsonDocument.Parse("{\"type\":\"map_pickup\",\"target_id\":\"10000\",\"awarded_items\":[100000000,100000001,100000002]}");
        int count = 0;
        bool rejected = false;
        LootInjector.ResetCache();
        try { LootInjector.InjectLootDistribution(tooMany.RootElement, Load, new(), new(), new(), ref count); }
        catch (InvalidOperationException) { rejected = true; }
        check(rejected && count == 0 && before == JsonSerializer.Serialize(map.Rows.Select(row => row.Cells.Select(c => c.Value))),
            "oversized direct reward groups fail before any row is appended");
        using var direct = JsonDocument.Parse("{\"type\":\"map_pickup\",\"target_id\":\"10000\",\"awarded_items\":[100000000]}");
        LootInjector.InjectLootDistribution(direct.RootElement, Load, new(), new(), new(), ref count);
        var world = new WorldLootCatalog();
        world.Bosses.Add(new(10000, "Boss", EntityProgressionTier.Early, 6, "fixture", 2));
        world.Chests.Add(new(10000, "Chest alias", EntityProgressionTier.Early, 6, "fixture", 2));
        BossLootPoolService.EnrichBossLootPools(Table("ItemLotParam"), map, weapons, armor, 10, verified: world);
        check(AdditiveLootService.RewardCount(map, 10000) == 4, "direct rewards plus boss enrichment share a four-item maximum");
        int rows = map.Rows.Count;
        ChestLootPoolService.EnrichChestLootPools(map, Table("ItemLotParam"), armor, weapons, 4, 4, verified: world);
        check(map.Rows.Count == rows && !AdditiveLootService.TryAppend(map, 10001, 100000009, 2, 1000, "fifth", true),
            "chest enrichment and alternate roots cannot add a fifth item after boss enrichment");
        check(AdditiveLootService.RewardCount(map, 10000, originalsOnly: true) == 2 &&
            before == JsonSerializer.Serialize(map.Rows.Where(row => row.Name == "Host reward").Select(row => row.Cells.Select(c => c.Value))),
            "all original reward rows, quantities, weights and flags remain intact");
        check(AdditiveLootService.TryAppend(map, 10008, 100000009, 2, 1000, "separate chain", true),
            "a disconnected original reward has its own budget and keeps its separation gap");
    }
}

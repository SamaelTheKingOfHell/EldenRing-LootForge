using System.Text.Json;
using LootForge.RegTool;
using SoulsFormats;
using SoulsFormats.Cryptography;

/// <summary>Real PARAM/FMG fixtures covering additive drops, legacy recovery and language parity.</summary>
public static class AdditiveLootChecks
{
    /// <summary>Exercise production paths against occupied, flagged, multi-item and multilingual sources.</summary>
    public static void Run(string defs, Action<bool, string> check)
    {
        PARAM Table(string name)
        {
            var definition = PARAMDEF.XmlDeserialize(Path.Combine(defs, name + ".xml"), false, false);
            var param = new PARAM { ParamType = definition.ParamType, Rows = new() };
            param.ApplyParamdef(definition);
            return param;
        }
        PARAM.Row Row(PARAM param, int id, string name = "Original")
        {
            var row = new PARAM.Row(id, name, param.AppliedParamdef);
            param.Rows.Add(row);
            return row;
        }
        string Snapshot(PARAM.Row row) => JsonSerializer.Serialize(row.Cells.Select(c => c.Value));
        var enemy = Table("ItemLotParam");
        var original = Row(enemy, 50000);
        ParamHelper.SetCellIfExists(original, "lotItemId01", 500);
        ParamHelper.SetCellIfExists(original, "lotItemBasePoint01", (ushort)1000);
        ParamHelper.SetCellIfExists(original, "lotItemBasePoint02", (ushort)500);
        ParamHelper.SetCellIfExists(original, "getItemFlagId", 123u);
        ParamHelper.SetCellIfExists(original, "cumulateNumFlagId", 456u);
        ParamHelper.SetCellIfExists(original, "enableLuck01", (byte)1);
        var existingChain = Row(enemy, 50001);
        ParamHelper.SetCellIfExists(existingChain, "lotItemId01", 600);
        var unrelated = Row(enemy, 50004);
        ParamHelper.SetCellIfExists(unrelated, "lotItemId01", 700);
        string before = Snapshot(original), chainBefore = Snapshot(existingChain), unrelatedBefore = Snapshot(unrelated);
        int independentCapacity = AdditiveLootService.Capacity(enemy);
        check(independentCapacity > 0, "independent capacity accounts for existing chains and separation gaps");
        check(AdditiveLootService.TryAppend(enemy, original.ID, 100000001, 4, 250, "Fixture accessory"), "custom roll is appended after existing chain");
        var extra = enemy.Rows.Single(r => r.ID == 50002);
        check(AdditiveLootService.Capacity(enemy) == independentCapacity, "capacity excludes earlier generated chains that a reforge purges");
        check(Snapshot(original) == before && Snapshot(existingChain) == chainBefore, "all original reward weights, quantities and flags remain identical");
        check(ParamHelper.GetCellInt(extra, "lotItemBasePoint01") == 250 && ParamHelper.GetCellInt(extra, "lotItemBasePoint02") == 750,
            "additional 25 percent roll has an independent 75 percent no-drop outcome");
        check(ParamHelper.GetCellInt(extra, "getItemFlagId") == 0 && ParamHelper.GetCellInt(extra, "cumulateNumFlagId") == 0 &&
            ParamHelper.GetCellInt(extra, "enableLuck01") == 0, "new rolls do not inherit original one-shot flags, pity counters or luck");
        check(!AdditiveLootService.TryAppend(enemy, original.ID, 100000002, 4, 1000, "Blocked") && Snapshot(unrelated) == unrelatedBefore,
            "insertion leaves the gap before an unrelated existing reward intact");
        enemy.ParamdefDataVersion = enemy.AppliedParamdef.DataVersion;
        var savedEnemy = PARAM.Read(ParamSerialization.Write(enemy));
        check(savedEnemy.Rows.Select(r => r.ID).SequenceEqual(savedEnemy.Rows.Select(r => r.ID).Order()),
            "new chained rows are serialized in runtime lookup order");
        var accessoryOrder = Table("EquipParamAccessory");
        Row(accessoryOrder, 1000);
        Row(accessoryOrder, 999999999, "Sentinel");
        Row(accessoryOrder, 100000001, "[LootForge] Custom");
        accessoryOrder.ParamdefDataVersion = accessoryOrder.AppliedParamdef.DataVersion;
        check(PARAM.Read(ParamSerialization.Write(accessoryOrder)).Rows.Select(r => r.ID).SequenceEqual(new[] { 1000, 100000001, 999999999 }),
            "accessories remain sorted when a host sentinel ID exceeds procedural IDs");

        var map = Table("ItemLotParam");
        var chest = Row(map, 10030, "Limgrave chest");
        ParamHelper.SetCellIfExists(chest, "lotItemId01", 900);
        ParamHelper.SetCellIfExists(chest, "lotItemBasePoint01", (ushort)1000);
        string chestBefore = Snapshot(chest);
        var tables = new Dictionary<string, PARAM> { ["ItemLotParam_enemy"] = enemy, ["ItemLotParam_map"] = map,
            ["EquipParamWeapon"] = Table("EquipParamWeapon"), ["EquipParamProtector"] = Table("EquipParamProtector"),
            ["EquipParamAccessory"] = Table("EquipParamAccessory"), ["ShopLineupParam"] = Table("ShopLineupParam") };
        (PARAM, BinderFile) Load(string table, string definition) => (tables[table], new BinderFile());
        using var spec = JsonDocument.Parse("{\"type\":\"map_pickup\",\"target_id\":\"10030\",\"awarded_items\":[100000003,100000004],\"drop_rate_percent\":100}");
        int count = 0;
        LootInjector.ResetCache();
        LootInjector.InjectLootDistribution(spec.RootElement, Load, new(), new(), new() { [100000003] = true, [100000004] = true }, ref count);
        check(Snapshot(chest) == chestBefore && count == 2 && map.Rows.Count == 3, "ordinary chest injection adds both items without changing its original lottery");
        bool overflowRejected = false;
        try { ShopLootInjector.RotateOverflowToEnemyDrop(100000005, Load, new(), new(), new() { [100000005] = true }, ref count); }
        catch (InvalidOperationException) { overflowRejected = true; }
        check(overflowRejected && Snapshot(original) == before && Snapshot(unrelated) == unrelatedBefore,
            "full shops reject unscoped overflow without touching enemy or gathering loot");
        var flaggedMap = Table("ItemLotParam");
        var flaggedChest = Row(flaggedMap, 20000);
        ParamHelper.SetCellIfExists(flaggedChest, "getItemFlagId", 987u);
        ParamHelper.SetCellIfExists(flaggedChest, "cumulateNumFlagId", 876u);
        AdditiveLootService.TryAppend(flaggedMap, 20000, 20001, 4, 1000, "One-time chest", true);
        check(ParamHelper.GetCellInt(flaggedMap.Rows[1], "getItemFlagId") == 987 &&
            ParamHelper.GetCellInt(flaggedMap.Rows[1], "cumulateNumFlagId") == 0,
            "chest bonuses share acquisition flags without inheriting pity counters");
        BossLootPoolService.EnrichBossLootPools(enemy, map, tables["EquipParamWeapon"], tables["EquipParamProtector"], 2);
        ChestLootPoolService.EnrichChestLootPools(map, enemy, tables["EquipParamProtector"], tables["EquipParamWeapon"], 1, 2);
        check(Snapshot(chest) == chestBefore && Snapshot(original) == before && Snapshot(existingChain) == chainBefore,
            "boss and chest enrichment preserve full original rows, including no-drop outcomes");

        var ownedWeapon = Row(tables["EquipParamWeapon"], 100000099, "[LootForge] Old weapon");
        var otherCategory = Row(map, 20000);
        ParamHelper.SetCellIfExists(otherCategory, "lotItemId01", ownedWeapon.ID);
        ParamHelper.SetCellIfExists(otherCategory, "lotItemCategory01", 4);
        ParamInjector.PurgePreviousInjections(Load);
        check(ParamHelper.GetCellInt(otherCategory, "lotItemId01") == ownedWeapon.ID,
            "purge does not erase another equipment category with the same numeric ID");

        string temporary = Path.Combine(Path.GetTempPath(), "lootforge-additive-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(temporary);
        try
        {
            var archive = new BND4();
            foreach (string name in new[] { "AccessoryName", "AccessoryInfo", "AccessoryCaption", "AccessoryName_dlc02" })
            {
                var fmg = new FMG();
                fmg.Entries.Add(new FMG.Entry(1000, "Original localized text"));
                archive.Files.Add(new BinderFile(Binder.FileFlags.Flag1, name + ".fmg", fmg.Write()));
            }
            string source = Path.Combine(temporary, "source", "msg");
            foreach (string language in new[] { "engus", "porbr", "zhocn" })
            {
                string directory = Path.Combine(source, language);
                Directory.CreateDirectory(directory);
                archive.Write(Path.Combine(directory, "item_dlc02.msgbnd.dcx"));
            }
            string output = Path.Combine(temporary, "output", "regulation.bin");
            var texts = new List<FmgInjector.FmgTextSpec> { new(100000001, 1000, false, "Custom talisman", "Custom caption", "Custom info", true) };
            FmgInjector.InjectFmgTexts(Path.Combine(source, "engus"), output, texts);
            foreach (string language in new[] { "engus", "porbr", "zhocn" })
            {
                var saved = BND4.Read(Path.Combine(temporary, "output", "msg", language, "item_dlc02.msgbnd.dcx"));
                check(saved.Files.Where(f => FmgArchiveService.MatchesCategory(f.Name, "AccessoryName"))
                    .All(f => FMG.Read(f.Bytes).Entries.Any(e => e.ID == 100000001 && e.Text == "[LootForge] Custom talisman")),
                    $"custom accessory name resolves in every {language} base/DLC table");
                check(saved.Files.All(f => FMG.Read(f.Bytes).Entries.Any(e => e.ID == 1000 && e.Text == "Original localized text")),
                    $"existing {language} localized text is preserved");
            }
            bool missingRejected = false;
            try { FmgArchiveService.InjectFmgEntriesIntoBnd(new BND4(), texts); }
            catch (InvalidDataException) { missingRejected = true; }
            check(missingRejected, "missing accessory name table fails instead of falsely counting injected names");
            var cleanup = new BND4();
            var staleNames = new FMG();
            staleNames.Entries.Add(new FMG.Entry(1000, "Original name"));
            staleNames.Entries.Add(new FMG.Entry(100000001, "Obsolete generated name"));
            cleanup.Files.Add(new BinderFile(Binder.FileFlags.Flag1, "AccessoryName.fmg", staleNames.Write()));
            FmgCleanupService.Prune(cleanup, new() { ["Accessory"] = new() { 100000001 } });
            check(FMG.Read(cleanup.Files[0].Bytes).Entries.Count == 1 && FMG.Read(cleanup.Files[0].Bytes).Entries[0].Text == "Original name",
                "text cleanup removes only known obsolete generated IDs and preserves original names");

            var clean = new BND4();
            var recoveryTables = new Dictionary<string, PARAM>();
            foreach (string table in new[] { "EquipParamWeapon", "EquipParamProtector", "EquipParamAccessory", "ItemLotParam_enemy", "ItemLotParam_map" })
            {
                var param = Table(table.StartsWith("ItemLot") ? "ItemLotParam" : table);
                var row = Row(param, 10030);
                if (table.StartsWith("ItemLot"))
                {
                    ParamHelper.SetCellIfExists(row, "lotItemId01", 2000);
                    ParamHelper.SetCellIfExists(row, "lotItemBasePoint01", (ushort)1000);
                    ParamHelper.SetCellIfExists(row, "lotItemBasePoint02", (ushort)350);
                }
                param.ParamdefDataVersion = param.AppliedParamdef.DataVersion;
                clean.Files.Add(new BinderFile(Binder.FileFlags.Flag1, table + ".param", param.Write()));
                recoveryTables[table] = param;
            }
            string backups = Path.Combine(temporary, "backups");
            Directory.CreateDirectory(backups);
            RegulationDecryptor.EncryptERRegulation(Path.Combine(backups, "regulation.bin.bak_1"), clean);
            Row(recoveryTables["EquipParamWeapon"], 100000001, "[LootForge] Legacy weapon");
            var legacy = recoveryTables["ItemLotParam_map"].Rows[0];
            ParamHelper.SetCellIfExists(legacy, "lotItemId02", 100000001);
            ParamHelper.SetCellIfExists(legacy, "lotItemCategory02", 2);
            ParamHelper.SetCellIfExists(legacy, "lotItemBasePoint02", (ushort)1000);
            (PARAM, BinderFile) RecoveryLoad(string table, string definition) => (recoveryTables[table], new());
            check(LegacyLootRecovery.Restore(clean, RecoveryLoad, backups, defs) == 1 &&
                ParamHelper.GetCellInt(legacy, "lotItemId02") == 0 && ParamHelper.GetCellInt(legacy, "lotItemBasePoint02") == 350,
                "legacy mixed rows recover original no-drop weights from a matching clean encrypted backup");
            ParamHelper.SetCellIfExists(legacy, "lotItemId02", 100000001);
            ParamHelper.SetCellIfExists(legacy, "lotItemCategory02", 2);
            ParamHelper.SetCellIfExists(legacy, "lotItemBasePoint01", (ushort)750);
            bool unrelatedRejected = false;
            try { LegacyLootRecovery.Restore(clean, RecoveryLoad, backups, defs); }
            catch (InvalidDataException) { unrelatedRejected = true; }
            check(unrelatedRejected && ParamHelper.GetCellInt(legacy, "lotItemBasePoint01") == 750,
                "legacy recovery refuses to overwrite unrelated loot edits");
        }
        finally { Directory.Delete(temporary, true); }
    }
}

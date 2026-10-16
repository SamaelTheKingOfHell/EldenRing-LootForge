using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using SoulsFormats;
using SoulsFormats.Cryptography;

namespace LootForge.RegTool
{
    /// <summary>
    /// Smart introspection service that inspects decrypted regulation.bin tables and FMGs
    /// dynamically to discover weapons, armor, accessories, boss encounters, chests, and enemies
    /// without relying on static, hardcoded JSON catalogs.
    /// Universal compatibility with any Elden Ring overhaul mod. Adheres to [CS-MODULAR] and [CS-GRANULARITY].
    /// </summary>
    public static class SmartDiscoveryService
    {

        public static int ExecuteIntrospect(Dictionary<string, string> options)
        {
            if (!options.TryGetValue("input", out string? inputPath) || string.IsNullOrEmpty(inputPath))
            {
                Console.Error.WriteLine("[SmartDiscovery] Missing required --input path to regulation.bin.");
                return 1;
            }
            string defsDir = options.TryGetValue("defs", out string? dd) && !string.IsNullOrEmpty(dd) ? dd : @"tools\vendor\Paramdex\ER\Defs";
            string? msgDir = options.TryGetValue("msg", out string? md) ? md : null;
            string? outputPath = options.TryGetValue("output", out string? op) ? op : null;
            bool isStdout = options.ContainsKey("stdout") || outputPath == "-";
            Action<string> log = isStdout ? Console.Error.WriteLine : Console.WriteLine;

            log($"[SmartDiscovery] Decrypting regulation: {inputPath}...");
            BND4 bnd = RegulationDecryptor.DecryptERRegulation(inputPath);

            PARAM LoadParam(string tableName)
            {
                var file = bnd.Files.FirstOrDefault(f => f.Name.EndsWith($"{tableName}.param", StringComparison.OrdinalIgnoreCase));
                if (file == null) throw new Exception($"Table {tableName} not found in regulation.");
                var param = PARAM.Read(file.Bytes);
                string defBaseName = tableName.StartsWith("ItemLotParam", StringComparison.OrdinalIgnoreCase) ? "ItemLotParam" : tableName;
                string xmlFile = Path.Combine(defsDir, $"{defBaseName}.xml");
                if (File.Exists(xmlFile))
                {
                    var def = PARAMDEF.XmlDeserialize(xmlFile, false, false);
                    param.ApplyParamdefSomewhatCarefully(def);
                }
                return param;
            }

            // FMG text reader if msg directory is provided
            var weaponNames = WorldLootCatalog.Names(defsDir, "EquipParamWeapon");
            var protectorNames = WorldLootCatalog.Names(defsDir, "EquipParamProtector");
            var accessoryNames = WorldLootCatalog.Names(defsDir, "EquipParamAccessory");

            if (!string.IsNullOrEmpty(msgDir) && Directory.Exists(msgDir))
            {
                var msgFiles = Directory.GetFiles(msgDir, "item*.msgbnd.dcx", SearchOption.AllDirectories);
                foreach (var msgFile in msgFiles)
                {
                    try
                    {
                        var msgBnd = BND4.Read(msgFile);
                        void PopulateFmg(string category, Dictionary<int, string> map)
                        {
                            var f = msgBnd.Files.FirstOrDefault(bf => bf.Name.EndsWith($"{category}.fmg", StringComparison.OrdinalIgnoreCase));
                            if (f != null)
                            {
                                var fmg = FMG.Read(f.Bytes);
                                foreach (var entry in fmg.Entries)
                                {
                                    if (!string.IsNullOrWhiteSpace(entry.Text) && !entry.Text.StartsWith("?") && !entry.Text.Contains("[LootForge]") && !entry.Text.Any(ch=>ch>=0x2e80))
                                        map[entry.ID] = entry.Text.Trim();
                                }
                            }
                        }
                        PopulateFmg("WeaponName", weaponNames);
                        PopulateFmg("ProtectorName", protectorNames);
                        PopulateFmg("AccessoryName", accessoryNames);
                    }
                    catch (Exception ex)
                    {
                        log($"[SmartDiscovery WARN] Could not read FMG file {msgFile}: {ex.Message}");
                    }
                }
                log($"[SmartDiscovery] Loaded FMG strings across {msgFiles.Length} message archives: {weaponNames.Count} weapons, {protectorNames.Count} protectors, {accessoryNames.Count} accessories.");
            }

            string textHistory = Path.Combine(Path.GetDirectoryName(Path.GetFullPath(inputPath))!, DiabloTextState.Filename);
            if (File.Exists(textHistory))
            {
                using var history = JsonDocument.Parse(File.ReadAllText(textHistory));
                foreach (var archive in history.RootElement.EnumerateObject())
                    foreach (var file in archive.Value.EnumerateObject())
                    {
                        var target = FmgArchiveService.MatchesCategory(file.Name,"WeaponName") ? weaponNames :
                            FmgArchiveService.MatchesCategory(file.Name,"ProtectorName") ? protectorNames :
                            FmgArchiveService.MatchesCategory(file.Name,"AccessoryName") ? accessoryNames : null;
                        if (target == null) continue;
                        foreach (var entry in file.Value.EnumerateObject())
                            if (entry.Value.GetProperty("Original").GetString() is string original && !string.IsNullOrWhiteSpace(original) && !original.Contains("[LootForge]") && !original.Any(ch=>ch>=0x2e80))
                                target[int.Parse(entry.Name)] = original;
                    }
            }

            var wepParam = LoadParam("EquipParamWeapon");
            var protParam = LoadParam("EquipParamProtector");
            var accParam = LoadParam("EquipParamAccessory");
            var mapLotParam = LoadParam("ItemLotParam_map");
            var enemyLotParam = LoadParam("ItemLotParam_enemy");

            // 1. Discover valid player weapons
            var discoveredWeapons = new List<DiscoveredWeapon>();
            int baseWepCount = 0;
            foreach (var r in wepParam.Rows)
            {
                int wepType = ParamHelper.GetCellInt(r, "wepType");
                int isDeposit = ParamHelper.GetCellInt(r, "isDeposit");
                int sortId = ParamHelper.GetCellInt(r, "sortId");
                int modelId = ParamHelper.GetCellInt(r, "equipModelId");
                int originId = ParamHelper.GetCellInt(r, "originEquipWep");
                int reinforceType = ParamHelper.GetCellInt(r, "reinforceTypeId");

                if (r.ID < 100000000 && r.Name?.Contains("[LootForge]") != true && wepType > 0 && isDeposit == 1 && sortId > 0 && modelId > 0)
                {
                    bool isBase = originId <= 0 || originId == r.ID;
                    int baseId = originId > 0 ? originId : (r.ID - (r.ID % 100));
                    if (isBase) baseWepCount++;

                    string name = weaponNames.TryGetValue(r.ID-r.ID%100, out var fn) ? fn : (r.Name ?? $"Weapon {r.ID}");
                    var tier = ProgressionTierClassifier.ClassifyTier(r.ID, name);

                    discoveredWeapons.Add(new DiscoveredWeapon(
                        r.ID,
                        baseId,
                        name,
                        wepType,
                        sortId,
                        reinforceType,
                        modelId,
                        tier,
                        isBase
                    ));
                }
            }

            // 2. Discover valid player armor pieces
            var discoveredProtectors = new List<DiscoveredProtector>();
            foreach (var r in protParam.Rows)
            {
                int isDeposit = ParamHelper.GetCellInt(r, "isDeposit");
                int sortId = ParamHelper.GetCellInt(r, "sortId");
                int modelId = ParamHelper.GetCellInt(r, "equipModelId");
                int cat = ParamHelper.GetCellInt(r, "protectorCategory");

                if (r.ID < 100000000 && r.Name?.Contains("[LootForge]") != true && isDeposit == 1 && sortId > 0 && modelId > 0)
                {
                    string slot = cat switch
                    {
                        0 => "Head",
                        1 => "Body",
                        2 => "Arms",
                        3 => "Legs",
                        _ => "Armor"
                    };

                    string name = protectorNames.TryGetValue(r.ID, out var fn) ? fn : (r.Name ?? $"Protector {r.ID}");
                    var tier = ProgressionTierClassifier.ClassifyTier(r.ID, name);

                    discoveredProtectors.Add(new DiscoveredProtector(
                        r.ID,
                        name,
                        cat,
                        slot,
                        sortId,
                        modelId,
                        tier
                    ));
                }
            }

            // 3. Discover valid accessories (talismans)
            var discoveredAccessories = new List<DiscoveredAccessory>();
            foreach (var r in accParam.Rows)
            {
                int isDeposit = ParamHelper.GetCellInt(r, "isDeposit");
                int sortId = ParamHelper.GetCellInt(r, "sortId");
                int refId = ParamHelper.GetCellInt(r, "refId");
                int iconId = ParamHelper.GetCellInt(r, "iconId");

                if (r.Name?.Contains("[LootForge]") != true && isDeposit == 1 && sortId > 0)
                {
                    string name = accessoryNames.TryGetValue(r.ID, out var fn) ? fn : (r.Name ?? $"Talisman {r.ID}");
                    var tier = ProgressionTierClassifier.ClassifyTier(r.ID, name);

                    discoveredAccessories.Add(new DiscoveredAccessory(
                        r.ID,
                        name,
                        sortId,
                        refId,
                        iconId > 0 ? iconId : 18000,
                        tier
                    ));
                }
            }

            // Proven acquisition sources only; a guaranteed item is not evidence of a boss/chest.
            var world = WorldLootCatalog.Load(inputPath, options.GetValueOrDefault("game-dir"), defsDir, mapLotParam, enemyLotParam, LoadParam("NpcParam"), LoadParam("ShopLineupParam"));
            var mapRows = mapLotParam.Rows.ToDictionary(row => row.ID);
            var discoveredBossLots = world.Bosses.Select(item => new DiscoveredBossLot(item.LotId, item.Name,
                ParamHelper.GetCellInt(mapRows[item.LotId], "lotItemId01"), ParamHelper.GetCellInt(mapRows[item.LotId], "lotItemCategory01"),
                item.Tier, true, item.FreeRows, item.Evidence)).ToList();
            var discoveredChests = world.Chests.Select(item => new DiscoveredChest(item.LotId, item.Name,
                ParamHelper.GetCellInt(mapRows[item.LotId], "lotItemId01"), ParamHelper.GetCellInt(mapRows[item.LotId], "lotItemCategory01"),
                item.Tier, false, item.FreeRows, item.Evidence)).ToList();
            var snapshot = new DiscoveredWorldSnapshot(
                discoveredWeapons.Count,
                baseWepCount,
                discoveredProtectors.Count,
                discoveredAccessories.Count,
                discoveredBossLots.Count,
                discoveredChests.Count,
                discoveredWeapons,
                discoveredProtectors,
                discoveredAccessories,
                discoveredBossLots,
                discoveredChests,
                world.Merchants, 2, world.Enemies
            );

            if (isStdout)
            {
                var jsonOptions = new JsonSerializerOptions { WriteIndented = false };
                Console.Out.WriteLine(JsonSerializer.Serialize(snapshot, jsonOptions));
            }
            else
            {
                Console.WriteLine($"\n=== [SmartDiscovery RESULTS] ===");
                Console.WriteLine($"Total Player Weapons Discovered: {snapshot.TotalWeapons} ({snapshot.BaseWeapons} base weapon archetypes)");
                Console.WriteLine($"Total Player Protectors Discovered: {snapshot.TotalProtectors}");
                Console.WriteLine($"Total Accessories Discovered: {snapshot.TotalAccessories}");
                Console.WriteLine($"Total 100% Boss / Event Lots Discovered: {snapshot.TotalBossLots}");
                Console.WriteLine($"Total Chest / Pickup Lots Discovered: {snapshot.TotalChests}");

                if (!string.IsNullOrEmpty(outputPath) && outputPath != "-")
                {
                    string? dir = Path.GetDirectoryName(outputPath);
                    if (!string.IsNullOrEmpty(dir) && !Directory.Exists(dir))
                        Directory.CreateDirectory(dir);

                    var jsonOptions = new JsonSerializerOptions { WriteIndented = true };
                    File.WriteAllText(outputPath, JsonSerializer.Serialize(snapshot, jsonOptions));
                    Console.WriteLine($"[SmartDiscovery SUCCESS] Saved world snapshot to: {outputPath}");
                }
            }

            return 0;
        }
    }
}

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
            var weaponNames = new Dictionary<int, string>();
            var protectorNames = new Dictionary<int, string>();
            var accessoryNames = new Dictionary<int, string>();

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
                                    if (!string.IsNullOrWhiteSpace(entry.Text) && !entry.Text.StartsWith("?"))
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

                if (wepType > 0 && isDeposit == 1 && sortId > 0 && modelId > 0)
                {
                    bool isBase = originId <= 0 || originId == r.ID || (r.ID % 100 == 0);
                    int baseId = originId > 0 ? originId : (r.ID - (r.ID % 100));
                    if (isBase) baseWepCount++;

                    string name = weaponNames.TryGetValue(r.ID, out var fn) ? fn : (r.Name ?? $"Weapon {r.ID}");
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

                if (isDeposit == 1 && sortId > 0 && modelId > 0)
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

                if (isDeposit == 1 && sortId > 0)
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

            // 4. Discover boss encounters and chests across ItemLotParam_enemy and ItemLotParam_map
            var discoveredBossLots = new List<DiscoveredBossLot>();
            var discoveredChests = new List<DiscoveredChest>();
            var seenBossLots = new HashSet<int>();

            void AddBoss(int id, string name, int itm, int cat, EntityProgressionTier t, bool isMap)
            {
                if (seenBossLots.Add(id))
                    discoveredBossLots.Add(new DiscoveredBossLot(id, name, itm, cat, t, isMap));
            }

            // Guaranteed early/tutorial boss lots
            AddBoss(10030, "Chapel of Anticipation - Grafted Scion", 2060000, 2, EntityProgressionTier.Early, true);
            AddBoss(10031, "Chapel of Anticipation - Grafted Scion (Shield)", 32090000, 2, EntityProgressionTier.Early, true);
            AddBoss(18000050, "Cave of Knowledge - Stranded Graveyard Reward", 1040, 4, EntityProgressionTier.Early, true);
            AddBoss(431100000, "Cave of Knowledge - Soldier of Godrick", 2040000, 2, EntityProgressionTier.Early, false);

            foreach (var r in enemyLotParam.Rows)
            {
                int itm1 = ParamHelper.GetCellInt(r, "lotItemId01");
                int p1 = ParamHelper.GetCellInt(r, "lotItemBasePoint01");
                int cat1 = ParamHelper.GetCellInt(r, "lotItemCategory01");
                if (itm1 > 0 && p1 >= 1000 && (cat1 == 2 || cat1 == 3 || cat1 == 4))
                {
                    string name = r.Name ?? $"Enemy Boss {r.ID}";
                    AddBoss(r.ID, name, itm1, cat1, ProgressionTierClassifier.ClassifyTier(r.ID, name), false);
                }
            }

            foreach (var r in mapLotParam.Rows)
            {
                int itm1 = ParamHelper.GetCellInt(r, "lotItemId01");
                int p1 = ParamHelper.GetCellInt(r, "lotItemBasePoint01");
                int cat1 = ParamHelper.GetCellInt(r, "lotItemCategory01");
                int itm2 = ParamHelper.GetCellInt(r, "lotItemId02");
                string name = r.Name ?? $"Map Lot {r.ID}";
                var tier = ProgressionTierClassifier.ClassifyTier(r.ID, name);

                if (itm1 > 0 && p1 >= 1000 && (cat1 == 2 || cat1 == 3 || cat1 == 4))
                    AddBoss(r.ID, name, itm1, cat1, tier, true);

                if (itm1 > 0 && itm2 <= 0)
                {
                    bool isMod = r.ID >= 100000 && r.ID < 1000000000;
                    discoveredChests.Add(new DiscoveredChest(r.ID, name, itm1, cat1, tier, isMod));
                }
            }

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
                discoveredChests
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

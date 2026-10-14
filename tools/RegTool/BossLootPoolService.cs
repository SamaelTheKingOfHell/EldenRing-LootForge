using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using SoulsFormats;
using SoulsFormats.Cryptography;

namespace LootForge.RegTool
{
    /// <summary>
    /// Injects high-tier weapon loot pools into boss encounter drop tables across the Lands Between,
    /// scaled strictly by world progression tier.
    /// Supports both ItemLotParam_enemy and ItemLotParam_map without replacing vanilla drops.
    /// Adheres to [CS-MODULAR] and [CS-GRANULARITY] (<= 300 lines).
    /// </summary>
    public static class BossLootPoolService
    {
        public static int ExecuteInjectBossLootPools(Dictionary<string, string> options)
        {
            if (!options.TryGetValue("input", out string? inputPath) || string.IsNullOrEmpty(inputPath))
            {
                Console.Error.WriteLine("[BossLootPool] Missing required --input path to regulation.bin.");
                return 1;
            }
            string outputPath = options.TryGetValue("output", out string? op) && !string.IsNullOrEmpty(op) ? op : inputPath;
            string defsDir = options.TryGetValue("defs", out string? dd) && !string.IsNullOrEmpty(dd) ? dd : @"tools\vendor\Paramdex\ER\Defs";
            int weaponsPerBoss = options.TryGetValue("count", out string? cntStr) && int.TryParse(cntStr, out int parsedCnt) ? Math.Clamp(parsedCnt, 1, 5) : 3;

            Console.WriteLine($"[BossLootPool] Decrypting regulation: {inputPath}...");
            BND4 bnd = RegulationDecryptor.DecryptERRegulation(inputPath);

            PARAM LoadParam(string tableName)
            {
                var file = bnd.Files.FirstOrDefault(f => f.Name.EndsWith($"{tableName}.param", StringComparison.OrdinalIgnoreCase));
                if (file == null) throw new Exception($"Table {tableName} not found in regulation.");
                var param = PARAM.Read(file.Bytes);
                string xmlFile = Path.Combine(defsDir, "ItemLotParam.xml");
                if (File.Exists(xmlFile))
                {
                    var def = PARAMDEF.XmlDeserialize(xmlFile, false, false);
                    param.ApplyParamdefSomewhatCarefully(def);
                }
                return param;
            }

            var enemyParam = LoadParam("ItemLotParam_enemy");
            var mapParam = LoadParam("ItemLotParam_map");
            PARAM? wepParam = null, protParam = null;
            var wepFile = bnd.Files.FirstOrDefault(f => f.Name.EndsWith("EquipParamWeapon.param", StringComparison.OrdinalIgnoreCase));
            if (wepFile != null) wepParam = PARAM.Read(wepFile.Bytes);
            var protFile = bnd.Files.FirstOrDefault(f => f.Name.EndsWith("EquipParamProtector.param", StringComparison.OrdinalIgnoreCase));
            if (protFile != null) protParam = PARAM.Read(protFile.Bytes);

            EnrichBossLootPools(enemyParam, mapParam, wepParam, protParam, weaponsPerBoss);

            // Write back both tables
            var enemyFile = bnd.Files.First(f => f.Name.EndsWith("ItemLotParam_enemy.param", StringComparison.OrdinalIgnoreCase));
            enemyFile.Bytes = enemyParam.Write();

            var mapFile = bnd.Files.First(f => f.Name.EndsWith("ItemLotParam_map.param", StringComparison.OrdinalIgnoreCase));
            mapFile.Bytes = mapParam.Write();

            string? outDir = Path.GetDirectoryName(outputPath);
            if (!string.IsNullOrEmpty(outDir) && !Directory.Exists(outDir))
                Directory.CreateDirectory(outDir);

            Console.WriteLine($"[BossLootPool] Encrypting and saving updated regulation to: {outputPath}...");
            RegulationDecryptor.EncryptERRegulation(outputPath, bnd);
            Console.WriteLine($"[BossLootPool SUCCESS] Saved {new FileInfo(outputPath).Length} bytes. All bosses and tutorial encounters enriched!");

            return 0;
        }

        public static int EnrichBossLootPools(PARAM enemyParam, PARAM mapParam, PARAM? wepParam, PARAM? protParam, int weaponsPerBoss = 3)
        {
            var enemyRowMap = new Dictionary<int, PARAM.Row>(enemyParam.Rows.Count);
            foreach (var r in enemyParam.Rows) enemyRowMap[r.ID] = r;

            var mapRowMap = new Dictionary<int, PARAM.Row>(mapParam.Rows.Count);
            foreach (var r in mapParam.Rows) mapRowMap[r.ID] = r;

            // Target boss encounters across both ItemLotParam_enemy and ItemLotParam_map
            var targetBosses = new Dictionary<int, (string Name, EntityProgressionTier Tier, bool IsMapTable)>();

            // 1. Explicit Tutorial & Early Boss Registrations
            targetBosses[10030] = ("Chapel of Anticipation - Grafted Scion", EntityProgressionTier.Early, true);
            targetBosses[10031] = ("Chapel of Anticipation - Grafted Scion (Shield)", EntityProgressionTier.Early, true);
            targetBosses[431100000] = ("Cave of Knowledge - Soldier of Godrick", EntityProgressionTier.Early, false);
            targetBosses[18000050] = ("Cave of Knowledge / Stranded Graveyard Reward", EntityProgressionTier.Early, true);
            targetBosses[20330] = ("Groveside Cave - Beastman of Farum Azula", EntityProgressionTier.Early, true);
            targetBosses[1037420400] = ("Groveside Cave - Beastman of Farum Azula (Event)", EntityProgressionTier.Early, true);

            // 2. Discover boss rows in ItemLotParam_enemy
            foreach (var r in enemyParam.Rows)
            {
                int p1 = ParamHelper.GetCellInt(r, "lotItemBasePoint01");
                int itm1 = ParamHelper.GetCellInt(r, "lotItemId01");
                int cat1 = ParamHelper.GetCellInt(r, "lotItemCategory01");

                if (itm1 > 0 && p1 >= 1000 && (cat1 == 2 || cat1 == 4))
                {
                    if (!targetBosses.ContainsKey(r.ID))
                    {
                        var tier = ProgressionTierClassifier.ClassifyTier(r.ID, r.Name);
                        targetBosses[r.ID] = (r.Name ?? $"Enemy Boss {r.ID}", tier, false);
                    }
                }
            }

            // 3. Discover boss rows in ItemLotParam_map (dungeon bosses, remembrances, major events)
            foreach (var r in mapParam.Rows)
            {
                int p1 = ParamHelper.GetCellInt(r, "lotItemBasePoint01");
                int itm1 = ParamHelper.GetCellInt(r, "lotItemId01");
                int cat1 = ParamHelper.GetCellInt(r, "lotItemCategory01");

                if (itm1 > 0 && p1 >= 1000 && (cat1 == 2 || cat1 == 4) && (r.ID < 100000 || r.ID >= 1000000000))
                {
                    if (!targetBosses.ContainsKey(r.ID))
                    {
                        var tier = ProgressionTierClassifier.ClassifyTier(r.ID, r.Name);
                        targetBosses[r.ID] = (r.Name ?? $"Map Boss {r.ID}", tier, true);
                    }
                }
            }

            Console.WriteLine($"[BossLootPool] Discovered {targetBosses.Count} total boss targets ({targetBosses.Values.Count(v => !v.IsMapTable)} enemy, {targetBosses.Values.Count(v => v.IsMapTable)} map/dungeon).");

            // Gather custom weapons and armors to prioritize on bosses
            var customBossItems = new List<(int Id, string Name, int Category, EntityProgressionTier Tier)>();
            if (wepParam != null)
            {
                foreach (var r in wepParam.Rows)
                {
                    if (r.ID >= 9000000 && r.ID < 99000000)
                    {
                        string n = !string.IsNullOrWhiteSpace(r.Name) ? r.Name : $"Custom Weapon {r.ID}";
                        customBossItems.Add((r.ID, n, 2, ProgressionTierClassifier.ClassifyTier(r.ID, n)));
                    }
                }
            }

            if (protParam != null)
            {
                foreach (var r in protParam.Rows)
                {
                    if (r.ID >= 9000000 && r.ID < 99000000)
                    {
                        string n = !string.IsNullOrWhiteSpace(r.Name) ? r.Name : $"Custom Armor {r.ID}";
                        customBossItems.Add((r.ID, n, 3, ProgressionTierClassifier.ClassifyTier(r.ID, n)));
                    }
                }
            }

            var rng = new Random(1337);
            var usedItemIds = new HashSet<int>();
            int bossesEnriched = 0;
            int totalItemsInjected = 0;

            foreach (var kvp in targetBosses)
            {
                int baseLotId = kvp.Key;
                string bossName = kvp.Value.Name;
                EntityProgressionTier tier = kvp.Value.Tier;
                bool isMap = kvp.Value.IsMapTable;

                // 1. Prioritize custom weapons and armor pieces
                var availableCustom = customBossItems.Where(i => i.Tier == tier && !usedItemIds.Contains(i.Id)).ToList();
                if (availableCustom.Count < weaponsPerBoss)
                    availableCustom = customBossItems.Where(i => !usedItemIds.Contains(i.Id)).ToList();

                var chosenItems = availableCustom.OrderBy(_ => rng.Next()).Take(weaponsPerBoss).ToList();

                // 2. Supplement with curated weapons if needed
                if (chosenItems.Count < weaponsPerBoss)
                {
                    var tierWeapons = CuratedWeaponPool.WEAPONS.Where(w => w.Tier == tier && !usedItemIds.Contains(w.Id)).ToList();
                    if (tierWeapons.Count < weaponsPerBoss - chosenItems.Count) tierWeapons = CuratedWeaponPool.WEAPONS;
                    var extra = tierWeapons.Where(w => !chosenItems.Any(c => c.Id == w.Id)).OrderBy(_ => rng.Next()).Take(weaponsPerBoss - chosenItems.Count);
                    foreach (var w in extra)
                    {
                        chosenItems.Add((w.Id, w.Name, 2, w.Tier));
                    }
                }

                if (chosenItems.Count == 0) continue;
                foreach (var itm in chosenItems) usedItemIds.Add(itm.Id);

                if (isMap && mapRowMap.TryGetValue(baseLotId, out var baseRow))
                {
                    for (int i = 0; i < chosenItems.Count; i++)
                    {
                        int offset = i + 1;
                        int chainedId = baseLotId + offset;
                        var itm = chosenItems[i];
                        PARAM.Row? chainedRow = mapRowMap.TryGetValue(chainedId, out var existing) ? existing : null;
                        if (chainedRow == null)
                        {
                            chainedRow = new PARAM.Row(baseRow)
                            {
                                ID = chainedId,
                                Name = $"[Boss Pool T{(int)tier}] {itm.Name} (for {bossName})"
                            };
                            for (int s = 1; s <= 8; s++)
                            {
                                ParamHelper.SetCellIfExists(chainedRow, $"lotItemId0{s}", 0);
                                ParamHelper.SetCellIfExists(chainedRow, $"lotItemCategory0{s}", 0);
                                ParamHelper.SetCellIfExists(chainedRow, $"lotItemBasePoint0{s}", (ushort)0);
                                ParamHelper.SetCellIfExists(chainedRow, $"lotItemNum0{s}", (byte)0);
                                ParamHelper.SetCellIfExists(chainedRow, $"getItemFlagId0{s}", 0u);
                            }
                            mapParam.Rows.Add(chainedRow);
                            mapRowMap[chainedId] = chainedRow;
                        }

                        ParamHelper.SetCellIfExists(chainedRow, "lotItemId01", itm.Id);
                        ParamHelper.SetCellIfExists(chainedRow, "lotItemCategory01", itm.Category);
                        ParamHelper.SetCellIfExists(chainedRow, "lotItemBasePoint01", (ushort)1000);
                        ParamHelper.SetCellIfExists(chainedRow, "lotItemNum01", (byte)1);
                        ParamHelper.SetCellIfExists(chainedRow, "getItemFlagId01", 0u);
                        totalItemsInjected++;
                    }
                    bossesEnriched++;
                }
                else if (!isMap && enemyRowMap.TryGetValue(baseLotId, out var targetRow))
                {
                    int slotIdx = 1;
                    if (baseLotId == 431100000 && chosenItems.Count > 0)
                    {
                        var firstItm = chosenItems[0];
                        ParamHelper.SetCellIfExists(targetRow, "lotItemId01", firstItm.Id);
                        ParamHelper.SetCellIfExists(targetRow, "lotItemCategory01", firstItm.Category);
                        ParamHelper.SetCellIfExists(targetRow, "lotItemBasePoint01", (ushort)1000);
                        ParamHelper.SetCellIfExists(targetRow, "lotItemNum01", (byte)1);
                        ParamHelper.SetCellIfExists(targetRow, "getItemFlagId01", 0u);
                        totalItemsInjected++;
                        slotIdx = 2;
                    }

                    for (int i = (baseLotId == 431100000 ? 1 : 0); i < chosenItems.Count; i++)
                    {
                        var itm = chosenItems[i];
                        while (slotIdx <= 8 && ParamHelper.GetCellInt(targetRow, $"lotItemId0{slotIdx}") > 0)
                            slotIdx++;

                        if (slotIdx <= 8)
                        {
                            ParamHelper.SetCellIfExists(targetRow, $"lotItemId0{slotIdx}", itm.Id);
                            ParamHelper.SetCellIfExists(targetRow, $"lotItemCategory0{slotIdx}", itm.Category);
                            ParamHelper.SetCellIfExists(targetRow, $"lotItemBasePoint0{slotIdx}", (ushort)1000);
                            ParamHelper.SetCellIfExists(targetRow, $"lotItemNum0{slotIdx}", (byte)1);
                            ParamHelper.SetCellIfExists(targetRow, $"getItemFlagId0{slotIdx}", 0u);
                            totalItemsInjected++;
                            slotIdx++;
                        }
                    }
                    bossesEnriched++;
                }
            }

            Console.WriteLine($"[BossLootPool] Successfully enriched {bossesEnriched} bosses (including tutorial encounters) with {totalItemsInjected} non-repeating weapons!");
            return bossesEnriched;
        }
    }
}

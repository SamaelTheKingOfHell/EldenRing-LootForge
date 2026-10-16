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
                string xmlFile = Path.Combine(defsDir, (tableName.StartsWith("ItemLot") ? "ItemLotParam" : tableName) + ".xml");
                if (File.Exists(xmlFile))
                {
                    var def = PARAMDEF.XmlDeserialize(xmlFile, false, false);
                    param.ApplyParamdefSomewhatCarefully(def);
                }
                return param;
            }

            var enemyParam = LoadParam("ItemLotParam_enemy");
            var mapParam = LoadParam("ItemLotParam_map");
            var wepParam = LoadParam("EquipParamWeapon");
            var protParam = LoadParam("EquipParamProtector");
            var world = WorldLootCatalog.Load(inputPath, options.GetValueOrDefault("game-dir"), defsDir, mapParam,
                enemyParam, LoadParam("NpcParam"));
            EnrichBossLootPools(enemyParam, mapParam, wepParam, protParam, weaponsPerBoss, verified: world);

            // Write back both tables
            var enemyFile = bnd.Files.First(f => f.Name.EndsWith("ItemLotParam_enemy.param", StringComparison.OrdinalIgnoreCase));
            enemyFile.Bytes = ParamSerialization.Write(enemyParam);

            var mapFile = bnd.Files.First(f => f.Name.EndsWith("ItemLotParam_map.param", StringComparison.OrdinalIgnoreCase));
            mapFile.Bytes = ParamSerialization.Write(mapParam);

            string? outDir = Path.GetDirectoryName(outputPath);
            if (!string.IsNullOrEmpty(outDir) && !Directory.Exists(outDir))
                Directory.CreateDirectory(outDir);

            Console.WriteLine($"[BossLootPool] Encrypting and saving updated regulation to: {outputPath}...");
            RegulationDecryptor.EncryptERRegulation(outputPath, bnd);
            Console.WriteLine($"[BossLootPool SUCCESS] Saved {new FileInfo(outputPath).Length} bytes. Verified boss rewards processed.");

            return 0;
        }

        public static int EnrichBossLootPools(
            PARAM enemyParam,
            PARAM mapParam,
            PARAM? wepParam,
            PARAM? protParam,
            int weaponsPerBoss = 3,
            HashSet<int>? customWeaponIds = null,
            HashSet<int>? customArmorIds = null, WorldLootCatalog? verified = null)
        {
            var targetBosses = new Dictionary<int, (string Name, EntityProgressionTier Tier, bool IsMapTable)>();
            foreach (var item in verified?.Bosses ?? new()) targetBosses[item.LotId] = (item.Name,item.Tier,true);
            Console.WriteLine($"[BossLootPool] Discovered {targetBosses.Count} total boss targets ({targetBosses.Values.Count(v => !v.IsMapTable)} enemy, {targetBosses.Values.Count(v => v.IsMapTable)} map/dungeon).");

            // Gather custom weapons and armors to prioritize on bosses
            var customBossItems = new List<(int Id, string Name, int Category, EntityProgressionTier Tier)>();
            if (wepParam != null)
            {
                foreach (var r in wepParam.Rows)
                {
                    bool isCustom = customWeaponIds != null
                        ? customWeaponIds.Contains(r.ID)
                        : (r.Name != null && r.Name.Contains("[LootForge]"));
                    if (isCustom)
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
                    bool isCustom = customArmorIds != null
                        ? customArmorIds.Contains(r.ID)
                        : (r.Name != null && r.Name.Contains("[LootForge]"));
                    if (isCustom)
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
                var destination = isMap ? mapParam : enemyParam;
                int available = isMap ? AdditiveLootService.RemainingRewardSlots(destination, baseLotId) : 4;
                var chosenItems = availableCustom.OrderBy(_ => rng.Next()).Take(Math.Min(available, weaponsPerBoss)).ToList();

                if (chosenItems.Count == 0) continue;
                foreach (var itm in chosenItems) usedItemIds.Add(itm.Id);

                foreach (var itm in chosenItems)
                {
                    if (AdditiveLootService.TryAppend(destination, baseLotId, itm.Id, itm.Category, 1000,
                            $"Boss Pool T{(int)tier}: {itm.Name} (for {bossName})", isMap))
                        totalItemsInjected++;
                }
                bossesEnriched++;
            }

            Console.WriteLine($"[BossLootPool] Successfully enriched {bossesEnriched} bosses with {totalItemsInjected} non-repeating custom items!");
            return bossesEnriched;
        }
    }
}

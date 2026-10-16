using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using SoulsFormats;
using SoulsFormats.Cryptography;

namespace LootForge.RegTool
{
    /// <summary>
    /// Service that dynamically discovers all chests/containers across the Lands Between (and modded maps),
    /// injects 1-4 random custom items via contiguous chained rows (lotId + 1..N),
    /// prioritizes custom armor and weapons within verified one-time chest rewards.
    /// Adheres to [CS-MODULAR] and [CS-GRANULARITY] (<= 300 lines).
    /// </summary>
    public static class ChestLootPoolService
    {
        public static int ExecuteInjectChestLootPools(Dictionary<string, string> options)
        {
            if (!options.TryGetValue("input", out string? inputPath) || string.IsNullOrEmpty(inputPath))
            {
                Console.Error.WriteLine("[ChestLootPool] Missing required --input path to regulation.bin.");
                return 1;
            }
            string outputPath = options.TryGetValue("output", out string? op) && !string.IsNullOrEmpty(op) ? op : inputPath;
            string defsDir = options.TryGetValue("defs", out string? dd) && !string.IsNullOrEmpty(dd) ? dd : @"tools\vendor\Paramdex\ER\Defs";
            int minItems = options.TryGetValue("min-items", out string? minS) && int.TryParse(minS, out int pMin) ? Math.Clamp(pMin, 1, 4) : 1;
            int maxItems = options.TryGetValue("max-items", out string? maxS) && int.TryParse(maxS, out int pMax) ? Math.Clamp(pMax, minItems, 4) : 4;

            Console.WriteLine($"[ChestLootPool] Decrypting regulation: {inputPath}...");
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

            var mapParam = LoadParam("ItemLotParam_map");
            var enemyParam = LoadParam("ItemLotParam_enemy");
            var protParam = LoadParam("EquipParamProtector");
            var wepParam = LoadParam("EquipParamWeapon");

            var world = WorldLootCatalog.Load(inputPath, options.GetValueOrDefault("game-dir"), defsDir, mapParam,
                enemyParam, LoadParam("NpcParam"));
            EnrichChestLootPools(mapParam, enemyParam, protParam, wepParam, minItems, maxItems, verified: world);

            // Write back tables and encrypt
            var mapFile = bnd.Files.First(f => f.Name.EndsWith("ItemLotParam_map.param", StringComparison.OrdinalIgnoreCase));
            mapFile.Bytes = ParamSerialization.Write(mapParam);

            var enemyFile = bnd.Files.First(f => f.Name.EndsWith("ItemLotParam_enemy.param", StringComparison.OrdinalIgnoreCase));
            enemyFile.Bytes = ParamSerialization.Write(enemyParam);

            string? outDir = Path.GetDirectoryName(outputPath);
            if (!string.IsNullOrEmpty(outDir) && !Directory.Exists(outDir))
                Directory.CreateDirectory(outDir);

            Console.WriteLine($"[ChestLootPool] Encrypting and saving updated regulation to: {outputPath}...");
            RegulationDecryptor.EncryptERRegulation(outputPath, bnd);
            Console.WriteLine($"[ChestLootPool SUCCESS] Saved {new FileInfo(outputPath).Length} bytes. All chests processed through verified one-time rewards.");

            return 0;
        }

        public static int EnrichChestLootPools(
            PARAM mapParam,
            PARAM enemyParam,
            PARAM protParam,
            PARAM wepParam,
            int minItems = 1,
            int maxItems = 4,
            HashSet<int>? customArmorIds = null,
            HashSet<int>? customWeaponIds = null, WorldLootCatalog? verified = null)
        {

            var mapRowMap = new Dictionary<int, PARAM.Row>(mapParam.Rows.Count);
            foreach (var r in mapParam.Rows) mapRowMap[r.ID] = r;

            // 1. Gather all custom items, prioritizing custom armor, then custom weapons
            var customArmorItems = new List<(int Id, string Name, int Category, EntityProgressionTier Tier)>();
            foreach (var r in protParam.Rows)
            {
                bool isCustom = customArmorIds != null
                    ? customArmorIds.Contains(r.ID)
                    : (r.Name != null && r.Name.Contains("[LootForge]"));
                if (isCustom)
                {
                    string itmName = !string.IsNullOrWhiteSpace(r.Name) ? r.Name : $"Custom Armor {r.ID}";
                    customArmorItems.Add((r.ID, itmName, 3, ProgressionTierClassifier.ClassifyTier(r.ID, itmName)));
                }
            }

            var customWeaponItems = new List<(int Id, string Name, int Category, EntityProgressionTier Tier)>();
            foreach (var r in wepParam.Rows)
            {
                bool isCustom = customWeaponIds != null
                    ? customWeaponIds.Contains(r.ID)
                    : (r.Name != null && r.Name.Contains("[LootForge]"));
                if (isCustom)
                {
                    string itmName = !string.IsNullOrWhiteSpace(r.Name) ? r.Name : $"Custom Weapon {r.ID}";
                    customWeaponItems.Add((r.ID, itmName, 2, ProgressionTierClassifier.ClassifyTier(r.ID, itmName)));
                }
            }

            Console.WriteLine($"[ChestLootPool] Discovered {customArmorItems.Count} custom armors and {customWeaponItems.Count} custom weapons for distribution.");

            var targetChests = (verified?.Chests ?? new()).Select(item =>
                (LotId: item.LotId, Name: item.Name, Tier: item.Tier)).ToList();
            Console.WriteLine($"[ChestLootPool] Dynamically discovered {targetChests.Count} valid chest/treasure locations across the world and modded maps.");

            var rng = new Random(42);
            var placedItemIds = new HashSet<int>();
            int chestsEnriched = 0;
            int totalItemsInChests = 0;

            // Prioritize custom armors first, then custom weapons
            var combinedCustomPool = new List<(int Id, string Name, int Category, EntityProgressionTier Tier)>(customArmorItems.Count + customWeaponItems.Count);
            combinedCustomPool.AddRange(customArmorItems);
            combinedCustomPool.AddRange(customWeaponItems);

            foreach (var chest in targetChests)
            {
                int baseLotId = chest.LotId;
                string chestName = chest.Name;
                EntityProgressionTier tier = chest.Tier;
                var baseRow = mapRowMap[baseLotId];

                int countToInject = rng.Next(minItems, maxItems + 1);
                var chosenForChest = new List<(int Id, string Name, int Category, EntityProgressionTier Tier)>();

                chosenForChest.AddRange(combinedCustomPool.Where(item => item.Tier == tier && !placedItemIds.Contains(item.Id)).Take(countToInject));

                if (chosenForChest.Count == 0) continue;

                // Inject via contiguous sequential chained rows (baseLotId + offset)
                for (int i = 0; i < chosenForChest.Count; i++)
                {
                    var itm = chosenForChest[i];
                    if (AdditiveLootService.TryAppend(mapParam, baseLotId, itm.Id, itm.Category, 1000,
                            $"Chest Drop T{(int)tier}: {itm.Name} (in {chestName})", true))
                    {
                        placedItemIds.Add(itm.Id);
                        totalItemsInChests++;
                    }
                }

                chestsEnriched++;
            }

            Console.WriteLine($"[ChestLootPool] Enriched {chestsEnriched} chests with {totalItemsInChests} items (1-4 per chest) via contiguous chained rows!");

            return chestsEnriched;
        }
    }
}

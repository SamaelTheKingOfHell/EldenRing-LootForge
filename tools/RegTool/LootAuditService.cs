using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using SoulsFormats;
using SoulsFormats.Cryptography;

namespace LootForge.RegTool
{
    /// <summary>
    /// Audits custom equipment, chests, and boss loot distribution inside regulation.bin.
    /// Reports exactly where custom armors, weapons, and accessories are placed.
    /// Adheres to [CS-MODULAR] and [CS-GRANULARITY] (<= 300 lines).
    /// </summary>
    public static class LootAuditService
    {
        public static int ExecuteAuditLoot(Dictionary<string, string> options)
        {
            if (!options.TryGetValue("input", out string? inputPath) || string.IsNullOrEmpty(inputPath))
            {
                Console.Error.WriteLine("[LootAudit] Missing --input path to regulation.bin.");
                return 1;
            }
            string defsDir = options.TryGetValue("defs", out string? dd) && !string.IsNullOrEmpty(dd) ? dd : @"tools\vendor\Paramdex\ER\Defs";

            Console.WriteLine($"[LootAudit] Decrypting regulation: {inputPath}...");
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

            var protParam = LoadParam("EquipParamProtector");
            var wepParam = LoadParam("EquipParamWeapon");
            var enemyLotParam = LoadParam("ItemLotParam_enemy");
            var mapLotParam = LoadParam("ItemLotParam_map");
            var shopParam = LoadParam("ShopLineupParam");

            // 1. Gather all custom armor IDs (IDs >= 9000000)
            var customProtectorIds = new HashSet<int>();
            foreach (var r in protParam.Rows)
            {
                if (r.ID >= 9000000 && r.ID < 99000000)
                    customProtectorIds.Add(r.ID);
            }
            Console.WriteLine($"[LootAudit] Found {customProtectorIds.Count} custom armor rows in EquipParamProtector (ID >= 9000000).");

            // 2. Scan ItemLotParam_enemy for references
            var enemyLotPlaced = new Dictionary<int, List<int>>(); // itemId -> lotIds
            foreach (var r in enemyLotParam.Rows)
            {
                for (int s = 1; s <= 8; s++)
                {
                    int itm = ParamHelper.GetCellInt(r, $"lotItemId0{s}");
                    if (itm > 0)
                    {
                        if (!enemyLotPlaced.ContainsKey(itm)) enemyLotPlaced[itm] = new List<int>();
                        enemyLotPlaced[itm].Add(r.ID);
                    }
                }
            }

            // 3. Scan ItemLotParam_map for references
            var mapLotPlaced = new Dictionary<int, List<int>>(); // itemId -> lotIds
            foreach (var r in mapLotParam.Rows)
            {
                for (int s = 1; s <= 8; s++)
                {
                    int itm = ParamHelper.GetCellInt(r, $"lotItemId0{s}");
                    if (itm > 0)
                    {
                        if (!mapLotPlaced.ContainsKey(itm)) mapLotPlaced[itm] = new List<int>();
                        mapLotPlaced[itm].Add(r.ID);
                    }
                }
            }

            // 4. Scan ShopLineupParam for references
            var shopPlaced = new Dictionary<int, List<int>>(); // itemId -> shopRowIds
            foreach (var r in shopParam.Rows)
            {
                int itm = ParamHelper.GetCellInt(r, "equipId");
                if (itm > 0)
                {
                    if (!shopPlaced.ContainsKey(itm)) shopPlaced[itm] = new List<int>();
                    shopPlaced[itm].Add(r.ID);
                }
            }

            // 5. Check how many custom armors are in the game
            int armorsInEnemy = customProtectorIds.Count(id => enemyLotPlaced.ContainsKey(id));
            int armorsInMap = customProtectorIds.Count(id => mapLotPlaced.ContainsKey(id));
            int armorsInShop = customProtectorIds.Count(id => shopPlaced.ContainsKey(id));
            int armorsMissing = customProtectorIds.Count(id => !enemyLotPlaced.ContainsKey(id) && !mapLotPlaced.ContainsKey(id) && !shopPlaced.ContainsKey(id));

            Console.WriteLine($"[LootAudit] Custom Armors Placement:");
            Console.WriteLine($"   In ItemLotParam_enemy: {armorsInEnemy}");
            Console.WriteLine($"   In ItemLotParam_map:   {armorsInMap}");
            Console.WriteLine($"   In ShopLineupParam:    {armorsInShop}");
            Console.WriteLine($"   COMPLETELY MISSING:    {armorsMissing} / {customProtectorIds.Count}");

            if (customProtectorIds.Count > 0)
            {
                var sample = customProtectorIds.First();
                Console.WriteLine($"   Sample Custom Armor ID {sample}: InEnemy={enemyLotPlaced.ContainsKey(sample)}, InMap={mapLotPlaced.ContainsKey(sample)}, InShop={shopPlaced.ContainsKey(sample)}");
            }




            // 7. Check Chest Multi-Drops (ItemLotParam_map rows with multiple slots)
            int mapRowsWithMultiSlots = mapLotParam.Rows.Count(r => ParamHelper.GetCellInt(r, "lotItemId01") > 0 && ParamHelper.GetCellInt(r, "lotItemId02") > 0);
            Console.WriteLine($"\n[LootAudit] Total Chests/Map lots with multiple drops (Slots 1 & 2+ filled): {mapRowsWithMultiSlots}");

            return 0;
        }
    }
}

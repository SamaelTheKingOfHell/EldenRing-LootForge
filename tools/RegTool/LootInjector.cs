using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using SoulsFormats;

namespace LootForge.RegTool
{
    /// <summary>
    /// Service responsible for injecting custom mod equipment drops into Elden Ring
    /// ItemLotParam_enemy and ItemLotParam_map tables (chests, world pickups, boss lots).
    /// Preserves every existing loot row and adds independent chained rolls.
    /// Delegates shop lineup and overflow handling to ShopLootInjector.
    /// Adheres to [CS-MODULAR] and [CS-GRANULARITY] (<= 300 lines).
    /// </summary>
    public static class LootInjector
    {
        private static Dictionary<int, PARAM.Row>? _enemyLotRowMap;
        private static Dictionary<int, PARAM.Row>? _mapLotRowMap;

        public static void ResetCache()
        {
            _enemyLotRowMap = null;
            _mapLotRowMap = null;
            ShopLootInjector.ResetCache();
        }

        public static void InjectLootDistribution(
            JsonElement lootEl,
            Func<string, string, (PARAM Param, BinderFile File)> getOrLoadParam,
            Dictionary<int, bool> itemIdToIsProtector,
            Dictionary<int, bool> itemIdToIsWeapon,
            Dictionary<int, bool> itemIdToIsAccessory,
            ref int injectedLootCount)
        {
            string lootType = lootEl.TryGetProperty("type", out var lt) ? lt.GetString() ?? "" : "";
            var awardedItems = new List<int>();
            if (lootEl.TryGetProperty("awarded_items", out var itemsEl) && itemsEl.ValueKind == JsonValueKind.Array)
            {
                foreach (var itm in itemsEl.EnumerateArray())
                    awardedItems.Add(itm.GetInt32());
            }

            if (lootType == "enemy_drop" && awardedItems.Count > 0)
            {
                InjectItemLotDrop("ItemLotParam_enemy", ref _enemyLotRowMap, lootEl, getOrLoadParam, itemIdToIsProtector, itemIdToIsWeapon, itemIdToIsAccessory, awardedItems, ref injectedLootCount);
            }
            else if ((lootType == "map_pickup" || lootType == "world_chest" || lootType == "map_drop") && awardedItems.Count > 0)
            {
                InjectItemLotDrop("ItemLotParam_map", ref _mapLotRowMap, lootEl, getOrLoadParam, itemIdToIsProtector, itemIdToIsWeapon, itemIdToIsAccessory, awardedItems, ref injectedLootCount);
            }
            else if ((lootType == "shop_lineup" || lootType == "merchant_shop") && awardedItems.Count > 0)
            {
                ShopLootInjector.InjectShopLineup(lootEl, getOrLoadParam, itemIdToIsProtector, itemIdToIsWeapon, itemIdToIsAccessory, awardedItems, ref injectedLootCount);
            }
        }

        private static void InjectItemLotDrop(
            string tableName,
            ref Dictionary<int, PARAM.Row>? rowMap,
            JsonElement lootEl,
            Func<string, string, (PARAM Param, BinderFile File)> getOrLoadParam,
            Dictionary<int, bool> itemIdToIsProtector,
            Dictionary<int, bool> itemIdToIsWeapon,
            Dictionary<int, bool> itemIdToIsAccessory,
            List<int> awardedItems,
            ref int injectedLootCount)
        {
            string rawTid = lootEl.TryGetProperty("target_id", out var tid) ? tid.GetString() ?? "" : "";
            int targetLotId = 0;
            if (int.TryParse(rawTid, out int parsedTid) && parsedTid > 10000 && !(parsedTid >= 9100000 && parsedTid < 9200000))
                targetLotId = parsedTid;
            else if (lootEl.TryGetProperty("lot_id", out var lid) && lid.GetInt32() > 10000 && !(lid.GetInt32() >= 9100000 && lid.GetInt32() < 9200000))
                targetLotId = lid.GetInt32();
            else
                targetLotId = ResolveEnemyLotId(rawTid);

            double dropRatePercent = lootEl.TryGetProperty("drop_rate_percent", out var dr) ? dr.GetDouble() : (tableName == "ItemLotParam_map" ? 100.0 : 20.0);
            var (itemLotParam, _) = getOrLoadParam(tableName, "ItemLotParam");

            if (rowMap == null)
            {
                rowMap = new Dictionary<int, PARAM.Row>(itemLotParam.Rows.Count);
                foreach (var r in itemLotParam.Rows)
                {
                    rowMap[r.ID] = r;
                }
            }

            bool isMapTable = tableName.Equals("ItemLotParam_map", StringComparison.OrdinalIgnoreCase);
            ushort points = (ushort)Math.Clamp((int)Math.Round(dropRatePercent * 10), 0, 1000);
            foreach (int itemId in awardedItems)
            {
                bool accessory = itemIdToIsAccessory.GetValueOrDefault(itemId);
                bool armor = itemIdToIsProtector.GetValueOrDefault(itemId);
                int category = accessory ? 4 : (armor ? 3 : 2);
                bool placed = AdditiveLootService.TryAppend(itemLotParam, targetLotId, itemId, category,
                    points, $"Additional drop for {targetLotId}");
                if (!placed)
                {
                    string other = isMapTable ? "ItemLotParam_enemy" : "ItemLotParam_map";
                    var otherParam = getOrLoadParam(other, "ItemLotParam").Param;
                    placed = AdditiveLootService.TryAppend(otherParam, targetLotId, itemId, category, points, "Additional cross-table drop")
                        || AdditiveLootService.TryAppendAny(itemLotParam, itemId, category, points, "Additional overflow drop")
                        || AdditiveLootService.TryAppendAny(otherParam, itemId, category, points, "Additional overflow drop");
                }
                if (!placed)
                    throw new InvalidOperationException($"No independent loot row remains for item {itemId}. Existing rewards were preserved. Reduce variants per item.");
                injectedLootCount++;
            }
        }

        private static int ResolveEnemyLotId(string? name)
        {
            string lower = name?.ToLowerInvariant() ?? "";
            if (lower.Contains("scion") || lower.Contains("anticipation")) return 10030;
            if (lower.Contains("soldier of godrick") || lower.Contains("tutorial")) return 18000050;
            if (lower.Contains("moongrum")) return 340000000;
            if (lower.Contains("crucible")) return 250000000;
            if (lower.Contains("black knife") || lower.Contains("assassin")) return 210000000;
            if (lower.Contains("cleanrot")) return 380000000;
            if (lower.Contains("banished")) return 301000000;
            if (lower.Contains("bloodhound") || lower.Contains("darriwil")) return 20600;
            if (lower.Contains("sentinel")) return 420000000;
            if (lower.Contains("cavalry")) return 450000000;
            if (lower.Contains("vyke")) return 440000000;
            if (lower.Contains("makar") || lower.Contains("wyrm")) return 350000000;
            if (lower.Contains("okina") || lower.Contains("bloody finger")) return 460000000;
            if (lower.Contains("omen")) return 214000000;
            if (lower.Contains("crab")) return 227000000;
            if (lower.Contains("exile") || lower.Contains("vargram")) return 300000000;
            if (lower.Contains("godrick knight")) return 435100000;
            if (lower.Contains("noble")) return 430000000;
            if (lower.Contains("soldier")) return 431100000;
            return 102100;
        }
    }
}

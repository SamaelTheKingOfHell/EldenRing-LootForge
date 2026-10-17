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
        private static HashSet<int>? allowedMap, allowedEnemy;
        private static Dictionary<string, int>? _nameToLotId;
        public static void Configure(WorldLootCatalog catalog)
        {
            allowedMap = catalog.Chests.Concat(catalog.Bosses).Select(item=>item.LotId).ToHashSet();
            allowedEnemy = catalog.Enemies.Select(item=>item.LotId).ToHashSet();
            _nameToLotId = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
            foreach (var d in catalog.Bosses.Concat(catalog.Chests).Concat(catalog.Enemies))
                _nameToLotId.TryAdd(d.Name, d.LotId);
            ShopLootInjector.Configure(catalog.Merchants);
        }
        private static Dictionary<int, PARAM.Row>? _enemyLotRowMap;
        private static Dictionary<int, PARAM.Row>? _mapLotRowMap;

        public static void ResetCache()
        {
            allowedMap = allowedEnemy = null;
            _nameToLotId = null;
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
            if (int.TryParse(rawTid, out int parsedTid) && parsedTid > 0 && !(parsedTid >= 9100000 && parsedTid < 9200000))
                targetLotId = parsedTid;
            else if (lootEl.TryGetProperty("lot_id", out var lid) && lid.GetInt32() > 0 && !(lid.GetInt32() >= 9100000 && lid.GetInt32() < 9200000))
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
            var allowed = isMapTable ? allowedMap : allowedEnemy;
            if (allowed != null && !allowed.Contains(targetLotId))
                throw new InvalidDataException($"Unverified loot destination {tableName}:{targetLotId}. No unrelated pickup was modified.");
            ushort points = (ushort)Math.Clamp((int)Math.Round(dropRatePercent * 10), 0, 1000);
            if (isMapTable && awardedItems.Count > AdditiveLootService.RemainingRewardSlots(itemLotParam, targetLotId))
                throw new InvalidOperationException($"Boss/chest {targetLotId} exceeds four total rewards, including original items. Reduce this reward group or reforge with current destination capacity.");
            foreach (int itemId in awardedItems)
            {
                bool accessory = itemIdToIsAccessory.GetValueOrDefault(itemId);
                bool armor = itemIdToIsProtector.GetValueOrDefault(itemId);
                int category = accessory ? 4 : (armor ? 3 : 2);
                bool placed = AdditiveLootService.TryAppend(itemLotParam, targetLotId, itemId, category,
                    points, $"Additional drop for {targetLotId}", isMapTable);
                if (!placed)
                    throw new InvalidOperationException($"No independent loot row remains for item {itemId}. Existing rewards were preserved. Reduce variants per item.");
                injectedLootCount++;
            }
        }

        private static int ResolveEnemyLotId(string? name)
        {
            if (string.IsNullOrWhiteSpace(name))
                throw new InvalidDataException("Missing loot destination identifier.");
            if (_nameToLotId != null)
            {
                if (_nameToLotId.TryGetValue(name, out int exact)) return exact;
                var partial = _nameToLotId.FirstOrDefault(kv => kv.Key.Contains(name, StringComparison.OrdinalIgnoreCase) || name.Contains(kv.Key, StringComparison.OrdinalIgnoreCase));
                if (partial.Value > 0) return partial.Value;
            }
            throw new InvalidDataException($"Unrecognized loot destination '{name}'. No destination was hardcoded.");
        }
    }
}

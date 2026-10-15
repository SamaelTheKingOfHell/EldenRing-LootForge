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
    /// Preserves original vanilla loot (slot 1) while injecting 1-4 mod items into available slots.
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

            double dropRatePercent = lootEl.TryGetProperty("drop_rate_percent", out var dr) ? dr.GetDouble() : 20.0;
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
            var candidateRows = new List<PARAM.Row>(2);
            if (rowMap.TryGetValue(targetLotId, out var pRow)) candidateRows.Add(pRow);
            if (rowMap.TryGetValue(targetLotId + 10, out var cRow)) candidateRows.Add(cRow);

            if (candidateRows.Count == 0)
            {
                // Cross-table fallback: check if targetLotId exists in the other table
                string otherTable = isMapTable ? "ItemLotParam_enemy" : "ItemLotParam_map";
                var (otherParam, _) = getOrLoadParam(otherTable, "ItemLotParam");
                var otherRow = otherParam.Rows.FirstOrDefault(r => r.ID == targetLotId);
                if (otherRow != null)
                {
                    ref var otherRowMap = ref (isMapTable ? ref _enemyLotRowMap : ref _mapLotRowMap);
                    InjectItemLotDrop(otherTable, ref otherRowMap, lootEl, getOrLoadParam, itemIdToIsProtector, itemIdToIsWeapon, itemIdToIsAccessory, awardedItems, ref injectedLootCount);
                    return;
                }

                // Fallback to any map chest with available slots
                var (mapParam, _) = getOrLoadParam("ItemLotParam_map", "ItemLotParam");
                var fallbackChest = mapParam.Rows.FirstOrDefault(r => ParamHelper.GetCellInt(r, "lotItemId01") > 0 && ParamHelper.GetCellInt(r, "lotItemId02") == 0);
                if (fallbackChest != null)
                {
                    candidateRows.Add(fallbackChest);
                    itemLotParam = mapParam;
                    isMapTable = true;
                }
                else
                {
                    ShopLootInjector.InjectShopLineup(lootEl, getOrLoadParam, itemIdToIsProtector, itemIdToIsWeapon, itemIdToIsAccessory, awardedItems, ref injectedLootCount);
                    return;
                }
            }

            var targetRow = candidateRows[0];
            var layout = ItemLotLayout.Extract(itemLotParam);
            ushort pts = (ushort)(isMapTable || dropRatePercent >= 100.0 ? 1000 : Math.Clamp((int)(dropRatePercent * 10), 1, 1000));
            var overflowItems = new List<int>();

            foreach (int itemId in awardedItems)
            {
                bool isAccessory = itemIdToIsAccessory.TryGetValue(itemId, out var ia) && ia;
                bool isArmor = itemIdToIsProtector.TryGetValue(itemId, out var ip) ? ip : (!isAccessory && !itemIdToIsWeapon.GetValueOrDefault(itemId, false));
                int lotCategory = isAccessory ? 4 : (isArmor ? 3 : 2);

                int slotToUse = -1;
                // Never touch slot 1 (preserves original vanilla/mod loot). Scan slots 2 to 8 (indices 1..7)
                for (int s = 1; s < 8; s++)
                {
                    int cur = ParamHelper.GetCellIntFast(targetRow, layout.ItemIdIndices[s]);
                    if (cur == itemId) { slotToUse = s; break; }
                    if (cur == 0 && slotToUse == -1) slotToUse = s;
                }

                if (slotToUse != -1)
                {
                    ParamHelper.SetCellFast(targetRow, layout.ItemIdIndices[slotToUse], itemId);
                    ParamHelper.SetCellFast(targetRow, layout.CategoryIndices[slotToUse], lotCategory);
                    ParamHelper.SetCellFast(targetRow, layout.BasePointIndices[slotToUse], pts);
                    ParamHelper.SetCellFast(targetRow, layout.NumIndices[slotToUse], (byte)1);
                    ParamHelper.SetCellFast(targetRow, layout.FlagIdIndices[slotToUse], 0u);
                }
                else
                {
                    overflowItems.Add(itemId);
                }
            }

            if (overflowItems.Count > 0)
            {
                var (mapParam, _) = getOrLoadParam("ItemLotParam_map", "ItemLotParam");
                var mapLayout = ItemLotLayout.Extract(mapParam);
                int mId0 = mapLayout.ItemIdIndices[0];
                var remaining = new List<int>();
                foreach (int itm in overflowItems)
                {
                    bool placed = false;
                    var freeSlot = LootSlotAllocator.Next(mapParam, mapLayout);
                    if (freeSlot is { } free)
                    {
                        bool isAccessory = itemIdToIsAccessory.GetValueOrDefault(itm);
                        bool isArmor = itemIdToIsProtector.GetValueOrDefault(itm);
                        int category = isAccessory ? 4 : (isArmor ? 3 : 2);
                        ParamHelper.SetCellFast(free.Row, mapLayout.ItemIdIndices[free.Slot], itm);
                        ParamHelper.SetCellFast(free.Row, mapLayout.CategoryIndices[free.Slot], category);
                        ParamHelper.SetCellFast(free.Row, mapLayout.BasePointIndices[free.Slot], (ushort)1000);
                        ParamHelper.SetCellFast(free.Row, mapLayout.NumIndices[free.Slot], (byte)1);
                        ParamHelper.SetCellFast(free.Row, mapLayout.FlagIdIndices[free.Slot], 0u);
                        placed = true;
                    }
                    if (!placed) remaining.Add(itm);
                }

                if (remaining.Count > 0)
                {
                    ShopLootInjector.InjectShopLineup(lootEl, getOrLoadParam, itemIdToIsProtector, itemIdToIsWeapon, itemIdToIsAccessory, remaining, ref injectedLootCount);
                }
            }

            injectedLootCount++;
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

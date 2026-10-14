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

            var candidateRows = new List<PARAM.Row>(2);
            if (rowMap.TryGetValue(targetLotId, out var pRow)) candidateRows.Add(pRow);
            if (rowMap.TryGetValue(targetLotId + 10, out var cRow)) candidateRows.Add(cRow);

            if (candidateRows.Count == 0)
            {
                ShopLootInjector.InjectShopLineup(lootEl, getOrLoadParam, itemIdToIsProtector, itemIdToIsWeapon, itemIdToIsAccessory, awardedItems, ref injectedLootCount);
                return;
            }

            bool isMapTable = tableName.Equals("ItemLotParam_map", StringComparison.OrdinalIgnoreCase);
            ushort ratePoints = (ushort)(dropRatePercent >= 100.0 ? 1000 : Math.Clamp((int)(dropRatePercent * 10), 1, 1000));
            var overflowItems = new List<int>();

            if (isMapTable)
            {
                // In ItemLotParam_map (chests, world pickups, map events):
                // Candidate row[0] is the exact entity triggered by the MSB event.
                // CRITICAL REQUIREMENT: Slot 1 (lotItemId01) is the original item and MUST REMAIN UNTOUCHED!
                // Inject up to 4 mod items into available empty slots (lotItemId02..lotItemId08).
                var targetRow = candidateRows[0];
                foreach (int itemId in awardedItems)
                {
                    bool isAccessory = itemIdToIsAccessory.TryGetValue(itemId, out var ia) && ia;
                    bool isArmor = itemIdToIsProtector.TryGetValue(itemId, out var ip) ? ip : (!isAccessory && !itemIdToIsWeapon.GetValueOrDefault(itemId, false));
                    int lotCategory = isAccessory ? 4 : (isArmor ? 3 : 2);

                    int slotToUse = -1;
                    // Scan slots 2 to 8. Never touch slot 1!
                    for (int s = 2; s <= 8; s++)
                    {
                        int cur = ParamHelper.GetCellInt(targetRow, $"lotItemId0{s}");
                        if (cur == itemId) { slotToUse = s; break; }
                        if (cur == 0 && slotToUse == -1) slotToUse = s;
                    }

                    if (slotToUse != -1)
                    {
                        ParamHelper.SetCellIfExists(targetRow, $"lotItemId0{slotToUse}", itemId);
                        ParamHelper.SetCellIfExists(targetRow, $"lotItemCategory0{slotToUse}", lotCategory);
                        ParamHelper.SetCellIfExists(targetRow, $"lotItemBasePoint0{slotToUse}", (ushort)1000);
                        ParamHelper.SetCellIfExists(targetRow, $"lotItemNum0{slotToUse}", (byte)1);
                        ParamHelper.SetCellIfExists(targetRow, $"getItemFlagId0{slotToUse}", 0u);
                    }
                    else
                    {
                        overflowItems.Add(itemId);
                    }
                }
            }
            else
            {
                // Enemy drops:
                // Check if primary slot is guaranteed drop (1000 points, e.g. boss remembrance / trophy).
                // If so, chain a sequential row so guaranteed drops are never cannibalized.
                int p01 = ParamHelper.GetCellInt(candidateRows[0], "lotItemBasePoint01");
                int item01 = ParamHelper.GetCellInt(candidateRows[0], "lotItemId01");
                bool isGuaranteedDrop = item01 > 0 && p01 >= 1000;

                foreach (int itemId in awardedItems)
                {
                    bool isAccessory = itemIdToIsAccessory.TryGetValue(itemId, out var ia) && ia;
                    bool isArmor = itemIdToIsProtector.TryGetValue(itemId, out var ip) ? ip : (!isAccessory && !itemIdToIsWeapon.GetValueOrDefault(itemId, false));
                    int lotCategory = isAccessory ? 4 : (isArmor ? 3 : 2);
                    bool placed = false;

                    if (isGuaranteedDrop)
                    {
                        var templateRow = candidateRows[0];
                        int freeChainId = -1;
                        for (int offset = 1; offset <= 9; offset++)
                        {
                            int candId = targetLotId + offset;
                            if (!rowMap.ContainsKey(candId))
                            {
                                freeChainId = candId;
                                break;
                            }
                        }

                        if (freeChainId != -1)
                        {
                            PARAM.Row chainedRow = new PARAM.Row(templateRow)
                            {
                                ID = freeChainId,
                                Name = $"[LootForge] Injected Enemy Drop ({itemId})"
                            };

                            for (int s = 1; s <= 8; s++)
                            {
                                ParamHelper.SetCellIfExists(chainedRow, $"lotItemId0{s}", 0);
                                ParamHelper.SetCellIfExists(chainedRow, $"lotItemCategory0{s}", 0);
                                ParamHelper.SetCellIfExists(chainedRow, $"lotItemBasePoint0{s}", (ushort)0);
                                ParamHelper.SetCellIfExists(chainedRow, $"lotItemNum0{s}", (byte)0);
                                ParamHelper.SetCellIfExists(chainedRow, $"getItemFlagId0{s}", 0u);
                            }

                            ParamHelper.SetCellIfExists(chainedRow, "lotItemId01", itemId);
                            ParamHelper.SetCellIfExists(chainedRow, "lotItemCategory01", lotCategory);
                            ParamHelper.SetCellIfExists(chainedRow, "lotItemBasePoint01", ratePoints);
                            ParamHelper.SetCellIfExists(chainedRow, "lotItemNum01", (byte)1);
                            ParamHelper.SetCellIfExists(chainedRow, "getItemFlagId01", 0u);

                            itemLotParam.Rows.Add(chainedRow);
                            rowMap[freeChainId] = chainedRow;
                            placed = true;
                        }
                    }
                    else
                    {
                        // Standard mob chance drop: use empty slot in candidate rows
                        foreach (var targetRow in candidateRows)
                        {
                            int slotToUse = -1;
                            for (int s = 1; s <= 8; s++)
                            {
                                int cur = ParamHelper.GetCellInt(targetRow, $"lotItemId0{s}");
                                if (cur == itemId) { slotToUse = s; break; }
                                if (cur == 0 && slotToUse == -1) slotToUse = s;
                            }

                            if (slotToUse != -1)
                            {
                                ParamHelper.SetCellIfExists(targetRow, $"lotItemId0{slotToUse}", itemId);
                                ParamHelper.SetCellIfExists(targetRow, $"lotItemCategory0{slotToUse}", lotCategory);
                                ParamHelper.SetCellIfExists(targetRow, $"lotItemBasePoint0{slotToUse}", ratePoints);
                                ParamHelper.SetCellIfExists(targetRow, $"lotItemNum0{slotToUse}", (byte)1);
                                ParamHelper.SetCellIfExists(targetRow, $"getItemFlagId0{slotToUse}", 0u);
                                placed = true;
                                break;
                            }
                        }
                    }

                    if (!placed)
                    {
                        overflowItems.Add(itemId);
                    }
                }
            }

            if (overflowItems.Count > 0)
            {
                ShopLootInjector.InjectShopLineup(lootEl, getOrLoadParam, itemIdToIsProtector, itemIdToIsWeapon, itemIdToIsAccessory, overflowItems, ref injectedLootCount);
            }

            injectedLootCount++;
        }

        private static int ResolveEnemyLotId(string? name)
        {
            string lower = name?.ToLowerInvariant() ?? "";
            if (lower.Contains("moongrum")) return 340000000;
            if (lower.Contains("crucible")) return 250000000;
            if (lower.Contains("black knife") || lower.Contains("assassin")) return 210000000;
            if (lower.Contains("cleanrot")) return 380000000;
            if (lower.Contains("banished")) return 301000000;
            if (lower.Contains("bloodhound") || lower.Contains("darriwil")) return 410000000;
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
            return 301000000; // Banished Knight safe non-tutorial fallback
        }
    }
}

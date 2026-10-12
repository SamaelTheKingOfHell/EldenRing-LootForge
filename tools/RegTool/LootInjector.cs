using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using SoulsFormats;

namespace LootForge.RegTool
{
    /// <summary>
    /// Service responsible for injecting custom mod equipment drops and shop lineups
    /// into Elden Ring ItemLotParam_enemy and ShopLineupParam tables.
    /// Handles merchant overflow spillover to Twin Maiden Husks to prevent invisible items.
    /// Adheres to [CS-MODULAR] and [CS-GRANULARITY].
    /// </summary>
    public static class LootInjector
    {
        private static Dictionary<int, PARAM.Row>? _enemyLotRowMap;
        private static Dictionary<int, PARAM.Row>? _mapLotRowMap;
        private static HashSet<int>? _shopRowIds;

        public static void ResetCache()
        {
            _enemyLotRowMap = null;
            _mapLotRowMap = null;
            _shopRowIds = null;
        }

        public static void InjectLootDistribution(
            JsonElement lootEl,
            Func<string, string, (PARAM Param, BinderFile File)> getOrLoadParam,
            Dictionary<int, bool> itemIdToIsProtector,
            Dictionary<int, bool> itemIdToIsWeapon,
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
                InjectItemLotDrop("ItemLotParam_enemy", ref _enemyLotRowMap, lootEl, getOrLoadParam, itemIdToIsProtector, itemIdToIsWeapon, awardedItems, ref injectedLootCount);
            }
            else if ((lootType == "map_pickup" || lootType == "world_chest" || lootType == "map_drop") && awardedItems.Count > 0)
            {
                InjectItemLotDrop("ItemLotParam_map", ref _mapLotRowMap, lootEl, getOrLoadParam, itemIdToIsProtector, itemIdToIsWeapon, awardedItems, ref injectedLootCount);
            }
            else if ((lootType == "shop_lineup" || lootType == "merchant_shop") && awardedItems.Count > 0)
            {
                InjectShopLineup(lootEl, getOrLoadParam, itemIdToIsProtector, itemIdToIsWeapon, awardedItems, ref injectedLootCount);
            }
        }

        private static void InjectItemLotDrop(
            string tableName,
            ref Dictionary<int, PARAM.Row>? rowMap,
            JsonElement lootEl,
            Func<string, string, (PARAM Param, BinderFile File)> getOrLoadParam,
            Dictionary<int, bool> itemIdToIsProtector,
            Dictionary<int, bool> itemIdToIsWeapon,
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
                // Fallback: If not found in this lot table, spill over to Twin Maiden Husks in ShopLineupParam
                InjectShopLineup(lootEl, getOrLoadParam, itemIdToIsProtector, itemIdToIsWeapon, awardedItems, ref injectedLootCount);
                return;
            }

            bool isMapTable = tableName.Equals("ItemLotParam_map", StringComparison.OrdinalIgnoreCase);
            ushort ratePoints = (ushort)(dropRatePercent >= 100.0 ? 1000 : Math.Clamp((int)(dropRatePercent * 10), 1, 1000));
            var overflowItems = new List<int>();

            foreach (int itemId in awardedItems)
            {
                bool isArmor = itemIdToIsProtector.TryGetValue(itemId, out var ip) ? ip : !itemIdToIsWeapon.GetValueOrDefault(itemId, false);
                int lotCategory = isArmor ? 3 : 2;
                bool placed = false;

                if (isMapTable)
                {
                    // Chests and world pickups: NEVER share an existing ItemLotParam row with an existing drop,
                    // as FromSoftware engines roll a single slot and will cannibalize/replace the vanilla chest item!
                    // Instead, chain a sequential ID (targetLotId + 1..9), which Elden Ring evaluates and awards
                    // concurrently with the chest!
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
                            Name = $"[LootForge] Injected Map Drop ({itemId})"
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
                        ParamHelper.SetCellIfExists(chainedRow, "lotItemBasePoint01", (ushort)1000);
                        ParamHelper.SetCellIfExists(chainedRow, "lotItemNum01", (byte)1);
                        ParamHelper.SetCellIfExists(chainedRow, "getItemFlagId01", 0u);

                        itemLotParam.Rows.Add(chainedRow);
                        rowMap[freeChainId] = chainedRow;
                        placed = true;
                    }
                }
                else
                {
                    // Enemy drops:
                    // Check if primary slot is a guaranteed drop (1000 points, e.g. boss remembrance / trophy).
                    // If so, chain a sequential row so the guaranteed drop is never cannibalized.
                    int p01 = ParamHelper.GetCellInt(candidateRows[0], "lotItemBasePoint01");
                    int item01 = ParamHelper.GetCellInt(candidateRows[0], "lotItemId01");
                    bool isGuaranteedDrop = item01 > 0 && p01 >= 1000;

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
                }

                if (!placed)
                {
                    overflowItems.Add(itemId);
                }
            }

            if (overflowItems.Count > 0)
            {
                InjectShopLineup(lootEl, getOrLoadParam, itemIdToIsProtector, itemIdToIsWeapon, overflowItems, ref injectedLootCount);
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

        private static void InjectShopLineup(
            JsonElement lootEl,
            Func<string, string, (PARAM Param, BinderFile File)> getOrLoadParam,
            Dictionary<int, bool> itemIdToIsProtector,
            Dictionary<int, bool> itemIdToIsWeapon,
            List<int> awardedItems,
            ref int injectedLootCount)
        {
            var (shopParam, _) = getOrLoadParam("ShopLineupParam", "ShopLineupParam");
            string shopName = lootEl.TryGetProperty("display_name", out var dn) ? dn.GetString() ?? "Merchant" : "Merchant";
            if (string.IsNullOrEmpty(shopName) && lootEl.TryGetProperty("merchant_name", out var mn))
                shopName = mn.GetString() ?? "Merchant";

            int cost = 500;
            if (lootEl.TryGetProperty("cost_or_remembrance", out var cst))
                cost = (int)cst.GetDouble();
            else if (lootEl.TryGetProperty("rune_cost", out var rc))
                cost = rc.GetInt32();

            string targetId = "";
            if (lootEl.TryGetProperty("target_id", out var tid))
                targetId = tid.GetString() ?? "";
            else if (lootEl.TryGetProperty("shop_id", out var sIdEl))
                targetId = sIdEl.GetString() ?? "";

            int rangeStart = 100500, rangeEnd = 100524;
            if (targetId.Contains("twin", StringComparison.OrdinalIgnoreCase) || shopName.Contains("twin", StringComparison.OrdinalIgnoreCase) || shopName.Contains("husks", StringComparison.OrdinalIgnoreCase))
            {
                rangeStart = 101800; rangeEnd = 101899;
            }
            else if (targetId.Contains("liurnia", StringComparison.OrdinalIgnoreCase) || shopName.Contains("liurnia", StringComparison.OrdinalIgnoreCase))
            {
                rangeStart = 100625; rangeEnd = 100637;
            }
            else if (targetId.Contains("remembrance", StringComparison.OrdinalIgnoreCase) || shopName.Contains("remembrance", StringComparison.OrdinalIgnoreCase) || shopName.Contains("enia", StringComparison.OrdinalIgnoreCase))
            {
                rangeStart = 101900; rangeEnd = 101949;
            }

            if (_shopRowIds == null)
            {
                _shopRowIds = new HashSet<int>(shopParam.Rows.Count + 10000);
                foreach (var r in shopParam.Rows)
                {
                    _shopRowIds.Add(r.ID);
                }
            }

            var templateRow = shopParam.Rows.FirstOrDefault(r => r.ID >= rangeStart && r.ID <= rangeEnd)
                              ?? shopParam.Rows.FirstOrDefault();

            for (int i = 0; i < awardedItems.Count; i++)
            {
                int itemId = awardedItems[i];

                int shopRowId = -1;
                for (int cand = rangeStart; cand <= rangeEnd; cand++)
                {
                    if (!_shopRowIds.Contains(cand))
                    {
                        shopRowId = cand;
                        break;
                    }
                }

                // Merchant capacity overflow handling:
                // If range is exhausted, spillover to Twin Maiden Husks (101800..101899)
                if (shopRowId == -1)
                {
                    for (int cand = 101800; cand <= 101899; cand++)
                    {
                        if (!_shopRowIds.Contains(cand))
                        {
                            shopRowId = cand;
                            shopName = "Twin Maiden Husks";
                            break;
                        }
                    }
                }

                // If Twin Maiden Husks is also exhausted, try Finger Reader Enia (101900..101949)
                if (shopRowId == -1)
                {
                    for (int cand = 101900; cand <= 101949; cand++)
                    {
                        if (!_shopRowIds.Contains(cand))
                        {
                            shopRowId = cand;
                            shopName = "Finger Reader Enia";
                            break;
                        }
                    }
                }

                // If ALL shop param ranges have reached capacity limitation, rotate to other pools (ItemLotParam_enemy)
                if (shopRowId == -1)
                {
                    Console.WriteLine($"[RegTool WARN] ShopLineupParam capacity limit reached. Rotating overflowed item ID {itemId} to ItemLotParam_enemy pool.");
                    RotateOverflowToEnemyDrop(itemId, getOrLoadParam, itemIdToIsProtector, itemIdToIsWeapon, ref injectedLootCount);
                    continue;
                }

                _shopRowIds.Add(shopRowId);

                PARAM.Row targetShopRow = new PARAM.Row(templateRow!)
                {
                    ID = shopRowId,
                    Name = $"[LootForge] {shopName}"
                };
                shopParam.Rows.Add(targetShopRow);

                bool isArmor = itemIdToIsProtector.TryGetValue(itemId, out var ip) ? ip : !itemIdToIsWeapon.GetValueOrDefault(itemId, false);
                ParamHelper.SetCellIfExists(targetShopRow, "equipId", itemId);
                ParamHelper.SetCellIfExists(targetShopRow, "equipType", (byte)(isArmor ? 1 : 0));
                ParamHelper.SetCellIfExists(targetShopRow, "value", cost);
                ParamHelper.SetCellIfExists(targetShopRow, "mtrlId", -1);
                ParamHelper.SetCellIfExists(targetShopRow, "eventFlag_forRelease", 0u);
                ParamHelper.SetCellIfExists(targetShopRow, "eventFlag_forStock", 0u);
                ParamHelper.SetCellIfExists(targetShopRow, "sellQuantity", (short)-1);
                ParamHelper.SetCellIfExists(targetShopRow, "costType", (byte)0);
                ParamHelper.SetCellIfExists(targetShopRow, "setNum", (ushort)1);
                ParamHelper.SetCellIfExists(targetShopRow, "value_Add", 0);
                ParamHelper.SetCellIfExists(targetShopRow, "value_Magnification", 1.0f);
                ParamHelper.SetCellIfExists(targetShopRow, "iconId", -1);
                ParamHelper.SetCellIfExists(targetShopRow, "nameMsgId", -1);
                ParamHelper.SetCellIfExists(targetShopRow, "menuTitleMsgId", -1);
                ParamHelper.SetCellIfExists(targetShopRow, "menuIconId", (short)-1);

                injectedLootCount++;
            }
        }

        private static void RotateOverflowToEnemyDrop(
            int itemId,
            Func<string, string, (PARAM Param, BinderFile File)> getOrLoadParam,
            Dictionary<int, bool> itemIdToIsProtector,
            Dictionary<int, bool> itemIdToIsWeapon,
            ref int injectedLootCount)
        {
            var (itemLotParam, _) = getOrLoadParam("ItemLotParam_enemy", "ItemLotParam_enemy");
            int[] fallbackLots = new[] { 301000000, 380000000, 431100000, 430000000 };
            PARAM.Row? targetRow = null;
            foreach (int lotId in fallbackLots)
            {
                var row = itemLotParam.Rows.FirstOrDefault(r => r.ID == lotId);
                if (row != null)
                {
                    for (int s = 1; s <= 8; s++)
                    {
                        int cur = ParamHelper.GetCellInt(row, $"lotItemId0{s}");
                        if (cur == 0 || cur == itemId)
                        {
                            targetRow = row;
                            break;
                        }
                    }
                    if (targetRow != null) break;
                }
            }

            if (targetRow == null)
            {
                targetRow = itemLotParam.Rows.FirstOrDefault(r => r.ID == 301000000) ?? itemLotParam.Rows.FirstOrDefault();
            }

            if (targetRow != null)
            {
                bool isArmor = itemIdToIsProtector.TryGetValue(itemId, out var ip) ? ip : !itemIdToIsWeapon.GetValueOrDefault(itemId, false);
                int lotCategory = isArmor ? 3 : 2;
                int slotToUse = 1;
                for (int s = 1; s <= 8; s++)
                {
                    int cur = ParamHelper.GetCellInt(targetRow, $"lotItemId0{s}");
                    if (cur == itemId || cur == 0) { slotToUse = s; break; }
                }

                ParamHelper.SetCellIfExists(targetRow, $"lotItemId0{slotToUse}", itemId);
                ParamHelper.SetCellIfExists(targetRow, $"lotItemCategory0{slotToUse}", lotCategory);
                ParamHelper.SetCellIfExists(targetRow, $"lotItemBasePoint0{slotToUse}", (ushort)250);
                ParamHelper.SetCellIfExists(targetRow, $"lotItemNum0{slotToUse}", (byte)1);
                ParamHelper.SetCellIfExists(targetRow, $"getItemFlagId0{slotToUse}", 0u);
                Console.WriteLine($"[RegTool SUCCESS] Rotated overflowed item ID {itemId} to ItemLotParam_enemy lot ID {targetRow.ID} slot {slotToUse}.");
                injectedLootCount++;
            }
        }
    }
}

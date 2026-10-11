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
                InjectEnemyDrop(lootEl, getOrLoadParam, itemIdToIsProtector, itemIdToIsWeapon, awardedItems, ref injectedLootCount);
            }
            else if ((lootType == "shop_lineup" || lootType == "merchant_shop") && awardedItems.Count > 0)
            {
                InjectShopLineup(lootEl, getOrLoadParam, itemIdToIsProtector, itemIdToIsWeapon, awardedItems, ref injectedLootCount);
            }
        }

        private static void InjectEnemyDrop(
            JsonElement lootEl,
            Func<string, string, (PARAM Param, BinderFile File)> getOrLoadParam,
            Dictionary<int, bool> itemIdToIsProtector,
            Dictionary<int, bool> itemIdToIsWeapon,
            List<int> awardedItems,
            ref int injectedLootCount)
        {
            string rawTid = lootEl.TryGetProperty("target_id", out var tid) ? tid.GetString() ?? "" : "";
            int targetLotId = 0;
            if (int.TryParse(rawTid, out int parsedTid) && parsedTid > 1000000 && !(parsedTid >= 9100000 && parsedTid < 9200000))
                targetLotId = parsedTid;
            else if (lootEl.TryGetProperty("lot_id", out var lid) && lid.GetInt32() > 1000000 && !(lid.GetInt32() >= 9100000 && lid.GetInt32() < 9200000))
                targetLotId = lid.GetInt32();
            else
                targetLotId = ResolveEnemyLotId(rawTid);

            double dropRatePercent = lootEl.TryGetProperty("drop_rate_percent", out var dr) ? dr.GetDouble() : 20.0;
            var (itemLotParam, _) = getOrLoadParam("ItemLotParam_enemy", "ItemLotParam");

            // Purge old orphaned synthetic rows in 9100000 range
            itemLotParam.Rows.RemoveAll(r => r.ID >= 9100000 && r.ID < 9200000);

            var candidateRows = new List<PARAM.Row>();
            var pRow = itemLotParam.Rows.FirstOrDefault(r => r.ID == targetLotId);
            if (pRow != null) candidateRows.Add(pRow);
            var cRow = itemLotParam.Rows.FirstOrDefault(r => r.ID == targetLotId + 10);
            if (cRow != null) candidateRows.Add(cRow);

            if (candidateRows.Count == 0) return;

            ushort ratePoints = (ushort)(dropRatePercent >= 100.0 ? 1000 : Math.Clamp((int)(dropRatePercent * 10), 1, 1000));

            foreach (var targetRow in candidateRows)
            {
                foreach (int itemId in awardedItems)
                {
                    bool isArmor = itemIdToIsProtector.TryGetValue(itemId, out var ip) ? ip : !itemIdToIsWeapon.GetValueOrDefault(itemId, false);
                    int lotCategory = isArmor ? 3 : 2;

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
                    }
                }
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

            int rangeStart = 100500;
            int rangeEnd = 100524;

            if (targetId.Contains("kale", StringComparison.OrdinalIgnoreCase) ||
                shopName.Contains("kale", StringComparison.OrdinalIgnoreCase) ||
                shopName.Contains("kalé", StringComparison.OrdinalIgnoreCase))
            {
                rangeStart = 100500;
                rangeEnd = 100524;
            }
            else if (targetId.Contains("twin", StringComparison.OrdinalIgnoreCase) ||
                     targetId.Contains("maiden", StringComparison.OrdinalIgnoreCase) ||
                     targetId.Contains("husks", StringComparison.OrdinalIgnoreCase) ||
                     shopName.Contains("twin", StringComparison.OrdinalIgnoreCase) ||
                     shopName.Contains("husks", StringComparison.OrdinalIgnoreCase))
            {
                rangeStart = 101800;
                rangeEnd = 101899;
            }
            else if (targetId.Contains("liurnia", StringComparison.OrdinalIgnoreCase) ||
                     shopName.Contains("liurnia", StringComparison.OrdinalIgnoreCase))
            {
                rangeStart = 100625;
                rangeEnd = 100637;
            }
            else if (targetId.Contains("remembrance", StringComparison.OrdinalIgnoreCase) ||
                     shopName.Contains("remembrance", StringComparison.OrdinalIgnoreCase) ||
                     shopName.Contains("enia", StringComparison.OrdinalIgnoreCase))
            {
                rangeStart = 101900;
                rangeEnd = 101949;
            }

            var templateRow = shopParam.Rows.FirstOrDefault(r => r.ID >= rangeStart && r.ID <= rangeEnd)
                              ?? shopParam.Rows.FirstOrDefault();

            for (int i = 0; i < awardedItems.Count; i++)
            {
                int itemId = awardedItems[i];

                var existingRow = shopParam.Rows.FirstOrDefault(r =>
                    r.ID >= rangeStart && r.ID <= rangeEnd && ParamHelper.GetCellInt(r, "equipId") == itemId);

                PARAM.Row targetShopRow;
                if (existingRow != null)
                {
                    targetShopRow = existingRow;
                }
                else
                {
                    int shopRowId = -1;
                    for (int cand = rangeStart; cand <= rangeEnd; cand++)
                    {
                        if (!shopParam.Rows.Any(r => r.ID == cand))
                        {
                            shopRowId = cand;
                            break;
                        }
                    }

                    // Merchant capacity overflow handling:
                    // If range is exhausted (e.g. Kalé's 8 free slots full), spillover to Twin Maiden Husks (101800..101899)
                    if (shopRowId == -1)
                    {
                        Console.WriteLine($"[RegTool] Merchant range {rangeStart}..{rangeEnd} full. Spilling item {itemId} to Twin Maiden Husks.");
                        for (int cand = 101800; cand <= 101899; cand++)
                        {
                            if (!shopParam.Rows.Any(r => r.ID == cand))
                            {
                                shopRowId = cand;
                                shopName = "Twin Maiden Husks";
                                break;
                            }
                        }
                    }

                    if (shopRowId == -1)
                    {
                        shopRowId = 101899 + 1;
                        while (shopParam.Rows.Any(r => r.ID == shopRowId))
                            shopRowId++;
                    }

                    targetShopRow = new PARAM.Row(templateRow!)
                    {
                        ID = shopRowId,
                        Name = $"[LootForge] {shopName}"
                    };
                    shopParam.Rows.Add(targetShopRow);
                }

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
    }
}

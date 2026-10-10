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
            int targetLotId = 0;
            if (lootEl.TryGetProperty("target_id", out var tid) && int.TryParse(tid.GetString(), out int parsedTid) && parsedTid > 0)
                targetLotId = parsedTid;
            else if (lootEl.TryGetProperty("lot_id", out var lid) && lid.GetInt32() > 0)
                targetLotId = lid.GetInt32();

            string targetEnemy = lootEl.TryGetProperty("target_enemy", out var te) ? te.GetString() ?? "Wild Enemy" : "Wild Enemy";
            double dropRatePercent = lootEl.TryGetProperty("drop_rate_percent", out var dr) ? dr.GetDouble() : 20.0;

            if (targetLotId <= 0) return;

            var (itemLotParam, _) = getOrLoadParam("ItemLotParam_enemy", "ItemLotParam");
            var targetLotRow = itemLotParam.Rows.FirstOrDefault(r => r.ID == targetLotId);

            if (targetLotRow == null)
            {
                var baseLot = itemLotParam.Rows.FirstOrDefault();
                if (baseLot != null)
                {
                    targetLotRow = new PARAM.Row(baseLot)
                    {
                        ID = targetLotId,
                        Name = $"[LootForge] {targetEnemy}"
                    };
                    for (int slot = 1; slot <= 8; slot++)
                    {
                        ParamHelper.SetCellIfExists(targetLotRow, $"lotItemId0{slot}", 0);
                        ParamHelper.SetCellIfExists(targetLotRow, $"lotItemCategory0{slot}", 0);
                        ParamHelper.SetCellIfExists(targetLotRow, $"lotItemBasePoint0{slot}", (ushort)0);
                        ParamHelper.SetCellIfExists(targetLotRow, $"lotItemNum0{slot}", (byte)0);
                    }
                    itemLotParam.Rows.Add(targetLotRow);
                }
            }

            if (targetLotRow == null) return;

            ushort ratePoints = (ushort)Math.Clamp((int)(dropRatePercent * 100), 1, 10000);
            for (int itemIndex = 0; itemIndex < awardedItems.Count; itemIndex++)
            {
                int itemId = awardedItems[itemIndex];
                bool isArmor = itemIdToIsProtector.TryGetValue(itemId, out var ip) ? ip : !itemIdToIsWeapon.GetValueOrDefault(itemId, false);
                // ItemLotParam category enum: 2 = Weapon, 3 = Protector (Armor)
                int lotCategory = isArmor ? 3 : 2;

                int existingSlot = -1;
                int firstEmptySlot = -1;

                for (int s = 1; s <= 8; s++)
                {
                    int curItem = ParamHelper.GetCellInt(targetLotRow, $"lotItemId0{s}");
                    if (curItem == itemId) { existingSlot = s; break; }
                    if (curItem == 0 && firstEmptySlot == -1) firstEmptySlot = s;
                }

                int slotToUse = existingSlot != -1 ? existingSlot : firstEmptySlot;
                if (slotToUse != -1)
                {
                    ParamHelper.SetCellIfExists(targetLotRow, $"lotItemId0{slotToUse}", itemId);
                    ParamHelper.SetCellIfExists(targetLotRow, $"lotItemCategory0{slotToUse}", lotCategory);
                    ParamHelper.SetCellIfExists(targetLotRow, $"lotItemBasePoint0{slotToUse}", ratePoints);
                    ParamHelper.SetCellIfExists(targetLotRow, $"lotItemNum0{slotToUse}", (byte)1);
                }
                else
                {
                    int overflowLotId = targetLotId < 9000000 ? 9100000 + (targetLotId % 10000) : targetLotId + 1;
                    var overflowRow = itemLotParam.Rows.FirstOrDefault(r => r.ID == overflowLotId);
                    if (overflowRow == null)
                    {
                        var baseLot = itemLotParam.Rows.FirstOrDefault();
                        if (baseLot != null)
                        {
                            overflowRow = new PARAM.Row(baseLot)
                            {
                                ID = overflowLotId,
                                Name = $"[LootForge Chained] {targetEnemy}"
                            };
                            for (int s = 1; s <= 8; s++)
                            {
                                ParamHelper.SetCellIfExists(overflowRow, $"lotItemId0{s}", 0);
                                ParamHelper.SetCellIfExists(overflowRow, $"lotItemCategory0{s}", 0);
                                ParamHelper.SetCellIfExists(overflowRow, $"lotItemBasePoint0{s}", (ushort)0);
                                ParamHelper.SetCellIfExists(overflowRow, $"lotItemNum0{s}", (byte)0);
                            }
                            itemLotParam.Rows.Add(overflowRow);
                        }
                    }
                    if (overflowRow != null)
                    {
                        ParamHelper.SetCellIfExists(overflowRow, "lotItemId01", itemId);
                        ParamHelper.SetCellIfExists(overflowRow, "lotItemCategory01", lotCategory);
                        ParamHelper.SetCellIfExists(overflowRow, "lotItemBasePoint01", ratePoints);
                        ParamHelper.SetCellIfExists(overflowRow, "lotItemNum01", (byte)1);
                    }
                }
            }
            injectedLootCount++;
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

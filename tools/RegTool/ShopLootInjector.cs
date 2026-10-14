using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using SoulsFormats;

namespace LootForge.RegTool
{
    /// <summary>
    /// Handles merchant shop lineup injections and capacity overflow rotations into shop/enemy tables.
    /// Adheres to [CS-MODULAR] and [CS-GRANULARITY] (<= 300 lines).
    /// </summary>
    public static class ShopLootInjector
    {
        private static HashSet<int>? _shopRowIds = null;

        public static void InjectShopLineup(
            JsonElement lootEl,
            Func<string, string, (PARAM Param, BinderFile File)> getOrLoadParam,
            Dictionary<int, bool> itemIdToIsProtector,
            Dictionary<int, bool> itemIdToIsWeapon,
            Dictionary<int, bool> itemIdToIsAccessory,
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

                if (shopRowId == -1)
                {
                    Console.WriteLine($"[RegTool WARN] ShopLineupParam capacity limit reached. Rotating overflowed item ID {itemId} to ItemLotParam_enemy pool.");
                    RotateOverflowToEnemyDrop(itemId, getOrLoadParam, itemIdToIsProtector, itemIdToIsWeapon, itemIdToIsAccessory, ref injectedLootCount);
                    continue;
                }

                _shopRowIds.Add(shopRowId);

                PARAM.Row targetShopRow = new PARAM.Row(templateRow!)
                {
                    ID = shopRowId,
                    Name = $"[LootForge] {shopName}"
                };
                shopParam.Rows.Add(targetShopRow);

                bool isAccessory = itemIdToIsAccessory.TryGetValue(itemId, out var ia) && ia;
                bool isArmor = itemIdToIsProtector.TryGetValue(itemId, out var ip) ? ip : (!isAccessory && !itemIdToIsWeapon.GetValueOrDefault(itemId, false));
                byte equipType = isAccessory ? (byte)2 : (isArmor ? (byte)1 : (byte)0);
                ParamHelper.SetCellIfExists(targetShopRow, "equipId", itemId);
                ParamHelper.SetCellIfExists(targetShopRow, "equipType", equipType);

                int itemCost = cost;
                if (lootEl.TryGetProperty("item_prices", out var pricesEl) && pricesEl.ValueKind == JsonValueKind.Object)
                {
                    if (pricesEl.TryGetProperty(itemId.ToString(), out var pEl) && pEl.TryGetInt32(out int parsedCost))
                    {
                        itemCost = parsedCost;
                    }
                }
                ParamHelper.SetCellIfExists(targetShopRow, "value", itemCost);
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

        public static void RotateOverflowToEnemyDrop(
            int itemId,
            Func<string, string, (PARAM Param, BinderFile File)> getOrLoadParam,
            Dictionary<int, bool> itemIdToIsProtector,
            Dictionary<int, bool> itemIdToIsWeapon,
            Dictionary<int, bool> itemIdToIsAccessory,
            ref int injectedLootCount)
        {
            var (itemLotParam, _) = getOrLoadParam("ItemLotParam_enemy", "ItemLotParam");
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
                bool isAccessory = itemIdToIsAccessory.TryGetValue(itemId, out var ia) && ia;
                bool isArmor = itemIdToIsProtector.TryGetValue(itemId, out var ip) ? ip : (!isAccessory && !itemIdToIsWeapon.GetValueOrDefault(itemId, false));
                int lotCategory = isAccessory ? 4 : (isArmor ? 3 : 2);
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

using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using SoulsFormats;

namespace LootForge.RegTool
{
    /// <summary>
    /// Inserts finite stock only inside shop intervals opened by installed talk scripts.
    /// Adheres to [CS-MODULAR] and [CS-GRANULARITY] (<= 300 lines).
    /// </summary>
    public static class ShopLootInjector
    {
        private static HashSet<int>? _shopRowIds = null;
        private static List<ShopRangeCatalog.Shop>? ranges;
        public static void Configure(List<ShopRangeCatalog.Shop> verified) => ranges = verified;


        /// <summary>Release table-specific state between patch operations.</summary>
        public static void ResetCache() { _shopRowIds = null; ranges = null; }

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

            int rangeStart = lootEl.TryGetProperty("range_start",out var first) && first.ValueKind == JsonValueKind.Number ? first.GetInt32() : -1;
            int rangeEnd = lootEl.TryGetProperty("range_end",out var last) && last.ValueKind == JsonValueKind.Number ? last.GetInt32() : -1;
            var verified = ranges?.FirstOrDefault(range => range.Start == rangeStart && range.End == rangeEnd);
            if (verified == null && ranges != null)
                verified = ranges.FirstOrDefault(range => targetId == $"shop_{range.Start}");
            if (verified == null && ranges != null && (targetId.Contains("remembrance") || targetId.Contains("enia")))
                verified = ranges.FirstOrDefault(range => range.IsExchange);
            if (verified == null && ranges != null)
                verified = ranges.FirstOrDefault(range => range.Name.Contains(targetId.Replace("nomadic_", "").Replace('_',' '),StringComparison.OrdinalIgnoreCase));
            if (verified == null) throw new InvalidDataException($"No verified talk-script shop range for {targetId}.");
            rangeStart = verified.Start; rangeEnd = verified.End;

            if (_shopRowIds == null)
            {
                _shopRowIds = new HashSet<int>(shopParam.Rows.Count + 10000);
                foreach (var r in shopParam.Rows)
                {
                    _shopRowIds.Add(r.ID);
                }
            }

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
                    throw new InvalidOperationException($"Shop {verified.Name} has no row space. No item was silently moved to another vendor or loot table.");

                _shopRowIds.Add(shopRowId);

                PARAM.Row targetShopRow = new PARAM.Row(shopRowId, $"[LootForge] {shopName}", shopParam.AppliedParamdef)
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
                ParamHelper.SetCellIfExists(targetShopRow, "eventFlag_forStock", (uint)(1900870000 + shopRowId));
                ParamHelper.SetCellIfExists(targetShopRow, "sellQuantity", (short)1);
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
            throw new InvalidOperationException("Unscoped shop overflow is disabled. Select a verified destination or reduce variants.");
        }
    }
}

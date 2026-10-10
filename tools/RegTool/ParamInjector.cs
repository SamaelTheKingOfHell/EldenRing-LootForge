using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using SoulsFormats;

namespace LootForge.RegTool
{
    /// <summary>
    /// Service responsible for injecting custom mod equipment and loot distributions
    /// into Elden Ring PARAM tables (EquipParamProtector, EquipParamWeapon,
    /// ItemLotParam_enemy, and ShopLineupParam).
    /// Adheres to [CS-MODULAR] and [CS-GRANULARITY].
    /// </summary>
    public static class ParamInjector
    {
        public static void InjectEquipParams(
            JsonElement equipParamsEl,
            Func<string, string, (PARAM Param, BinderFile File)> getOrLoadParam,
            Dictionary<int, bool> itemIdToIsProtector,
            Dictionary<int, bool> itemIdToIsWeapon,
            Dictionary<int, int> itemIdToVanillaSourceId,
            ref int injectedEquipCount)
        {
            foreach (var ep in equipParamsEl.EnumerateArray())
            {
                string tableName = ep.GetProperty("param_table").GetString()!;
                int newParamId = ep.GetProperty("new_param_id").GetInt32();
                int baseCloneId = ep.TryGetProperty("base_clone_id", out var bc) ? bc.GetInt32() : 0;
                int targetModelId = ep.TryGetProperty("target_model_id", out var tmEl) ? tmEl.GetInt32() : 0;
                int slotOffset = ep.TryGetProperty("slot_offset", out var soEl) ? soEl.GetInt32() : 0;
                string rowName = ep.TryGetProperty("row_name", out var rn) ? rn.GetString() ?? "" : "";

                bool isProtector = tableName == "EquipParamProtector";
                itemIdToIsProtector[newParamId] = isProtector;
                itemIdToIsWeapon[newParamId] = !isProtector;

                string defName = tableName;
                var (param, _) = getOrLoadParam(tableName, defName);

                // If already present (re-forge), remove old injected row to update cleanly
                var existingIndex = param.Rows.FindIndex(r => r.ID == newParamId);
                if (existingIndex >= 0)
                {
                    param.Rows.RemoveAt(existingIndex);
                }

                // Locate authentic vanilla clone source row
                PARAM.Row? baseRow = null;

                // 1. Try by direct baseCloneId
                if (baseCloneId > 0)
                {
                    baseRow = param.Rows.FirstOrDefault(r => r.ID == baseCloneId);
                }

                // 2. Try by authentic equipModelId (matching targetModelId)
                if (baseRow == null && targetModelId > 0)
                {
                    if (isProtector)
                    {
                        baseRow = param.Rows.FirstOrDefault(r => r.ID < 9000000 && r.ID % 1000 == slotOffset && ParamHelper.GetCellInt(r, "equipModelId") == targetModelId)
                               ?? param.Rows.FirstOrDefault(r => r.ID < 9000000 && ParamHelper.GetCellInt(r, "equipModelId") == targetModelId);
                    }
                    else
                    {
                        baseRow = param.Rows.FirstOrDefault(r => r.ID < 9000000 && ParamHelper.GetCellInt(r, "equipModelId") == targetModelId);
                    }
                }

                // 3. Fallback: ANY authentic vanilla row (NEVER row 0 which is empty/naked with icon=0)
                if (baseRow == null)
                {
                    if (isProtector)
                    {
                        baseRow = param.Rows.FirstOrDefault(r => r.ID > 0 && r.ID < 9000000 && r.ID % 1000 == slotOffset && ParamHelper.GetCellInt(r, "iconIdM") > 0)
                               ?? param.Rows.FirstOrDefault(r => r.ID > 0 && r.ID < 9000000 && ParamHelper.GetCellInt(r, "iconIdM") > 0)
                               ?? param.Rows.FirstOrDefault(r => r.ID > 0 && r.ID < 9000000);
                    }
                    else
                    {
                        baseRow = param.Rows.FirstOrDefault(r => r.ID > 0 && r.ID < 9000000 && ParamHelper.GetCellInt(r, "iconId") > 0)
                               ?? param.Rows.FirstOrDefault(r => r.ID > 0 && r.ID < 9000000);
                    }
                }

                if (baseRow == null)
                {
                    Console.WriteLine($"[RegTool WARN] Cannot find base row to clone for {tableName} ID {newParamId}");
                    continue;
                }

                // Save the real authentic vanilla row ID for FMG text injection
                itemIdToVanillaSourceId[newParamId] = baseRow.ID;

                var newRow = new PARAM.Row(baseRow)
                {
                    ID = newParamId,
                    Name = rowName
                };

                if (ep.TryGetProperty("field_updates", out var fieldsEl) && fieldsEl.ValueKind == JsonValueKind.Object)
                {
                    foreach (var prop in fieldsEl.EnumerateObject())
                    {
                        string fieldName = prop.Name;
                        if (fieldName.EndsWith("ModelId", StringComparison.OrdinalIgnoreCase))
                        {
                            fieldName = "equipModelId";
                        }

                        var cell = newRow.Cells.FirstOrDefault(c => string.Equals(c.Def.InternalName, fieldName, StringComparison.OrdinalIgnoreCase));
                        if (cell != null)
                        {
                            ParamHelper.SetCellValue(cell, prop.Value);
                        }
                    }
                }

                // Ensure icon is never 0 (inherit authentic icons from baseRow)
                if (isProtector)
                {
                    int iconM = ParamHelper.GetCellInt(newRow, "iconIdM");
                    int baseIconM = ParamHelper.GetCellInt(baseRow, "iconIdM");
                    int baseIconF = ParamHelper.GetCellInt(baseRow, "iconIdF");
                    if (iconM == 0 && baseIconM > 0)
                    {
                        ParamHelper.SetCellIfExists(newRow, "iconIdM", (ushort)baseIconM);
                        ParamHelper.SetCellIfExists(newRow, "iconIdF", (ushort)baseIconF);
                    }
                }
                else
                {
                    int icon = ParamHelper.GetCellInt(newRow, "iconId");
                    int baseIcon = ParamHelper.GetCellInt(baseRow, "iconId");
                    if (icon == 0 && baseIcon > 0)
                    {
                        ParamHelper.SetCellIfExists(newRow, "iconId", (ushort)baseIcon);
                    }
                }

                param.Rows.Add(newRow);
                injectedEquipCount++;
            }
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
                int targetLotId = 0;
                if (lootEl.TryGetProperty("target_id", out var tid) && int.TryParse(tid.GetString(), out int parsedTid) && parsedTid > 0)
                {
                    targetLotId = parsedTid;
                }
                else if (lootEl.TryGetProperty("lot_id", out var lid) && lid.GetInt32() > 0)
                {
                    targetLotId = lid.GetInt32();
                }

                string targetEnemy = lootEl.TryGetProperty("target_enemy", out var te) ? te.GetString() ?? "Wild Enemy" : "Wild Enemy";
                double dropRatePercent = lootEl.TryGetProperty("drop_rate_percent", out var dr) ? dr.GetDouble() : 20.0;

                if (targetLotId > 0)
                {
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

                    if (targetLotRow != null)
                    {
                        ushort ratePoints = (ushort)Math.Clamp((int)(dropRatePercent * 100), 1, 10000);
                        int itemIndex = 0;
                        while (itemIndex < awardedItems.Count)
                        {
                            int itemId = awardedItems[itemIndex];
                            bool isArmor = itemIdToIsProtector.TryGetValue(itemId, out var ip) ? ip : !itemIdToIsWeapon.GetValueOrDefault(itemId, false);

                            int existingSlot = -1;
                            int firstEmptySlot = -1;

                            for (int s = 1; s <= 8; s++)
                            {
                                int curItem = ParamHelper.GetCellInt(targetLotRow, $"lotItemId0{s}");
                                if (curItem == itemId)
                                {
                                    existingSlot = s;
                                    break;
                                }
                                if (curItem == 0 && firstEmptySlot == -1)
                                {
                                    firstEmptySlot = s;
                                }
                            }

                            int slotToUse = existingSlot != -1 ? existingSlot : firstEmptySlot;
                            if (slotToUse != -1)
                            {
                                ParamHelper.SetCellIfExists(targetLotRow, $"lotItemId0{slotToUse}", itemId);
                                ParamHelper.SetCellIfExists(targetLotRow, $"lotItemCategory0{slotToUse}", isArmor ? 0x10000000 : 0x20000000);
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
                                    ParamHelper.SetCellIfExists(overflowRow, "lotItemCategory01", isArmor ? 0x10000000 : 0x20000000);
                                    ParamHelper.SetCellIfExists(overflowRow, "lotItemBasePoint01", ratePoints);
                                    ParamHelper.SetCellIfExists(overflowRow, "lotItemNum01", (byte)1);
                                }
                            }

                            itemIndex++;
                        }
                        injectedLootCount++;
                    }
                }
            }
            else if ((lootType == "shop_lineup" || lootType == "merchant_shop") && awardedItems.Count > 0)
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
                else if (lootType == "shop_lineup" ||
                         targetId.Contains("remembrance", StringComparison.OrdinalIgnoreCase) ||
                         shopName.Contains("remembrance", StringComparison.OrdinalIgnoreCase) ||
                         shopName.Contains("enia", StringComparison.OrdinalIgnoreCase))
                {
                    rangeStart = 101900;
                    rangeEnd = 101949;
                }
                else
                {
                    var matchingRows = shopParam.Rows.Where(r =>
                        r.Name != null && (r.Name.Contains(shopName, StringComparison.OrdinalIgnoreCase) ||
                                           (!string.IsNullOrEmpty(targetId) && r.Name.Contains(targetId, StringComparison.OrdinalIgnoreCase)))).ToList();
                    if (matchingRows.Count > 0)
                    {
                        rangeStart = matchingRows.Min(r => r.ID);
                        rangeEnd = matchingRows.Max(r => r.ID);
                    }
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

                        if (shopRowId == -1)
                        {
                            shopRowId = rangeEnd + 1;
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
}

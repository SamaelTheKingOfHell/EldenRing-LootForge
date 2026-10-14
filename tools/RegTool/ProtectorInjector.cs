using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using SoulsFormats;

namespace LootForge.RegTool
{
    /// <summary>
    /// Service responsible for validating and injecting custom armor (protector)
    /// rows into Elden Ring's EquipParamProtector table.
    /// Handles gender coverage, unisex flagging, authentic icon inheritance, and mesh fallbacks.
    /// Adheres to [CS-MODULAR] and [CS-GRANULARITY].
    /// </summary>
    public static class ProtectorInjector
    {
        private static readonly Dictionary<(int, int, int), PARAM.Row> _baseProtectorCache = new();

        public static void ResetCache()
        {
            _baseProtectorCache.Clear();
        }

        public static bool IsValidProtectorRow(PARAM.Row r)
        {
            if (r.ID <= 0 || r.ID >= 9000000) return false;
            if (r.ID >= 10000 && r.ID <= 10300) return false; // Default naked skin rows
            if (r.ID >= 900000 && r.ID < 902000) return false; // DS3 test rows
            if (r.ID >= 1960000 && r.ID <= 1980000) return false;

            if (string.IsNullOrWhiteSpace(r.Name)) return false;
            if (r.Name.Contains("[ERROR]", StringComparison.OrdinalIgnoreCase)) return false;
            if (r.Name.Contains("Dummy", StringComparison.OrdinalIgnoreCase)) return false;
            if (r.Name.StartsWith("?")) return false;
            if (r.Name.StartsWith("dummy", StringComparison.OrdinalIgnoreCase)) return false;

            int iconM = ParamHelper.GetCellInt(r, "iconIdM");
            int iconF = ParamHelper.GetCellInt(r, "iconIdF");
            if (iconM <= 0 && iconF <= 0) return false;
            if (iconM == 3141 || iconM == 3142 || iconF == 3141 || iconF == 3142) return false;

            return true;
        }

        public static PARAM.Row? ResolveBaseProtectorRow(
            int baseCloneId,
            int targetModelId,
            int slotOffset,
            Dictionary<int, PARAM.Row> rowMap,
            PARAM param)
        {
            var cacheKey = (baseCloneId, targetModelId, slotOffset);
            if (_baseProtectorCache.TryGetValue(cacheKey, out var cached))
                return cached;

            int targetCat = slotOffset == 0 ? 0 : slotOffset == 100 ? 1 : slotOffset == 200 ? 2 : 3;
            PARAM.Row? baseRow = null;

            // 1. Direct baseCloneId lookup if valid and matching targetModelId (if specified)
            if (baseCloneId > 0 && rowMap.TryGetValue(baseCloneId, out var cand) && IsValidProtectorRow(cand))
            {
                int candModel = ParamHelper.GetCellInt(cand, "equipModelId");
                if (targetModelId <= 0 || candModel == targetModelId)
                {
                    baseRow = cand;
                }
            }

            // 2. Direct lookup by authentic equipModelId
            if (baseRow == null && targetModelId > 0)
            {
                baseRow = param.Rows.FirstOrDefault(r => IsValidProtectorRow(r) && ParamHelper.GetCellInt(r, "protectorCategory") == targetCat && ParamHelper.GetCellInt(r, "equipModelId") == targetModelId)
                       ?? param.Rows.FirstOrDefault(r => IsValidProtectorRow(r) && ParamHelper.GetCellInt(r, "equipModelId") == targetModelId);
            }

            // 2b. Nearby model variant in same set family (within +- 10)
            if (baseRow == null && targetModelId > 0)
            {
                baseRow = param.Rows
                    .Where(r => IsValidProtectorRow(r) && ParamHelper.GetCellInt(r, "protectorCategory") == targetCat && Math.Abs(ParamHelper.GetCellInt(r, "equipModelId") - targetModelId) <= 10)
                    .OrderBy(r => Math.Abs(ParamHelper.GetCellInt(r, "equipModelId") - targetModelId))
                    .FirstOrDefault();
            }

            // 3. Category and slot fallback
            if (baseRow == null)
            {
                baseRow = param.Rows.FirstOrDefault(r => IsValidProtectorRow(r) && ParamHelper.GetCellInt(r, "protectorCategory") == targetCat && r.ID % 1000 == slotOffset)
                       ?? param.Rows.FirstOrDefault(r => IsValidProtectorRow(r) && ParamHelper.GetCellInt(r, "protectorCategory") == targetCat)
                       ?? param.Rows.FirstOrDefault(r => IsValidProtectorRow(r));
            }

            // 4. Retail fallback set
            if (baseRow == null)
            {
                int fallbackId = slotOffset switch
                {
                    0 => 40000,   // Scale Helm
                    100 => 40100, // Scale Armor
                    200 => 40200, // Iron Gauntlets
                    300 => 40300, // Leather Boots
                    _ => 40100
                };
                baseRow = (rowMap.TryGetValue(fallbackId, out var fb) ? fb : null)
                       ?? param.Rows.FirstOrDefault(r => IsValidProtectorRow(r));
            }

            if (baseRow != null)
            {
                _baseProtectorCache[cacheKey] = baseRow;
            }

            return baseRow;
        }

        public static void InjectProtector(
            JsonElement ep,
            int newParamId,
            int baseCloneId,
            int targetModelId,
            int slotOffset,
            string rowName,
            Dictionary<int, PARAM.Row> rowMap,
            PARAM param,
            Dictionary<int, int> itemIdToVanillaSourceId,
            ref int injectedEquipCount)
        {
            if (rowMap.TryGetValue(newParamId, out var existingRow))
            {
                bool updateExisting = ep.TryGetProperty("update_existing", out var ue) && ue.GetBoolean();
                if (updateExisting && ep.TryGetProperty("field_updates", out var fieldsElUpdate) && fieldsElUpdate.ValueKind == JsonValueKind.Object)
                {
                    ApplyFieldUpdates(existingRow, fieldsElUpdate);
                    injectedEquipCount++;
                }
                return;
            }

            var baseRow = ResolveBaseProtectorRow(baseCloneId, targetModelId, slotOffset, rowMap, param);
            if (baseRow == null)
            {
                Console.WriteLine($"[RegTool WARN] Cannot find valid base row to clone for EquipParamProtector ID {newParamId}");
                return;
            }

            itemIdToVanillaSourceId[newParamId] = baseRow.ID;

            var newRow = new PARAM.Row(baseRow)
            {
                ID = newParamId,
                Name = rowName
            };

            if (ep.TryGetProperty("field_updates", out var fieldsEl) && fieldsEl.ValueKind == JsonValueKind.Object)
            {
                bool hasMaleFiles = true;
                bool hasFemaleFiles = true;
                int fallbackModelId = 220; // Commoner's Garb

                if (fieldsEl.TryGetProperty("_lf_hasMaleFiles", out var hm)) hasMaleFiles = hm.GetInt32() != 0;
                if (fieldsEl.TryGetProperty("_lf_hasFemaleFiles", out var hf)) hasFemaleFiles = hf.GetInt32() != 0;
                if (fieldsEl.TryGetProperty("_lf_fallbackModelId", out var fm)) fallbackModelId = fm.GetInt32();

                ApplyFieldUpdates(newRow, fieldsEl);

                if (!hasMaleFiles && !hasFemaleFiles && fallbackModelId > 0)
                {
                    ParamHelper.SetCellIfExists(newRow, "equipModelId", (ushort)fallbackModelId);
                    Console.WriteLine($"[RegTool WARN] Mod has no mesh files at all for ID {newParamId}; using vanilla fallback model {fallbackModelId}");
                }
            }

            // Unisex and authentic icon inheritance
            ParamHelper.SetCellIfExists(newRow, "equipModelGender", (byte)0);

            int iconM = ParamHelper.GetCellInt(newRow, "iconIdM");
            int iconF = ParamHelper.GetCellInt(newRow, "iconIdF");
            int baseIconM = ParamHelper.GetCellInt(baseRow, "iconIdM");
            int baseIconF = ParamHelper.GetCellInt(baseRow, "iconIdF");

            if ((iconM <= 0 || iconM == 3141 || iconM == 3142) && baseIconM > 0 && baseIconM != 3141 && baseIconM != 3142)
                ParamHelper.SetCellIfExists(newRow, "iconIdM", (ushort)baseIconM);
            if ((iconF <= 0 || iconF == 3141 || iconF == 3142) && baseIconF > 0 && baseIconF != 3141 && baseIconF != 3142)
                ParamHelper.SetCellIfExists(newRow, "iconIdF", (ushort)baseIconF);

            int finalM = ParamHelper.GetCellInt(newRow, "iconIdM");
            int finalF = ParamHelper.GetCellInt(newRow, "iconIdF");
            if ((finalM <= 0 || finalM == 3141 || finalM == 3142) && finalF > 0 && finalF != 3141 && finalF != 3142)
                ParamHelper.SetCellIfExists(newRow, "iconIdM", (ushort)finalF);
            if ((finalF <= 0 || finalF == 3141 || finalF == 3142) && finalM > 0 && finalM != 3141 && finalM != 3142)
                ParamHelper.SetCellIfExists(newRow, "iconIdF", (ushort)finalM);

            int curM = ParamHelper.GetCellInt(newRow, "iconIdM");
            int curF = ParamHelper.GetCellInt(newRow, "iconIdF");
            if (curM <= 0 || curM == 3141 || curM == 3142)
            {
                ushort defaultIcon = (ushort)(slotOffset switch
                {
                    0 => 13000,   // Scale Helm
                    100 => 14481, // Finger Maiden Robe
                    200 => 13002, // Iron Gauntlets
                    300 => 13003, // Leather Boots
                    _ => 13001
                });
                ParamHelper.SetCellIfExists(newRow, "iconIdM", defaultIcon);
            }
            if (curF <= 0 || curF == 3141 || curF == 3142)
            {
                ushort finalMIcon = (ushort)ParamHelper.GetCellInt(newRow, "iconIdM");
                ParamHelper.SetCellIfExists(newRow, "iconIdF", finalMIcon > 0 ? finalMIcon : (ushort)13001);
            }

            rowMap[newParamId] = newRow;
            param.Rows.Add(newRow);
            injectedEquipCount++;
        }

        private static void ApplyFieldUpdates(PARAM.Row row, JsonElement fieldsEl)
        {
            foreach (var prop in fieldsEl.EnumerateObject())
            {
                string fieldName = prop.Name;
                if (fieldName.StartsWith("_lf_", StringComparison.OrdinalIgnoreCase))
                    continue;

                if (fieldName.EndsWith("ModelId", StringComparison.OrdinalIgnoreCase))
                {
                    fieldName = "equipModelId";
                }

                var cell = row.Cells.FirstOrDefault(c => string.Equals(c.Def.InternalName, fieldName, StringComparison.OrdinalIgnoreCase));
                if (cell != null)
                {
                    ParamHelper.SetCellValue(cell, prop.Value);
                }
            }
        }
    }
}

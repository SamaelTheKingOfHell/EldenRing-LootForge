using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using SoulsFormats;

namespace LootForge.RegTool
{
    /// <summary>
    /// Service responsible for validating and injecting custom accessory (talisman)
    /// rows into Elden Ring's EquipParamAccessory table.
    /// Ensures authentic talisman icon inheritance and valid non-placeholder IDs.
    /// Adheres to [CS-MODULAR] and [CS-GRANULARITY].
    /// </summary>
    public static class AccessoryInjector
    {
        public const ushort DefaultAccessoryIconId = 18000; // Crimson Amber Medallion authentic icon

        private static readonly Dictionary<int, PARAM.Row> _baseAccessoryCache = new();

        public static void ResetCache()
        {
            _baseAccessoryCache.Clear();
        }

        public static bool IsValidAccessoryRow(PARAM.Row r)
        {
            if (r.ID <= 0 || r.ID >= 9000000) return false;
            if (r.ID >= 9000000 && r.ID < 9900000 && r.Name != null && r.Name.Contains("[LootForge]")) return false;

            // FromSoftware strips row names in production regulation files.
            // Do not reject rows solely due to empty names if they have authentic talisman attributes.
            if (!string.IsNullOrWhiteSpace(r.Name))
            {
                if (r.Name.Contains("[ERROR]", StringComparison.OrdinalIgnoreCase)) return false;
                if (r.Name.Contains("Dummy", StringComparison.OrdinalIgnoreCase)) return false;
                if (r.Name.StartsWith("?")) return false;
                if (r.Name.StartsWith("dummy", StringComparison.OrdinalIgnoreCase)) return false;
            }

            int icon = ParamHelper.GetCellInt(r, "iconId");
            int isDeposit = ParamHelper.GetCellInt(r, "isDeposit");

            // Authentic talismans have iconId >= 18000 or isDeposit == 1 with positive icon
            if (icon <= 0 && isDeposit != 1) return false;

            return true;
        }

        public static PARAM.Row? ResolveBaseAccessoryRow(
            int baseCloneId,
            Dictionary<int, PARAM.Row> rowMap,
            PARAM param)
        {
            if (_baseAccessoryCache.TryGetValue(baseCloneId, out var cached))
                return cached;

            PARAM.Row? baseRow = null;

            // 1. Direct base clone lookup
            if (baseCloneId > 0 && rowMap.TryGetValue(baseCloneId, out var cand) && IsValidAccessoryRow(cand))
            {
                baseRow = cand;
            }

            // 2. Direct base clone even if row name was stripped in regulation
            if (baseRow == null && baseCloneId > 0 && rowMap.TryGetValue(baseCloneId, out var rawCand) && rawCand.ID > 0)
            {
                baseRow = rawCand;
            }

            // 3. Fallback to Crimson Amber Medallion (ID 1000)
            if (baseRow == null && rowMap.TryGetValue(1000, out var fallback1000))
            {
                baseRow = fallback1000;
            }

            // 4. Any valid accessory row
            if (baseRow == null)
            {
                baseRow = param.Rows.FirstOrDefault(IsValidAccessoryRow);
            }

            // 5. Guaranteed retail fallback row
            if (baseRow == null)
            {
                baseRow = param.Rows.FirstOrDefault(r => r.ID > 0 && r.ID < 9000000);
            }

            if (baseRow != null)
            {
                _baseAccessoryCache[baseCloneId] = baseRow;
            }

            return baseRow;
        }

        public static void InjectAccessory(
            JsonElement ep,
            int newParamId,
            int baseCloneId,
            string rowName,
            Dictionary<int, PARAM.Row> rowMap,
            PARAM param,
            Dictionary<int, int> itemIdToVanillaSourceId,
            ref int injectedEquipCount)
        {
            // If already present in table, check if update_existing is requested
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

            var baseRow = ResolveBaseAccessoryRow(baseCloneId, rowMap, param);
            if (baseRow == null)
            {
                Console.WriteLine($"[RegTool WARN] Cannot find valid base row to clone for EquipParamAccessory ID {newParamId}");
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
                ApplyFieldUpdates(newRow, fieldsEl);
            }

            // Ensure valid authentic talisman icon (never 0, negative, or invalid placeholder 1000)
            int icon = ParamHelper.GetCellInt(newRow, "iconId");
            int baseIcon = ParamHelper.GetCellInt(baseRow, "iconId");

            if (icon <= 0 || icon == 1000)
            {
                if (baseIcon >= 18000)
                {
                    ParamHelper.SetCellIfExists(newRow, "iconId", (ushort)baseIcon);
                }
                else
                {
                    ParamHelper.SetCellIfExists(newRow, "iconId", DefaultAccessoryIconId);
                }
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

                var cell = row.Cells.FirstOrDefault(c => string.Equals(c.Def.InternalName, fieldName, StringComparison.OrdinalIgnoreCase));
                if (cell != null)
                {
                    ParamHelper.SetCellValue(cell, prop.Value);
                }
            }
        }
    }
}

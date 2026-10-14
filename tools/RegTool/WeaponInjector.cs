using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using SoulsFormats;

namespace LootForge.RegTool
{
    /// <summary>
    /// Service responsible for validating and injecting custom weapon
    /// rows into Elden Ring's EquipParamWeapon table.
    /// Handles base weapon cloning, model matching, and valid icon inheritance.
    /// Adheres to [CS-MODULAR] and [CS-GRANULARITY].
    /// </summary>
    public static class WeaponInjector
    {
        private static readonly Dictionary<(int, int), PARAM.Row> _baseWeaponCache = new();

        public static void ResetCache()
        {
            _baseWeaponCache.Clear();
        }

        public static bool IsValidWeaponRow(PARAM.Row r)
        {
            if (r.ID <= 0 || r.ID >= 90000000) return false;
            if (r.ID >= 9000000 && r.ID < 9900000 && r.Name != null && r.Name.Contains("[LootForge]")) return false;

            if (string.IsNullOrWhiteSpace(r.Name)) return false;
            if (r.Name.Contains("[ERROR]", StringComparison.OrdinalIgnoreCase)) return false;
            if (r.Name.Contains("Dummy", StringComparison.OrdinalIgnoreCase)) return false;
            if (r.Name.StartsWith("?")) return false;
            if (r.Name.StartsWith("dummy", StringComparison.OrdinalIgnoreCase)) return false;

            int icon = ParamHelper.GetCellInt(r, "iconId");
            if (icon <= 0) return false;
            if (icon == 3141 || icon == 3142) return false;

            return true;
        }

        public static PARAM.Row? ResolveBaseWeaponRow(
            int baseCloneId,
            int targetModelId,
            Dictionary<int, PARAM.Row> rowMap,
            PARAM param)
        {
            var cacheKey = (baseCloneId, targetModelId);
            if (_baseWeaponCache.TryGetValue(cacheKey, out var cached))
                return cached;

            PARAM.Row? baseRow = null;

            // 1. Direct baseCloneId lookup if valid and matching targetModelId
            if (baseCloneId > 0 && rowMap.TryGetValue(baseCloneId, out var cand) && IsValidWeaponRow(cand))
            {
                int candModel = ParamHelper.GetCellInt(cand, "equipModelId");
                if (targetModelId <= 0 || candModel == targetModelId)
                {
                    baseRow = cand;
                }
            }

            // 2. Direct lookup by authentic equipModelId (prefer base uninfused weapon ID % 100 == 0)
            if (baseRow == null && targetModelId > 0)
            {
                baseRow = param.Rows.FirstOrDefault(r => IsValidWeaponRow(r) && ParamHelper.GetCellInt(r, "equipModelId") == targetModelId && (r.ID % 100 == 0))
                       ?? param.Rows.FirstOrDefault(r => IsValidWeaponRow(r) && ParamHelper.GetCellInt(r, "equipModelId") == targetModelId);
            }

            // 3. Fallback: first valid weapon row
            if (baseRow == null)
            {
                baseRow = param.Rows.FirstOrDefault(IsValidWeaponRow);
            }

            // 4. Guaranteed retail fallback: Longsword (ID 2020000)
            if (baseRow == null)
            {
                baseRow = (rowMap.TryGetValue(2020000, out var fb) ? fb : null)
                       ?? param.Rows.FirstOrDefault(IsValidWeaponRow);
            }

            if (baseRow != null)
            {
                _baseWeaponCache[cacheKey] = baseRow;
            }

            return baseRow;
        }

        public static void InjectWeapon(
            JsonElement ep,
            int newParamId,
            int baseCloneId,
            int targetModelId,
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

            var baseRow = ResolveBaseWeaponRow(baseCloneId, targetModelId, rowMap, param);
            if (baseRow == null)
            {
                Console.WriteLine($"[RegTool WARN] Cannot find valid base row to clone for EquipParamWeapon ID {newParamId}");
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

            // Ensure valid authentic weapon icon
            int icon = ParamHelper.GetCellInt(newRow, "iconId");
            int baseIcon = ParamHelper.GetCellInt(baseRow, "iconId");
            if ((icon <= 0 || icon == 3141 || icon == 3142) && baseIcon > 0 && baseIcon != 3141 && baseIcon != 3142)
            {
                ParamHelper.SetCellIfExists(newRow, "iconId", (ushort)baseIcon);
            }
            int curIcon = ParamHelper.GetCellInt(newRow, "iconId");
            if (curIcon <= 0 || curIcon == 3141 || curIcon == 3142)
            {
                ParamHelper.SetCellIfExists(newRow, "iconId", (ushort)2020); // Longsword
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

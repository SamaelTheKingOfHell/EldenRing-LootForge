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
        private static Dictionary<int, PARAM.Row>? _modelIdToWeaponMap;
        private static PARAM.Row? _defaultValidWeapon;

        public static void ResetCache()
        {
            _baseWeaponCache.Clear();
            _modelIdToWeaponMap = null;
            _defaultValidWeapon = null;
        }

        private static void EnsureModelIndex(PARAM param)
        {
            if (_modelIdToWeaponMap != null) return;
            _modelIdToWeaponMap = new Dictionary<int, PARAM.Row>();
            if (param.Rows.Count == 0) return;
            int modelIdx = -1, iconIdx = -1;
            for (int i = 0; i < param.Rows[0].Cells.Count; i++)
            {
                var name = param.Rows[0].Cells[i].Def?.InternalName;
                if (string.Equals(name, "equipModelId", StringComparison.OrdinalIgnoreCase)) modelIdx = i;
                else if (string.Equals(name, "iconId", StringComparison.OrdinalIgnoreCase)) iconIdx = i;
            }

            foreach (var r in param.Rows)
            {
                if (r.ID <= 0 || r.ID >= 90000000) continue;
                if (r.ID >= 9000000 && r.ID < 9900000 && r.Name != null && r.Name.Contains("[LootForge]")) continue;
                if (!string.IsNullOrWhiteSpace(r.Name) && (r.Name.Contains("[ERROR]", StringComparison.OrdinalIgnoreCase) || r.Name.Contains("Dummy", StringComparison.OrdinalIgnoreCase) || r.Name.StartsWith("?"))) continue;
                int icon = iconIdx >= 0 ? ParamHelper.GetCellIntFast(r, iconIdx) : 0;
                if (icon <= 0 || icon == 3141 || icon == 3142) continue;

                if (_defaultValidWeapon == null) _defaultValidWeapon = r;
                if (modelIdx >= 0)
                {
                    int mId = ParamHelper.GetCellIntFast(r, modelIdx);
                    if (mId > 0 && (!_modelIdToWeaponMap.ContainsKey(mId) || (r.ID % 100 == 0)))
                        _modelIdToWeaponMap[mId] = r;
                }
            }
        }

        public static bool IsValidWeaponRow(PARAM.Row r)
        {
            if (r.ID <= 0 || r.ID >= 90000000) return false;
            if (r.ID >= 9000000 && r.ID < 9900000 && r.Name != null && r.Name.Contains("[LootForge]")) return false;

            string sourceName = r.Name ?? "";
            if (sourceName.Contains("[ERROR]", StringComparison.OrdinalIgnoreCase)) return false;
            if (sourceName.Contains("Dummy", StringComparison.OrdinalIgnoreCase)) return false;
            if (sourceName.StartsWith("?")) return false;
            if (sourceName.StartsWith("dummy", StringComparison.OrdinalIgnoreCase)) return false;

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

            EnsureModelIndex(param);
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

            // 2. Direct O(1) lookup by authentic equipModelId
            if (baseRow == null && targetModelId > 0 && _modelIdToWeaponMap != null && _modelIdToWeaponMap.TryGetValue(targetModelId, out var mRow))
            {
                baseRow = mRow;
            }

            // 3. Fallback: first valid weapon row or Longsword (ID 2020000)
            baseRow ??= _defaultValidWeapon ?? (rowMap.TryGetValue(2020000, out var fb) ? fb : null);

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
                if (!updateExisting)
                    throw new InvalidOperationException($"Equipment ID {newParamId} already exists. Refusing to discard or overwrite an item.");
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

                var cell = ParamHelper.FindCell(row, fieldName);
                if (cell != null)
                {
                    ParamHelper.SetCellValue(cell, prop.Value);
                }
            }
        }
    }
}

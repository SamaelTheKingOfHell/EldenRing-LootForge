using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using SoulsFormats;

namespace LootForge.RegTool
{
    /// <summary>
    /// Service responsible for injecting custom mod equipment rows into Elden Ring
    /// EquipParamProtector and EquipParamWeapon tables.
    /// Ensures authentic base row cloning and valid icons without dummy placeholders.
    /// Adheres to [CS-MODULAR] and [CS-GRANULARITY].
    /// </summary>
    public static class EquipInjector
    {
        public static bool IsValidProtectorRow(PARAM.Row r)
        {
            if (r.ID <= 0 || r.ID >= 9000000) return false;
            if (!string.IsNullOrEmpty(r.Name))
            {
                if (r.Name.Contains("[ERROR]", StringComparison.OrdinalIgnoreCase)) return false;
                if (r.Name.Contains("Dummy", StringComparison.OrdinalIgnoreCase)) return false;
                if (r.Name.StartsWith("?")) return false;
            }
            int iconM = ParamHelper.GetCellInt(r, "iconIdM");
            int iconF = ParamHelper.GetCellInt(r, "iconIdF");
            return iconM > 0 || iconF > 0;
        }

        public static bool IsValidWeaponRow(PARAM.Row r)
        {
            if (r.ID <= 0 || r.ID >= 9000000) return false;
            if (!string.IsNullOrEmpty(r.Name))
            {
                if (r.Name.Contains("[ERROR]", StringComparison.OrdinalIgnoreCase)) return false;
                if (r.Name.Contains("Dummy", StringComparison.OrdinalIgnoreCase)) return false;
                if (r.Name.StartsWith("?")) return false;
            }
            int icon = ParamHelper.GetCellInt(r, "iconId");
            return icon > 0;
        }

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

                // 1. Try by direct baseCloneId if valid
                if (baseCloneId > 0)
                {
                    var cand = param.Rows.FirstOrDefault(r => r.ID == baseCloneId);
                    if (cand != null && (isProtector ? IsValidProtectorRow(cand) : IsValidWeaponRow(cand)))
                    {
                        baseRow = cand;
                    }
                }

                // 2. Try by authentic equipModelId (matching targetModelId)
                if (baseRow == null && targetModelId > 0)
                {
                    if (isProtector)
                    {
                        baseRow = param.Rows.FirstOrDefault(r => IsValidProtectorRow(r) && r.ID % 1000 == slotOffset && ParamHelper.GetCellInt(r, "equipModelId") == targetModelId)
                               ?? param.Rows.FirstOrDefault(r => IsValidProtectorRow(r) && ParamHelper.GetCellInt(r, "equipModelId") == targetModelId);
                    }
                    else
                    {
                        baseRow = param.Rows.FirstOrDefault(r => IsValidWeaponRow(r) && ParamHelper.GetCellInt(r, "equipModelId") == targetModelId);
                    }
                }

                // 3. Fallback: ANY authentic valid vanilla row (guaranteed icon > 0 and no dummy row)
                if (baseRow == null)
                {
                    if (isProtector)
                    {
                        baseRow = param.Rows.FirstOrDefault(r => IsValidProtectorRow(r) && r.ID % 1000 == slotOffset)
                               ?? param.Rows.FirstOrDefault(r => IsValidProtectorRow(r));
                    }
                    else
                    {
                        baseRow = param.Rows.FirstOrDefault(r => IsValidWeaponRow(r));
                    }
                }

                if (baseRow == null)
                {
                    Console.WriteLine($"[RegTool WARN] Cannot find valid base row to clone for {tableName} ID {newParamId}");
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
                    int iconF = ParamHelper.GetCellInt(newRow, "iconIdF");
                    int baseIconM = ParamHelper.GetCellInt(baseRow, "iconIdM");
                    int baseIconF = ParamHelper.GetCellInt(baseRow, "iconIdF");

                    if (iconM <= 0 && baseIconM > 0)
                        ParamHelper.SetCellIfExists(newRow, "iconIdM", (ushort)baseIconM);
                    if (iconF <= 0 && baseIconF > 0)
                        ParamHelper.SetCellIfExists(newRow, "iconIdF", (ushort)baseIconF);

                    // Cross-gender safeguard if one is missing
                    int finalM = ParamHelper.GetCellInt(newRow, "iconIdM");
                    int finalF = ParamHelper.GetCellInt(newRow, "iconIdF");
                    if (finalM <= 0 && finalF > 0) ParamHelper.SetCellIfExists(newRow, "iconIdM", (ushort)finalF);
                    if (finalF <= 0 && finalM > 0) ParamHelper.SetCellIfExists(newRow, "iconIdF", (ushort)finalM);
                }
                else
                {
                    int icon = ParamHelper.GetCellInt(newRow, "iconId");
                    int baseIcon = ParamHelper.GetCellInt(baseRow, "iconId");
                    if (icon <= 0 && baseIcon > 0)
                    {
                        ParamHelper.SetCellIfExists(newRow, "iconId", (ushort)baseIcon);
                    }
                }

                param.Rows.Add(newRow);
                injectedEquipCount++;
            }
        }
    }
}

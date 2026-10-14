using System;
using System.Collections.Generic;
using System.Text.Json;
using SoulsFormats;

namespace LootForge.RegTool
{
    /// <summary>
    /// High-level equipment injection dispatcher.
    /// Delegates row cloning and validation to specialized, isolated injectors:
    /// - ProtectorInjector for EquipParamProtector
    /// - WeaponInjector for EquipParamWeapon
    /// - AccessoryInjector for EquipParamAccessory
    /// Adheres to [CS-MODULAR], [CS-DECOUPLE], and [CS-GRANULARITY].
    /// </summary>
    public static class EquipInjector
    {
        public static bool IsValidProtectorRow(PARAM.Row r) => ProtectorInjector.IsValidProtectorRow(r);
        public static bool IsValidWeaponRow(PARAM.Row r) => WeaponInjector.IsValidWeaponRow(r);
        public static bool IsValidAccessoryRow(PARAM.Row r) => AccessoryInjector.IsValidAccessoryRow(r);

        private static readonly Dictionary<string, Dictionary<int, PARAM.Row>> _rowMapByTable = new(StringComparer.OrdinalIgnoreCase);

        public static void ResetCache()
        {
            _rowMapByTable.Clear();
            ProtectorInjector.ResetCache();
            WeaponInjector.ResetCache();
            AccessoryInjector.ResetCache();
        }

        public static void InjectEquipParams(
            JsonElement equipParamsEl,
            Func<string, string, (PARAM Param, BinderFile File)> getOrLoadParam,
            Dictionary<int, bool> itemIdToIsProtector,
            Dictionary<int, bool> itemIdToIsWeapon,
            Dictionary<int, int> itemIdToVanillaSourceId,
            ref int injectedEquipCount,
            Dictionary<int, bool>? itemIdToIsAccessory = null)
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
                bool isAccessory = tableName == "EquipParamAccessory";
                bool isWeapon = tableName == "EquipParamWeapon";

                itemIdToIsProtector[newParamId] = isProtector;
                itemIdToIsWeapon[newParamId] = isWeapon;
                if (itemIdToIsAccessory != null)
                    itemIdToIsAccessory[newParamId] = isAccessory;

                string defName = tableName;
                var (param, _) = getOrLoadParam(tableName, defName);

                // Index rows for O(1) lookups
                if (!_rowMapByTable.TryGetValue(tableName, out var rowMap))
                {
                    rowMap = new Dictionary<int, PARAM.Row>(param.Rows.Count + 100000);
                    foreach (var r in param.Rows)
                    {
                        rowMap[r.ID] = r;
                    }
                    _rowMapByTable[tableName] = rowMap;
                }

                if (isAccessory)
                {
                    AccessoryInjector.InjectAccessory(
                        ep,
                        newParamId,
                        baseCloneId,
                        rowName,
                        rowMap,
                        param,
                        itemIdToVanillaSourceId,
                        ref injectedEquipCount
                    );
                }
                else if (isProtector)
                {
                    ProtectorInjector.InjectProtector(
                        ep,
                        newParamId,
                        baseCloneId,
                        targetModelId,
                        slotOffset,
                        rowName,
                        rowMap,
                        param,
                        itemIdToVanillaSourceId,
                        ref injectedEquipCount
                    );
                }
                else if (isWeapon)
                {
                    WeaponInjector.InjectWeapon(
                        ep,
                        newParamId,
                        baseCloneId,
                        targetModelId,
                        rowName,
                        rowMap,
                        param,
                        itemIdToVanillaSourceId,
                        ref injectedEquipCount
                    );
                }
                else
                {
                    Console.WriteLine($"[RegTool WARN] Unsupported equipment param table: {tableName}");
                }
            }
        }
    }
}

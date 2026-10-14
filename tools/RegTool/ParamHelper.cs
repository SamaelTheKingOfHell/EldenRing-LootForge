using System;
using System.Linq;
using System.Text.Json;
using SoulsFormats;

namespace LootForge.RegTool
{
    /// <summary>
    /// Utility methods for reading, writing, and type-converting PARAM cell values.
    /// Adheres to [CS-MODULAR] by encapsulating low-level cell manipulation.
    /// </summary>
    public static class ParamHelper
    {
        public static int GetCellInt(PARAM.Row row, string fieldName)
        {
            var cell = row.Cells.FirstOrDefault(c => string.Equals(c.Def.InternalName, fieldName, StringComparison.OrdinalIgnoreCase));
            if (cell == null || cell.Value == null) return 0;
            try
            {
                return Convert.ToInt32(cell.Value);
            }
            catch
            {
                return 0;
            }
        }

        public static void SetCellIfExists(PARAM.Row row, string fieldName, object value)
        {
            var cell = row.Cells.FirstOrDefault(c => string.Equals(c.Def.InternalName, fieldName, StringComparison.OrdinalIgnoreCase));
            if (cell != null)
            {
                cell.Value = value;
            }
        }

        public static void SetCellValue(PARAM.Cell cell, JsonElement jsonVal)
        {
            switch (cell.Def.DisplayType)
            {
                case PARAMDEF.DefType.s8:
                    cell.Value = (sbyte)jsonVal.GetInt32();
                    break;
                case PARAMDEF.DefType.u8:
                    cell.Value = (byte)jsonVal.GetInt32();
                    break;
                case PARAMDEF.DefType.s16:
                    cell.Value = (short)jsonVal.GetInt32();
                    break;
                case PARAMDEF.DefType.u16:
                    cell.Value = (ushort)jsonVal.GetInt32();
                    break;
                case PARAMDEF.DefType.s32:
                case PARAMDEF.DefType.b32:
                    cell.Value = jsonVal.GetInt32();
                    break;
                case PARAMDEF.DefType.u32:
                    cell.Value = (uint)jsonVal.GetInt64();
                    break;
                case PARAMDEF.DefType.f32:
                    cell.Value = (float)jsonVal.GetDouble();
                    break;
                case PARAMDEF.DefType.f64:
                    cell.Value = jsonVal.GetDouble();
                    break;
                case PARAMDEF.DefType.fixstr:
                case PARAMDEF.DefType.fixstrW:
                    cell.Value = jsonVal.GetString() ?? "";
                    break;
                default:
                    break;
            }
        }

        private static readonly System.Collections.Generic.Dictionary<string, string> ParamdefAliases = new(StringComparer.OrdinalIgnoreCase)
        {
            { "AtkParam_Pc", "AtkParam" },
            { "AtkParam_Npc", "AtkParam" },
            { "BehaviorParam_PC", "BehaviorParam" },
            { "ItemLotParam_enemy", "ItemLotParam" },
            { "ItemLotParam_map", "ItemLotParam" },
            { "SpEffectParam", "SpEffect" },
            { "SpEffectVfxParam", "SpEffectVfx" },
        };

        public static string? ResolveDefFile(string defsDir, string defName)
        {
            if (ParamdefAliases.TryGetValue(defName, out var alias))
            {
                string path = System.IO.Path.Combine(defsDir, $"{alias}.xml");
                if (System.IO.File.Exists(path)) return path;
            }

            foreach (var suffix in new[] { "_Pc", "_PC", "_enemy", "_map" })
            {
                if (defName.EndsWith(suffix, StringComparison.OrdinalIgnoreCase))
                {
                    string candidate = defName.Substring(0, defName.Length - suffix.Length);
                    string path = System.IO.Path.Combine(defsDir, $"{candidate}.xml");
                    if (System.IO.File.Exists(path)) return path;
                }
            }

            if (defName.EndsWith("Param", StringComparison.OrdinalIgnoreCase) && defName.Length > 5)
            {
                string candidate = defName.Substring(0, defName.Length - 5);
                string path = System.IO.Path.Combine(defsDir, $"{candidate}.xml");
                if (System.IO.File.Exists(path)) return path;
            }

            try
            {
                if (System.IO.Directory.Exists(defsDir))
                {
                    var match = System.IO.Directory.EnumerateFiles(defsDir, "*.xml", System.IO.SearchOption.TopDirectoryOnly)
                        .FirstOrDefault(f => System.IO.Path.GetFileNameWithoutExtension(f).Equals(defName, StringComparison.OrdinalIgnoreCase));
                    if (match != null) return match;
                }
            }
            catch { }

            return null;
        }
    }
}

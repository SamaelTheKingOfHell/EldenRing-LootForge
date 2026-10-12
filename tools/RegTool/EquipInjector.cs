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
            // Exclude naked body rows (unarmored default skin: 10000..10300)
            if (r.ID >= 10000 && r.ID <= 10300) return false;
            // Exclude developer test ranges (DS3 test rows and internal debug rows)
            if (r.ID >= 900000 && r.ID < 902000) return false; // 901200, 901600 are test rows; 902000+ are authentic Finger Maiden sets
            if (r.ID >= 1960000 && r.ID <= 1980000) return false;

            // Reject rows with empty or whitespace names (developer test rows)
            if (string.IsNullOrWhiteSpace(r.Name)) return false;

            // Reject placeholder strings
            if (r.Name.Contains("[ERROR]", StringComparison.OrdinalIgnoreCase)) return false;
            if (r.Name.Contains("Dummy", StringComparison.OrdinalIgnoreCase)) return false;
            if (r.Name.StartsWith("?")) return false;
            if (r.Name.StartsWith("dummy", StringComparison.OrdinalIgnoreCase)) return false;

            int iconM = ParamHelper.GetCellInt(r, "iconIdM");
            int iconF = ParamHelper.GetCellInt(r, "iconIdF");
            if (iconM <= 0 && iconF <= 0) return false;

            // Reject non-existent test icons (DS3 orphan textures that render as gray "ICON" box)
            if (iconM == 3141 || iconM == 3142 || iconF == 3141 || iconF == 3142) return false;

            return true;
        }

        public static bool IsValidWeaponRow(PARAM.Row r)
        {
            if (r.ID <= 0 || r.ID >= 90000000) return false;
            // Exclude injected LootForge rows
            if (r.ID >= 9000000 && r.ID < 9900000 && r.Name != null && r.Name.Contains("[LootForge]")) return false;

            // Reject rows with empty or whitespace names
            if (string.IsNullOrWhiteSpace(r.Name)) return false;

            // Reject placeholder strings
            if (r.Name.Contains("[ERROR]", StringComparison.OrdinalIgnoreCase)) return false;
            if (r.Name.Contains("Dummy", StringComparison.OrdinalIgnoreCase)) return false;
            if (r.Name.StartsWith("?")) return false;
            if (r.Name.StartsWith("dummy", StringComparison.OrdinalIgnoreCase)) return false;

            int icon = ParamHelper.GetCellInt(r, "iconId");
            if (icon <= 0) return false;
            if (icon == 3141 || icon == 3142) return false;

            return true;
        }

        private static readonly Dictionary<string, Dictionary<int, PARAM.Row>> _rowMapByTable = new(StringComparer.OrdinalIgnoreCase);
        private static readonly Dictionary<(string, int, int, int), PARAM.Row> _baseRowCache = new();

        public static void ResetCache()
        {
            _rowMapByTable.Clear();
            _baseRowCache.Clear();
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

                // If already present in table, check if update_existing is requested
                if (rowMap.TryGetValue(newParamId, out var existingRow))
                {
                    bool updateExisting = ep.TryGetProperty("update_existing", out var ue) && ue.GetBoolean();
                    if (updateExisting)
                    {
                        if (ep.TryGetProperty("field_updates", out var fieldsElUpdate) && fieldsElUpdate.ValueKind == JsonValueKind.Object)
                        {
                            foreach (var prop in fieldsElUpdate.EnumerateObject())
                            {
                                string fieldName = prop.Name;
                                // Skip private LootForge metadata fields
                                if (fieldName.StartsWith("_lf_", StringComparison.OrdinalIgnoreCase))
                                    continue;
                                if (fieldName.EndsWith("ModelId", StringComparison.OrdinalIgnoreCase))
                                {
                                    fieldName = "equipModelId";
                                }

                                var cell = existingRow.Cells.FirstOrDefault(c => string.Equals(c.Def.InternalName, fieldName, StringComparison.OrdinalIgnoreCase));
                                if (cell != null)
                                {
                                    ParamHelper.SetCellValue(cell, prop.Value);
                                }
                            }
                        }
                        injectedEquipCount++;
                    }
                    continue;
                }

                int targetCat = slotOffset == 0 ? 0 : slotOffset == 100 ? 1 : slotOffset == 200 ? 2 : 3;

                // Fast O(1) cached lookup for identical base set variants
                var cacheKey = (tableName, baseCloneId, targetModelId, slotOffset);
                if (!_baseRowCache.TryGetValue(cacheKey, out PARAM.Row? baseRow))
                {
                    // 1. Try by direct baseCloneId if valid
                    if (baseCloneId > 0 && rowMap.TryGetValue(baseCloneId, out var cand) && (isProtector ? IsValidProtectorRow(cand) : IsValidWeaponRow(cand)))
                    {
                        baseRow = cand;
                    }

                    // 2. Try by authentic equipModelId (matching targetModelId)
                    if (baseRow == null && targetModelId > 0)
                    {
                        if (isProtector)
                        {
                            baseRow = param.Rows.FirstOrDefault(r => IsValidProtectorRow(r) && ParamHelper.GetCellInt(r, "protectorCategory") == targetCat && ParamHelper.GetCellInt(r, "equipModelId") == targetModelId)
                                   ?? param.Rows.FirstOrDefault(r => IsValidProtectorRow(r) && ParamHelper.GetCellInt(r, "equipModelId") == targetModelId);
                        }
                        else
                        {
                            baseRow = param.Rows.FirstOrDefault(r => IsValidWeaponRow(r) && ParamHelper.GetCellInt(r, "equipModelId") == targetModelId);
                        }
                    }

                    // 2b. Try nearby model variant in same set family (within +- 10)
                    if (baseRow == null && targetModelId > 0 && isProtector)
                    {
                        baseRow = param.Rows
                            .Where(r => IsValidProtectorRow(r) && ParamHelper.GetCellInt(r, "protectorCategory") == targetCat && Math.Abs(ParamHelper.GetCellInt(r, "equipModelId") - targetModelId) <= 10)
                            .OrderBy(r => Math.Abs(ParamHelper.GetCellInt(r, "equipModelId") - targetModelId))
                            .FirstOrDefault();
                    }

                    // 3. Fallback: authentic vanilla row matching equipment slot and category
                    if (baseRow == null)
                    {
                        if (isProtector)
                        {
                            baseRow = param.Rows.FirstOrDefault(r => IsValidProtectorRow(r) && ParamHelper.GetCellInt(r, "protectorCategory") == targetCat && r.ID % 1000 == slotOffset)
                                   ?? param.Rows.FirstOrDefault(r => IsValidProtectorRow(r) && ParamHelper.GetCellInt(r, "protectorCategory") == targetCat)
                                   ?? param.Rows.FirstOrDefault(r => IsValidProtectorRow(r));
                        }
                        else
                        {
                            baseRow = param.Rows.FirstOrDefault(r => IsValidWeaponRow(r));
                        }
                    }

                    // 4. Guaranteed retail fallbacks with verified non-placeholder textures
                    if (baseRow == null)
                    {
                        if (isProtector)
                        {
                            int fallbackId = slotOffset switch
                            {
                                0 => 40000,   // Scale Helm (icon 13000)
                                100 => 40100, // Scale Armor (icon 13001)
                                200 => 40200, // Iron Gauntlets (icon 13002)
                                300 => 40300, // Leather Boots (icon 13003)
                                _ => 40100
                            };
                            baseRow = (rowMap.TryGetValue(fallbackId, out var fb) ? fb : null)
                                   ?? param.Rows.FirstOrDefault(r => IsValidProtectorRow(r));
                        }
                        else
                        {
                            baseRow = (rowMap.TryGetValue(2020000, out var fb) ? fb : null)
                                   ?? param.Rows.FirstOrDefault(r => IsValidWeaponRow(r));
                        }
                    }

                    if (baseRow != null)
                    {
                        _baseRowCache[cacheKey] = baseRow;
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
                    // Extract LootForge private fields (prefixed _lf_) before writing to param.
                    // These carry gender coverage metadata and are not real EquipParamProtector fields.
                    bool hasMaleFiles = true;
                    bool hasFemaleFiles = true;
                    int fallbackModelId = 220; // Commoner's Garb — ships all slots for both genders

                    if (fieldsEl.TryGetProperty("_lf_hasMaleFiles", out var hm)) hasMaleFiles = hm.GetInt32() != 0;
                    if (fieldsEl.TryGetProperty("_lf_hasFemaleFiles", out var hf)) hasFemaleFiles = hf.GetInt32() != 0;
                    if (fieldsEl.TryGetProperty("_lf_fallbackModelId", out var fm)) fallbackModelId = fm.GetInt32();

                    foreach (var prop in fieldsEl.EnumerateObject())
                    {
                        string fieldName = prop.Name;

                        // Skip private LootForge metadata fields — they are not real param fields
                        if (fieldName.StartsWith("_lf_", StringComparison.OrdinalIgnoreCase))
                            continue;

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

                    // Vanilla fallback model ID safety net:
                    // When the mod only shipped one gender's mesh files, the cross-mirror in
                    // PartsDeployer/AssetRenumberer should have created the missing gender file.
                    // If that file somehow fails to land (wrong Mod Engine overlay path, etc.),
                    // the game would render an invisible body. As a last resort, when one gender
                    // is missing we set equipModelId to the vanilla fallback model ID for the
                    // missing gender — the player sees vanilla Commoner gear instead of nothing.
                    //
                    // Implementation: we can't set different model IDs per-gender in one row,
                    // so we only override equipModelId with the fallback when BOTH gender files
                    // are absent (total failure). When the cross-mirror succeeded (which is
                    // the normal case), the modded ID already points to both files correctly.
                    if (isProtector && !hasMaleFiles && !hasFemaleFiles && fallbackModelId > 0)
                    {
                        // Total failure — no mesh files at all; use vanilla fallback
                        ParamHelper.SetCellIfExists(newRow, "equipModelId", (ushort)fallbackModelId);
                        Console.WriteLine($"[RegTool WARN] Mod has no mesh files at all for ID {newParamId}; using vanilla fallback model {fallbackModelId}");
                    }
                }

                // Ensure icon is never 0 or placeholder 3141/3142 (inherit authentic icons from baseRow)
                if (isProtector)
                {
                    // Ensure all standalone forged armor pieces are unisex (equipModelGender = 0: usable by both Type A and Type B)
                    ParamHelper.SetCellIfExists(newRow, "equipModelGender", (byte)0);

                    int iconM = ParamHelper.GetCellInt(newRow, "iconIdM");
                    int iconF = ParamHelper.GetCellInt(newRow, "iconIdF");
                    int baseIconM = ParamHelper.GetCellInt(baseRow, "iconIdM");
                    int baseIconF = ParamHelper.GetCellInt(baseRow, "iconIdF");

                    if ((iconM <= 0 || iconM == 3141 || iconM == 3142) && baseIconM > 0 && baseIconM != 3141 && baseIconM != 3142)
                        ParamHelper.SetCellIfExists(newRow, "iconIdM", (ushort)baseIconM);
                    if ((iconF <= 0 || iconF == 3141 || iconF == 3142) && baseIconF > 0 && baseIconF != 3141 && baseIconF != 3142)
                        ParamHelper.SetCellIfExists(newRow, "iconIdF", (ushort)baseIconF);

                    // Cross-gender safeguard if one is missing or invalid
                    int finalM = ParamHelper.GetCellInt(newRow, "iconIdM");
                    int finalF = ParamHelper.GetCellInt(newRow, "iconIdF");
                    if ((finalM <= 0 || finalM == 3141 || finalM == 3142) && finalF > 0 && finalF != 3141 && finalF != 3142)
                        ParamHelper.SetCellIfExists(newRow, "iconIdM", (ushort)finalF);
                    if ((finalF <= 0 || finalF == 3141 || finalF == 3142) && finalM > 0 && finalM != 3141 && finalM != 3142)
                        ParamHelper.SetCellIfExists(newRow, "iconIdF", (ushort)finalM);

                    // Absolute guaranteed fallback icon if both failed
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
                }
                else
                {
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
                }

                rowMap[newParamId] = newRow;
                param.Rows.Add(newRow);
                injectedEquipCount++;
            }
        }
    }
}

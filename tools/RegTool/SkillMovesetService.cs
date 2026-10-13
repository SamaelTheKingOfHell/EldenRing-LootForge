using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using SoulsFormats;
using SoulsFormats.Cryptography;

namespace LootForge.RegTool
{
    /// <summary>
    /// Service responsible for introspecting, extracting, and injecting custom weapon skills
    /// (SwordArtsParam, EquipParamGem) and movesets (BehaviorParam_PC, AtkParam_Pc, animation mappings).
    /// Adheres to [CS-MODULAR] and [CS-GRANULARITY].
    /// </summary>
    public static class SkillMovesetService
    {
        public class WeaponSkillInfo
        {
            public int WeaponId { get; set; }
            public string Name { get; set; } = "";
            public int ModelId { get; set; }
            public int IconId { get; set; }
            public int SwordArtsParamId { get; set; }
            public int BehaviorVariationId { get; set; }
            public int WepmotionCategory { get; set; }
            public int WepmotionOneHandId { get; set; }
            public int WepmotionBothHandId { get; set; }
            public int SpAtkCategory { get; set; }
            public string? SkillName { get; set; }
            public string? SkillCaption { get; set; }
        }

        public class ExtractionResult
        {
            public List<WeaponSkillInfo> Weapons { get; set; } = new();
            public Dictionary<int, Dictionary<string, object>> CustomSkills { get; set; } = new();
            public Dictionary<int, List<Dictionary<string, object>>> CustomBehaviors { get; set; } = new();
            public Dictionary<int, Dictionary<string, object>> CustomAttacks { get; set; } = new();
            public Dictionary<int, (string Name, string Caption)> SkillFmgTexts { get; set; } = new();
        }

        /// <summary>
        /// Introspects an input mod's regulation.bin and optional msg directory to discover
        /// all custom weapons, skills, and moveset parameters.
        /// </summary>
        public static int ExecuteExtractSkillsMovesets(Dictionary<string, string> options)
        {
            if (!options.TryGetValue("input", out string? inputPath) || string.IsNullOrEmpty(inputPath) || !File.Exists(inputPath))
            {
                Console.Error.WriteLine("[RegTool ERROR] Missing or invalid --input <mod_regulation.bin>.");
                return 1;
            }

            string defsDir = options.TryGetValue("defs", out string? dd) && !string.IsNullOrEmpty(dd) ? dd : @"tools\vendor\Paramdex\ER\Defs";
            if (!Directory.Exists(defsDir))
            {
                Console.Error.WriteLine($"[RegTool ERROR] Defs directory not found: {defsDir}");
                return 1;
            }

            string outputPath = options.TryGetValue("output", out string? outPath) && !string.IsNullOrEmpty(outPath)
                ? outPath : Path.ChangeExtension(inputPath, ".skills_movesets.json");

            Console.WriteLine($"[RegTool] Introspecting mod regulation: {inputPath}...");
            BND4 bnd = RegulationDecryptor.DecryptERRegulation(inputPath);

            var paramCache = new Dictionary<string, PARAM>(StringComparer.OrdinalIgnoreCase);
            PARAM GetOrLoadParam(string tableName)
            {
                if (!paramCache.TryGetValue(tableName, out var param))
                {
                    var file = bnd.Files.FirstOrDefault(f => f.Name.EndsWith($"{tableName}.param", StringComparison.OrdinalIgnoreCase));
                    if (file == null) throw new KeyNotFoundException($"Param {tableName} not found in regulation.");
                    param = PARAM.Read(file.Bytes);
                    string defBase = tableName.StartsWith("ItemLotParam", StringComparison.OrdinalIgnoreCase) ? "ItemLotParam"
                        : tableName.StartsWith("BehaviorParam", StringComparison.OrdinalIgnoreCase) ? "BehaviorParam"
                        : tableName.StartsWith("AtkParam", StringComparison.OrdinalIgnoreCase) ? "AtkParam"
                        : tableName;
                    string xml = Path.Combine(defsDir, $"{defBase}.xml");
                    if (File.Exists(xml))
                    {
                        var def = PARAMDEF.XmlDeserialize(xml, false, false);
                        param.ApplyParamdefSomewhatCarefully(def);
                    }
                    paramCache[tableName] = param;
                }
                return param;
            }

            // Extract optional FMG names/captions from mod msg folder if provided
            var skillNames = new Dictionary<int, string>();
            var skillCaptions = new Dictionary<int, string>();
            if (options.TryGetValue("msg", out string? msgDir) && Directory.Exists(msgDir))
            {
                LoadModSkillFmg(msgDir, skillNames, skillCaptions);
            }

            var weaponParam = GetOrLoadParam("EquipParamWeapon");
            var swordArtsParam = GetOrLoadParam("SwordArtsParam");
            var behaviorParam = GetOrLoadParam("BehaviorParam_PC");
            PARAM? attackParam = null;
            try { attackParam = GetOrLoadParam("AtkParam_Pc"); } catch { }

            var result = new ExtractionResult();

            // Locate custom or modified weapon rows
            foreach (var wRow in weaponParam.Rows)
            {
                int wId = wRow.ID;
                // Exclude invalid rows and arrows/bolts (50M..60M range)
                if (wId <= 0 || (wId >= 50000000 && wId < 60000000)) continue;

                int modelId = ParamHelper.GetCellInt(wRow, "equipModelId");
                int skillId = ParamHelper.GetCellInt(wRow, "swordArtsParamId");
                int behVar = ParamHelper.GetCellInt(wRow, "behaviorVariationId");
                int motCat = ParamHelper.GetCellInt(wRow, "wepmotionCategory");
                int mot1h = ParamHelper.GetCellInt(wRow, "wepmotionOneHandId");
                int mot2h = ParamHelper.GetCellInt(wRow, "wepmotionBothHandId");
                int spAtk = ParamHelper.GetCellInt(wRow, "spAtkCategory");
                int icon = ParamHelper.GetCellInt(wRow, "iconId");
                string wName = wRow.Name ?? "";

                // Detection criterion: high ID (mod custom range), custom skill ID, or non-default behavior variation
                bool isCustomId = wId >= 9000000;
                bool isCustomSkill = skillId >= 1000 || (skillId > 0 && swordArtsParam.Rows.Any(r => r.ID == skillId && !string.IsNullOrWhiteSpace(r.Name) && !r.Name.StartsWith("?")));
                bool isCustomMoveset = behVar >= 800 || motCat == 60 || spAtk > 100;

                if (!isCustomId && !isCustomSkill && !isCustomMoveset) continue;

                var wInfo = new WeaponSkillInfo
                {
                    WeaponId = wId,
                    Name = wName,
                    ModelId = modelId,
                    IconId = icon,
                    SwordArtsParamId = skillId,
                    BehaviorVariationId = behVar,
                    WepmotionCategory = motCat,
                    WepmotionOneHandId = mot1h,
                    WepmotionBothHandId = mot2h,
                    SpAtkCategory = spAtk
                };

                // Capture skill data
                if (skillId > 0)
                {
                    var saRow = swordArtsParam.Rows.FirstOrDefault(r => r.ID == skillId);
                    if (saRow != null)
                    {
                        wInfo.SkillName = skillNames.TryGetValue(skillId, out var sn) ? sn : saRow.Name;
                        wInfo.SkillCaption = skillCaptions.TryGetValue(skillId, out var sc) ? sc : "";

                        if (!result.CustomSkills.ContainsKey(skillId))
                        {
                            var sDict = RowToDictionary(saRow);
                            result.CustomSkills[skillId] = sDict;
                            result.SkillFmgTexts[skillId] = (wInfo.SkillName ?? "", wInfo.SkillCaption ?? "");
                        }
                    }
                }

                // Capture behavior variation rows and linked attack parameters
                if (behVar > 0)
                {
                    if (!result.CustomBehaviors.TryGetValue(behVar, out var bList))
                    {
                        bList = new List<Dictionary<string, object>>();
                        var behRows = behaviorParam.Rows.Where(r => ParamHelper.GetCellInt(r, "variationId") == behVar).ToList();
                        foreach (var bRow in behRows)
                        {
                            var bDict = RowToDictionary(bRow);
                            bList.Add(bDict);

                            int refType = ParamHelper.GetCellInt(bRow, "refType");
                            int refId = ParamHelper.GetCellInt(bRow, "refId");
                            if (refType == 1 && refId > 0 && attackParam != null && !result.CustomAttacks.ContainsKey(refId))
                            {
                                var atkRow = attackParam.Rows.FirstOrDefault(r => r.ID == refId);
                                if (atkRow != null)
                                {
                                    result.CustomAttacks[refId] = RowToDictionary(atkRow);
                                }
                            }
                        }
                        result.CustomBehaviors[behVar] = bList;
                    }
                }

                result.Weapons.Add(wInfo);
            }

            string json = JsonSerializer.Serialize(result, new JsonSerializerOptions { WriteIndented = true });
            string? outDir = Path.GetDirectoryName(outputPath);
            if (!string.IsNullOrEmpty(outDir) && !Directory.Exists(outDir))
            {
                Directory.CreateDirectory(outDir);
            }
            File.WriteAllText(outputPath, json);
            Console.WriteLine($"[RegTool SUCCESS] Discovered {result.Weapons.Count} custom weapons, {result.CustomSkills.Count} skills, {result.CustomBehaviors.Count} moveset behaviors.");
            Console.WriteLine($"[RegTool] Exported introspection to: {outputPath}");
            return 0;
        }

        private static void LoadModSkillFmg(string msgDir, Dictionary<int, string> names, Dictionary<int, string> captions)
        {
            try
            {
                foreach (var bndFile in Directory.GetFiles(msgDir, "*.msgbnd.dcx", SearchOption.AllDirectories))
                {
                    BND4 bnd = BND4.Read(bndFile);
                    foreach (var f in bnd.Files)
                    {
                        string fname = Path.GetFileNameWithoutExtension(f.Name ?? "");
                        if (fname.Equals("SwordArtsName", StringComparison.OrdinalIgnoreCase))
                        {
                            var fmg = FMG.Read(f.Bytes);
                            foreach (var e in fmg.Entries)
                                if (!string.IsNullOrWhiteSpace(e.Text)) names[e.ID] = e.Text;
                        }
                        else if (fname.Equals("SwordArtsCaption", StringComparison.OrdinalIgnoreCase))
                        {
                            var fmg = FMG.Read(f.Bytes);
                            foreach (var e in fmg.Entries)
                                if (!string.IsNullOrWhiteSpace(e.Text)) captions[e.ID] = e.Text;
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[RegTool WARN] Could not parse mod FMG: {ex.Message}");
            }
        }

        private static Dictionary<string, object> RowToDictionary(PARAM.Row row)
        {
            var dict = new Dictionary<string, object>();
            dict["_row_id"] = row.ID;
            dict["_row_name"] = row.Name ?? "";
            foreach (var cell in row.Cells)
            {
                string? name = cell.Def?.InternalName;
                if (!string.IsNullOrEmpty(name))
                {
                    dict[name] = cell.Value ?? 0;
                }
            }
            return dict;
        }

        /// <summary>
        /// Injects custom SwordArtsParam and BehaviorParam_PC rows specified in the patch specification.
        /// </summary>
        public static void InjectSkillsAndMovesets(
            JsonElement customSkillsEl,
            JsonElement customBehaviorsEl,
            JsonElement customAttacksEl,
            Func<string, string, (PARAM Param, BinderFile File)> getOrLoadParam,
            ref int injectedSkillCount,
            ref int injectedMovesetCount)
        {
            // 1. Inject SwordArtsParam
            if (customSkillsEl.ValueKind == JsonValueKind.Array)
            {
                var (saParam, _) = getOrLoadParam("SwordArtsParam", "SwordArtsParam");
                foreach (var sEl in customSkillsEl.EnumerateArray())
                {
                    int skillId = sEl.GetProperty("skill_id").GetInt32();
                    string skillName = sEl.TryGetProperty("name", out var sn) ? sn.GetString() ?? "" : "";
                    var existing = saParam.Rows.FirstOrDefault(r => r.ID == skillId);
                    if (existing == null)
                    {
                        var baseRow = saParam.Rows.FirstOrDefault(r => r.ID > 0) ?? saParam.Rows.First();
                        var newRow = new PARAM.Row(baseRow) { ID = skillId, Name = $"[LootForge] {skillName}" };
                        if (sEl.TryGetProperty("fields", out var fEl) && fEl.ValueKind == JsonValueKind.Object)
                        {
                            ApplyFields(newRow, fEl);
                        }
                        saParam.Rows.Add(newRow);
                        injectedSkillCount++;
                    }
                }
            }

            // 2. Inject BehaviorParam_PC
            if (customBehaviorsEl.ValueKind == JsonValueKind.Array)
            {
                var (bParam, _) = getOrLoadParam("BehaviorParam_PC", "BehaviorParam");
                foreach (var bEl in customBehaviorsEl.EnumerateArray())
                {
                    int behId = bEl.GetProperty("id").GetInt32();
                    if (!bParam.Rows.Any(r => r.ID == behId))
                    {
                        var baseRow = bParam.Rows.FirstOrDefault(r => r.ID > 0) ?? bParam.Rows.First();
                        var newRow = new PARAM.Row(baseRow) { ID = behId, Name = "[LootForge] Custom Behavior" };
                        if (bEl.TryGetProperty("fields", out var fEl) && fEl.ValueKind == JsonValueKind.Object)
                        {
                            ApplyFields(newRow, fEl);
                        }
                        bParam.Rows.Add(newRow);
                        injectedMovesetCount++;
                    }
                }
            }

            // 3. Inject AtkParam_Pc
            if (customAttacksEl.ValueKind == JsonValueKind.Array)
            {
                var (atkParam, _) = getOrLoadParam("AtkParam_Pc", "AtkParam_Pc");
                foreach (var aEl in customAttacksEl.EnumerateArray())
                {
                    int atkId = aEl.GetProperty("id").GetInt32();
                    if (!atkParam.Rows.Any(r => r.ID == atkId))
                    {
                        var baseRow = atkParam.Rows.FirstOrDefault(r => r.ID > 0) ?? atkParam.Rows.First();
                        var newRow = new PARAM.Row(baseRow) { ID = atkId, Name = "[LootForge] Custom Attack" };
                        if (aEl.TryGetProperty("fields", out var fEl) && fEl.ValueKind == JsonValueKind.Object)
                        {
                            ApplyFields(newRow, fEl);
                        }
                        atkParam.Rows.Add(newRow);
                    }
                }
            }
        }

        private static void ApplyFields(PARAM.Row row, JsonElement fields)
        {
            foreach (var prop in fields.EnumerateObject())
            {
                if (prop.Name.StartsWith("_")) continue;
                var cell = row.Cells.FirstOrDefault(c => string.Equals(c.Def.InternalName, prop.Name, StringComparison.OrdinalIgnoreCase));
                if (cell != null)
                {
                    ParamHelper.SetCellValue(cell, prop.Value);
                }
            }
        }

        /// <summary>
        /// Purges previous LootForge custom skills and behaviors to guarantee a pristine baseline.
        /// </summary>
        public static void PurgePreviousInjections(Func<string, string, (PARAM Param, BinderFile File)> getOrLoadParam)
        {
            try
            {
                var (saParam, _) = getOrLoadParam("SwordArtsParam", "SwordArtsParam");
                saParam.Rows.RemoveAll(r => (r.Name != null && r.Name.Contains("[LootForge]")) || (r.ID >= 9000000 && r.ID < 9100000));
            }
            catch { }

            try
            {
                var (bParam, _) = getOrLoadParam("BehaviorParam_PC", "BehaviorParam");
                bParam.Rows.RemoveAll(r => (r.Name != null && r.Name.Contains("[LootForge]")) || (r.ID >= 9000000 && r.ID < 9100000));
            }
            catch { }

            try
            {
                var (atkParam, _) = getOrLoadParam("AtkParam_Pc", "AtkParam_Pc");
                atkParam.Rows.RemoveAll(r => (r.Name != null && r.Name.Contains("[LootForge]")) || (r.ID >= 9000000 && r.ID < 9100000));
            }
            catch { }
        }
    }
}

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
    /// Service orchestrating regulation patch pipeline, diagnostic dumps, and message extraction.
    /// Adheres to [CS-MODULAR] and [CS-GRANULARITY].
    /// </summary>
    public static class PatchService
    {
        public static int ExecutePatch(Dictionary<string, string> options)
        {
            if (!options.TryGetValue("input", out string? inputPath) || string.IsNullOrEmpty(inputPath))
            {
                Console.Error.WriteLine("Missing required argument: --input <source_regulation.bin>");
                return 1;
            }

            if (!options.TryGetValue("output", out string? outputPath) || string.IsNullOrEmpty(outputPath))
            {
                Console.Error.WriteLine("Missing required argument: --output <target_regulation.bin>");
                return 1;
            }

            if (!options.TryGetValue("defs", out string? defsDir) || string.IsNullOrEmpty(defsDir))
            {
                Console.Error.WriteLine("Missing required argument: --defs <paramdex_er_defs_folder>");
                return 1;
            }

            if (!options.TryGetValue("spec", out string? specPath) || string.IsNullOrEmpty(specPath))
            {
                Console.Error.WriteLine("Missing required argument: --spec <patch_spec.json>");
                return 1;
            }

            if (!File.Exists(inputPath))
            {
                Console.Error.WriteLine($"Source regulation file not found: {inputPath}");
                return 1;
            }

            if (!Directory.Exists(defsDir))
            {
                Console.Error.WriteLine($"Paramdex Defs directory not found: {defsDir}");
                return 1;
            }

            if (!File.Exists(specPath))
            {
                Console.Error.WriteLine($"Patch spec JSON file not found: {specPath}");
                return 1;
            }

            Console.WriteLine($"[RegTool] Loading patch specification: {specPath}...");
            string specJson = File.ReadAllText(specPath);
            using var doc = JsonDocument.Parse(specJson);
            var root = doc.RootElement;

            Console.WriteLine($"[RegTool] Decrypting source regulation: {inputPath}...");
            BND4 bnd = RegulationDecryptor.DecryptERRegulation(inputPath);

            var paramdefCache = new Dictionary<string, PARAMDEF>(StringComparer.OrdinalIgnoreCase);
            var paramCache = new Dictionary<string, (PARAM Param, BinderFile File)>(StringComparer.OrdinalIgnoreCase);

            PARAMDEF GetParamdef(string defName)
            {
                if (!paramdefCache.TryGetValue(defName, out var def))
                {
                    string xmlFile = Path.Combine(defsDir, $"{defName}.xml");
                    if (!File.Exists(xmlFile))
                    {
                        throw new FileNotFoundException($"Paramdef XML not found: {xmlFile}");
                    }
                    def = PARAMDEF.XmlDeserialize(xmlFile, false, false);
                    paramdefCache[defName] = def;
                }
                return def;
            }

            (PARAM Param, BinderFile File) GetOrLoadParam(string tableName, string defName)
            {
                if (!paramCache.TryGetValue(tableName, out var entry))
                {
                    var file = bnd.Files.FirstOrDefault(f => f.Name.EndsWith($"{tableName}.param", StringComparison.OrdinalIgnoreCase));
                    if (file == null)
                    {
                        throw new KeyNotFoundException($"Param file '{tableName}.param' not found in regulation BND!");
                    }
                    var param = PARAM.Read(file.Bytes);
                    var def = GetParamdef(defName);
                    param.ApplyParamdefSomewhatCarefully(def);
                    entry = (param, file);
                    paramCache[tableName] = entry;
                }
                return entry;
            }

            int injectedEquipCount = 0;
            int injectedLootCount = 0;
            int injectedFmgCount = 0;

            var allFmgTexts = new List<FmgInjector.FmgTextSpec>();
            var itemIdToIsWeapon = new Dictionary<int, bool>();
            var itemIdToIsProtector = new Dictionary<int, bool>();
            var itemIdToVanillaSourceId = new Dictionary<int, int>();

            List<JsonElement> specs = new List<JsonElement>();
            if (root.ValueKind == JsonValueKind.Array)
            {
                foreach (var el in root.EnumerateArray())
                    specs.Add(el);
            }
            else
            {
                specs.Add(root);
            }

            foreach (var setSpec in specs)
            {
                // 1. Equip Params (EquipParamProtector / EquipParamWeapon)
                if (setSpec.TryGetProperty("equip_params", out var equipParamsEl) && equipParamsEl.ValueKind == JsonValueKind.Array)
                {
                    ParamInjector.InjectEquipParams(
                        equipParamsEl,
                        GetOrLoadParam,
                        itemIdToIsProtector,
                        itemIdToIsWeapon,
                        itemIdToVanillaSourceId,
                        ref injectedEquipCount
                    );
                }

                // 2. Loot Distribution (NON-DESTRUCTIVE: Never clears vanilla loot)
                if (setSpec.TryGetProperty("loot_distribution", out var lootEl) && lootEl.ValueKind == JsonValueKind.Object)
                {
                    ParamInjector.InjectLootDistribution(
                        lootEl,
                        GetOrLoadParam,
                        itemIdToIsProtector,
                        itemIdToIsWeapon,
                        ref injectedLootCount
                    );
                }

                // 3. Collect FMG text entries for batch injection
                if (setSpec.TryGetProperty("fmg_texts", out var fmgTextsEl) && fmgTextsEl.ValueKind == JsonValueKind.Array)
                {
                    foreach (var ft in fmgTextsEl.EnumerateArray())
                    {
                        int ftItemId = ft.GetProperty("item_id").GetInt32();
                        int ftVanillaId = ft.TryGetProperty("vanilla_source_id", out var vs) ? vs.GetInt32() : 0;
                        if (itemIdToVanillaSourceId.TryGetValue(ftItemId, out int realVanillaId) && realVanillaId > 0)
                        {
                            ftVanillaId = realVanillaId;
                        }
                        bool ftIsWeapon = itemIdToIsWeapon.TryGetValue(ftItemId, out var iw) ? iw : (ft.TryGetProperty("is_weapon", out var iwProp) && iwProp.GetBoolean());
                        string ftName = ft.TryGetProperty("name", out var n) ? n.GetString() ?? "" : "";
                        string ftCaption = ft.TryGetProperty("caption", out var c) ? c.GetString() ?? "" : "";
                        string ftInfo = ft.TryGetProperty("info", out var inf) ? inf.GetString() ?? "" : "";
                        allFmgTexts.Add(new FmgInjector.FmgTextSpec(ftItemId, ftVanillaId, ftIsWeapon, ftName, ftCaption, ftInfo));
                    }
                }
            }

            foreach (var kvp in paramCache)
            {
                var (param, file) = kvp.Value;
                Console.WriteLine($"[RegTool] Serializing modified table: {kvp.Key} ({param.Rows.Count} rows)...");
                file.Bytes = param.Write();
            }

            string? outDir = Path.GetDirectoryName(outputPath);
            if (!string.IsNullOrEmpty(outDir) && !Directory.Exists(outDir))
            {
                Directory.CreateDirectory(outDir);
            }

            Console.WriteLine($"[RegTool] Encrypting and saving modified regulation to: {outputPath}...");
            RegulationDecryptor.EncryptERRegulation(outputPath, bnd);

            // Phase 2: FMG Text Injection
            if (options.TryGetValue("msg", out string? msgDir) && !string.IsNullOrEmpty(msgDir) && allFmgTexts.Count > 0)
            {
                injectedFmgCount = FmgInjector.InjectFmgTexts(msgDir, outputPath, allFmgTexts);
            }
            else if (allFmgTexts.Count > 0)
            {
                Console.WriteLine($"[RegTool WARN] No --msg directory provided. Skipping FMG text injection for {allFmgTexts.Count} item(s).");
                Console.WriteLine("     Items will display as ?ProtectorName? / ?WeaponName? in-game.");
            }

            Console.WriteLine($"[RegTool SUCCESS] Successfully patched regulation.bin!");
            Console.WriteLine($" - Injected equipment entries: {injectedEquipCount}");
            Console.WriteLine($" - Injected loot/shop entries: {injectedLootCount}");
            Console.WriteLine($" - Injected FMG text entries:  {injectedFmgCount}");
            Console.WriteLine($" - Output file size: {new FileInfo(outputPath).Length} bytes");
            return 0;
        }
    }
}

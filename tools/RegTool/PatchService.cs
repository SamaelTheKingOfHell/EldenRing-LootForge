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

        public static int ExecuteVerify(Dictionary<string, string> options)
        {
            if (!options.TryGetValue("input", out string? inputPath) || string.IsNullOrEmpty(inputPath))
            {
                Console.Error.WriteLine("Missing required --input path.");
                return 1;
            }

            if (!File.Exists(inputPath))
            {
                Console.Error.WriteLine($"Input regulation file not found: {inputPath}");
                return 1;
            }

            Console.WriteLine($"Decrypting: {inputPath}");
            BND4 bnd = RegulationDecryptor.DecryptERRegulation(inputPath);
            Console.WriteLine($"Decryption successful. BND contains {bnd.Files.Count} param files.");
            return 0;
        }

        public static int ExecuteDumpFmg(Dictionary<string, string> options)
        {
            if (!options.TryGetValue("input", out string? inputPath) || string.IsNullOrEmpty(inputPath))
            {
                Console.Error.WriteLine("Missing required --input path to item.msgbnd.dcx.");
                return 1;
            }

            if (!File.Exists(inputPath))
            {
                Console.Error.WriteLine($"File not found: {inputPath}");
                return 1;
            }

            Console.WriteLine($"[RegTool] Loading BND4: {inputPath} (size: {new FileInfo(inputPath).Length} bytes)...");
            BND4 bnd = BND4.Read(inputPath);
            Console.WriteLine($"[RegTool] BND4 contains {bnd.Files.Count} files.");

            string searchQuery = options.TryGetValue("search", out string? sq) ? sq : "";

            foreach (var file in bnd.Files)
            {
                string fname = Path.GetFileName(file.Name ?? "???");
                if (!fname.EndsWith(".fmg", StringComparison.OrdinalIgnoreCase)) continue;

                FMG fmg = FMG.Read(file.Bytes);
                if (!string.IsNullOrEmpty(searchQuery))
                {
                    var matches = fmg.Entries.Where(e => e.Text != null && e.Text.Contains(searchQuery, StringComparison.OrdinalIgnoreCase)).ToList();
                    if (int.TryParse(searchQuery, out int sId))
                    {
                        var idMatch = fmg.Entries.FirstOrDefault(e => e.ID == sId);
                        if (idMatch != null && !matches.Contains(idMatch)) matches.Add(idMatch);
                    }
                    if (matches.Count > 0)
                    {
                        Console.WriteLine($"  {fname,-30} Search='{searchQuery}' Matches: {matches.Count}");
                        foreach (var entry in matches.Take(15))
                        {
                            string text = entry.Text ?? "<null>";
                            if (text.Length > 80) text = text.Substring(0, 80) + "...";
                            Console.WriteLine($"    [{entry.ID}] {text}");
                        }
                    }
                }
                else
                {
                    var highEntries = fmg.Entries.Where(e => e.ID >= 9000000).ToList();
                    Console.WriteLine($"  {fname,-30} Version={fmg.Version,-12} Total={fmg.Entries.Count,6}  ID>=9M: {highEntries.Count}");
                    foreach (var entry in highEntries)
                    {
                        string text = entry.Text ?? "<null>";
                        if (text.Length > 80) text = text.Substring(0, 80) + "...";
                        Console.WriteLine($"    [{entry.ID}] {text}");
                    }
                }
            }
            return 0;
        }

        public static int ExecuteDumpReg(Dictionary<string, string> options)
        {
            if (!options.TryGetValue("input", out string? inputPath) || string.IsNullOrEmpty(inputPath))
            {
                Console.Error.WriteLine("Missing required --input path to regulation.bin.");
                return 1;
            }
            string defsDir = options.TryGetValue("defs", out string? dd) && !string.IsNullOrEmpty(dd) ? dd : @"tools\vendor\Paramdex\ER\Defs";

            Console.WriteLine($"[RegTool] Decrypting regulation: {inputPath}...");
            BND4 bnd = RegulationDecryptor.DecryptERRegulation(inputPath);

            void InspectTable(string tableName)
            {
                var file = bnd.Files.FirstOrDefault(f => f.Name.EndsWith($"{tableName}.param", StringComparison.OrdinalIgnoreCase));
                if (file == null) return;
                var param = PARAM.Read(file.Bytes);
                string xmlFile = Path.Combine(defsDir, $"{tableName}.xml");
                if (File.Exists(xmlFile))
                {
                    var def = PARAMDEF.XmlDeserialize(xmlFile, false, false);
                    param.ApplyParamdefSomewhatCarefully(def);
                }

                Console.WriteLine($"\n=== {tableName} (total rows: {param.Rows.Count}) ===");
                if (tableName == "ShopLineupParam")
                {
                    var interesting = param.Rows.Where(r => (r.ID >= 100500 && r.ID <= 100524) || r.ID >= 9000000 || (r.Name != null && r.Name.Contains("LootForge"))).ToList();
                    Console.WriteLine($"Found {interesting.Count} matching rows:");
                    foreach (var r in interesting)
                    {
                        int eqId = ParamHelper.GetCellInt(r, "equipId");
                        int eqType = ParamHelper.GetCellInt(r, "equipType");
                        int val = ParamHelper.GetCellInt(r, "value");
                        int icon = ParamHelper.GetCellInt(r, "iconId");
                        int nameMsg = ParamHelper.GetCellInt(r, "nameMsgId");
                        Console.WriteLine($"  ID={r.ID} Name='{r.Name}' equipId={eqId} equipType={eqType} value={val} iconId={icon} nameMsgId={nameMsg}");
                    }
                }
            }

            InspectTable("ShopLineupParam");
            InspectTable("EquipParamProtector");
            InspectTable("EquipParamWeapon");
            return 0;
        }

        public static int ExtractMsgFiles(Dictionary<string, string> options)
        {
            if (!options.TryGetValue("game-dir", out string? gameDir) || string.IsNullOrEmpty(gameDir))
            {
                Console.WriteLine("[RegTool ERROR] --game-dir required for extract-msg command");
                return 1;
            }

            if (!options.TryGetValue("output", out string? outputDir) || string.IsNullOrEmpty(outputDir))
            {
                Console.WriteLine("[RegTool ERROR] --output required for extract-msg command");
                return 1;
            }

            string bhdPath = Path.Combine(gameDir, "Data0.bhd");
            string bdtPath = Path.Combine(gameDir, "Data0.bdt");

            if (!File.Exists(bhdPath) || !File.Exists(bdtPath))
            {
                Console.WriteLine($"[RegTool ERROR] Data0 archives not found in: {gameDir}");
                return 1;
            }

            try
            {
                Console.WriteLine($"[RegTool] Reading BXF4 archive: Data0.bhd + Data0.bdt...");
                BXF4 bxf = BXF4.Read(bhdPath, bdtPath);
                foreach (var file in bxf.Files)
                {
                    byte[] fileData = file.Bytes;
                    if (fileData.Length > 4 && fileData[0] == 'D' && fileData[1] == 'C' && fileData[2] == 'X')
                    {
                        try
                        {
                            BND4 bnd = BND4.Read(fileData);
                            var fmgFiles = bnd.Files.Where(f => f.Name != null && f.Name.EndsWith(".fmg", StringComparison.OrdinalIgnoreCase)).ToList();
                            if (fmgFiles.Any(f => f.Name.Contains("Weapon", StringComparison.OrdinalIgnoreCase) || f.Name.Contains("Protector", StringComparison.OrdinalIgnoreCase)))
                            {
                                string engUSDir = Path.Combine(outputDir, "engUS");
                                Directory.CreateDirectory(engUSDir);
                                string outputPath = Path.Combine(engUSDir, "item.msgbnd.dcx");
                                File.WriteAllBytes(outputPath, fileData);
                                Console.WriteLine($"[RegTool SUCCESS] Extracted item.msgbnd.dcx to: {outputPath}");
                                return 0;
                            }
                        }
                        catch { }
                    }
                }
                Console.WriteLine("[RegTool WARN] Could not find item.msgbnd.dcx in Data0.bdt");
                return 1;
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[RegTool ERROR] {ex.Message}");
                return 1;
            }
        }
    }
}

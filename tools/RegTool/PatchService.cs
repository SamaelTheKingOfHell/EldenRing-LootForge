using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using System.Diagnostics;
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
            var timer = Stopwatch.StartNew();
            void Stage(string name) => Console.WriteLine($"[RegTool TIMING] {name}: {timer.Elapsed.TotalSeconds:F3}s elapsed");
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
            using var specStream = File.OpenRead(specPath);
            using var doc = JsonDocument.Parse(specStream);
            var root = doc.RootElement;

            Console.WriteLine($"[RegTool] Decrypting source regulation: {inputPath}...");
            BND4 bnd = RegulationDecryptor.DecryptERRegulation(inputPath);
            Stage("decrypt");

            var paramdefCache = new Dictionary<string, PARAMDEF>(StringComparer.OrdinalIgnoreCase);
            var paramCache = new Dictionary<string, (PARAM Param, BinderFile File)>(StringComparer.OrdinalIgnoreCase);

            PARAMDEF GetParamdef(string defName)
            {
                if (!paramdefCache.TryGetValue(defName, out var def))
                {
                    string xmlFile = Path.Combine(defsDir, $"{defName}.xml");
                    if (!File.Exists(xmlFile))
                    {
                        string? resolved = ParamHelper.ResolveDefFile(defsDir, defName);
                        if (resolved != null && File.Exists(resolved))
                        {
                            xmlFile = resolved;
                        }
                        else
                        {
                            throw new FileNotFoundException($"Paramdef XML not found: {xmlFile}");
                        }
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
                    if (!param.ApplyParamdefSomewhatCarefully(def))
                        throw new InvalidDataException($"Paramdef does not match table {tableName}.");
                    entry = (param, file);
                    paramCache[tableName] = entry;
                }
                return entry;
            }

            // PARAM row names are readable without materializing every cell.
            // Most runs contain no generated effects/skills; leave those large tables untouched.
            void PurgeNamedRows(string tableName, string defName)
            {
                var file = bnd.Files.FirstOrDefault(f => f.Name.EndsWith($"{tableName}.param", StringComparison.OrdinalIgnoreCase));
                if (file == null) return;
                var metadata = PARAM.Read(file.Bytes);
                if (!metadata.Rows.Any(r => r.Name?.Contains("[LootForge]") == true)) return;
                var param = GetOrLoadParam(tableName, defName).Param;
                param.Rows.RemoveAll(r => r.Name?.Contains("[LootForge]") == true);
            }

            int injectedEquipCount = 0;
            int injectedLootCount = 0;
            int injectedFmgCount = 0;
            int injectedCustomSkillCount = 0;
            int injectedCustomMovesetCount = 0;

            var allFmgTexts = new List<FmgInjector.FmgTextSpec>();
            var itemIdToIsWeapon = new Dictionary<int, bool>();
            var itemIdToIsProtector = new Dictionary<int, bool>();
            var itemIdToIsAccessory = new Dictionary<int, bool>();
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

            // 0. Purge any stale or previous LootForge injections to ensure a pristine baseline
            var previousTextIds = new Dictionary<string, HashSet<int>>();
            foreach (var (table, category) in new[] { ("EquipParamWeapon", "Weapon"), ("EquipParamProtector", "Protector"), ("EquipParamAccessory", "Accessory") })
                previousTextIds[category] = GetOrLoadParam(table, table).Param.Rows
                    .Where(row => row.Name?.Contains("[LootForge]") == true).Select(row => row.ID).ToHashSet();
            LegacyLootRecovery.Restore(bnd, GetOrLoadParam,
                options.GetValueOrDefault("loot-backups", "backups"), defsDir);
            ParamInjector.PurgePreviousInjections(GetOrLoadParam, PurgeNamedRows);
            EquipInjector.ResetCache();
            LootInjector.ResetCache();
            PatchPreflight.Validate(specs, GetOrLoadParam);
            Stage("load and purge");

            foreach (var setSpec in specs)
            {
                // 1. Equip Params (EquipParamProtector / EquipParamWeapon / EquipParamAccessory)
                if (setSpec.TryGetProperty("equip_params", out var equipParamsEl) && equipParamsEl.ValueKind == JsonValueKind.Array)
                {
                    ParamInjector.InjectEquipParams(
                        equipParamsEl,
                        GetOrLoadParam,
                        itemIdToIsProtector,
                        itemIdToIsWeapon,
                        itemIdToIsAccessory,
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
                        itemIdToIsAccessory,
                        ref injectedLootCount
                    );
                }

                // 2b. Custom Skills & Movesets Injection
                if (setSpec.TryGetProperty("custom_skills", out var customSkillsEl) ||
                    setSpec.TryGetProperty("custom_behaviors", out var customBehEl) ||
                    setSpec.TryGetProperty("custom_attacks", out var customAtkEl))
                {
                    var csEl = setSpec.TryGetProperty("custom_skills", out var s) ? s : default;
                    var cbEl = setSpec.TryGetProperty("custom_behaviors", out var b) ? b : default;
                    var caEl = setSpec.TryGetProperty("custom_attacks", out var a) ? a : default;

                    SkillMovesetService.InjectSkillsAndMovesets(
                        csEl,
                        cbEl,
                        caEl,
                        GetOrLoadParam,
                        ref injectedCustomSkillCount,
                        ref injectedCustomMovesetCount
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
                        bool ftIsAccessory = itemIdToIsAccessory.TryGetValue(ftItemId, out var ia) ? ia : (ft.TryGetProperty("is_accessory", out var iaProp) && iaProp.GetBoolean());
                        bool ftIsWeapon = itemIdToIsWeapon.TryGetValue(ftItemId, out var iw) ? iw : (ft.TryGetProperty("is_weapon", out var iwProp) && iwProp.GetBoolean());
                        string ftName = ft.TryGetProperty("name", out var n) ? n.GetString() ?? "" : "";
                        string ftCaption = ft.TryGetProperty("caption", out var c) ? c.GetString() ?? "" : "";
                        string ftInfo = ft.TryGetProperty("info", out var inf) ? inf.GetString() ?? "" : "";
                        allFmgTexts.Add(new FmgInjector.FmgTextSpec(ftItemId, ftVanillaId, ftIsWeapon, ftName, ftCaption, ftInfo, ftIsAccessory));
                    }
                }
            }

            Stage("inject specifications");
            // Optional In-Memory Single-Pass Enrichment for Bosses and Chests
            if (options.TryGetValue("enrich-bosses", out var eb) && eb.Equals("true", StringComparison.OrdinalIgnoreCase))
            {
                int bCount = options.TryGetValue("boss-count", out var bcStr) && int.TryParse(bcStr, out int bc) ? bc : 3;
                var enemyP = GetOrLoadParam("ItemLotParam_enemy", "ItemLotParam").Param;
                var mapP = GetOrLoadParam("ItemLotParam_map", "ItemLotParam").Param;
                var wepP = GetOrLoadParam("EquipParamWeapon", "EquipParamWeapon").Param;
                var protP = GetOrLoadParam("EquipParamProtector", "EquipParamProtector").Param;
                BossLootPoolService.EnrichBossLootPools(enemyP, mapP, wepP, protP, bCount, itemIdToIsWeapon.Where(x => x.Value).Select(x => x.Key).ToHashSet(), itemIdToIsProtector.Where(x => x.Value).Select(x => x.Key).ToHashSet());
            }

            if (options.TryGetValue("enrich-chests", out var ec) && ec.Equals("true", StringComparison.OrdinalIgnoreCase))
            {
                int minItms = options.TryGetValue("chest-min-items", out var miStr) && int.TryParse(miStr, out int mi) ? mi : 1;
                int maxItms = options.TryGetValue("chest-max-items", out var mxStr) && int.TryParse(mxStr, out int mx) ? mx : 4;
                var mapP = GetOrLoadParam("ItemLotParam_map", "ItemLotParam").Param;
                var enemyP = GetOrLoadParam("ItemLotParam_enemy", "ItemLotParam").Param;
                var protP = GetOrLoadParam("EquipParamProtector", "EquipParamProtector").Param;
                var wepP = GetOrLoadParam("EquipParamWeapon", "EquipParamWeapon").Param;
                ChestLootPoolService.EnrichChestLootPools(mapP, enemyP, protP, wepP, minItms, maxItms, itemIdToIsProtector.Where(x => x.Value).Select(x => x.Key).ToHashSet(), itemIdToIsWeapon.Where(x => x.Value).Select(x => x.Key).ToHashSet());
            }

            var sweepEffects = new List<SweepFmgService.Effect>();
            if (options.TryGetValue("sweep-vanilla", out var sweep) && bool.TryParse(sweep, out var sweepEnabled) && sweepEnabled)
            {
                bool randomize = !options.TryGetValue("randomize-skills", out var rs) || bool.Parse(rs);
                int seed = options.TryGetValue("seed", out var seedText) ? int.Parse(seedText) : 42;
                sweepEffects = UniversalSweeperService.InfuseParams(GetOrLoadParam, randomize, seed);
            }
            Stage("enrich and infuse");

            // Validate all tables before any output is replaced.
            foreach (var entry in paramCache)
                if (entry.Value.Param.Rows.Count > ushort.MaxValue)
                    throw new InvalidOperationException($"{entry.Key} has {entry.Value.Param.Rows.Count} rows; Elden Ring allows at most {ushort.MaxValue}. Reduce variants per item.");

            Parallel.ForEach(paramCache, new ParallelOptions { MaxDegreeOfParallelism = Math.Min(4, Environment.ProcessorCount) }, kvp =>
            {
                var (param, file) = kvp.Value;
                Console.WriteLine($"[RegTool] Serializing modified table: {kvp.Key} ({param.Rows.Count} rows)...");
                file.Bytes = ParamSerialization.Write(param);
            });
            Stage("serialize tables");

            string? outDir = Path.GetDirectoryName(outputPath);
            if (!string.IsNullOrEmpty(outDir) && !Directory.Exists(outDir))
            {
                Directory.CreateDirectory(outDir);
            }

            Console.WriteLine($"[RegTool] Encrypting and saving modified regulation to: {outputPath}...");
            using var output = new PatchOutputTransaction(outputPath);
            RegulationDecryptor.EncryptERRegulation(output.RegulationPath, bnd);
            Stage("encrypt and save");

            // Phase 2: FMG Text Injection
            foreach (var text in allFmgTexts)
                previousTextIds[text.IsAccessory ? "Accessory" : (text.IsWeapon ? "Weapon" : "Protector")].Remove(text.ItemId);
            if (options.TryGetValue("msg", out string? msgDir) && !string.IsNullOrEmpty(msgDir) && (allFmgTexts.Count > 0 || sweepEffects.Count > 0))
            {
                injectedFmgCount = FmgInjector.InjectFmgTexts(msgDir, output.RegulationPath, allFmgTexts,
                    sweepEffects.Count > 0 ? archive => SweepFmgService.Apply(archive, sweepEffects) : null,
                    archive => FmgCleanupService.Prune(archive, previousTextIds));
            }
            else if (allFmgTexts.Count > 0)
            {
                throw new InvalidDataException($"No message archives were provided for {allFmgTexts.Count} generated item names. Refusing to publish unnamed items.");
            }

            output.Commit();
            Stage("messages and total");
            Console.WriteLine($"[RegTool SUCCESS] Successfully patched regulation.bin!");
            Console.WriteLine($" - Injected equipment entries: {injectedEquipCount}");
            Console.WriteLine($" - Injected loot/shop entries: {injectedLootCount}");
            Console.WriteLine($" - Injected custom skills:     {injectedCustomSkillCount}");
            Console.WriteLine($" - Injected custom movesets:   {injectedCustomMovesetCount}");
            Console.WriteLine($" - Injected FMG text entries:  {injectedFmgCount}");
            Console.WriteLine($" - Output file size: {new FileInfo(outputPath).Length} bytes");
            return 0;
        }
    }
}
